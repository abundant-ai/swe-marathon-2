"""Train and score a supplied model using the task's fixed corpus recipe."""

import json
import math
import random
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import numpy as np
import torch
from titans import ContinualModel, TrainingResult
from titans.training.pretraining import (
    _block_loss,
    _prepare_next_block,
    _validate_batch,
    fp32_execution,
)
from torch import Tensor

from .data import (
    BLOCK_SIZE,
    EVALUATION_WEIGHTS,
    EvaluationSplit,
    TokenIds,
    evaluation_files,
    evaluation_tokens,
    input_count,
    packed_batches,
    training_tokens,
)


def train(model: ContinualModel, *, data_dir: str | Path, output_dir: str | Path,
          learning_rate: float = 1e-4, eval_every_steps: int | None = 512) -> TrainingResult:
    """Pretrain a supplied scratch model on the fixed 10M-token, 80/20 corpus mix.

    Reuse the library's FP32, batch-size-one trainer: one AdamW update per 4096
    tokens, averaged causal loss and global gradient clipping at 1.0. Active memory
    continues across documents and batches; ordinary attention resets per batch.
    The pretokenized training stream is validated and memory-mapped before any
    optimizer step. Only the current block is converted to int64 tensors; no
    source text is tokenized. The model is updated in place.
    Periodic evaluation runs between completed steps without restarting the
    trainer. The final checkpoint is also evaluated, without duplicating an
    evaluation when its step is a multiple of the requested interval.

    Args:
        model: A scratch-backed ContinualModel, including TitansModel or a model
            using other memory and connection protocols. No model is instantiated.
        data_dir: Root containing the prepared training files and public streams.
        output_dir: New checkpoint directory, as required by ``model.pretrain``.
            Periodic checkpoints and ``public-eval.jsonl`` are written to the
            sibling directory ``<output_dir.name>.checkpoints``.
        learning_rate: Positive finite outer AdamW learning rate.
        eval_every_steps: Evaluate the public set after this many optimizer
            steps, defaulting to 512. None disables evaluation and its artifacts.

    Returns:
        The library's training result, including checkpoint, loss and step count.
        When evaluation is enabled, elapsed_seconds includes its wall time.

    Raises:
        ValueError: The data, backbone or learning rate violates the contract.
        OSError: Data cannot be read or the checkpoint cannot be written.
    """
    if model.backbone_kind != "scratch":
        raise ValueError("train requires a scratch-backed model")
    if not math.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("learning_rate must be positive and finite")
    if eval_every_steps is not None and (
        isinstance(eval_every_steps, bool) or not isinstance(eval_every_steps, int)
        or eval_every_steps <= 0
    ):
        raise ValueError("eval_every_steps must be a positive integer or None")
    destination = Path(output_dir)
    if destination.exists():
        raise FileExistsError(output_dir)
    source = Path(data_dir)
    checkpoints = destination.with_name(f"{destination.name}.checkpoints")
    if eval_every_steps is not None:
        if checkpoints.exists():
            raise FileExistsError(checkpoints)
        evaluation_files(source, "public", model.tokenizer)
    tokens = training_tokens(source, model.tokenizer)
    if eval_every_steps is None:
        return model.pretrain(packed_batches(tokens), output_dir=destination,
                              learning_rate=learning_rate)
    checkpoints.mkdir(parents=True)
    started = time.perf_counter()
    batches = _evaluating_batches(model, tokens, source, checkpoints, eval_every_steps)
    result = model.pretrain(batches, output_dir=destination, learning_rate=learning_rate)
    _record_public_evaluation(model, source, result.checkpoint_path, checkpoints,
                              result.optimizer_steps, result.tokens_processed, save=False)
    return replace(result, elapsed_seconds=time.perf_counter() - started)


def _evaluating_batches(model: ContinualModel, tokens: TokenIds, data_dir: Path,
                        checkpoints: Path, interval: int) -> Iterator[tuple[Tensor, Tensor]]:
    """Evaluate between completed steps while one pretrain call owns the stream.

    The library consumes one yielded batch, completes its optimizer step and
    detaches training memory before requesting another batch. Resuming here is
    therefore a completed-step boundary. The final evaluation runs after the
    library saves its final checkpoint, avoiding a duplicate checkpoint copy.

    Args:
        model: Model whose shared parameters have just completed a training step.
        tokens: Pretokenized stream, including one lookahead token.
        data_dir: Prepared input root with the public evaluation split.
        checkpoints: Fresh directory for periodic checkpoints and the loss log.
        interval: Positive number of optimizer steps between evaluations.

    Yields:
        The original consecutive input/label batches without changing their order.
    """
    total_steps = (input_count(tokens) + BLOCK_SIZE - 1) // BLOCK_SIZE
    processed = 0
    for step, (inputs, labels) in enumerate(packed_batches(tokens), 1):
        yield inputs, labels
        processed += inputs.numel()
        if step % interval == 0 and step < total_steps:
            checkpoint = checkpoints / f"step-{step:06d}"
            _record_public_evaluation(model, data_dir, checkpoint, checkpoints,
                                      step, processed, save=True)


def _record_public_evaluation(model: ContinualModel, data_dir: Path, checkpoint: Path,
                              checkpoints: Path, step: int, processed: int, *, save: bool) -> None:
    """Score checkpoint parameters on fresh public memory and append one result.

    The same model instance is evaluated using disposable memory; reloading a
    checkpoint would unnecessarily rebuild custom memory/connection factories.
    Only shared model parameters are saved, matching the library's checkpoint
    format. These are evaluation checkpoints, not exact optimizer-resume files.

    Args:
        model: Current model at a completed optimizer step.
        data_dir: Prepared public-data root.
        checkpoint: Checkpoint to save, or the already saved final checkpoint.
        checkpoints: Directory containing ``public-eval.jsonl``.
        step: Number of completed optimizer steps.
        processed: Number of training input tokens consumed so far.
        save: Whether to save a periodic checkpoint before evaluating.

    Raises:
        FloatingPointError: The public score is not finite.
        OSError: A checkpoint or result record cannot be written.
    """
    if save:
        model.save_pretrained(checkpoint)
    loss = evaluate(model, data_dir=data_dir, split="public")
    if not math.isfinite(loss):
        raise FloatingPointError("Nonfinite public evaluation loss")
    record = {"step": step, "tokens_processed": processed, "public_loss": loss,
              "checkpoint": str(checkpoint.resolve())}
    with (checkpoints / "public-eval.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, allow_nan=False) + "\n")
    print(f"step={step} tokens={processed} public_loss={loss:.6f} checkpoint={checkpoint}",
          flush=True)


@contextmanager
def _evaluation_mode(model: ContinualModel) -> Iterator[None]:
    """Freeze shared parameters temporarily while allowing local memory learning.

    ``no_grad`` avoids outer training graphs; memory implementations may enter
    ``enable_grad`` for their own inner updates. Never use inference_mode here.
    Restore every module's training flag and parameter's requires_grad flag even
    after an evaluation failure. Existing outer gradients are untouched. Python,
    NumPy, CPU Torch and the model device's CUDA RNG state are restored so public
    evaluation cannot consume randomness intended for subsequent training steps.

    Args:
        model: FP32 model evaluated in place with disposable stream memory.

    Yields:
        A full-precision evaluation scope with no outer optimizer.

    Raises:
        ValueError: Model storage is not FP32 or the caller enabled inference_mode.
    """
    if torch.is_inference_mode_enabled():
        raise ValueError("Evaluation needs local inner gradients; call outside inference_mode")
    tensors = (*model.parameters(), *model.buffers())
    if any(t.is_floating_point() and t.dtype != torch.float32 for t in tensors):
        raise ValueError("Evaluation requires FP32 model parameters and buffers")
    parameters = tuple((parameter, parameter.requires_grad) for parameter in model.parameters())
    modes = tuple((module, module.training) for module in model.modules())
    device = model.backbone.model.embed_tokens.weight.device
    cuda_devices = [device.index if device.index is not None else torch.cuda.current_device()] \
        if device.type == "cuda" else []
    python_random = random.getstate()
    numpy_random = np.random.get_state()
    try:
        model.eval()
        for parameter, _ in parameters:
            parameter.requires_grad_(False)
        with torch.random.fork_rng(devices=cuda_devices), torch.no_grad(), fp32_execution(device):
            yield
    finally:
        random.setstate(python_random)
        np.random.set_state(numpy_random)
        for parameter, requires_grad in parameters:
            parameter.requires_grad_(requires_grad)
        for module, training in modes:
            module.training = training


def _stream_loss(model: ContinualModel, tokens: TokenIds) -> tuple[float, int]:
    """Score one independent stream with the same boundaries as scratch training.

    Args:
        model: Temporarily frozen model inside ``_evaluation_mode``.
        tokens: Continuous IDs and one lookahead, as a uint32 memory map or a
            reference int64 tensor with shape [1, N + 1].

    Returns:
        Summed negative log likelihood and number of scored next-token targets.

    Raises:
        ValueError: Token IDs or memory dtypes violate the training contract.
        FloatingPointError: Any block produces nonfinite loss.
    """
    device = model.backbone.model.embed_tokens.weight.device
    state = model._new_state(prefix_hidden_only=True)
    summed_losses: list[float] = []
    scored = 0
    try:
        for inputs, labels in packed_batches(tokens):
            _validate_batch(inputs, labels, model.backbone.config.vocab_size)
            if scored:
                _prepare_next_block(model, state)
            loss = _block_loss(model, inputs.to(device), labels.to(device), state)
            value = float(loss.item())
            if not math.isfinite(value):
                raise FloatingPointError("Nonfinite evaluation loss")
            summed_losses.append(value)
            scored += labels.numel()
            state._detach()
    finally:
        state._detach()
    return math.fsum(summed_losses), scored


def evaluate(model: ContinualModel, *, data_dir: str | Path,
             split: EvaluationSplit = "public") -> float:
    """Return exactly the accepted weighted streaming next-token loss.

    The scalar is 0.50 * FineWeb-Edu NLL + 0.25 * PG19 NLL + 0.25 * WikiText NLL.
    Each corpus NLL is its summed loss divided by its scored token count. Every
    file starts fresh memory; within a file, memory learns from arriving inputs
    and continues across documents and 4096-token batches. Targets never enter
    memory before the predictions that score them. No shared weight is optimized.

    Args:
        model: Supplied FP32 model, including Titans or another protocol-based
            method. Its shared weights, gradients and training mode are preserved.
        data_dir: Root containing prepared public or private stream directories.
        split: ``public`` scores 16 streams; ``private`` scores 64. Each stream
            supplies 65,536 targets. Missing streams fail instead of changing weights.

    Returns:
        Weighted mean negative log likelihood in nats per token; lower is better.

    Raises:
        ValueError: Data, model precision or execution mode is invalid.
        OSError: A required stream cannot be read.
        FloatingPointError: Any loss is nonfinite.
    """
    source = Path(data_dir)
    files = evaluation_files(source, split, model.tokenizer)
    losses: dict[str, list[float]] = {name: [] for name, _ in EVALUATION_WEIGHTS}
    counts = {name: 0 for name, _ in EVALUATION_WEIGHTS}
    with _evaluation_mode(model):
        for corpus, record in files:
            tokens = evaluation_tokens(source, split, record, model.tokenizer)
            loss, count = _stream_loss(model, tokens)
            losses[corpus].append(loss)
            counts[corpus] += count
    return math.fsum(weight * math.fsum(losses[name]) / counts[name]
                     for name, weight in EVALUATION_WEIGHTS)
