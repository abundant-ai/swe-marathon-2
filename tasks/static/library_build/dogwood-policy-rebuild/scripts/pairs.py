"""Paired cases for the private case set (B-dedup, B-scope and K), seeded.

Each pair is two bundles that differ in one place:
- B-dedup: the case's `for` list leaves out the timepoint (or ranges over a value column) and its
  trace repeats equal values for the deciding principal; the dual adds `(t: Timepoint)` and
  `tp(t)`, where set and bag readings agree.
- B-scope: the case's aggregation body has no past operator, so it reads the decision point only;
  the dual wraps the same body in `formerly within W`.
- K: the case puts another principal's event between this principal's last event and the
  decision, so `previous` must mean this principal's previous event (the default
  `callerPrincipal` pin makes every condition key-local); the dual has no event in between.
Other principals' events are mixed in, which the default pin must ignore.

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


def write(out, name, policy, trace, meta):
    d = os.path.join(out, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "schema.cedarschema"), "w") as f:
        f.write(SCHEMA)
    with open(os.path.join(d, "policy.dw"), "w") as f:
        f.write(policy)
    with open(os.path.join(d, "trace.log"), "w") as f:
        f.write("\n".join(trace) + "\n")
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


def keylocal_pair(r, idx, out):
    me = r.choice(PEOPLE)
    other = r.choice([p for p in PEOPLE if p != me])
    window = r.choice(["1h", "30m", "2h"])
    kind = r.choice(["login", "transfer"])
    if kind == "login":
        pred = 'Ledger::Action::"Login"::request{ input.user: _, input.server: context.input.server }'
        mine = ("Login", [("server", "s1"), ("user", r.choice(USERS))])
        theirs = ("Login", [("server", "s1"), ("user", r.choice(USERS))])
    else:
        pred = 'Ledger::Action::"Transfer"::request{ input.amount: * }'
        mine = (
            "Transfer",
            [("amount", r.choice([10, 20, 30])), ("user", r.choice(USERS))],
        )
        theirs = (
            "Transfer",
            [("amount", r.choice([10, 20, 30])), ("user", r.choice(USERS))],
        )
    pol = (
        '@id("pair_{idx}_{member}")\npermit (\n    principal,\n    action == Ledger::Action::"Alert",\n    resource\n)\n'
        "when temporal {{\n    previous within {window} {pred}\n}};\n"
    )
    for member, interleave in (("case", True), ("dual", False)):
        lines, ts, rid = [], r.randint(0, 50), 0
        for _ in range(r.randint(0, 2)):
            rid += 1
            lines.append(event(ts, other, theirs[0], theirs[1], f"r{rid}"))
            ts += r.randint(1, 20)
        rid += 1
        lines.append(event(ts, me, mine[0], mine[1], f"r{rid}"))
        ts += r.randint(1, 20)
        if interleave:
            rid += 1
            lines.append(event(ts, other, theirs[0], theirs[1], f"r{rid}"))
            ts += r.randint(1, 20)
        rid += 1
        lines.append(
            event(ts, me, "Alert", [("level", 1), ("server", "s1")], f"r{rid}")
        )
        text = pol.format(idx=idx, member=member, window=window, pred=pred)
        write(
            out,
            f"bk{idx:03d}_{member}",
            text,
            lines,
            {
                "family": "pairs",
                "b_family": "K",
                "pair": idx,
                "member": member,
                "kind": kind,
            },
        )


def write_pairs(seed, pairs, out):
    r = random.Random(seed)
    for i in range(pairs):
        dedup_pair(r, i, str(out))
        scope_pair(r, i, str(out))
        keylocal_pair(r, i, str(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--pairs", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    write_pairs(a.seed, a.pairs, a.out)


if __name__ == "__main__":
    main()
