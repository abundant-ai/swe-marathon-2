"""Instrumented, manually launched scratch-learning experiment."""

import json
import math
import time
from pathlib import Path


def run_experiment(run_name: str, hours: float = 3.0, max_steps: int = 2560,
                   full_eval: bool = True, stable_memory: bool = False) -> dict[str, object]:
    """Train the fixed scratch model and persist telemetry on a remote GPU.

    Args:
        run_name: Unique output directory and W&B display name.
        hours: Training-loop wall-clock allowance, including periodic probes.
        max_steps: Maximum consecutive training blocks, bounded by the corpus.
        full_eval: Score the complete public split after training.
        stable_memory: Test a smaller inner rate and slower initial forgetting.

    Returns:
        Run URL, completed steps, initial/final probe loss and checkpoint path.
    """
    import hashlib
    import os
    from dataclasses import asdict

    import modal
    import torch
    import wandb
    from titans import TitansConfig, TitansModel
    from titans.runtime.backbones import scratch_config
    from titans.training.pretraining import (
        _block_loss,
        _prepare_next_block,
        fp32_execution,
    )
    from transformers import AutoTokenizer, LlamaForCausalLM

    from titans_task.clipping import clip_gradients
    from titans_task.data import (
        evaluation_files,
        evaluation_tokens,
        packed_batches,
        training_tokens,
    )
    from titans_task.runner import _evaluation_mode, _stream_loss, evaluate

    output = Path('/runs') / run_name
    output.mkdir(exist_ok=False, parents=True)
    volume = modal.Volume.from_name('titans-learning-runs')
    root = Path('/data')
    torch.manual_seed(17)
    tokenizer = AutoTokenizer.from_pretrained(root / 'tokenizer', local_files_only=True)
    config = TitansConfig(use_liger=True, compile_kernels=True,
                          max_inner_learning_rate=1e-4 if stable_memory else 0.01)
    model = TitansModel(LlamaForCausalLM(scratch_config()).float().cuda(), tokenizer, config).cuda()
    if stable_memory:
        with torch.no_grad():
            for memory in model.memories.values():
                memory.gates.bias[0] = -10.0
    parameters = model.outer_parameters(train_backbone=True)
    for parameter in parameters:
        parameter.requires_grad_(True)
    model.train()
    model._checkpoint_backbone = True
    optimizer = torch.optim.AdamW(parameters, lr=1e-4)
    sources = {str(p.relative_to('/workspace')): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in Path('/workspace').rglob('*.py')}
    provenance = {'config': asdict(config), 'seed': 17, 'dtype': 'float32', 'tf32': False,
                  'batch_size': 1, 'block_size': 4096, 'lr': 1e-4, 'clip_norm': 1.0,
                  'parameters': sum(p.numel() for p in parameters), 'hours': hours,
                  'max_steps': max_steps, 'initial_forget_bias': -10.0 if stable_memory else -5.0,
                  'torch': torch.__version__, 'device': torch.cuda.get_device_name(),
                  'source_sha256': sources,
                  'train_manifest': json.loads((root / 'train/manifest.json').read_text())}
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2))
    run = wandb.init(project='titans-scratch-pretraining', entity=os.getenv('WANDB_ENTITY', 'ppo2-abundant'),
                     name=run_name, config=provenance, dir=str(output), mode='online')
    run.define_metric('step')
    run.define_metric('*', step_metric='step')
    (output / 'run.json').write_text(json.dumps({'url': run.url, 'id': run.id}))
    volume.commit()
    records = evaluation_files(root, 'public', tokenizer)
    probes = {}
    for corpus, record in records:
        if corpus not in probes:
            probes[corpus] = evaluation_tokens(root, 'public', record, tokenizer)[:4097]

    def log(metrics: dict[str, float | int]) -> None:
        """Write matching online and durable local scalar telemetry.

        Args:
            metrics: Finite metrics including the completed optimizer step.
        """
        run.log(metrics)
        with (output / 'metrics.jsonl').open('a') as handle:
            handle.write(json.dumps(metrics, allow_nan=False) + '\n')
        print(json.dumps(metrics), flush=True)

    def probe(step: int) -> float:
        """Score fixed 4096-token prefixes, separate from the full public score.

        Args:
            step: Completed optimizer steps.

        Returns:
            Weighted three-corpus probe NLL.
        """
        metrics: dict[str, float | int] = {'step': step}
        with _evaluation_mode(model):
            for corpus, ids in probes.items():
                total, count = _stream_loss(model, ids)
                metrics[f'probe/{corpus}_nll'] = total / count
        value = (0.5 * metrics['probe/fineweb_edu_nll'] + 0.25 * metrics['probe/pg19_nll']
                 + 0.25 * metrics['probe/wikitext103_nll'])
        metrics['probe/weighted_nll'] = value
        log(metrics)
        volume.commit()
        return value

    state = None
    steps = 0
    total_loss = 0.0
    try:
        initial = probe(0)
        if full_eval:
            initial_public = evaluate(model, data_dir=root, split='public')
            log({'step': 0, 'public/weighted_nll': initial_public})
            run.summary['initial_public_nll'] = initial_public
            volume.commit()
        started = time.monotonic()
        with torch.enable_grad(), fp32_execution(torch.device('cuda')):
            for inputs, labels in packed_batches(training_tokens(root, tokenizer)):
                if steps >= max_steps or time.monotonic() - started >= hours * 3600:
                    break
                torch.cuda.synchronize()
                tick = time.monotonic()
                torch.cuda.reset_peak_memory_stats()
                optimizer.zero_grad(set_to_none=True)
                if state is None:
                    state = model._new_state(prefix_hidden_only=True)
                else:
                    _prepare_next_block(model, state)
                loss = _block_loss(model, inputs.cuda(), labels.cuda(), state) / labels.numel()
                if not torch.isfinite(loss):
                    raise FloatingPointError('Nonfinite training loss')
                loss.backward()
                if steps < 10 or steps % 25 == 0:
                    named = [(name, parameter) for name, parameter in model.named_parameters()
                             if parameter.grad is not None]
                    norms = torch.stack([parameter.grad.norm(dtype=torch.float64)
                                         for _, parameter in named]).cpu().tolist()
                    ranked = sorted(zip(norms, [name for name, _ in named]), reverse=True)[:10]
                    with (output / 'gradient_diagnostics.jsonl').open('a') as handle:
                        handle.write(json.dumps({'step': steps + 1, 'largest_norms': ranked}) + '\n')
                    print('Largest gradient norms: ' + json.dumps(ranked[:3]), flush=True)
                norm, clipped_norm = clip_gradients(parameters, 1.0)
                optimizer.step()
                state._detach()
                torch.cuda.synchronize()
                seconds = time.monotonic() - tick
                value = loss.item()
                steps += 1
                total_loss += value
                log({'step': steps, 'tokens': steps * 4096, 'train/nll': value,
                     'train/perplexity': math.exp(value), 'train/mean_nll': total_loss / steps,
                     'train/grad_norm_before_clip': norm,
                     'train/grad_norm_after_clip': clipped_norm, 'train/lr': 1e-4,
                     'perf/step_seconds': seconds, 'perf/tokens_per_second': 4096 / seconds,
                     'perf/peak_allocated_gib': torch.cuda.max_memory_allocated() / 2**30,
                     'perf/peak_reserved_gib': torch.cuda.max_memory_reserved() / 2**30,
                     'perf/elapsed_seconds': time.monotonic() - started})
                del loss
                if steps % 25 == 0:
                    probe(steps)
                if full_eval and steps % 512 == 0:
                    score = evaluate(model, data_dir=root, split='public')
                    log({'step': steps, 'public/weighted_nll': score})
                    volume.commit()
                if steps % 100 == 0:
                    model.save_pretrained(output / f'checkpoint-{steps:06d}')
                    volume.commit()
        final = probe(steps)
        model.save_pretrained(output / 'final')
        volume.commit()
        result = {'url': run.url, 'steps': steps, 'tokens': steps * 4096,
                  'initial_probe_nll': initial, 'final_probe_nll': final,
                  'mean_training_nll': total_loss / max(steps, 1), 'checkpoint': str(output / 'final')}
        if full_eval:
            score = evaluate(model, data_dir=root, split='public')
            log({'step': steps, 'public/weighted_nll': score})
            result['public_nll'] = score
        run.summary.update(result)
        (output / 'result.json').write_text(json.dumps(result, indent=2))
        run.finish()
        return result
    except Exception:
        import traceback
        (output / 'error.txt').write_text(traceback.format_exc())
        run.finish(exit_code=1)
        raise
    finally:
        volume.commit()
