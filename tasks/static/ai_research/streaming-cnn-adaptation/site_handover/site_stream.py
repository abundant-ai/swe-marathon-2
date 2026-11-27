"""Replay a scanner that moves between two stockrooms independently of its optical module."""

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from core_model import load
from execution import updater
from ordering import frame_order
from stream_common import balanced, dataset, predict, test_probe
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


def visit(
    data: Path,
    protocol: dict,
    world: str,
    schedule: str,
    phase: str,
    site: int,
    rng: np.random.Generator,
) -> dict:
    """Build one chronological inventory visit and its two calibration frames.

    Site selects stock labels. Its scanner frames, gains, positions and presentation
    order are the same for both counterfactual site choices.
    """
    first = int(phase == "middle")
    key = f"a_{phase}"
    local_site = site ^ int(world == "b")
    with np.load(data / (key + ".npz"), allow_pickle=False) as a:
        camera = [a["x" if i == first else "x_alt"] for i in range(2)]
        y = a["y" if local_site == first else "y_alt"]
        ids = a["ids"]
    length = int(rng.integers(5, 9))
    off = int(rng.integers(0, 9 - length))
    ix = frame_order(
        np.arange(len(y)).reshape(10, 8)[:, off : off + length], rng, schedule
    )
    position = int(rng.integers(len(ix) // 3, 2 * len(ix) // 3))
    frames = []
    charts = []
    for interval, indices in enumerate((ix[:position], ix[position:])):
        prefix = f"a_{schedule}_{phase}_{interval}"
        mode = int(protocol[prefix + "_mode"])
        gain = protocol[prefix + "_gain"]
        frames.append(
            np.rint(camera[mode][indices] * gain).clip(0, 255).astype(np.uint8)
        )
        charts.append(protocol[prefix + f"_site{site}"])
    probe = "a" + ("_middle_probe" if phase == "middle" else "_probe")
    with np.load(data / (probe + ".npz"), allow_pickle=False) as a:
        px = (
            np.rint(a["x" if mode == first else "x_alt"] * gain)
            .clip(0, 255)
            .astype(np.uint8)
        )
        py = a["y" if local_site == first else "y_alt"]
    return {
        "rgb": np.concatenate(frames),
        "y": y[ix],
        "probe": (px, py),
        "charts": charts,
        "second": position,
        "ids": ids[ix],
        "source_indices": ix,
    }


def test_online(context: VerificationContext) -> dict:
    """Measure independent CNN states before each scored prediction with two unscored chart events per visit."""
    frozen = load(context.checkpoint)
    model = deepcopy(frozen)
    buffer = deepcopy(frozen)
    source = dataset(context.data, "source_probe")
    before = balanced(predict(frozen, source[0]), source[1])
    # One stream realization for both site orders. Only the chart pixels and stock targets change.
    rng = np.random.default_rng(51429 if context.schedule == "clips" else 28371)
    all_y = []
    all_predictions = []
    first_y = []
    first_preds = []
    blocks = []
    event_count = 0
    commissioned = None
    with (
        np.load(context.data / "site-handovers.npz", allow_pickle=False) as fixtures,
        updater(context.source, context.public, StateLayout(model)) as step,
    ):
        protocol = dict(fixtures)
        step(protocol[f"renewal_{context.world}_{context.schedule}"])
        for phase in ("arrival", "middle", "return"):
            site = int(phase == "middle") ^ int(context.order == 7303)
            segment = visit(
                context.data,
                protocol,
                context.world,
                context.schedule,
                phase,
                site,
                rng,
            )
            x, y = segment["rgb"], segment["y"]
            paused = balanced(predict(model, x), y)
            base = predict(frozen, x)
            adapted = []
            buffer_preds = []
            retained = []
            for i, frame in enumerate(x):
                if i == 0 or i == segment["second"]:
                    step(segment["charts"][int(i != 0)])
                    event_count += 1
                    retained.append(balanced(predict(model, source[0]), source[1]))
                with torch.no_grad():
                    for dst, src in zip(buffer.buffers(), model.buffers(), strict=True):
                        dst.copy_(src)
                adapted.append(predict(model, frame[None])[0])
                buffer_preds.append(predict(buffer, frame[None])[0])
                step(frame)
            pred = np.array(adapted)
            triples = np.stack((base, pred, buffer_preds), axis=1)
            _, starts = np.unique(segment["ids"][:, :2], axis=0, return_index=True)
            if len(starts) != 10:
                raise RuntimeError("Incomplete inventory feeds")
            starts.sort()
            all_y.extend(y.tolist())
            all_predictions.extend(triples.tolist())
            first_y.extend(y[starts].tolist())
            first_preds.extend(triples[starts].tolist())
            block = {
                "block": context.world + "_" + phase,
                "adapted": balanced(pred, y),
                "frozen": balanced(base, y),
                "probe": test_probe(model, frozen, segment["probe"]),
                "source_accuracy_after_chart": retained,
                "source_accuracy_after_first_update": min(retained),
                "source_accuracy_after": balanced(predict(model, source[0]), source[1]),
            }
            if phase != "arrival":
                block["paused_at_switch_accuracy"] = paused
                block["commissioned_accuracy"] = balanced(predict(commissioned, x), y)
            else:
                commissioned = deepcopy(model)
            blocks.append(block)
    y = np.array(all_y)
    pred = np.array(all_predictions)
    first = np.array(first_preds)
    scores = [balanced(pred[:, i], y) for i in range(3)]
    return {
        "frozen": scores[0],
        "adapted": scores[1],
        "gain_pp": 100 * (scores[1] - scores[0]),
        "buffers_only": scores[2],
        "learned_weight_gain_pp": 100 * (scores[1] - scores[2]),
        "first_clip_adapted": balanced(first[:, 1], np.array(first_y)),
        "first_clip_frozen": balanced(first[:, 0], np.array(first_y)),
        "source_before": before,
        "source_after": blocks[-1]["source_accuracy_after"],
        "max_parameter_change": max(
            float((v.detach() - w.detach()).abs().max())
            for v, w in zip(model.parameters(), frozen.parameters(), strict=True)
        ),
        "first_appearance_count": len(first),
        "n": len(y),
        "blocks": blocks,
        "chart_count": event_count,
        "stock_targets": all_y,
        "stock_predictions": pred[:, 1].tolist(),
    }
