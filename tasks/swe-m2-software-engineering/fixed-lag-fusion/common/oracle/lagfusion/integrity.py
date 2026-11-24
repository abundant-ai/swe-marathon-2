"""Online SE(2) smoothing and single-radio integrity monitoring."""

from dataclasses import dataclass
import json
from math import cos, sin
from pathlib import Path

import numpy as np

from .contract import Array, Json, covariance, integer, name, number, obj, rows, vector
from .gaussian import canonical
from .session import commit, lock


@dataclass(frozen=True)
class Model:
    """Immutable surveyed installation and integrity settings."""

    start: int
    lag: int
    mean: Array
    covariance: Array
    lever: Array
    radios: dict[str, tuple[Array, float]]
    penalty: float
    margin: float


def read_model(value: object) -> Model:
    """Validate the commissioned pose prior, radio routing and tag geometry."""
    config = obj(value)
    lag = integer(config['lag_ticks'], 2)
    anchors = {name(key): vector(point) for key, point in obj(config['anchors']).items()}
    mapping = {name(key): name(anchor) for key, anchor in obj(config['radio_to_anchor']).items()}
    biases = {name(key): number(bias) for key, bias in obj(config['anchor_bias_m']).items()}
    if lag > 24 or not 3 <= len(anchors) <= 6 or set(mapping.values()) != anchors.keys() or len(mapping) != len(anchors):
        raise ValueError('invalid lag or commissioning map')
    if biases.keys() != anchors.keys() or len(set(map(tuple, anchors.values()))) != len(anchors):
        raise ValueError('invalid bias coverage or anchor positions')
    radios = {key: (anchors[anchor], biases[anchor]) for key, anchor in mapping.items()}
    return Model(integer(config['start_tick']), lag, vector(config['prior_pose'], 3),
                 covariance(config['prior_covariance'], 3), vector(config['tag_in_body_m']), radios,
                 number(config['range_drop_cost'], positive=True), number(config['ambiguity_cost'], nonnegative=True))


def sigma(value: object) -> Array:
    """Read axiswise displacement or pose uncertainty."""
    return np.array([number(item, positive=True) for item in rows(value, 3)])


def read_events(value: object, model: Model) -> list[Json]:
    """Validate all event contents before examining the journal."""
    events = [obj(data) for data in rows(value)]
    if not events or len(events) > 128:
        raise ValueError('packet event count outside 1..128')
    for event in events:
        op = name(event['op'])
        integer(event['tick'])
        if op == 'advance':
            vector(event['body_delta'], 3)
            sigma(event['sigma'])
        elif op in ('upsert', 'retract'):
            name(event['id'])
            integer(event['revision'], 1)
            if op == 'upsert':
                measurement = obj(event['measurement'])
                if measurement['kind'] == 'range':
                    if name(measurement['radio']) not in model.radios:
                        raise ValueError('range radio is outside the commissioned map')
                    number(measurement['value_m'], nonnegative=True)
                    number(measurement['sigma_m'], positive=True)
                elif measurement['kind'] == 'survey':
                    vector(measurement['pose'], 3)
                    sigma(measurement['sigma'])
                else:
                    raise ValueError('unknown measurement')
        else:
            raise ValueError('unknown integrity event')
    return events


def rotation(yaw: float) -> Array:
    """Map a planar body vector into lab axes."""
    c, s = cos(yaw), sin(yaw)
    return np.array([[c, -s], [s, c]])


def perpendicular(point: Array) -> Array:
    """Differentiate a rotated planar vector with respect to its angle."""
    return np.array([-point[1], point[0]])


class Window:
    """The active nonlinear factors and a frozen quadratic prior on the oldest pose."""

    def __init__(self, model: Model, saved: Json | None) -> None:
        self.model = model
        if saved is None:
            self.first = model.start
            self.guess = model.mean[None, :].copy()
            self.motions: list[Json] = []
            self.evidence: dict[tuple[int, str], Json] = {}
            self.prior = model.mean.copy()
            self.covariance = model.covariance.copy()
        else:
            self.first = saved['first']
            self.guess = np.asarray(saved['guess'])
            self.motions = saved['motions']
            self.evidence = {(event['tick'], event['id']): event for event in saved['evidence']}
            self.prior = np.asarray(saved['prior'])
            self.covariance = np.asarray(saved['covariance'])

    def encoded(self) -> Json:
        """Store only active factors, their revision records and summarized information."""
        return {'first': self.first, 'guess': self.guess.tolist(), 'motions': self.motions,
                'evidence': [event for _, event in sorted(self.evidence.items())],
                'prior': self.prior.tolist(), 'covariance': self.covariance.tolist()}

    def factors(self, poses: Array, excluded: str | None, *, oldest_only: bool = False, all_ranges_off: bool = False) -> tuple[Array, Array]:
        """Build whitened residuals and analytic Jacobians in additive lab coordinates."""
        width = poses.size
        noise = np.linalg.solve(np.linalg.cholesky(self.covariance), np.eye(3))
        prior_j = np.zeros((3, width))
        prior_j[:, :3] = noise
        errors = [noise @ (poses[0] - self.prior)]
        gradients = [prior_j]
        for i, event in enumerate(self.motions[:1] if oldest_only else self.motions):
            a, b = poses[i:i+2]
            measured = np.asarray(event['body_delta'])
            weights = np.asarray(event['sigma'])
            body = rotation(a[2]).T
            increment = body @ (b[:2] - a[:2])
            offset = 3 * i
            jac = np.zeros((3, width))
            jac[:2, offset:offset+2] = -body
            jac[:2, offset+2] = -perpendicular(increment)
            jac[:2, offset+3:offset+5] = body
            jac[2, offset+2] = -1.0
            jac[2, offset+5] = 1.0
            errors.append((np.r_[increment, b[2] - a[2]] - measured) / weights)
            gradients.append(jac / weights[:, None])
        for (tick, _), event in sorted(self.evidence.items()):
            if event['op'] == 'retract' or (oldest_only and tick != self.first):
                continue
            measurement = event['measurement']
            index = tick - self.first
            offset = 3 * index
            pose = poses[index]
            if measurement['kind'] == 'survey':
                weights = np.asarray(measurement['sigma'])
                jac = np.zeros((3, width))
                jac[:, offset:offset+3] = np.diag(1.0 / weights)
                errors.append((pose - measurement['pose']) / weights)
            else:
                radio = measurement['radio']
                if all_ranges_off or excluded == radio:
                    continue
                anchor, bias = self.model.radios[radio]
                rotated = rotation(pose[2]) @ self.model.lever
                delta = pose[:2] + rotated - anchor
                radius = np.linalg.norm(delta)
                direction = delta / radius if radius > 0 else np.zeros(2)
                scale = measurement['sigma_m']
                jac = np.zeros((1, width))
                jac[0, offset:offset+3] = np.r_[direction, direction @ perpendicular(rotated)] / scale
                errors.append(np.array([(radius + bias - measurement['value_m']) / scale]))
            gradients.append(jac)
        return np.concatenate(errors), np.concatenate(gradients)

    def fit(self, excluded: str | None, *, all_ranges_off: bool = False) -> tuple[Array, float, Array]:
        """Use damped Gauss–Newton with a monotone residual line search."""
        state = self.guess.copy()
        res, jac = self.factors(state, excluded, all_ranges_off=all_ranges_off)
        cost = float(res @ res / 2)
        for _ in range(40):
            information = jac.T @ jac
            step = np.linalg.solve(information, -jac.T @ res).reshape(state.shape)
            if np.max(np.abs(step)) < 2e-10:
                break
            for scale in (1.0, .5, .25, .125, .0625, .03125, .015625, .0078125):
                candidate = state + step * scale
                new_res, new_jac = self.factors(candidate, excluded, all_ranges_off=all_ranges_off)
                after = float(new_res @ new_res / 2)
                if after < cost:
                    state, res, jac, cost = candidate, new_res, new_jac, after
                    break
            else:
                break
        return state, cost, jac.T @ jac

    def choose(self) -> tuple[Array, str | None, str, list[Json], Array]:
        """Compare explicit channel exclusions, then use a conservative fallback on ties."""
        counts: dict[str, int] = {}
        for item in self.evidence.values():
            if item['op'] == 'upsert' and item['measurement']['kind'] == 'range':
                radio = item['measurement']['radio']
                counts[radio] = counts.get(radio, 0) + 1
        fits = {radio: self.fit(radio) for radio in (None, *sorted(counts))}
        scores = {radio: fit[1] + self.model.penalty * counts.get(radio, 0) for radio, fit in fits.items()}
        ordered = sorted(scores, key=scores.__getitem__)
        best = ordered[0]
        if len(ordered) > 1 and scores[ordered[1]] - scores[best] <= self.model.margin:
            selected, status = None, 'ambiguous'
            poses, _, information = self.fit(None, all_ranges_off=True)
        else:
            selected, status = best, 'nominal' if best is None else 'isolated'
            poses, _, information = fits[best]
        self.guess = poses
        profiles = [{'excluded_radio': radio, 'score': score} for radio, score in scores.items()]
        return poses, selected, status, profiles, information

    def advance(self, event: Json) -> Json | None:
        """Retire just the oldest factor neighborhood before adding a new pose."""
        if event['tick'] != self.first + len(self.guess):
            raise ValueError('advances must add exactly one adjacent tick')
        finalized = None
        if len(self.guess) == self.model.lag:
            poses, selected, status, _, information = self.choose()
            marginals = np.linalg.inv(information)
            finalized = {'tick': self.first, 'pose': poses[0].tolist(),
                         'covariance': marginals[:3, :3].tolist(), 'status': status,
                         'fault_radio': selected if status == 'isolated' else None}
            error, jac = self.factors(poses[:2], selected, oldest_only=True, all_ranges_off=(status == 'ambiguous'))
            hessian, gradient = jac.T @ jac, jac.T @ error
            first, mixed = hessian[:3, :3], hessian[:3, 3:]
            schur = hessian[3:, 3:] - mixed.T @ np.linalg.solve(first, mixed)
            linear = gradient[3:] - mixed.T @ np.linalg.solve(first, gradient[:3])
            self.prior = poses[1] - np.linalg.solve(schur, linear)
            self.covariance = np.linalg.inv((schur + schur.T) / 2)
            self.guess = poses[1:].copy()
            self.motions.pop(0)
            self.evidence = {key: value for key, value in self.evidence.items() if key[0] > self.first}
            self.first += 1
        last = self.guess[-1]
        delta = np.asarray(event['body_delta'])
        following = last + np.r_[rotation(last[2]) @ delta[:2], delta[2]]
        self.guess = np.vstack((self.guess, following))
        self.motions.append(event)
        return finalized

    def revise(self, event: Json) -> str:
        """Apply one correction only when its observation is still revisable."""
        stamp = event['tick']
        if stamp < self.first:
            return 'expired'
        if stamp >= self.first + len(self.guess):
            return 'future'
        key = stamp, event['id']
        old = self.evidence.get(key)
        old_revision = 0 if old is None else old['revision']
        revision = event['revision']
        if revision < old_revision:
            return 'stale'
        if revision == old_revision:
            return 'duplicate' if canonical(event) == canonical(old) else 'conflict'
        if revision != old_revision + 1 or (event['op'] == 'retract' and (old is None or old['op'] == 'retract')):
            return 'conflict'
        if old is None and sum(1 for tick, _ in self.evidence if tick == stamp) >= 24:
            raise ValueError('more than 24 observation identities at one tick')
        self.evidence[key] = event
        return 'accepted' if event['op'] == 'upsert' else 'retracted'

    def execute(self, events: list[Json]) -> Json:
        """Apply event order and report the current integrity decision and Gaussian blocks."""
        finalized, dispositions = [], []
        for event in events:
            if event['op'] == 'advance':
                retired = self.advance(event)
                if retired is not None:
                    finalized.append(retired)
                dispositions.append('advanced')
            else:
                dispositions.append(self.revise(event))
        poses, selected, status, profiles, information = self.choose()
        covariance_blocks = np.linalg.inv(information)
        active = [{'tick': tick, 'pose': pose.tolist(),
                   'covariance': covariance_blocks[3*i:3*i+3, 3*i:3*i+3].tolist()}
                  for i, (tick, pose) in enumerate(zip(range(self.first, self.first + len(poses)), poses, strict=True))]
        return {'integrity': status, 'fault_radio': selected if status == 'isolated' else None,
                'profiles': profiles, 'poses': active, 'finalized': finalized, 'events': dispositions}


def track(packet: Json, state: Path) -> Json:
    """Durably accept a nonlinear packet and keep its decision after a lost reply."""
    stream = name(packet['stream_id'])
    sequence = integer(packet['sequence'], 1)
    model = read_model(packet['config'])
    events = read_events(packet['events'], model)
    request = canonical(packet)
    with lock(state):
        try:
            journal = obj(json.loads(state.read_text(encoding='utf-8')))
        except FileNotFoundError:
            journal = {}
        previous = journal.get(stream)
        if previous is not None and previous['request'] == request:
            return previous['reply']
        expected = 1 if previous is None else previous['reply']['sequence'] + 1
        if sequence != expected or (previous is not None and canonical(previous['config']) != canonical(packet['config'])):
            return {'stream_id': stream, 'sequence': sequence, 'status': 'rejected', 'result': None}
        window = Window(model, None if previous is None else previous['window'])
        report = window.execute(events)
        reply = {'stream_id': stream, 'sequence': sequence, 'status': 'accepted', 'result': report}
        journal[stream] = {'request': request, 'config': packet['config'], 'window': window.encoded(), 'reply': reply}
        commit(state, journal)
        return reply
