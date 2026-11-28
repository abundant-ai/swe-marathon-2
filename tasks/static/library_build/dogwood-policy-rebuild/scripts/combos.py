"""More documented combinations for B-dedup, B-scope and K, and replay templates for R's window
edges, `since` boundary and `previous` (fix round 1: QA 17 F2 and F5, panel 2026-11-28), seeded.

Every template states the guide sentences that decide its answer, and records the answer those
sentences give (`expect`: the verdict of every trace line, in order: ALLOW, DENY, or REJECTED for
a history event that is not ingested). `checks/combos_check.py` compares that with the release
build's recorded answers; a template the build answers otherwise is dropped, never kept on the
build's word alone. All B traces are one principal's, so only the deduplication or scope rule
moves them; K's traces add another principal (or session) where the shape needs one, and no K
aggregate repeats a value, so deduplication never moves K.

Guide sentences (chapter 04 unless named):
- [AGG] "The `for <binders>.` clause names the aggregation domain: the satisfying assignments of
  `where φ` are collected, projected onto the `for` variables, deduplicated, then aggregated."
- [TP] "Whether `t` is listed in the aggregation's `for` domain determines distinctness ...
  Omit `t` from the `for` list to deduplicate equal values across time."
- [BARE] "The body is a bare predicate with no past operator, so it matches only the event being
  decided" (the B-scope example), and "formerly within W body holds iff body holds at some j in
  [0, i]" (Operator semantics).
- [CMP] Aggregate-vs-aggregate comparison, and arithmetic over aggregates ("(count …) - (count …)
  <= 5"), in "Aggregations" and "Arithmetic in comparison operands" (enabled in this build).
- [EXISTS] "Every free variable of an aggregation body must be bound — either by the for list or
  by an enclosing binder".
- [WIN] "Windows are closed (inclusive) ... A witness exactly W seconds back is in; one second
  further is out."
- [PREV] "previous within W body checks only j = i - 1: it holds iff the immediately preceding
  timepoint is in-window and body holds there."
- [SINCE] "left since within W right holds iff there is an anchor j in the window where right
  holds and left holds at every step k in [j+1, i] (through the decision point)."
- [NEG] "`!A since within W B`: no A since B" (the open-session idiom).
- [KEY] Chapter 03, "Universal symmetric pins": "`previous` means 'this key's previous event'",
  "The positive left of `since` quantifies over this key's positions only ... the key's own
  non-matching events still do", the slice "agreeing with the current request on every
  universally-pinned field", "If a kind is left out the pin is not universal" (custom kinds
  included), and symmetric pins "whatever the field is called" (`pin actor ... = principal`).
- [MIRROR] Chapter 03, "The mirror rule": an event whose symmetric-pin field differs from its own
  request's value, or that logs it with no scope, "is not ingested: no later decision sees it,
  and a decision event fails closed"; "a history event with no principal is rejected".
- [DECIDE] Chapter 03: only `request` is a decision kind in the default schema, so every request
  line has a verdict and a `response` or `error` line has none.
"""

from __future__ import annotations

import json
import os
import random

import pairs

ALERT_RULE = "Alert"
WINDOWS = {"30m": 1800, "1h": 3600, "2h": 7200}


# ---------------------------------------------------------------------------------------------
# One principal's trace for the B combinations: every request is a decision [DECIDE].


def one_principal(r, me, events, decide):
    """`events` then the decision, 1-30 s apart; returns the lines and the decision's index."""
    ts, lines = r.randint(0, 50), []
    for i, (action, inp) in enumerate([*events, decide]):
        lines.append(pairs.event(ts, me, action, inp, f"r{i + 1}"))
        ts += r.randint(1, 30)
    return lines


def write_pair(out, prefix, idx, family, kind, members):
    """`members`: {"case"|"dual": (policy, lines, expect, extra)}."""
    for member, (policy, lines, expect, extra) in members.items():
        meta = {
            "family": "bdual" if family.startswith("B") else "pairs",
            "b_family": family,
            "pair": idx,
            "member": member,
            "kind": kind,
            "expect": {"trace.log": expect},
        }
        pairs.write(out, f"{prefix}{idx:03d}_{member}", policy, lines, meta, extra)


def rule(idx, member, action, condition):
    return pairs.permit(idx, member, action, condition)


def transfer_ev(amount, user):
    return ("Transfer", [("amount", amount), ("user", user)])


def login_ev(user, server="s1"):
    return ("Login", [("server", server), ("user", user)])


ALERT_EV = ("Alert", [("level", 1), ("server", "s1")])


def last_only(n_before, verdict):
    """n_before decisions on other actions (DENY: the rule is on another action), then one."""
    return ["DENY"] * n_before + [verdict]


# ---------------------------------------------------------------------------------------------
# B-dedup: the case leaves the timepoint out of the domain (equal values are deduplicated [AGG]
# [TP]); the dual adds `(t: Timepoint)` and `tp(t)`, so equal values at different timepoints count
# separately. The decision is the trace's last event, an Alert.


def tp_dual(domain, pattern_body, window):
    return (
        f"{domain}, (t: Timepoint). where formerly within {window} "
        f"({pattern_body} && tp(t))"
    )


def dedup_two_columns(r, idx, out):
    """count over two value columns: distinct (user, amount) pairs [AGG], one repeated."""
    me, window = r.choice(pairs.PEOPLE), r.choice(list(WINDOWS))
    u1, u2 = r.sample(pairs.USERS, 2)
    a1, a2 = r.sample([10, 20, 30, 45], 2)
    rows = [(u1, a1), (u1, a1), (u2, a1), (u1, a2)]
    r.shuffle(rows)
    distinct, total = len(set(rows)), len(rows)
    body = 'Ledger::Action::"Transfer"::request{ input.user: u, input.amount: n }'
    case = f"(count for (u: String), (n: Long). where formerly within {window} {body}) > {distinct}"
    dual = f"(count {tp_dual('for (u: String), (n: Long)', body, window)}) > {distinct}"
    events = [transfer_ev(a, u) for u, a in rows]
    lines = one_principal(r, me, events, ALERT_EV)
    write_pair(
        out,
        "bd",
        idx,
        "B-dedup",
        "two_columns",
        {
            "case": (
                rule(idx, "case", ALERT_RULE, case),
                lines,
                last_only(4, "DENY"),
                None,
            ),
            "dual": (
                rule(idx, "dual", ALERT_RULE, dual),
                lines,
                last_only(4, "ALLOW" if total > distinct else "DENY"),
                None,
            ),
        },
    )


def dedup_negative_zero(r, idx, out):
    """sum with negative and zero summands: the distinct values' sum is above the threshold,
    every occurrence's sum is not [AGG] (summation is exact)."""
    me, window = r.choice(pairs.PEOPLE), r.choice(list(WINDOWS))
    neg = r.choice([-40, -30, -20, -10])
    pos = r.choice([60, 80, 100])
    values = [neg, neg, 0, 0, pos]
    r.shuffle(values)
    set_sum, bag_sum = sum(set(values)), sum(values)  # bag_sum < set_sum, set_sum >= 20
    thr = r.randint(max(bag_sum, 0), set_sum - 1)  # a threshold that is not negative
    body = 'Ledger::Action::"Transfer"::request{ input.amount: a }'
    case = f"(sum a for (a: Long). where formerly within {window} {body}) > {thr}"
    dual = f"(sum a {tp_dual('for (a: Long)', body, window)}) > {thr}"
    events = [transfer_ev(v, r.choice(pairs.USERS)) for v in values]
    lines = one_principal(r, me, events, ALERT_EV)
    write_pair(
        out,
        "bd",
        idx,
        "B-dedup",
        "negative_zero",
        {
            "case": (
                rule(idx, "case", ALERT_RULE, case),
                lines,
                last_only(5, "ALLOW"),
                None,
            ),
            "dual": (
                rule(idx, "dual", ALERT_RULE, dual),
                lines,
                last_only(5, "DENY"),
                None,
            ),
        },
    )


def dedup_agg_vs_agg(r, idx, out):
    """One aggregate compared with another [CMP]: distinct amounts against distinct users."""
    me, window = r.choice(pairs.PEOPLE), r.choice(list(WINDOWS))
    amount = r.choice([10, 20, 30])
    k = r.randint(3, 4)  # k equal amounts: 1 distinct, k in all
    m = r.randint(1, k - 1)  # m distinct users, each logging in once
    users = r.sample(pairs.USERS, m)
    events = [transfer_ev(amount, r.choice(pairs.USERS)) for _ in range(k)]
    events += [login_ev(u) for u in users]
    r.shuffle(events)
    t_body = 'Ledger::Action::"Transfer"::request{ input.amount: n }'
    l_body = 'Ledger::Action::"Login"::request{ input.user: u }'
    case = (
        f"(count for (n: Long). where formerly within {window} {t_body}) > "
        f"(count for (u: String). where formerly within {window} {l_body})"
    )
    dual = (
        f"(count {tp_dual('for (n: Long)', t_body, window)}) > "
        f"(count {tp_dual('for (u: String)', l_body, window)})"
    )
    lines = one_principal(r, me, events, ALERT_EV)
    n = len(events)
    write_pair(
        out,
        "bd",
        idx,
        "B-dedup",
        "agg_vs_agg",
        {  # 1 > m is false; k > m holds
            "case": (
                rule(idx, "case", ALERT_RULE, case),
                lines,
                last_only(n, "DENY"),
                None,
            ),
            "dual": (
                rule(idx, "dual", ALERT_RULE, dual),
                lines,
                last_only(n, "ALLOW"),
                None,
            ),
        },
    )


def dedup_agg_arith(r, idx, out):
    """Arithmetic over an aggregate [CMP]: three times the number of distinct amounts."""
    me, window = r.choice(pairs.PEOPLE), r.choice(list(WINDOWS))
    a1, a2 = r.sample([10, 20, 30, 45], 2)
    values = [a1, a1, a1, a2]
    r.shuffle(values)
    distinct, total = 2, 4
    thr = r.randint(3 * distinct, 3 * total - 1)
    body = 'Ledger::Action::"Transfer"::request{ input.amount: n }'
    case = f"(count for (n: Long). where formerly within {window} {body}) * 3 > {thr}"
    dual = f"(count {tp_dual('for (n: Long)', body, window)}) * 3 > {thr}"
    events = [transfer_ev(v, r.choice(pairs.USERS)) for v in values]
    lines = one_principal(r, me, events, ALERT_EV)
    write_pair(
        out,
        "bd",
        idx,
        "B-dedup",
        "agg_arith",
        {
            "case": (
                rule(idx, "case", ALERT_RULE, case),
                lines,
                last_only(4, "DENY"),
                None,
            ),
            "dual": (
                rule(idx, "dual", ALERT_RULE, dual),
                lines,
                last_only(4, "ALLOW"),
                None,
            ),
        },
    )


def dedup_exists_corr(r, idx, out):
    """A correlated aggregate inside `exists` [EXISTS]: some user who logged in has more than one
    distinct amount (the case: no, one amount twice) or more than one transfer (the dual: yes)."""
    me, window = r.choice(pairs.PEOPLE), r.choice(list(WINDOWS))
    u = r.choice(pairs.USERS)
    amount = r.choice([10, 20, 30, 45])
    events = [login_ev(u), transfer_ev(amount, u), transfer_ev(amount, u)]
    login = (
        f'formerly within {window} Ledger::Action::"Login"::request{{ input.user: u }}'
    )
    body = 'Ledger::Action::"Transfer"::request{ input.user: u, input.amount: n }'
    case = (
        f"exists (u: String). ({login} && "
        f"(count for (n: Long). where formerly within {window} {body}) > 1)"
    )
    dual = (
        f"exists (u: String). ({login} && "
        f"(count {tp_dual('for (n: Long)', body, window)}) > 1)"
    )
    lines = one_principal(r, me, events, ALERT_EV)
    write_pair(
        out,
        "bd",
        idx,
        "B-dedup",
        "exists_corr",
        {
            "case": (
                rule(idx, "case", ALERT_RULE, case),
                lines,
                last_only(3, "DENY"),
                None,
            ),
            "dual": (
                rule(idx, "dual", ALERT_RULE, dual),
                lines,
                last_only(3, "ALLOW"),
                None,
            ),
        },
    )


def dedup_entity_domain(r, idx, out):
    """An entity-typed `for` variable: distinct gateways (one, gw1) against transfers (several)."""
    me, window = r.choice(pairs.PEOPLE), r.choice(list(WINDOWS))
    k = r.randint(2, 4)
    events = [
        transfer_ev(r.choice([10, 20, 30, 45]), r.choice(pairs.USERS)) for _ in range(k)
    ]
    body = 'Ledger::Action::"Transfer"::request{ callerResource: g }'
    case = (
        f"(count for (g: Ledger::Gateway). where formerly within {window} {body}) > 1"
    )
    dual = f"(count {tp_dual('for (g: Ledger::Gateway)', body, window)}) > 1"
    lines = one_principal(r, me, events, ALERT_EV)
    write_pair(
        out,
        "bd",
        idx,
        "B-dedup",
        "entity_domain",
        {
            "case": (
                rule(idx, "case", ALERT_RULE, case),
                lines,
                last_only(k, "DENY"),
                None,
            ),
            "dual": (
                rule(idx, "dual", ALERT_RULE, dual),
                lines,
                last_only(k, "ALLOW"),
                None,
            ),
        },
    )


# ---------------------------------------------------------------------------------------------
# B-scope: the case's body has no past operator, so it reads the decision point only [BARE]; the
# dual puts the same body under `formerly within W`. Values never repeat, so deduplication does
# not move these pairs.


def scope_pair(r, idx, out, kind, action, events, body, agg, thr, truth):
    """`truth(prefix, at_point)` gives the condition at each decision of `action`: `at_point` is
    True for the case (the decision point only), False for the dual (the window)."""
    me, window = r.choice(pairs.PEOPLE), r.choice(list(WINDOWS))
    lines = one_principal(r, me, events[:-1], events[-1])
    members = {}
    for member in ("case", "dual"):
        where = (
            f"({body})" if member == "case" else f"formerly within {window} ({body})"
        )
        cond = f"({agg}. where {where}) > {thr}"
        expect = []
        for i, (act, _inp) in enumerate(events):
            if act != action:
                expect.append("DENY")
                continue
            ok = truth(events[: i + 1], member == "case")
            expect.append("ALLOW" if ok else "DENY")
        members[member] = (rule(idx, member, action, cond), lines, expect, None)
    write_pair(out, "bs", idx, "B-scope", kind, members)


def scope_combos():
    """(kind, builder) for the six new B-scope combinations."""

    def count_self(r, idx, out):
        """count of Transfers at a Transfer decision: one at the point, more in the window."""
        amounts = r.sample([10, 20, 30, 45, 60], 3)
        events = [transfer_ev(a, r.choice(pairs.USERS)) for a in amounts]
        body = 'Ledger::Action::"Transfer"::request{ input.amount: * } && tp(t)'

        def truth(prefix, point):
            n = 1 if point else sum(1 for e in prefix if e[0] == "Transfer")
            return n > 1

        scope_pair(
            r,
            idx,
            out,
            "count_self",
            "Transfer",
            events,
            body,
            "count for (t: Timepoint)",
            1,
            truth,
        )

    def sum_other(r, idx, out):
        """sum of Transfer amounts at an Alert decision: none at the point (0), the past ones in
        the window."""
        amounts = r.sample([30, 60, 90, 120], 3)
        thr = max(amounts) + r.randint(1, 20)
        events = [transfer_ev(a, r.choice(pairs.USERS)) for a in amounts] + [ALERT_EV]
        body = 'Ledger::Action::"Transfer"::request{ input.amount: a } && tp(t)'

        def truth(prefix, point):
            total = (
                0
                if point
                else sum(dict(e[1])["amount"] for e in prefix if e[0] == "Transfer")
            )
            return total > thr

        scope_pair(
            r,
            idx,
            out,
            "sum_other",
            "Alert",
            events,
            body,
            "sum a for (a: Long), (t: Timepoint)",
            thr,
            truth,
        )

    def count_users_self(r, idx, out):
        """distinct users at a Login decision: the decision's own user at the point, every
        distinct user in the window (users never repeat)."""
        users = r.sample(pairs.USERS, 3)
        events = [login_ev(u) for u in users]
        body = 'Ledger::Action::"Login"::request{ input.user: u, input.server: "s1" }'

        def truth(prefix, point):
            n = (
                1
                if point
                else len({dict(e[1])["user"] for e in prefix if e[0] == "Login"})
            )
            return n > 1

        scope_pair(
            r,
            idx,
            out,
            "count_users_self",
            "Login",
            events,
            body,
            "count for (u: String)",
            1,
            truth,
        )

    def sum_self_filtered(r, idx, out):
        """sum with a range filter in the body: the decision's own amount if it passes, against
        the window's passing amounts."""
        amounts = r.sample([20, 30, 40, 50], 3)
        thr = max(amounts) + r.randint(1, 5)
        events = [transfer_ev(a, r.choice(pairs.USERS)) for a in amounts]
        body = (
            'Ledger::Action::"Transfer"::request{ input.amount: a } && tp(t) && a > 15'
        )

        def truth(prefix, point):
            vals = [dict(e[1])["amount"] for e in prefix if e[0] == "Transfer"]
            total = (
                (vals[-1] if vals[-1] > 15 else 0)
                if point
                else sum(v for v in vals if v > 15)
            )
            return total > thr

        scope_pair(
            r,
            idx,
            out,
            "sum_self_filtered",
            "Transfer",
            events,
            body,
            "sum a for (a: Long), (t: Timepoint)",
            thr,
            truth,
        )

    def bare_past(r, idx, out):
        """a bare predicate next to a past operator in one body: the bare Transfer matches only
        the decision point, which needs a Login in the window before it."""
        window = r.choice(list(WINDOWS))
        amounts = r.sample([10, 20, 30, 45], 3)
        events = [login_ev(r.choice(pairs.USERS))] + [
            transfer_ev(a, r.choice(pairs.USERS)) for a in amounts
        ]
        body = (
            'Ledger::Action::"Transfer"::request{ input.amount: * } && tp(t) && '
            f'formerly within {window} Ledger::Action::"Login"::request{{ input.server: "s1" }}'
        )

        def truth(prefix, point):
            n = 1 if point else sum(1 for e in prefix if e[0] == "Transfer")
            return n > 1

        scope_pair(
            r,
            idx,
            out,
            "bare_past",
            "Transfer",
            events,
            body,
            "count for (t: Timepoint)",
            1,
            truth,
        )

    def count_amount_self(r, idx, out):
        """distinct amounts (a value column, no timepoint) at a Transfer decision: its own amount
        at the point, every distinct amount in the window (amounts never repeat)."""
        amounts = r.sample([10, 20, 30, 45, 60], 3)
        events = [transfer_ev(a, r.choice(pairs.USERS)) for a in amounts]
        body = 'Ledger::Action::"Transfer"::request{ input.amount: n }'

        def truth(prefix, point):
            n = (
                1
                if point
                else len({dict(e[1])["amount"] for e in prefix if e[0] == "Transfer"})
            )
            return n > 1

        scope_pair(
            r,
            idx,
            out,
            "count_amount_self",
            "Transfer",
            events,
            body,
            "count for (n: Long)",
            1,
            truth,
        )

    return [
        ("count_self", count_self),
        ("sum_other", sum_other),
        ("count_users_self", count_users_self),
        ("sum_self_filtered", sum_self_filtered),
        ("bare_past", bare_past),
        ("count_amount_self", count_amount_self),
    ]


DEDUP_COMBOS = [
    ("two_columns", dedup_two_columns),
    ("negative_zero", dedup_negative_zero),
    ("agg_vs_agg", dedup_agg_vs_agg),
    ("agg_arith", dedup_agg_arith),
    ("exists_corr", dedup_exists_corr),
    ("entity_domain", dedup_entity_domain),
]


# ---------------------------------------------------------------------------------------------
# K: a second template for each of the eight shapes. Each returns the policy, the lines and the
# expected verdicts, and may add files (`extra`).


class Trace:
    """Lines with strictly increasing timestamps, and the expected token of each line."""

    def __init__(self, r):
        self.r, self.c, self.lines, self.expect = r, pairs.Clock(r), [], []

    def add(self, action, inp, who, verdict, **kw):
        ts, rid = self.c.tick()
        self.lines.append(pairs.line(ts, action, inp, rid, scope=who, **kw))
        if verdict is not None:
            self.expect.append(verdict)

    def raw(self, text, verdict):
        ts, rid = self.c.tick()
        self.lines.append(text(ts, rid))
        if verdict is not None:
            self.expect.append(verdict)

    def lapse(self, window, action, inp, who, **kw):
        """The rule's own action an hour after the window has passed: DENY [WIN]."""
        self.c.ts += WINDOWS[window] + 3600
        self.add(action, inp, who, "DENY", **kw)


def noise(t, other, n, **kw):
    """Another principal's requests (decisions on other actions: DENY)."""
    for _ in range(n):
        ev = t.r.choice([pairs.login(t.r), pairs.transfer(t.r)])
        t.add(ev[0], ev[1], other, "DENY", **kw)


def k_previous_response(r, member, me, other, window, extra):
    """`previous` on a history kind [KEY][PREV][DECIDE]: this principal's Login response, then
    another principal's request (case: invisible, ALLOW) or this principal's own Transfer (dual:
    the immediately preceding event fails the body, DENY)."""
    t = Trace(r)
    noise(t, other, r.randint(0, 2))
    t.add(
        "Login",
        [("server", "s1"), ("user", r.choice(pairs.USERS))],
        me,
        None,
        kind="response",
    )
    if member == "case":
        ev = r.choice([pairs.login(r), pairs.transfer(r)])
        t.add(ev[0], ev[1], other, "DENY")
    else:
        ev = pairs.transfer(r)
        t.add(ev[0], ev[1], me, "DENY")
    t.add(*ALERT_EV, me, "ALLOW" if member == "case" else "DENY")
    t.lapse(window, *ALERT_EV, me)
    cond = f"previous within {window} {pairs.LOGIN_RESPONSE}"
    return cond, t


def k_since_alerts(own):
    """A positive left on the rule's own action [KEY][SINCE]: after this principal's Login, its
    level-1 Alerts hold the left at every step. `own` breaks the run with this principal's own
    level-2 Alert (case) against another principal's (dual); otherwise another principal's request
    sits after the anchor (case) or nothing (dual), and neither breaks it."""

    def build(r, member, me, other, window, extra):
        t = Trace(r)
        noise(t, other, r.randint(0, 2))
        t.add("Login", [("server", "s1"), ("user", r.choice(pairs.USERS))], me, "DENY")
        t.add("Alert", [("level", 1), ("server", "s1")], me, "ALLOW")
        if own:
            who = me if member == "case" else other
            # me: the left fails at the decision point itself; other: no anchor in its slice
            t.add("Alert", [("level", 2), ("server", "s1")], who, "DENY")
            final = "DENY" if member == "case" else "ALLOW"
        else:
            if member == "case":
                ev = r.choice([pairs.login(r), pairs.transfer(r)])
                t.add(ev[0], ev[1], other, "DENY")
            final = "ALLOW"
        t.add("Alert", [("level", 1), ("server", "s1")], me, final)
        t.lapse(window, "Alert", [("level", 1), ("server", "s1")], me)
        left = 'Ledger::Action::"Alert"::request{ input.level: 1 }'
        return f"{left}\n    since within {window}\n    {pairs.LOGIN_ANCHOR}", t

    return build


AUDIT_KIND = (
    "event <A>::audit {{\n    ...inputs(A),\n{pin}    callerResource: resourceType(A),\n"
    "    requestId: String,\n}}\n"
)


def k_custom_kind(r, member, me, other, window, extra):
    """A custom kind left without the pin [KEY]: the pin on request and response is then not
    universal, so `previous` reads the whole trace and another principal's Transfer is the
    previous event (case: DENY); with the pin on the custom kind too it is universal, and this
    principal's Login is its previous event (dual: ALLOW)."""
    pin = "    pin callerPrincipal: principalType(A) = principal,\n"
    audit = AUDIT_KIND.format(
        pin=pin if member == "dual" else "    callerPrincipal: principalType(A),\n"
    )
    extra["event.dwschema"] = pairs.UNIVERSAL_EVENTS + "\n" + audit
    t = Trace(r)
    noise(t, other, r.randint(0, 2))
    t.add(*pairs.login(r), me, "DENY")
    ev = pairs.transfer(r)
    t.add(ev[0], ev[1], other, "DENY")
    t.add(*ALERT_EV, me, "DENY" if member == "case" else "ALLOW")
    t.lapse(window, *ALERT_EV, me)
    return f"previous within {window} {pairs.LOGIN_PRED}", t


TWO_PINS = (
    "decision event <A>::request {\n    ...inputs(A),\n"
    "    pin callerPrincipal: principalType(A) = principal,\n"
    "    pin sess: String = context.session,\n"
    "    callerResource: resourceType(A),\n    requestId: String,\n}\n\n"
    "event <A>::response {\n    ...inputs(A),\n    ...outputs(A),\n"
    "    pin callerPrincipal: principalType(A) = principal,\n"
    "    pin sess: String = context.session,\n"
    "    callerResource: resourceType(A),\n    requestId: String,\n}\n"
)


def k_two_pins(r, member, me, other, window, extra):
    """Two universal pins, principal and session [KEY]: the slice agrees on both. Between this
    principal's Login and its Alert in one session sits its own request in another session (case:
    another slice, ALLOW) or its own Transfer in the same session (dual: DENY)."""
    extra["schema.cedarschema"] = pairs.SESSION_SCHEMA
    extra["event.dwschema"] = TWO_PINS
    mine_s, other_s = r.sample(pairs.SESSIONS, 2)
    t = Trace(r)
    noise(t, other, r.randint(0, 2), session=mine_s)
    t.add(*pairs.login(r), me, "DENY", session=mine_s)
    if member == "case":
        ev = r.choice([pairs.login(r), pairs.transfer(r)])
        t.add(ev[0], ev[1], me, "DENY", session=other_s)
    else:
        ev = pairs.transfer(r)
        t.add(ev[0], ev[1], me, "DENY", session=mine_s)
    t.add(*ALERT_EV, me, "ALLOW" if member == "case" else "DENY", session=mine_s)
    t.lapse(window, *ALERT_EV, me, session=mine_s)
    return f"previous within {window} {pairs.LOGIN_PRED}", t


ACTOR_EVENTS = pairs.UNIVERSAL_EVENTS.replace(
    "pin callerPrincipal: principalType(A) = principal",
    "pin actor: principalType(A) = principal",
)


def actor_line(ts, action, inp, rid, scope, kind, actor):
    """A line of the `actor` schema: it logs `actor`, and no `callerPrincipal`."""
    text = pairs.line(ts, action, inp, rid, scope=scope, kind=kind, caller=actor)
    return text.replace("callerPrincipal: ", "actor: ")


def k_actor(kind):
    """The mirror rule under a pin named `actor` [MIRROR][KEY]: this principal's Login (a
    `response`, or a `request`) logs `actor` as this principal but carries another principal's
    scope (case: not ingested, and a request fails closed: the Alert's `formerly` finds no Login,
    DENY); the dual's event carries its own scope (ALLOW)."""

    def build(r, member, me, other, window, extra):
        extra["event.dwschema"] = ACTOR_EVENTS
        t = Trace(r)
        for _ in range(r.randint(0, 2)):
            ev = r.choice([pairs.login(r), pairs.transfer(r)])
            t.raw(
                lambda ts, rid, ev=ev: actor_line(
                    ts, ev[0], ev[1], rid, other, "request", other
                ),
                "DENY",
            )
        scope = other if member == "case" else me
        inp = [("server", "s1"), ("user", r.choice(pairs.USERS))]
        if kind == "response":
            verdict = "REJECTED" if member == "case" else None
        else:
            verdict = (
                "DENY"  # a request on another action: DENY, failed closed in the case
            )
        t.raw(
            lambda ts, rid: actor_line(ts, "Login", inp, rid, scope, kind, me), verdict
        )
        t.raw(
            lambda ts, rid: actor_line(ts, *ALERT_EV, rid, me, "request", me),
            "DENY" if member == "case" else "ALLOW",
        )
        t.c.ts += WINDOWS[window] + 3600
        t.raw(lambda ts, rid: actor_line(ts, *ALERT_EV, rid, me, "request", me), "DENY")
        target = pairs.LOGIN_RESPONSE if kind == "response" else pairs.LOGIN_ANCHOR
        return f"formerly within {window} {target}", t

    return build


def k_error_noscope(r, member, me, other, window, extra):
    """Under the default pin a history event with no principal is rejected [MIRROR]: this
    principal's Login `error` with no scope (case: REJECTED, the Alert's `formerly` finds none,
    DENY); the dual's event carries its scope (ALLOW)."""
    t = Trace(r)
    noise(t, other, r.randint(0, 2))
    inp = [("server", "s1"), ("user", r.choice(pairs.USERS))]
    scope = None if member == "case" else me
    t.add(
        "Login",
        inp,
        scope,
        "REJECTED" if member == "case" else None,
        kind="error",
        caller=me,
    )
    t.add(*ALERT_EV, me, "DENY" if member == "case" else "ALLOW")
    t.lapse(window, *ALERT_EV, me)
    return (
        f'formerly within {window} Ledger::Action::"Login"::error{{ input.server: "s1" }}',
        t,
    )


KEY_COMBOS = {
    "previous_response": k_previous_response,
    "since_other_alerts": k_since_alerts(own=False),
    "since_own_alerts": k_since_alerts(own=True),
    "custom_kind": k_custom_kind,
    "two_pins": k_two_pins,
    "actor_history": k_actor("response"),
    "actor_decision": k_actor("request"),
    "error_noscope": k_error_noscope,
}


def key_pair(r, idx, shape, out):
    me = r.choice(pairs.PEOPLE)
    other = r.choice([p for p in pairs.PEOPLE if p != me])
    window = r.choice(list(WINDOWS))
    state = r.getstate()
    members = {}
    for member in ("case", "dual"):
        r.setstate(
            state
        )  # both members draw the same trace, apart from what the shape changes
        extra: dict[str, str] = {}
        cond, t = KEY_COMBOS[shape](r, member, me, other, window, extra)
        members[member] = (rule(idx, member, "Alert", cond), t.lines, t.expect, extra)
    write_pair(out, "bk", idx, "K", shape, members)


# ---------------------------------------------------------------------------------------------
# F5: R units at a window's edge, the `since` boundary and `previous`, one principal [WIN][SINCE]
# [PREV][NEG]. Written as feature templates (fx bundles, replay family R).


def f5_window_edge(r):
    """A witness exactly W back is in and W+1 out [WIN], for `formerly`, `previous` and a negated
    `since`, with W 10m, 1h or 2h."""
    op = r.choice(["formerly", "previous", "since"])
    w_name, w = r.choice([("10m", 600), ("1h", 3600), ("2h", 7200)])
    me, user = r.choice(pairs.PEOPLE), r.choice(pairs.USERS)
    lines, expect, ts = [], [], r.randint(10, 500)

    def add(action, inp, verdict):
        lines.append(pairs.line(ts, action, inp, f"r{len(lines) + 1}", scope=me))
        expect.append(verdict)

    add(*ALERT_EV, "DENY")  # no Login yet
    ts += r.randint(2, 9)
    login = ts
    add("Login", [("server", "s1"), ("user", user)], "DENY")
    if op == "previous":  # the Alert right after the Login, exactly W later: in
        ts = login + w
        add(*ALERT_EV, "ALLOW")
        ts += r.randint(2, 9)
        login = ts
        add("Login", [("server", "s1"), ("user", user)], "DENY")
        ts = login + w + 1  # the next one W+1 after its Login: out
        add(*ALERT_EV, "DENY")
        cond = f"previous within {w_name} {pairs.LOGIN_ANCHOR}"
    else:
        ts = login + w
        add(*ALERT_EV, "ALLOW")
        ts = login + w + 1
        add(*ALERT_EV, "DENY")
        if op == "formerly":
            cond = f"formerly within {w_name} {pairs.LOGIN_ANCHOR}"
        else:
            cond = (
                '!Ledger::Action::"Transfer"::request{ input.amount: 99 }\n'
                f"    since within {w_name}\n    {pairs.LOGIN_ANCHOR}"
            )
    return cond, lines, expect


def f5_since_boundary(r):
    """The left of `since` must hold at the decision point too [SINCE]: level-1 Alerts after the
    Login hold it; a level-2 Alert fails it at its own decision, and breaks the run after."""
    w_name = r.choice(["30m", "1h", "2h"])
    me, user = r.choice(pairs.PEOPLE), r.choice(pairs.USERS)
    lines, expect = [], []
    c = pairs.Clock(r)

    def add(action, inp, verdict):
        ts, rid = c.tick()
        lines.append(pairs.line(ts, action, inp, rid, scope=me))
        expect.append(verdict)

    a1, a2 = [("level", 1), ("server", "s1")], [("level", 2), ("server", "s1")]
    add("Login", [("server", "s1"), ("user", user)], "DENY")
    for _ in range(r.randint(1, 2)):
        add("Alert", a1, "ALLOW")
    add("Alert", a2, "DENY")  # the left fails at the decision point
    add("Alert", a1, "DENY")  # the level-2 Alert broke the run
    add("Login", [("server", "s1"), ("user", user)], "DENY")
    add("Alert", a1, "ALLOW")
    left = 'Ledger::Action::"Alert"::request{ input.level: 1 }'
    cond = f"{left}\n    since within {w_name}\n    {pairs.LOGIN_ANCHOR}"
    return cond, lines, expect


def f5_previous_immediate(r):
    """`previous` reads only the immediately preceding event [PREV]: after a Login, an Alert is
    ALLOW; after a Transfer that follows the Login, an Alert is DENY though the Login is earlier
    in the window."""
    w_name = r.choice(["30m", "1h", "2h"])
    me, user = r.choice(pairs.PEOPLE), r.choice(pairs.USERS)
    lines, expect = [], []
    c = pairs.Clock(r)

    def add(action, inp, verdict):
        ts, rid = c.tick()
        lines.append(pairs.line(ts, action, inp, rid, scope=me))
        expect.append(verdict)

    add("Login", [("server", "s1"), ("user", user)], "DENY")
    add(*ALERT_EV, "ALLOW")
    add(*pairs.transfer(r), "DENY")
    add(*ALERT_EV, "DENY")  # the previous event is the Transfer
    add("Login", [("server", "s1"), ("user", user)], "DENY")
    add(*ALERT_EV, "ALLOW")
    add(*ALERT_EV, "DENY")  # the previous event is the Alert just decided
    return f"previous within {w_name} {pairs.LOGIN_ANCHOR}", lines, expect


F5_TEMPLATES = {
    "feat:04:window-closed": f5_window_edge,
    "feat:04:since": f5_since_boundary,
    "feat:04:previous": f5_previous_immediate,
}


def alert_rule(cond):
    return (
        '@id("@RID@")\npermit (\n    principal,\n    action == Ledger::Action::"Alert",\n'
        f"    resource\n)\nwhen temporal {{\n    {cond}\n}};\n"
    )


def write_f5(r, idx, out, copies=6):
    """Write the F5 templates as feature bundles from index `idx`; return the next index.
    (`restrictions` imports this module, so its `fill` is imported here, at call time.)"""
    from restrictions import fill

    for fid, build in F5_TEMPLATES.items():
        for _ in range(copies):
            cond, lines, expect = build(r)
            d = os.path.join(out, f"fx{idx:03d}")
            os.makedirs(d, exist_ok=True)
            texts = {
                "policy.dw": fill(alert_rule(cond), r, idx),
                "schema.cedarschema": pairs.SCHEMA,
                "trace.log": "\n".join(lines) + "\n",
            }
            for name, text in texts.items():
                with open(os.path.join(d, name), "w") as f:
                    f.write(text)
            meta = {
                "family": "features",
                "kind": fid,
                "cmds": ["replay"],
                "replay_family": "R",
                "expect": {"trace.log": expect},
            }
            with open(os.path.join(d, "meta.json"), "w") as f:
                json.dump(meta, f, indent=1)
            idx += 1
    return idx


def write_combos(seed, out, b_start, k_start, per_kind=8, per_shape=6):
    """The new B-dedup and B-scope pairs from index `b_start` and the new K pairs from `k_start`,
    with their own random stream, so the existing pairs stay as they were."""
    r = random.Random(seed)
    idx = b_start
    for _kind, build in DEDUP_COMBOS:
        for _ in range(per_kind):
            build(r, idx, str(out))
            idx += 1
    idx = b_start
    for _kind, build in scope_combos():
        for _ in range(per_kind):
            build(r, idx, str(out))
            idx += 1
    idx = k_start
    for shape in KEY_COMBOS:
        for _ in range(per_shape):
            key_pair(r, idx, shape, str(out))
            idx += 1
