"""Paired cases for the private case set (B-dedup, B-scope and K), seeded.

Each pair is two bundles that differ in one place:
- B-dedup: the case's `for` list leaves out the timepoint (or ranges over a value column) and its
  trace repeats equal values for the deciding principal; the dual adds `(t: Timepoint)` and
  `tp(t)`, where set and bag readings agree.
- B-scope: the case's aggregation body has no past operator, so it reads the decision point only;
  the dual wraps the same body in `formerly within W`.
- K, key-local slicing and the mirror rule, in eight shapes (`KEY_SHAPES`):
  - previous: another principal's event sits between this principal's last event and the
    decision, so `previous` must mean this principal's previous event (the default
    `callerPrincipal` pin is universal and symmetric); in the dual this principal's own event that
    fails the predicate sits there, so `previous` must mean the immediately preceding event;
  - since_other: the positive left of `since` ranges over this key's positions only, so another
    principal's event after the anchor does not break it; the dual has no such event;
  - since_own: this principal's own non-matching event after the anchor does break it; the dual
    has another principal's event in its place;
  - partial_pin: an event schema that pins `callerPrincipal` on `request` but not on
    `response` is not universal, so `previous` reads the whole trace; the dual pins both kinds;
  - context_pin: a universal pin to `context.session` keys every condition on the session, so
    another session of the same principal is invisible; in the dual an event of the same session
    that fails the predicate sits there;
  - mirror_history: a history event that logs a caller it does not carry is rejected and never
    counts; the dual's event carries its caller;
  - mirror_decision: a decision event that logs a caller it does not carry fails closed and is not
    ingested; the dual's event carries its caller;
  - no_scope_history: under the default pin, a history event with no principal is rejected; the
    dual's event has its scope.
Other principals' events are mixed in, which the pins must ignore. Every K trace ends with one
more decision of the same principal on the rule's action, after the window has passed (DENY).

Usage: python3 -I pairs.py --seed S --pairs N --out DIR (or write_pairs from make_cases.py)
"""

import argparse
import json
import os
import random

SCHEMA = """namespace Ledger {
  type TransferInput = {
    amount: Long,
    user: String
  };
  type LoginInput = {
    server: String,
    user: String
  };
  type AlertInput = {
    level: Long,
    server: String
  };
  type Empty = {  };
  entity Gateway;
  entity User = {
    id: String
  };
  action "Transfer" appliesTo {
    principal: [User],
    resource: [Gateway],
    context: {
      input: TransferInput,
      output?: Empty
    }
  };
  action "Login" appliesTo {
    principal: [User],
    resource: [Gateway],
    context: {
      input: LoginInput,
      output?: Empty
    }
  };
  action "Alert" appliesTo {
    principal: [User],
    resource: [Gateway],
    context: {
      input: AlertInput,
      output?: Empty
    }
  };
}
"""

PEOPLE = ["ana", "bo", "cy", "dee", "eli", "fay"]
USERS = ["u1", "u2", "u3", "u4"]
SESSIONS = ["s-17", "s-23", "s-41", "s-58", "s-60", "s-72"]

# The Ledger schema with a `session` attribute in every action's context, for the session pin.
SESSION_SCHEMA = SCHEMA.replace(
    "output?: Empty\n", "output?: Empty,\n      session: String\n"
)


def event_schema(pins: dict[str, str]) -> str:
    """An event schema with `request` (a decision kind) and `response`; `pins` maps a kind to the
    pin line it declares, and a kind with no entry logs `callerPrincipal` unpinned."""
    out = []
    for kind, head in (("request", "decision event"), ("response", "event")):
        fields = ["    ...inputs(A),"]
        if kind == "response":
            fields.append("    ...outputs(A),")
        pin = pins.get(kind)
        if pin and "callerPrincipal" in pin:
            fields.append(f"    {pin},")
        else:
            if pin:
                fields.append(f"    {pin},")
            fields.append("    callerPrincipal: principalType(A),")
        fields += ["    callerResource: resourceType(A),", "    requestId: String,"]
        out.append(f"{head} <A>::{kind} {{\n" + "\n".join(fields) + "\n}\n")
    return "\n".join(out)


CALLER_PIN = "pin callerPrincipal: principalType(A) = principal"
UNIVERSAL_EVENTS = event_schema({"request": CALLER_PIN, "response": CALLER_PIN})
PARTIAL_EVENTS = event_schema({"request": CALLER_PIN})
SESSION_PIN = "pin sess: String = context.session"
SESSION_EVENTS = event_schema({"request": SESSION_PIN, "response": SESSION_PIN})


def rec(fields):
    parts = []
    for k, v in fields:
        parts.append(f"{k}: {json.dumps(v) if isinstance(v, str) else v}")
    return "{ " + ", ".join(parts) + " }"


def event(ts, who, action, inp, rid):
    scope = f'scope(principal: Ledger::User::"{who}", resource: Ledger::Gateway::"gw1")'
    ctx = f"request_context(input: {rec(inp)})"
    logged = (
        f'Ledger::Action::"{action}"::request(input: {rec(inp)}, callerPrincipal: Ledger::User::"{who}", '
        f'callerResource: Ledger::Gateway::"gw1", requestId: "{rid}")'
    )
    return f"@{ts} {scope} {ctx} {logged}"


def line(ts, action, inp, rid, *, scope, kind="request", caller=None, session=None):
    """One trace line. `scope` is the principal the event carries (None: no scope envelope);
    `caller` the principal it logs (default: its scope); `session` adds `context.session` and the
    logged `sess` field of the session-pinned event schema."""
    caller = scope if caller is None else caller
    parts = [f"@{ts}"]
    if scope is not None:
        parts.append(
            f'scope(principal: Ledger::User::"{scope}", resource: Ledger::Gateway::"gw1")'
        )
    ctx = [f"input: {rec(inp)}"]
    if session is not None:
        ctx.append(f"session: {json.dumps(session)}")
    parts.append(f"request_context({', '.join(ctx)})")
    logged = [f"input: {rec(inp)}"]
    if kind == "response":
        logged.append("output: {  }")
    if session is not None:
        logged.append(f"sess: {json.dumps(session)}")
    logged += [
        f'callerPrincipal: Ledger::User::"{caller}"',
        'callerResource: Ledger::Gateway::"gw1"',
        f'requestId: "{rid}"',
    ]
    parts.append(f'Ledger::Action::"{action}"::{kind}({", ".join(logged)})')
    return " ".join(parts)


def write(out, name, policy, trace, meta, extra=None):
    d = os.path.join(out, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "schema.cedarschema"), "w") as f:
        f.write(SCHEMA)
    with open(os.path.join(d, "policy.dw"), "w") as f:
        f.write(policy)
    with open(os.path.join(d, "trace.log"), "w") as f:
        f.write("\n".join(trace) + "\n")
    for fname, text in (extra or {}).items():
        with open(os.path.join(d, fname), "w") as f:
            f.write(text)
    with open(os.path.join(d, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)


def trace_with_noise(r, me, mine, others_count):
    """Interleave my events with other principals' events; strictly increasing timestamps."""
    evs = [(me, e) for e in mine]
    for _ in range(others_count):
        evs.append((r.choice([p for p in PEOPLE if p != me]), None))
    r.shuffle(evs)
    return evs


def dedup_pair(r, idx, out):
    me = r.choice(PEOPLE)
    kind = r.choice(["sum", "count_user", "count_amount"])
    window = r.choice(["1h", "30m", "2h"])
    if kind == "sum":
        base = r.sample([20, 40, 60, 80, 100, 150, 200], 3)
        values = [base[0], base[0], base[1]] + (
            [base[2], base[2]] if r.random() < 0.5 else [base[2]]
        )
        set_total, bag_total = sum(set(values)), sum(values)
        thr = r.randint(set_total, bag_total - 1)
        agg_case = f'(sum a for (a: Long). where formerly within {window} Ledger::Action::"Transfer"::request{{ input.amount: a }}) > {thr}'
        agg_dual = (
            f"(sum a for (a: Long), (t: Timepoint). where formerly within {window} "
            f'(Ledger::Action::"Transfer"::request{{ input.amount: a }} && tp(t))) > {thr}'
        )
        mine = [
            ("Transfer", [("amount", v), ("user", r.choice(USERS))]) for v in values
        ]
    elif kind == "count_user":
        us = r.sample(USERS, 2)
        values = [us[0], us[0], us[1]] + ([us[0]] if r.random() < 0.5 else [])
        thr = len(set(values))
        agg_case = (
            f"(count for (u: String). where formerly within {window} "
            f'Ledger::Action::"Login"::request{{ input.user: u, input.server: context.input.server }}) > {thr}'
        )
        agg_dual = (
            f"(count for (u: String), (t: Timepoint). where formerly within {window} "
            f'(Ledger::Action::"Login"::request{{ input.user: u, input.server: context.input.server }} && tp(t))) > {thr}'
        )
        mine = [("Login", [("server", "s1"), ("user", v)]) for v in values]
    else:
        base = r.sample([5, 10, 15, 25, 50], 2)
        values = [base[0], base[0], base[0], base[1]]
        agg_case = f'(count for (n: Long). where formerly within {window} Ledger::Action::"Transfer"::request{{ input.amount: n }}) > 2'
        agg_dual = (
            f"(count for (n: Long), (t: Timepoint). where formerly within {window} "
            f'(Ledger::Action::"Transfer"::request{{ input.amount: n }} && tp(t))) > 2'
        )
        mine = [
            ("Transfer", [("amount", v), ("user", r.choice(USERS))]) for v in values
        ]
    evs = trace_with_noise(r, me, mine, r.randint(1, 4))
    lines, ts, rid = [], r.randint(0, 50), 0
    for who, e in evs:
        rid += 1
        if e is None:
            e = r.choice(mine)
        lines.append(event(ts, who, e[0], e[1], f"r{rid}"))
        ts += r.randint(1, 30)
    rid += 1
    lines.append(event(ts, me, "Alert", [("level", 1), ("server", "s1")], f"r{rid}"))
    for member, agg in (("case", agg_case), ("dual", agg_dual)):
        pol = (
            f'@id("pair_{idx}_{member}")\npermit (\n    principal,\n    action == Ledger::Action::"Alert",\n    resource\n)\n'
            f"when temporal {{\n    {agg}\n}};\n"
        )
        write(
            out,
            f"bd{idx:03d}_{member}",
            pol,
            lines,
            {
                "family": "bdual",
                "b_family": "B-dedup",
                "pair": idx,
                "member": member,
                "kind": kind,
            },
        )


def scope_pair(r, idx, out):
    me = r.choice(PEOPLE)
    window = r.choice(["1h", "30m", "2h"])
    kind = r.choice(["count_login", "sum_self"])
    if kind == "count_login":
        n = r.randint(2, 4)
        thr = r.randint(1, n - 1)
        body = 'Ledger::Action::"Login"::request{ input.user: _, input.server: context.input.server } && tp(t)'
        agg_case = f"(count for (t: Timepoint). where ({body})) > {thr}"
        agg_dual = f"(count for (t: Timepoint). where formerly within {window} ({body})) > {thr}"
        mine = [
            ("Login", [("server", "s1"), ("user", r.choice(USERS))]) for _ in range(n)
        ]
        decide = ("Alert", [("level", 2), ("server", "s1")])
        action = "Alert"
    else:
        vals = r.sample([30, 60, 90, 120], 3)
        thr = max(vals) + r.randint(1, 20)
        body = 'Ledger::Action::"Transfer"::request{ input.amount: a } && tp(t)'
        agg_case = f"(sum a for (a: Long), (t: Timepoint). where ({body})) > {thr}"
        agg_dual = f"(sum a for (a: Long), (t: Timepoint). where formerly within {window} ({body})) > {thr}"
        mine = [("Transfer", [("amount", v), ("user", r.choice(USERS))]) for v in vals]
        decide = ("Transfer", [("amount", min(vals)), ("user", "u1")])
        action = "Transfer"
    evs = trace_with_noise(r, me, mine, r.randint(1, 4))
    lines, ts, rid = [], r.randint(0, 50), 0
    for who, e in evs:
        rid += 1
        if e is None:
            e = r.choice(mine)
        lines.append(event(ts, who, e[0], e[1], f"r{rid}"))
        ts += r.randint(1, 30)
    rid += 1
    lines.append(event(ts, me, decide[0], decide[1], f"r{rid}"))
    for member, agg in (("case", agg_case), ("dual", agg_dual)):
        pol = (
            f'@id("pair_{idx}_{member}")\npermit (\n    principal,\n    action == Ledger::Action::"{action}",\n    resource\n)\n'
            f"when temporal {{\n    {agg}\n}};\n"
        )
        write(
            out,
            f"bs{idx:03d}_{member}",
            pol,
            lines,
            {
                "family": "bdual",
                "b_family": "B-scope",
                "pair": idx,
                "member": member,
                "kind": kind,
            },
        )


def permit(idx, member, action, condition):
    return (
        f'@id("pair_{idx}_{member}")\npermit (\n    principal,\n    action == Ledger::Action::"{action}",\n    resource\n)\n'
        f"when temporal {{\n    {condition}\n}};\n"
    )


LOGIN_PRED = 'Ledger::Action::"Login"::request{ input.user: _, input.server: context.input.server }'
LOGIN_ANCHOR = 'Ledger::Action::"Login"::request{ input.server: "s1" }'
LOGIN_RESPONSE = 'Ledger::Action::"Login"::response{ input.server: "s1" }'
TRANSFER_LEFT = 'Ledger::Action::"Transfer"::request{ input.amount: * }'


class Clock:
    def __init__(self, r):
        self.r, self.ts, self.rid = r, r.randint(0, 50), 0

    def tick(self):
        """The next timestamp and request id; timestamps strictly increase."""
        ts, self.rid = self.ts, self.rid + 1
        self.ts += self.r.randint(1, 20)
        return ts, f"r{self.rid}"


def login(r):
    return ("Login", [("server", "s1"), ("user", r.choice(USERS))])


def transfer(r):
    return (
        "Transfer",
        [("amount", r.choice([10, 20, 30, 45])), ("user", r.choice(USERS))],
    )


ALERT = ("Alert", [("level", 1), ("server", "s1")])


WINDOW_SECONDS = {"30m": 1800, "1h": 3600, "2h": 7200}


def lapsed(c, lines, ev, who, window, session=None):
    """One more decision of `who` on the rule's own action, an hour after the window that holds
    everything before it has passed: whatever matched lies outside the window, so it is DENY, which
    a program that ignores the history, or that allows the last decision of a trace, gets wrong."""
    c.ts += WINDOW_SECONDS[window] + 3600
    ts, rid = c.tick()
    lines.append(line(ts, ev[0], ev[1], rid, scope=who, session=session))


def noise(r, c, lines, who, n_max=2, session=None):
    for _ in range(r.randint(0, n_max)):
        ev = r.choice([login(r), transfer(r)])
        ts, rid = c.tick()
        lines.append(line(ts, ev[0], ev[1], rid, scope=who, session=session))


def key_previous(r, idx, member, me, other, window, extra):
    """`previous` under the default pin. Between this principal's matching event and its Alert sits
    another principal's event (case: key-local `previous` still sees the match, ALLOW) or this
    principal's own event that fails the predicate (dual: DENY, where a reading of `previous` as
    "some earlier event", or one that drops the temporal condition, says ALLOW)."""
    pred = r.choice(
        [LOGIN_PRED, 'Ledger::Action::"Transfer"::request{ input.amount: * }']
    )
    mine = login(r) if "Login" in pred else transfer(r)
    c, lines = Clock(r), []
    noise(r, c, lines, other)
    ts, rid = c.tick()
    lines.append(line(ts, mine[0], mine[1], rid, scope=me))
    alt_login, alt_transfer = login(r), transfer(r)
    pick = r.choice([alt_login, alt_transfer])
    ts, rid = c.tick()
    if member == "case":
        lines.append(line(ts, pick[0], pick[1], rid, scope=other))
    else:
        miss = alt_transfer if "Login" in pred else alt_login
        lines.append(line(ts, miss[0], miss[1], rid, scope=me))
    ts, rid = c.tick()
    lines.append(line(ts, ALERT[0], ALERT[1], rid, scope=me))
    lapsed(c, lines, ALERT, me, window)
    return permit(idx, member, "Alert", f"previous within {window} {pred}"), lines


def key_since(r, idx, member, me, other, window, extra, own):
    """The positive left of `since`: after this principal's anchor, every step of this key must
    match the left. `own` puts this principal's own Alert after the anchor in the case (it breaks
    the run) and another principal's Alert in the dual; otherwise the case has another
    principal's event after the anchor and the dual has none."""
    cond = f"{TRANSFER_LEFT}\n    since within {window}\n    {LOGIN_ANCHOR}"
    c, lines = Clock(r), []
    noise(r, c, lines, other)
    ts, rid = c.tick()
    lines.append(
        line(ts, "Login", [("server", "s1"), ("user", r.choice(USERS))], rid, scope=me)
    )
    steps = r.randint(0, 2)
    at = r.randint(0, steps)
    for k in range(steps + 1):
        if k == at:
            if own:
                ts, rid = c.tick()
                lines.append(
                    line(
                        ts,
                        ALERT[0],
                        ALERT[1],
                        rid,
                        scope=me if member == "case" else other,
                    )
                )
            elif member == "case":
                ev = r.choice([login(r), ALERT])
                ts, rid = c.tick()
                lines.append(line(ts, ev[0], ev[1], rid, scope=other))
        if k < steps:
            ev = transfer(r)
            ts, rid = c.tick()
            lines.append(line(ts, ev[0], ev[1], rid, scope=me))
    ev = transfer(r)
    ts, rid = c.tick()
    lines.append(line(ts, ev[0], ev[1], rid, scope=me))
    lapsed(c, lines, transfer(r), me, window)
    return permit(idx, member, "Transfer", cond), lines


def key_partial_pin(r, idx, member, me, other, window, extra):
    """A pin on `request` only is not universal, so `previous` reads the whole trace (case); the
    same pin on both kinds is universal and key-local (dual). Same trace for both."""
    extra["event.dwschema"] = PARTIAL_EVENTS if member == "case" else UNIVERSAL_EVENTS
    c, lines = Clock(r), []
    noise(r, c, lines, other)
    mine = login(r)
    ts, rid = c.tick()
    lines.append(line(ts, mine[0], mine[1], rid, scope=me))
    ev = r.choice([login(r), transfer(r)])
    ts, rid = c.tick()
    lines.append(line(ts, ev[0], ev[1], rid, scope=other))
    ts, rid = c.tick()
    lines.append(line(ts, ALERT[0], ALERT[1], rid, scope=me))
    lapsed(c, lines, ALERT, me, window)
    return permit(idx, member, "Alert", f"previous within {window} {LOGIN_PRED}"), lines


def key_context_pin(r, idx, member, me, other, window, extra):
    """A universal pin to `context.session` keys conditions on the session. Between this session's
    Login and its Alert sits the same principal's event in another session (case: invisible, ALLOW)
    or an event of this session that fails the predicate (dual: DENY)."""
    extra["schema.cedarschema"] = SESSION_SCHEMA
    extra["event.dwschema"] = SESSION_EVENTS
    mine_s, other_s = r.sample(SESSIONS, 2)
    c, lines = Clock(r), []
    noise(r, c, lines, other, session=other_s)
    ev = login(r)
    ts, rid = c.tick()
    lines.append(line(ts, ev[0], ev[1], rid, scope=me, session=mine_s))
    alt_login, alt_transfer = login(r), transfer(r)
    pick = r.choice([alt_login, alt_transfer])
    ts, rid = c.tick()
    if member == "case":
        lines.append(line(ts, pick[0], pick[1], rid, scope=me, session=other_s))
    else:
        lines.append(
            line(ts, alt_transfer[0], alt_transfer[1], rid, scope=me, session=mine_s)
        )
    ts, rid = c.tick()
    lines.append(line(ts, ALERT[0], ALERT[1], rid, scope=me, session=mine_s))
    lapsed(c, lines, ALERT, me, window, session=mine_s)
    return permit(idx, member, "Alert", f"previous within {window} {LOGIN_PRED}"), lines


def key_mirror(r, idx, member, me, other, window, extra, kind, scope_less=False):
    """The mirror rule. The case's Login event (a `response`, or a `request`) logs this principal
    as its caller but carries another principal's scope, or no scope at all: it is not ingested,
    so it cannot satisfy this principal's `formerly`. The dual's event carries its caller."""
    target = LOGIN_RESPONSE if kind == "response" else LOGIN_ANCHOR
    c, lines = Clock(r), []
    noise(r, c, lines, other)
    ev = ("Login", [("server", "s1"), ("user", r.choice(USERS))])
    ts, rid = c.tick()
    if member == "case":
        scope = None if scope_less else other
    else:
        scope = me
    lines.append(line(ts, ev[0], ev[1], rid, scope=scope, caller=me, kind=kind))
    noise(r, c, lines, other, n_max=1)
    ts, rid = c.tick()
    lines.append(line(ts, ALERT[0], ALERT[1], rid, scope=me))
    lapsed(c, lines, ALERT, me, window)
    return permit(idx, member, "Alert", f"formerly within {window} {target}"), lines


KEY_SHAPES = {
    "previous": key_previous,
    "since_other": lambda *a: key_since(*a, own=False),
    "since_own": lambda *a: key_since(*a, own=True),
    "partial_pin": key_partial_pin,
    "context_pin": key_context_pin,
    "mirror_history": lambda *a: key_mirror(*a, kind="response"),
    "mirror_decision": lambda *a: key_mirror(*a, kind="request"),
    "no_scope_history": lambda *a: key_mirror(*a, kind="response", scope_less=True),
}


def keylocal_pair(r, idx, shape, out):
    me = r.choice(PEOPLE)
    other = r.choice([p for p in PEOPLE if p != me])
    window = r.choice(["1h", "30m", "2h"])
    state = r.getstate()
    for member in ("case", "dual"):
        r.setstate(
            state
        )  # both members draw the same trace, apart from what the shape changes
        extra: dict[str, str] = {}
        policy, lines = KEY_SHAPES[shape](r, idx, member, me, other, window, extra)
        schema = extra.pop("schema.cedarschema", None)
        write(
            out,
            f"bk{idx:03d}_{member}",
            policy,
            lines,
            {
                "family": "pairs",
                "b_family": "K",
                "pair": idx,
                "member": member,
                "kind": shape,
            },
            extra,
        )
        if schema is not None:
            with open(
                os.path.join(out, f"bk{idx:03d}_{member}", "schema.cedarschema"), "w"
            ) as f:
                f.write(schema)


def write_pairs(seed, pairs, out, key_per_shape=None):
    """`pairs` B-dedup and B-scope pairs; `key_per_shape` K pairs of each shape (default:
    `pairs` previous pairs only)."""
    r = random.Random(seed)
    for i in range(pairs):
        dedup_pair(r, i, str(out))
        scope_pair(r, i, str(out))
    shapes = key_per_shape or {"previous": pairs}
    idx = 0
    for shape in KEY_SHAPES:
        for _ in range(shapes.get(shape, 0)):
            keylocal_pair(r, idx, shape, str(out))
            idx += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--pairs", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    write_pairs(a.seed, a.pairs, a.out)


if __name__ == "__main__":
    main()
