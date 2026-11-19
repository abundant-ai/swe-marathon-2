"""Ad hoc, offline CPU checks against the current local Titans checkout.

Run from the repository root with the Titans dependency available. This script
does not download corpora, use a GPU, or belong to the CI test collection.
"""

import copy
import json
import math
import random
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import numpy as np
import torch
from titans import (
    ConnectionExecution,
    ContinualModel,
    ResidualConnection,
    TitansConfig,
    TitansModel,
)
from titans.core.protocols import MemoryModule, MemoryState
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace
from torch import Tensor, nn
from torch.nn import functional as F
from transformers import LlamaConfig, LlamaForCausalLM, PreTrainedTokenizerFast

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from titans_task import data, evaluate, runner, train  # noqa: E402
from titans_task.token_store import open_tokens, write_manifest, write_tokens  # noqa: E402

CHECK = TestCase()


@dataclass
class ScalarState:
    """An independent memory protocol implementation used only in this probe."""

    value: Tensor

    def copy(self, *, detach: bool = False) -> "ScalarState":
        """Copy the scalar memory, optionally dropping gradient history.

        Args:
            detach: Whether to sever autograd history.

        Returns:
            State with independent tensor storage.
        """
        return ScalarState(self.value.detach().clone() if detach else self.value.clone())

    def detach(self) -> None:
        """Preserve values while releasing the current autograd graph."""
        self.value = self.value.detach()

    def tensors(self) -> tuple[Tensor, ...]:
        """Return the memory buffer for the runtime's precision checks."""
        return (self.value,)

    def adaptable(self) -> Mapping[str, Tensor]:
        """Expose the scalar as the method's active memory parameter."""
        return {"value": self.value}

    def replace(self, updates: Mapping[str, Tensor]) -> None:
        """Apply a protocol-driven update to the scalar.

        Args:
            updates: A replacement for value, or an empty mapping.
        """
        if set(updates) - {"value"}:
            raise ValueError("Unknown memory parameter")
        self.value = updates.get("value", self.value)


class GradientMemory(MemoryModule):
    """Read a scalar and adapt it with a local autograd gradient for every token."""

    def __init__(self, hidden_size: int) -> None:
        """Create the learned initial value and input/output projections.

        Args:
            hidden_size: Decoder width supplied by the memory factory.
        """
        super().__init__()
        self.initial = nn.Parameter(torch.zeros(1))
        self.input = nn.Linear(hidden_size, 1, bias=False)
        self.output = nn.Linear(1, hidden_size, bias=False)

    def initial_state(self, batch_size: int = 1) -> ScalarState:
        """Initialize independent scalar memory for the requested instances.

        Args:
            batch_size: Number of instances, always one in the task.

        Returns:
            A differentiable copy of the learned initial value.
        """
        return ScalarState(self.initial.expand(batch_size, 1).clone())

    def transition(self, hidden: Tensor, state: MemoryState, *, write: bool = True) -> Tensor:
        """Read before each local gradient update, including under outer no_grad.

        Args:
            hidden: Causal decoder activations [instances, tokens, hidden].
            state: This method's scalar state.
            write: Whether each observed token may update active memory.

        Returns:
            Memory contributions matching the decoder activations.
        """
        if not isinstance(state, ScalarState):
            raise TypeError("Expected ScalarState")
        tracking = torch.is_grad_enabled()
        outputs: list[Tensor] = []
        for observation in self.input(hidden).unbind(1):
            outputs.append(state.value)
            if write:
                with torch.enable_grad():
                    value = state.value
                    if not value.requires_grad:
                        value = value.detach().requires_grad_(True)
                    loss = 0.5 * (value - observation).square().sum()
                    gradient = torch.autograd.grad(loss, value, create_graph=tracking)[0]
                    updated = value - 0.01 * gradient
                state.value = updated if tracking else updated.detach()
        return self.output(torch.stack(outputs, dim=1))


class SmallConnection(ResidualConnection):
    """Bound attention allocations independently of Titans MAC segmentation."""

    def execution(self, position: int, tokens: int, *, prefix_tokens: int,
                  segment_length: int, attention_window: int) -> ConnectionExecution:
        """Choose short execution blocks for the independent memory probe.

        Args:
            position: Absolute stream position, unused by this connection.
            tokens: Number of available input tokens.
            prefix_tokens: Persistent-prefix length, unused here.
            segment_length: Titans setting, deliberately unused here.
            attention_window: Host window, unchanged by this connection.

        Returns:
            A normal residual-attention block of at most 64 tokens.
        """
        return ConnectionExecution(block_size=min(tokens, 64))


def small_connection(layer_index: int, hidden_size: int) -> SmallConnection:
    """Construct the independent connection through the public factory protocol.

    Args:
        layer_index: Host-selected layer, unused in this uniform factory.
        hidden_size: Host width, unused in this parameter-free connection.

    Returns:
        A fresh connection instance.
    """
    return SmallConnection()


def make_model(*, independent: bool = False) -> ContinualModel:
    """Build a tiny real decoder and an offline tokenizer for CPU integration.

    Args:
        independent: Whether to replace both Titans memory and its connection.

    Returns:
        A deterministic FP32 model. Only the probe bypasses the production-size lock.
    """
    torch.manual_seed(17)
    words = ["[PAD]", "[UNK]", "[EOS]", "web", "book", "wiki", "one", "two"]
    raw = Tokenizer(WordLevel({word: index for index, word in enumerate(words)}, unk_token="[UNK]"))
    raw.pre_tokenizer = Whitespace()
    tokenizer = PreTrainedTokenizerFast(tokenizer_object=raw, pad_token="[PAD]",
                                       unk_token="[UNK]", eos_token="[EOS]")
    backbone = LlamaForCausalLM(LlamaConfig(
        vocab_size=len(words), hidden_size=8, intermediate_size=16, num_hidden_layers=2,
        num_attention_heads=2, num_key_value_heads=1, max_position_embeddings=4096,
        eos_token_id=2, pad_token_id=0, attention_dropout=0.0,
    ))
    config = TitansConfig(memory_layers=(0,), memory_dim=2, memory_hidden_dim=4,
                          attention_window=16, persistent_tokens=2,
                          compile_kernels=False, use_liger=False)
    with patch("titans.runtime.model.validate_backbone", return_value="scratch"):
        if independent:
            return ContinualModel(backbone, tokenizer, config, memory_architecture=GradientMemory,
                                  connection_factory=small_connection)
        return TitansModel(backbone, tokenizer, config)


def write_training(root: Path, model: ContinualModel) -> None:
    """Create a small already-tokenized training fixture with real batch boundaries.

    Args:
        root: Temporary prepared-data root.
        model: Model supplying the fixture tokenizer identity.
    """
    record = write_tokens(root / "train", "stream.npy", "mixed", [3] * 3287 + [2] + [4] * 823)
    write_manifest(root / "train", "train", model.tokenizer, [record],
                   metadata={"source_token_counts": {"fineweb_edu": 3288, "pg19": 822}})


def write_evaluation(root: Path, model: ContinualModel, split: data.EvaluationSplit) -> None:
    """Create complete pretokenized evaluation manifests with short test streams.

    Args:
        root: Temporary prepared-data root.
        model: Model supplying the fixture tokenizer identity.
        split: Public or private stream-count contract to populate.
    """
    records = []
    for name, count in data.EVALUATION_COUNTS[split]:
        token = {"fineweb_edu": 3, "pg19": 4, "wikitext103": 5}[name]
        for index in range(count):
            records.append(write_tokens(root / split, f"{name}/{index:02}.npy", name, [token] * 18))
    write_manifest(root / split, split, model.tokenizer, records)


def check_data(root: Path, model: ContinualModel) -> None:
    """Check fixed budgets, mapped-file validation and causal label alignment.

    Args:
        root: Temporary fixture directory.
        model: Real model supplying the offline tokenizer.
    """
    assert data.TRAINING_QUOTAS == (("fineweb_edu", 8_388_608), ("pg19", 2_097_152))
    assert sum(budget for _, budget in data.TRAINING_QUOTAS) // data.BLOCK_SIZE == 2560
    assert sum(count for _, count in data.EVALUATION_COUNTS["public"]) * data.STREAM_TOKENS == 1_048_576
    assert sum(count for _, count in data.EVALUATION_COUNTS["private"]) * data.STREAM_TOKENS == 4_194_304
    expected = [3, 3, 2, 4, 2, 3, 3, 2, 3, 3, 2]
    record = write_tokens(root / "train", "stream.npy", "mixed", expected)
    write_manifest(root / "train", "train", model.tokenizer, [record],
                   metadata={"source_token_counts": {"fineweb_edu": 8, "pg19": 2}})
    with patch.object(data, "TRAINING_QUOTAS", (("fineweb_edu", 8), ("pg19", 2))):
        tokens = data.training_tokens(root, model.tokenizer)
    assert isinstance(tokens, np.memmap) and not tokens.flags.writeable
    assert tokens.tolist() == expected
    reference = torch.tensor([expected])
    with patch.object(data, "BLOCK_SIZE", 4):
        batches = list(data.packed_batches(tokens))
    assert [pair[0].shape for pair in batches] == [(1, 4), (1, 4), (1, 2)]
    assert torch.equal(torch.cat([x for x, _ in batches], 1), reference[:, :-1])
    assert torch.equal(torch.cat([y for _, y in batches], 1), reference[:, 1:])
    assert batches[0][1][0, -1] == batches[1][0][0, 0]
    with CHECK.assertRaisesRegex(ValueError, "one nonempty stream"):
        list(data.packed_batches(reference.expand(2, -1)))
    batches[0][0][0, 0] = 0
    assert tokens[0] == 3
    with CHECK.assertRaises(OSError):
        data.evaluation_files(root, "public", model.tokenizer)
    with CHECK.assertRaisesRegex(ValueError, "split"):
        data.evaluation_files(root, "unknown", model.tokenizer)
    revision = model._revision
    with CHECK.assertRaisesRegex(ValueError, "quotas"):
        train(model, data_dir=root, output_dir=root / "incomplete-checkpoint", eval_every_steps=None)
    assert model._revision == revision
    assert not (root / "incomplete-checkpoint").exists()
    mismatched = copy.deepcopy(model.tokenizer)
    mismatched.add_tokens(["different-tokenizer"])
    with CHECK.assertRaisesRegex(ValueError, "tokenizer"):
        data.training_tokens(root, mismatched)
    with (root / "train/stream.npy").open("ab") as handle:
        handle.write(b"corrupt")
    with CHECK.assertRaisesRegex(ValueError, "checksum"):
        open_tokens(root / "train", record, len(model.tokenizer))


def reference_loss(model: ContinualModel, tokens: Tensor) -> float:
    """Calculate loss directly, rebuilding prefix KV manually at block boundaries.

    Args:
        model: An independent model copy evaluated on CPU.
        tokens: One continuous stream with a real final lookahead.

    Returns:
        Independently accumulated summed next-token cross-entropy.
    """
    total = 0.0
    model.eval().requires_grad_(False)
    with torch.no_grad():
        state = model._new_state(prefix_hidden_only=True)
        for start in range(0, tokens.shape[1] - 1, 4096):
            if start:
                # Both probe connections end their attention segments at 4096.
                # Keep memory and absolute position; replace all attention KV.
                fresh = model._new_state(prefix_hidden_only=True)
                state._attention = fresh._attention
            end = min(start + 4096, tokens.shape[1] - 1)
            logits = model._forward_embeddings(model.backbone.model.embed_tokens(tokens[:, start:end]), state)
            total += F.cross_entropy(logits.flatten(0, 1), tokens[:, start + 1:end + 1].flatten(),
                                     reduction="sum").item()
            state._detach()
    return total


def check_stream(model: ContinualModel) -> None:
    """Check long-stream loss, causality, independent resets and preserved weights.

    Args:
        model: Titans or the independent gradient-based memory implementation.
    """
    tokens = (torch.arange(4111) % 5 + 3).reshape(1, -1)
    tokens[:, 2000] = model.tokenizer.eos_token_id
    expected = reference_loss(copy.deepcopy(model), tokens)
    parameters = {name: value.detach().clone() for name, value in model.named_parameters()}
    with torch.autocast("cpu", dtype=torch.bfloat16), runner._evaluation_mode(model):
        observed, count = runner._stream_loss(model, tokens)
        repeated, repeated_count = runner._stream_loss(model, tokens)
    assert count == repeated_count == 4110
    assert math.isclose(observed, expected, rel_tol=2e-6)
    assert observed == repeated
    for name, value in model.named_parameters():
        torch.testing.assert_close(value, parameters[name], rtol=0, atol=0)
    captured: list[Tensor] = []

    def observe_head(module: nn.Module, inputs: tuple[Tensor, ...], output: Tensor) -> None:
        """Capture actual predictions to test whether a changed label reaches memory.

        Args:
            module: The vocabulary head under observation.
            inputs: Its normalized hidden states.
            output: Next-token logits to copy before the next forward call.
        """
        captured.append(output.detach().clone())

    handle = model.backbone.lm_head.register_forward_hook(observe_head)
    first = tokens[:, :18].clone()
    second = first.clone()
    second[:, -1] = 2
    try:
        with runner._evaluation_mode(model):
            loss1, count1 = runner._stream_loss(model, first)
            predictions1 = torch.cat(captured, 1)
            captured.clear()
            loss2, count2 = runner._stream_loss(model, second)
            predictions2 = torch.cat(captured, 1)
    finally:
        handle.remove()
    assert count1 == count2 == 17
    torch.testing.assert_close(predictions1, predictions2, rtol=0, atol=0)
    expected_difference = (
        F.cross_entropy(predictions1[:, -1], first[:, -1], reduction="sum")
        - F.cross_entropy(predictions1[:, -1], second[:, -1], reduction="sum")
    ).item()
    assert math.isclose(loss1 - loss2, expected_difference, abs_tol=5e-6)


def check_evaluate(root: Path, model: ContinualModel) -> None:
    """Exercise the public API and its exact scalar aggregation and failure cleanup.

    Args:
        root: Temporary prepared-data root.
        model: Model supplying the tokenizer and precision context.
    """
    for split in ("public", "private"):
        write_evaluation(root, model, split)

    def known_loss(current: ContinualModel, tokens: data.TokenIds) -> tuple[float, int]:
        """Provide independently known corpus losses for aggregation checks.

        Args:
            current: Model whose shared parameters must all be frozen here.
            tokens: Actual packed fixture IDs identifying the corpus.

        Returns:
            A summed loss with known per-token means of 3, 4 and 5.
        """
        assert not any(parameter.requires_grad for parameter in current.parameters())
        count = data.input_count(tokens)
        return float(tokens.flatten()[0]) * count, count

    model.train()
    model.backbone.eval()
    modes = [module.training for module in model.modules()]
    flags = [parameter.requires_grad for parameter in model.parameters()]
    parameter = next(model.parameters())
    parameter.grad = torch.full_like(parameter, 0.125)
    prior_gradient = parameter.grad.clone()
    with patch.object(data, "STREAM_TOKENS", 17), patch.object(runner, "_stream_loss", known_loss):
        assert evaluate(model, data_dir=root, split="public") == 3.75
        assert evaluate(model, data_dir=root, split="private") == 3.75
    assert modes == [module.training for module in model.modules()]
    assert flags == [parameter.requires_grad for parameter in model.parameters()]
    torch.testing.assert_close(parameter.grad, prior_gradient, rtol=0, atol=0)
    with patch.object(data, "STREAM_TOKENS", 17), patch.object(model.tokenizer, "encode", side_effect=AssertionError("runtime tokenization")):
        score = evaluate(model, data_dir=root)
    assert isinstance(score, float) and math.isfinite(score)
    with (root / "public/fineweb_edu/00.npy").open("ab") as handle:
        handle.write(b"corrupt")
    with patch.object(data, "STREAM_TOKENS", 17), CHECK.assertRaisesRegex(ValueError, "checksum"):
        evaluate(model, data_dir=root)
    assert modes == [module.training for module in model.modules()]
    assert flags == [parameter.requires_grad for parameter in model.parameters()]
    torch.testing.assert_close(parameter.grad, prior_gradient, rtol=0, atol=0)
    with patch.object(runner, "_block_loss", return_value=torch.tensor(float("nan"))):
        with CHECK.assertRaisesRegex(FloatingPointError, "Nonfinite"):
            with runner._evaluation_mode(model):
                runner._stream_loss(model, torch.tensor([[3, 4, 5]]))
    assert modes == [module.training for module in model.modules()]
    assert flags == [parameter.requires_grad for parameter in model.parameters()]
    with torch.inference_mode(), CHECK.assertRaisesRegex(ValueError, "inference_mode"):
        with runner._evaluation_mode(model):
            raise AssertionError("The invalid mode should have been rejected")


def check_training(root: Path, model: ContinualModel) -> None:
    """Run two real CPU optimizer steps, checking clipping and continued memory.

    Args:
        root: Temporary fixture and checkpoint root.
        model: Scratch-backed model with either memory implementation.
    """
    write_training(root, model)
    before = {name: value.detach().clone() for name, value in model.named_parameters()}
    original_step = torch.optim.AdamW.step
    observed_norms: list[float] = []

    def checked_step(optimizer: torch.optim.AdamW, closure: object = None) -> None:
        """Check the actual gradients consumed by AdamW on CPU.

        Args:
            optimizer: The library's outer optimizer.
            closure: Unused by this training path.
        """
        assert closure is None
        gradients = [parameter.grad for group in optimizer.param_groups
                     for parameter in group["params"] if parameter.grad is not None]
        norm = torch.stack([gradient.norm() for gradient in gradients]).norm().item()
        assert 0 < norm <= 1.0 + 1e-6
        observed_norms.append(norm)
        original_step(optimizer)

    with patch.object(data, "TRAINING_QUOTAS", (("fineweb_edu", 3288), ("pg19", 822))):
        with patch.object(torch.optim.AdamW, "step", checked_step), patch.object(model.tokenizer, "encode", side_effect=AssertionError("runtime tokenization")):
            result = train(model, data_dir=root, output_dir=root / "checkpoint", eval_every_steps=None)
    assert result.tokens_processed == 4110 and result.optimizer_steps == 2
    assert len(observed_norms) == 2
    assert result.mean_loss is not None and math.isfinite(result.mean_loss)
    assert result.checkpoint_path.is_dir() and result.final_state is not None
    assert result.final_state.tokens_processed == 4110
    assert all(tensor.grad_fn is None for memory in result.final_state.memory.values()
               for tensor in memory.tensors())
    assert any(not torch.equal(before[name], value) for name, value in model.named_parameters()
               if name.startswith("backbone."))
    assert any(not torch.equal(before[name], value) for name, value in model.named_parameters()
               if name.startswith("memories."))
    assert all(parameter.dtype == torch.float32 for parameter in model.parameters())


def check_periodic_evaluation(root: Path, model: ContinualModel) -> None:
    """Compare real training with and without interleaved public checkpoint scoring.

    Args:
        root: Temporary prepared-data and checkpoint directory.
        model: A tiny Titans or independent-memory model to train in place.
    """
    write_training(root, model)
    write_evaluation(root, model, "public")
    for interval in (0, -1, True, 1.5):
        with CHECK.assertRaisesRegex(ValueError, "eval_every_steps"):
            train(model, data_dir=root, output_dir=root / "invalid", eval_every_steps=interval)
    reference = copy.deepcopy(model)
    original_score = runner._stream_loss
    observed_flags: list[bool] = []

    def stochastic_score(current: ContinualModel, tokens: data.TokenIds) -> tuple[float, int]:
        """Consume random numbers inside evaluation to detect training RNG leakage.

        Args:
            current: Model frozen by the real public evaluator.
            tokens: Actual fixture inputs with a final lookahead target.

        Returns:
            The real streaming loss and scored token count.
        """
        random.random()
        np.random.random()
        torch.rand(3)
        observed_flags.append(any(parameter.requires_grad for parameter in current.parameters()))
        return original_score(current, tokens)

    with patch.object(data, "TRAINING_QUOTAS", (("fineweb_edu", 3288), ("pg19", 822))):
        expected = train(reference, data_dir=root, output_dir=root / "reference", eval_every_steps=None)
        assert not (root / "reference.checkpoints").exists()
        torch_rng = torch.get_rng_state().clone()
        python_rng = random.getstate()
        numpy_rng = np.random.get_state()
        with patch.object(data, "STREAM_TOKENS", 17), patch.object(runner, "_stream_loss", stochastic_score):
            observed = train(model, data_dir=root, output_dir=root / "periodic", eval_every_steps=1)
    torch.testing.assert_close(torch.get_rng_state(), torch_rng, rtol=0, atol=0)
    assert random.getstate() == python_rng
    current_numpy = np.random.get_state()
    assert current_numpy[0] == numpy_rng[0] and current_numpy[2:] == numpy_rng[2:]
    assert np.array_equal(current_numpy[1], numpy_rng[1])
    assert observed_flags and not any(observed_flags)
    assert observed.optimizer_steps == expected.optimizer_steps == 2
    assert observed.tokens_processed == expected.tokens_processed == 4110
    assert observed.mean_loss == expected.mean_loss
    for actual, target in zip(model.parameters(), reference.parameters(), strict=True):
        torch.testing.assert_close(actual, target, rtol=0, atol=0)
    assert observed.final_state is not None and expected.final_state is not None
    for index, memory in observed.final_state.memory.items():
        for actual, target in zip(memory.tensors(), expected.final_state.memory[index].tensors(), strict=True):
            torch.testing.assert_close(actual, target, rtol=0, atol=0)
    history = root / "periodic.checkpoints/public-eval.jsonl"
    records = [json.loads(line) for line in history.read_text().splitlines()]
    assert [record["step"] for record in records] == [1, 2]
    assert [record["tokens_processed"] for record in records] == [4096, 4110]
    assert all(math.isfinite(record["public_loss"]) for record in records)
    assert all(Path(record["checkpoint"]).is_dir() for record in records)
    assert Path(records[0]["checkpoint"]) == (root / "periodic.checkpoints/step-000001").resolve()
    assert Path(records[1]["checkpoint"]) == observed.checkpoint_path.resolve()
    assert not (root / "periodic.checkpoints/step-000002").exists()


def check_schedule(root: Path, model: ContinualModel) -> None:
    """Check scheduling only after a batch is consumed, excluding the final step.

    Args:
        root: Unused artifact location while checkpoint recording is observed.
        model: Model reference passed through to the recorder.
    """
    calls: list[tuple[int, int]] = []

    def record(current: ContinualModel, data_dir: Path, checkpoint: Path, checkpoints: Path,
               step: int, processed: int, *, save: bool) -> None:
        """Observe scheduled evaluations without touching model or filesystem.

        Args:
            current: Supplied model, retained by the generator.
            data_dir: Prepared-data path supplied by the caller.
            checkpoint: Scheduled checkpoint path.
            checkpoints: History directory supplied by the caller.
            step: Completed step number to record.
            processed: Completed input-token count to record.
            save: Whether the periodic checkpoint would be saved.
        """
        assert save and current is model
        calls.append((step, processed))

    tokens = torch.full((1, 8209 + 1), 3, dtype=torch.int64)
    with patch.object(runner, "_record_public_evaluation", record):
        iterator = runner._evaluating_batches(model, tokens, root, root, 2)
        next(iterator)
        assert not calls
        next(iterator)
        assert not calls
        next(iterator)
        assert calls == [(2, 8192)]
        with CHECK.assertRaises(StopIteration):
            next(iterator)
        assert calls == [(2, 8192)]


def main() -> None:
    """Run small offline checks; production token budgets are never trained here."""
    torch.set_num_threads(1)
    with TemporaryDirectory(prefix="titans-task-check-") as temporary:
        root = Path(temporary)
        model = make_model()
        check_data(root / "data", model)
        print("PASS fixed budgets, memory maps, shifted labels and input failures", flush=True)
        check_schedule(root / "schedule", model)
        print("PASS evaluation frequency and completed-step scheduling", flush=True)
        for independent in (False, True):
            name = "independent memory" if independent else "Titans MAC"
            model = make_model(independent=independent)
            check_stream(model)
            print(f"PASS {name}: 4096-boundary reference loss and target causality", flush=True)
            check_evaluate(root / name / "evaluation", model)
            print(f"PASS {name}: weighted scalar, stream resets and mode restoration", flush=True)
            check_training(root / name / "training", model)
            print(f"PASS {name}: CPU optimizer steps, clipping and memory continuity", flush=True)
            # Compare two fresh training runs, independently of earlier probes.
            check_periodic_evaluation(root / name / "periodic", make_model(independent=independent))
            print(f"PASS {name}: periodic checkpoints, logs and identical training/RNG", flush=True)


if __name__ == "__main__":
    main()
