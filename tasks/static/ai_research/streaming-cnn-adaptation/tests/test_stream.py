"""Independent measurements for a causally updated RGB classifier."""

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from core_model import load, tensor
from execution import CandidateFailure, updater
from wire import StateLayout


@dataclass(frozen=True)
class VerificationContext:
    data: Path
    public: Path
    source: Path
    checkpoint: Path
    world: str
    order: int
    schedule: str = "clips"


def dataset(root, key, image_key="x"):
    with np.load(root / (key + ".npz"), allow_pickle=False) as z:
        label_key = "y_alt" if image_key == "x_alt" and "y_alt" in z else "y"
        x, y = z[image_key], z[label_key]
    if (
        x.ndim != 4
        or x.shape[1:] != (32, 32, 3)
        or set(y.tolist()) != set(range(10))
        or len(y) != len(x)
    ):
        raise RuntimeError("Incomplete capture evidence: " + key)
    return x, y


def balanced(pred, y):
    return float(np.mean([np.mean(pred[y == k] == k) for k in range(10)]))


@torch.no_grad()
def predict(model, rgb):
    logits = model.eval()(tensor(rgb))
    if not torch.isfinite(logits).all():
        raise CandidateFailure("Nonfinite classifier output")
    return logits.argmax(1).numpy()


def test_probe(adapted, frozen, probe):
    x, y = probe
    with_params = deepcopy(frozen)
    with_buffers = deepcopy(frozen)
    with torch.no_grad():
        for dst, src in zip(
            with_params.parameters(), adapted.parameters(), strict=True
        ):
            dst.copy_(src)
        for dst, src in zip(with_buffers.buffers(), adapted.buffers(), strict=True):
            dst.copy_(src)
    variants = {
        "frozen": frozen,
        "weights_only": with_params,
        "buffers_only": with_buffers,
        "adapted": adapted,
    }
    return {key: balanced(predict(model, x), y) for key, model in variants.items()}


from ordering import frame_order


def test_online(context):
    frozen = load(context.checkpoint)
    model = deepcopy(frozen)
    buffers_only = deepcopy(frozen)
    layout = StateLayout(model)
    traces = []
    categories = []
    firsts = []
    first_targets = []
    segments = []
    source_probe = dataset(context.data, "source_probe")
    source_before = balanced(predict(frozen, source_probe[0]), source_probe[1])
    rng = np.random.default_rng(context.order)
    middle = (
        context.world + "_middle"
        if (context.data / (context.world + "_middle.npz")).is_file()
        else "middle"
    )
    routed = (context.data / "routed-protocol.json").is_file()
    image_key = "x_alt" if routed and context.order == 7303 else "x"
    stock_service = (context.data / "stock-service.json").exists()
    commissioned = None
    with updater(context.source, context.public, layout) as step:
        for block, probe in [
            (context.world + "_arrival", context.world + "_probe"),
            (middle, middle + "_probe"),
            (context.world + "_return", context.world + "_probe"),
        ]:
            x, y = dataset(context.data, block, image_key)
            clips = np.arange(len(y)).reshape(10, 8)
            if not (y[clips] == y[clips][:, :1]).all():
                raise RuntimeError("Broken temporal clip")
            if routed:
                duration = int(rng.integers(5, 9))
                offset = int(rng.integers(0, 9 - duration))
                clips = clips[:, offset : offset + duration]
            ids = frame_order(clips, rng, context.schedule)
            before_switch = None
            if stock_service and segments:
                before_switch = balanced(predict(model, x[ids]), y[ids])
            baseline = predict(frozen, x)
            predictions = []
            buffer_predictions = []
            transition_source = None
            for index, i in enumerate(ids):
                with torch.no_grad():
                    for target, source in zip(
                        buffers_only.buffers(), model.buffers(), strict=True
                    ):
                        target.copy_(source)
                predictions.append(predict(model, x[i : i + 1])[0])
                buffer_predictions.append(predict(buffers_only, x[i : i + 1])[0])
                step(x[i])
                if routed and index == 0:
                    transition_source = balanced(
                        predict(model, source_probe[0]), source_probe[1]
                    )
            pred = np.asarray(predictions)
            pairs = np.stack([baseline[ids], pred, buffer_predictions], axis=1)
            traces.extend(pairs.tolist())
            categories.extend(y[ids].tolist())
            if stock_service:
                with np.load(
                    context.data / (block + ".npz"), allow_pickle=False
                ) as captures:
                    objects = captures["ids"][ids, :2]
                _, arrivals = np.unique(objects, axis=0, return_index=True)
                arrivals.sort()
                if len(arrivals) != 10:
                    raise RuntimeError(
                        "Expected ten distinct object feeds per station visit"
                    )
            else:
                arrivals = np.r_[True, y[ids][1:] != y[ids][:-1]]
            firsts.extend(pairs[arrivals].tolist())
            first_targets.extend(y[ids][arrivals].tolist())
            segments.append(
                {
                    "block": block,
                    "source_accuracy_after": balanced(
                        predict(model, source_probe[0]), source_probe[1]
                    ),
                    "frozen": balanced(baseline[ids], y[ids]),
                    "adapted": balanced(pred, y[ids]),
                    "probe": test_probe(
                        model, frozen, dataset(context.data, probe, image_key)
                    ),
                }
            )
            if before_switch is not None:
                segments[-1]["paused_at_switch_accuracy"] = before_switch
            if routed:
                segments[-1]["source_accuracy_after_first_update"] = transition_source
                if commissioned is None:
                    commissioned = deepcopy(model)
                else:
                    segments[-1]["commissioned_accuracy"] = balanced(
                        predict(commissioned, x[ids]), y[ids]
                    )
    y = np.asarray(categories)
    pred = np.asarray(traces)
    first = np.asarray(firsts)
    first_targets = np.asarray(first_targets)
    scores = [balanced(pred[:, i], y) for i in (0, 1, 2)]
    shift = max(
        float((new.detach() - old.detach()).abs().max())
        for old, new in zip(frozen.parameters(), model.parameters(), strict=True)
    )
    return {
        "frozen": scores[0],
        "adapted": scores[1],
        "gain_pp": 100 * (scores[1] - scores[0]),
        "buffers_only": scores[2],
        "learned_weight_gain_pp": 100 * (scores[1] - scores[2]),
        "first_clip_frozen": balanced(first[:, 0], first_targets),
        "first_clip_adapted": balanced(first[:, 1], first_targets),
        "source_before": source_before,
        "source_after": segments[-1]["source_accuracy_after"],
        "max_parameter_change": shift,
        "blocks": segments,
        "n": len(y),
        "first_appearance_count": len(first_targets),
    }
