"""Bundles that each break one stated restriction the bundle generator never breaks, seeded.

The generator writes syntactically valid policies and in-contract traces, so most of the guide's
parse rejections, some validation rules, and the trace, event-schema and provider-declaration
errors would have no case. Each template here breaks one of them, in the Ledger schema of
`pairs.py`, and names the inventory id it kills (`checks/features.json`) and the commands whose
answers show it. Two instances of each are written, with different names and numbers.
"""

from __future__ import annotations

import json
import os
import random

import pairs

ALERT_SCOPE = 'principal,\n    action == Ledger::Action::"Alert",\n    resource'
TRANSFER_SCOPE = 'principal,\n    action == Ledger::Action::"Transfer",\n    resource'
LOGIN_ANCHOR = 'Ledger::Action::"Login"::request{ input.server: "s1" }'

PROVIDERS = {
    "availableProviders": {
        "Risk::Score": {
            "argumentTypes": [{"paramType": "integer"}],
            "outputType": {
                "paramType": "record",
                "fields": {"score": {"paramType": "integer"}},
                "required": ["score"],
            },
            "implementation": {
                "kind": "rhai",
                "script": (
                    "fn evaluate(amount) {\n"
                    '    if type_of(amount) == "()" {\n'
                    "        return #{ score: -1 };\n"
                    "    }\n"
                    "    #{ score: amount * @K@ }\n"
                    "}\n"
                ),
            },
        }
    }
}


def policy(cond, scope=TRANSFER_SCOPE, effect="permit", keyword="when", temporal=False):
    block = f"{keyword} temporal" if temporal else keyword
    return f'@id("@RID@")\n{effect} (\n    {scope}\n)\n{block} {{\n    {cond}\n}};\n'


def alert(cond):
    return policy(cond, scope=ALERT_SCOPE, temporal=True)


def providers(edit=None):
    decl = json.loads(json.dumps(PROVIDERS))
    if edit:
        edit(decl["availableProviders"]["Risk::Score"])
    return json.dumps(decl, indent=1) + "\n"


PARSE = ("check-parse", "validate")
VALIDATE = ("validate",)
REPLAY = ("replay",)

# id -> (commands, {file: text}); a text may hold @RID@, @N@, @W@, @WHO@, @K@, @EFF@.
TEMPLATES: dict[str, tuple[tuple[str, ...], dict[str, str]]] = {
    "restr:02:no-block-comments": (
        PARSE,
        {"policy.dw": "/* reviewed */\n" + policy("context.input.amount < @N@")},
    ),
    "restr:02:effect-permit-forbid": (
        PARSE,
        {"policy.dw": policy("context.input.amount < @N@", effect="@EFF@")},
    ),
    "restr:02:terminating-semicolon": (
        PARSE,
        {"policy.dw": policy("context.input.amount < @N@")[:-2] + "\n"},
    ),
    "restr:02:scope-duplicate-variable": (
        PARSE,
        {
            "policy.dw": policy(
                "context.input.amount < @N@",
                scope="principal,\n    principal,\n    resource",
            )
        },
    ),
    "restr:02:scope-extra-element": (
        PARSE,
        {
            "policy.dw": policy(
                "context.input.amount < @N@",
                scope="principal,\n    action,\n    resource,\n    context",
            )
        },
    ),
    "restr:02:scope-unknown-variable": (
        PARSE,
        {
            "policy.dw": policy(
                "context.input.amount < @N@",
                scope="subject,\n    action,\n    resource",
            )
        },
    ),
    "restr:02:scope-eq-entity-operand": (
        PARSE,
        {
            "policy.dw": policy(
                "context.input.amount < @N@",
                scope='principal == "@WHO@",\n    action,\n    resource',
            )
        },
    ),
    "restr:02:action-scope-reference": (
        PARSE,
        {
            "policy.dw": policy(
                "context.input.amount < @N@",
                scope="principal,\n    action == ?action,\n    resource",
            )
        },
    ),
    "restr:02:list-only-on-action": (
        PARSE,
        {
            "policy.dw": policy(
                "context.input.amount < @N@",
                scope='principal in [Ledger::User::"@WHO@"],\n    action,\n    resource',
            )
        },
    ),
    "restr:02:action-is-invalid": (
        PARSE,
        {
            "policy.dw": policy(
                "context.input.amount < @N@",
                scope="principal,\n    action is Ledger::Action,\n    resource",
            )
        },
    ),
    "restr:02:is-then-only-in": (
        PARSE,
        {
            "policy.dw": policy(
                "context.input.amount < @N@",
                scope='principal is Ledger::User == Ledger::User::"@WHO@",\n    action,\n    resource',
            )
        },
    ),
    "restr:02:scope-colon-form": (
        PARSE,
        {
            "policy.dw": policy(
                "context.input.amount < @N@",
                scope="principal : Ledger::User,\n    action,\n    resource",
            )
        },
    ),
    "restr:02:scope-single-equals": (
        PARSE,
        {
            "policy.dw": policy(
                "context.input.amount < @N@",
                scope='principal = Ledger::User::"@WHO@",\n    action,\n    resource',
            )
        },
    ),
    "restr:02:scope-other-operator": (
        PARSE,
        {
            "policy.dw": policy(
                "context.input.amount < @N@",
                scope='principal != Ledger::User::"@WHO@",\n    action,\n    resource',
            )
        },
    ),
    "restr:02:condition-keyword": (
        PARSE,
        {"policy.dw": policy("context.input.amount < @N@", keyword="if")},
    ),
    "restr:02:relational-chain": (
        PARSE,
        {"policy.dw": policy("1 < context.input.amount < @N@")},
    ),
    "restr:02:no-div-mod": (
        PARSE,
        {"policy.dw": policy("context.input.amount / 2 > @N@")},
    ),
    "restr:02:unary-no-mix": (
        PARSE,
        {"policy.dw": policy("!-context.input.amount == 0")},
    ),
    "restr:02:index-string-literal": (
        PARSE,
        {"policy.dw": policy('context.input[context.input.user] == "@WHO@"')},
    ),
    "restr:02:call-only-functions-methods": (
        PARSE,
        {"policy.dw": policy('(context.input.user)("x") == "@WHO@"')},
    ),
    "restr:02:has-rhs-forms": (
        PARSE,
        {"policy.dw": policy("context.input has user-name")},
    ),
    "restr:02:like-single-literal": (
        PARSE,
        {"policy.dw": policy("context.input.user like context.input.user")},
    ),
    "restr:02:extension-one-argument": (
        PARSE,
        {"policy.dw": policy('decimal("1.5", "2.5") == decimal("1.5")')},
    ),
    "restr:02:method-arity": (
        PARSE,
        {"policy.dw": policy('ip("10.0.0.@N@").isIpv4(1)')},
    ),
    "restr:02:unknown-method": (
        VALIDATE,
        {"policy.dw": policy('context.input.user.toUpper() == "@WHO@"')},
    ),
    "restr:02:bare-name-variable": (PARSE, {"policy.dw": policy("amount > @N@")}),
    "restr:02:record-keys": (PARSE, {"policy.dw": policy('{1: "a"} == {1: "a"}')}),
    "restr:02:integer-range": (
        PARSE,
        {"policy.dw": policy("context.input.amount < 9223372036854775808")},
    ),
    "restr:02:entity-initializer": (
        PARSE,
        {"policy.dw": policy('Ledger::User::{ id: "@WHO@" } == principal')},
    ),
    "restr:02:if-branches-same-type": (
        VALIDATE,
        {"policy.dw": policy('(if context.input.amount > @N@ then "big" else 1) == 1')},
    ),
    "restr:02:string-no-order": (
        VALIDATE,
        {"policy.dw": policy('context.input.user < "@WHO@"')},
    ),
    "restr:02:decimal-no-order": (
        VALIDATE,
        {"policy.dw": policy('decimal("1.5") < decimal("2.@K@")')},
    ),
    "restr:02:action-schema-must-parse": (
        ("validate", "schema-action"),
        {
            "policy.dw": policy("context.input.amount < @N@"),
            "schema.cedarschema": pairs.SCHEMA.replace(
                "  };\n  entity Gateway;", "  \n  entity Gateway;", 1
            ),
        },
    ),
    "restr:03:predicate-identifier-paths": (
        PARSE,
        {
            "policy.dw": alert(
                'formerly within @W@ Ledger::Action::"Login"::request{ "input.user": _ }'
            )
        },
    ),
    "restr:04:kind-suffix": (
        PARSE,
        {
            "policy.dw": alert(
                'formerly within @W@ Ledger::Action::"Login"{ input.server: "s1" }'
            )
        },
    ),
    "restr:04:integer-term-range": (
        PARSE,
        {
            "policy.dw": alert(
                f"(count for (t: Timepoint). where formerly within @W@ ({LOGIN_ANCHOR} && tp(t))) > 99999999999999999999"
            )
        },
    ),
    "restr:04:within-mandatory": (
        PARSE,
        {"policy.dw": alert(f"formerly {LOGIN_ANCHOR}")},
    ),
    "restr:04:units-integer-amount": (
        PARSE,
        {"policy.dw": alert(f"formerly within 2w {LOGIN_ANCHOR}")},
    ),
    "restr:04:window-param-macro-only": (
        PARSE,
        {"policy.dw": alert(f"formerly within ?w {LOGIN_ANCHOR}")},
    ),
    "restr:04:no-disjunction": (
        PARSE,
        {
            "policy.dw": alert(
                f'formerly within @W@ {LOGIN_ANCHOR} || formerly within @W@ Ledger::Action::"Transfer"::request{{ input.amount: * }}'
            )
        },
    ),
    "restr:04:binder-type-mandatory": (
        PARSE,
        {
            "policy.dw": alert(
                'exists (u). formerly within @W@ Ledger::Action::"Login"::request{ input.user: u }'
            )
        },
    ),
    "restr:04:extension-types": (
        VALIDATE,
        {
            "policy.dw": alert(
                'exists (d: duration). formerly within @W@ Ledger::Action::"Login"::request{ input.user: d }'
            )
        },
    ),
    "restr:04:binding-field-type": (
        VALIDATE,
        {
            "policy.dw": alert(
                'exists (u: Long). formerly within @W@ Ledger::Action::"Login"::request{ input.user: u }'
            )
        },
    ),
    "restr:04:no-min-max-avg": (
        PARSE,
        {
            "policy.dw": alert(
                '(max a for (a: Long). where formerly within @W@ Ledger::Action::"Transfer"::request{ input.amount: a }) > @N@'
            )
        },
    ),
    "restr:04:for-binder-typed": (
        PARSE,
        {
            "policy.dw": alert(
                '(count for (a). where formerly within @W@ Ledger::Action::"Transfer"::request{ input.amount: a }) > 1'
            )
        },
    ),
    "restr:04:arithmetic-operand-only": (
        PARSE,
        {
            "policy.dw": alert(
                'formerly within @W@ Ledger::Action::"Transfer"::request{ input.amount: (1 + @N@) }'
            )
        },
    ),
    "restr:04:aggregation-body-vars": (
        PARSE,
        {
            "policy.dw": alert(
                '(count for (t: Timepoint). where formerly within @W@ (Ledger::Action::"Login"::request{ input.user: u } && tp(t))) > 1'
            )
        },
    ),
    "restr:04:for-var-occurs": (
        PARSE,
        {
            "policy.dw": alert(
                f"(count for (t: Timepoint), (u: String). where formerly within @W@ ({LOGIN_ANCHOR} && tp(t))) > 1"
            )
        },
    ),
    "restr:06:top-level-only": (
        PARSE,
        {
            "policy.dw": policy(
                "def cedar small(?n) { ?n < 100 };\n    context.input.amount < @N@"
            )
        },
    ),
    "restr:06:sigil-no-space": (
        PARSE,
        {
            "policy.dw": "def cedar small(? n) { ? n < @N@ };\n\n"
            + policy("small(context.input.amount)")
        },
    ),
    "restr:08:template-slot-not-static": (
        ("validate", "lower"),
        {
            "policy.dw": policy(
                "context.input.amount < @N@",
                scope="principal == ?principal,\n    action,\n    resource",
            )
        },
    ),
    "restr:03:window-cap-not-over-horizon": (
        ("validate", "schema-event"),
        {
            "policy.dw": alert(f"formerly within @W@ {LOGIN_ANCHOR}"),
            "event.dwschema": "max_window = 2h\nmax_horizon = 1h\n\n"
            + pairs.UNIVERSAL_EVENTS,
        },
    ),
    "restr:03:horizon-over-cap": (
        VALIDATE,
        {
            "policy.dw": alert(
                f"formerly within 1h (formerly within 1h {LOGIN_ANCHOR})"
            ),
            "event.dwschema": "max_horizon = 1h\n\n" + pairs.UNIVERSAL_EVENTS,
        },
    ),
    "restr:05:provider-name-qualified": (
        VALIDATE,
        {
            "policy.dw": policy("Score(context.input.amount).score > @N@"),
            "providers.json": providers(),
        },
    ),
    "restr:05:argument-forms": (
        ("validate", "lower"),
        {
            "policy.dw": policy("Risk::Score(context.input.amount + 1).score > @N@"),
            "providers.json": providers(),
        },
    ),
    "restr:10:path-argument-type": (
        VALIDATE,
        {
            "policy.dw": policy("Risk::Score(context.input.user).score > @N@"),
            "providers.json": providers(),
        },
    ),
    "restr:10:output-type-required": (
        ("validate", "schema-providers"),
        {
            "policy.dw": policy("Risk::Score(context.input.amount).score > @N@"),
            "providers.json": providers(lambda d: d.pop("outputType")),
        },
    ),
    "restr:10:implementation-rhai": (
        ("validate", "schema-providers"),
        {
            "policy.dw": policy("Risk::Score(context.input.amount).score > @N@"),
            "providers.json": providers(
                lambda d: d["implementation"].update({"kind": "wasm"})
            ),
        },
    ),
}

# Trace templates: the policy decides an Alert from this principal's Login, and one line of the
# trace breaks a rule of the trace format or of the event schema.
TRACE_TEMPLATES = {
    "restr:03:pinned-field-logged": "drop_caller",
    "restr:12:decision-needs-scope": "no_scope_request",
    "restr:12:strict-trace-parsing": "duplicate_key",
    "restr:08:undeclared-event-rejected": "undeclared_kind",
    "restr:08:entity-conformance": "bad_entity",
}
SANDBOX = "restr:10:sandbox"


def fill(text: str, r: random.Random, idx: int) -> str:
    return (
        text.replace("@RID@", f"rule_{idx}")
        .replace("@N@", str(r.randint(5, 400)))
        .replace("@K@", str(r.randint(2, 9)))
        .replace("@W@", r.choice(["30m", "1h", "2h"]))
        .replace("@WHO@", r.choice(pairs.PEOPLE))
        .replace("@EFF@", r.choice(["allow", "grant", "deny"]))
    )


def trace_line(r, kind, me, ts, rid):
    login = ("Login", [("server", "s1"), ("user", r.choice(pairs.USERS))])
    line = pairs.line(ts, login[0], login[1], rid, scope=me)
    if kind == "drop_caller":
        return line.replace(f'callerPrincipal: Ledger::User::"{me}", ', "")
    if kind == "no_scope_request":
        return pairs.line(ts, login[0], login[1], rid, scope=None, caller=me)
    if kind == "duplicate_key":
        return line.replace("request(input: ", 'request(requestId: "dup", input: ', 1)
    if kind == "undeclared_kind":
        return line.replace("::request(", "::audit(", 1)
    if kind == "bad_entity":
        return line.replace(
            "request_context(",
            f'entities(Ledger::User::"{me}": {{ id: {r.randint(1, 99)} }}) request_context(',
            1,
        )
    raise ValueError(kind)


def write_trace_bundle(r, idx, rid, kind, out):
    me = r.choice(pairs.PEOPLE)
    c = pairs.Clock(r)
    lines = []
    pairs.noise(r, c, lines, r.choice([p for p in pairs.PEOPLE if p != me]))
    ts, req = c.tick()
    lines.append(trace_line(r, kind, me, ts, req))
    ts, req = c.tick()
    lines.append(pairs.line(ts, pairs.ALERT[0], pairs.ALERT[1], req, scope=me))
    pol = alert(f"formerly within 1h {LOGIN_ANCHOR}").replace("@RID@", f"rule_{idx}")
    name = f"rx{idx:03d}"
    pairs.write(
        out,
        name,
        pol,
        lines,
        {"family": "restrictions", "kind": rid, "cmds": list(REPLAY)},
    )
    return name


def write_sandbox_bundle(r, idx, out):
    script = providers(
        lambda d: d["implementation"].update(
            {
                "script": d["implementation"]["script"].replace(
                    "    #{ score:", "    let now = timestamp();\n    #{ score:"
                )
            }
        )
    )
    me = r.choice(pairs.PEOPLE)
    c = pairs.Clock(r)
    lines = []
    for _ in range(r.randint(1, 3)):
        ev = pairs.transfer(r)
        ts, req = c.tick()
        lines.append(pairs.line(ts, ev[0], ev[1], req, scope=me))
    pol = fill(policy("Risk::Score(context.input.amount).score > @N@"), r, idx)
    name = f"rx{idx:03d}"
    pairs.write(
        out,
        name,
        pol,
        lines,
        {"family": "restrictions", "kind": SANDBOX, "cmds": list(REPLAY)},
        {"providers.json": fill(script, r, idx)},
    )
    return name


def write_restrictions(seed: int, out, copies: int = 2) -> int:
    r = random.Random(seed)
    idx = 0
    for rid, (cmds, files) in TEMPLATES.items():
        for _ in range(copies):
            d = os.path.join(out, f"rx{idx:03d}")
            os.makedirs(d, exist_ok=True)
            texts = {name: fill(text, r, idx) for name, text in files.items()}
            texts.setdefault("schema.cedarschema", pairs.SCHEMA)
            for name, text in texts.items():
                with open(os.path.join(d, name), "w") as f:
                    f.write(text)
            with open(os.path.join(d, "meta.json"), "w") as f:
                json.dump(
                    {"family": "restrictions", "kind": rid, "cmds": list(cmds)},
                    f,
                    indent=1,
                )
            idx += 1
    for rid, kind in TRACE_TEMPLATES.items():
        for _ in range(copies):
            write_trace_bundle(r, idx, rid, kind, str(out))
            idx += 1
    for _ in range(copies):
        write_sandbox_bundle(r, idx, str(out))
        idx += 1
    return idx


# Bundles that use, correctly, a documented feature the generator never writes. Each names the
# inventory id it exercises and the commands that show it; replays run on a short mixed trace.
LOGIN_REQ = 'Ledger::Action::"Login"::request{ input.user: _, input.server: context.input.server }'
TRANSFER_REQ = 'Ledger::Action::"Transfer"::request{ input.amount: a }'
REGEX_PROVIDER = {
    "availableProviders": {
        "Text::Flag": {
            "argumentTypes": [{"paramType": "string"}],
            "outputType": {
                "paramType": "record",
                "fields": {"hit": {"paramType": "bool"}, "n": {"paramType": "integer"}},
                "required": ["hit", "n"],
            },
            "implementation": {
                "kind": "rhai",
                "script": (
                    "fn evaluate(text) {\n"
                    '    if type_of(text) == "()" {\n'
                    "        return #{ hit: false, n: 0 };\n"
                    "    }\n"
                    '    #{ hit: regex_is_match("^u[0-@K@]$", text), n: regex_count("[0-9]", text) }\n'
                    "}\n"
                ),
            },
        }
    }
}
FEATURES: dict[str, tuple[tuple[str, ...], dict[str, str]]] = {
    "feat:02:arithmetic": (
        ("validate", "replay", "lower", "explain"),
        {
            "policy.dw": policy(
                "context.input.amount + @N@ > 100 && context.input.amount * 2 < 1000"
            )
        },
    ),
    "feat:02:has-reserved-words": (
        ("check-parse", "lower", "explain"),
        {"policy.dw": policy("context has output || context.input has if")},
    ),
    "feat:02:in-expression": (
        ("validate", "replay", "lower"),
        {
            "policy.dw": policy(
                'principal in Ledger::User::"@WHO@" && context.input.amount > @N@'
            )
        },
    ),
    "feat:02:line-comments": (
        ("check-parse", "format", "explain", "replay"),
        {
            "policy.dw": "// Transfers under the limit, from anyone.\n"
            + policy(
                'context.input.amount < @N@ // the limit\n    && context.input.user != "u9"'
            )
            + "\n// end of file\n"
        },
    ),
    "feat:02:scope-order-omission": (
        ("validate", "replay", "lower"),
        {
            "policy.dw": '@id("@RID@")\npermit (resource, principal)\nwhen { context.input.amount > @N@ };\n'
        },
    ),
    "feat:02:template-slots": (
        ("check-parse", "format"),
        {
            "policy.dw": policy(
                "context.input.amount < @N@",
                scope="principal == ?principal,\n    action,\n    resource == ?resource",
            )
        },
    ),
    "feat:02:unary-runs": (
        ("validate", "replay", "lower"),
        {
            "policy.dw": policy(
                "!!(context.input.amount > @N@) && --context.input.amount > 0"
            )
        },
    ),
    "feat:03:comments-trailing-comma": (
        ("validate", "replay", "schema-event"),
        {
            "policy.dw": alert(f"formerly within @W@ {LOGIN_REQ}"),
            "event.dwschema": "// Our two kinds; trailing commas are fine.\nmax_horizon = 6h\n\n"
            + pairs.UNIVERSAL_EVENTS.replace(
                "requestId: String,\n}", "requestId: String, // last\n}"
            ),
        },
    ),
    "feat:04:aggregate-comparisons": (
        ("validate", "replay"),
        {
            "policy.dw": alert(
                f"(count for (t: Timepoint). where formerly within @W@ ({LOGIN_REQ} && tp(t))) >= "
                '(count for (t: Timepoint). where formerly within @W@ (Ledger::Action::"Transfer"::request{ input.amount: * } && tp(t)))'
            )
        },
    ),
    "feat:04:compound-never-binds": (
        ("validate", "replay"),
        {
            "policy.dw": alert(
                f"exists (a: Long). formerly within @W@ {TRANSFER_REQ} && a + 1 == 11"
            )
        },
    ),
    "feat:04:entity-equality-other": (
        ("validate", "replay", "explain"),
        {"policy.dw": policy("principal != resource && context.input.amount > @N@")},
    ),
    "feat:04:macro-call-args": (
        ("validate", "replay", "explain"),
        {
            "policy.dw": "def temporal recent(?w, ?s) { formerly within ?w ?s };\n\n"
            + alert(f"recent(@W@, {LOGIN_REQ})")
        },
    ),
    "feat:09:value-macro-as-argument": (
        ("validate", "replay"),
        {
            "policy.dw": "def temporal bind(?n, ?A, ?B) { exists (?n: Long). (?A == ?n && ?B) };\n\n"
            + alert(f"bind(n, count_within(@W@, {LOGIN_REQ}), n > 1)")
        },
    ),
    "feat:05:projection": (
        ("validate", "replay", "lower"),
        {
            "policy.dw": policy('Risk::Score(context.input.amount)["score"] > @N@'),
            "providers.json": providers(),
        },
    ),
    "feat:06:callable-positions": (
        ("validate", "replay"),
        {
            "policy.dw": "def cedar small(?n) { ?n < @N@ };\n\n"
            + policy(
                f"small(context.input.level) && temporal {{ formerly within @W@ {LOGIN_REQ} }}",
                scope=ALERT_SCOPE,
            )
        },
    ),
    "feat:08:balanced-fold": (
        ("lower", "explain", "replay"),
        {
            "policy.dw": '@id("@RID@")\npermit (\n    '
            + TRANSFER_SCOPE
            + "\n)\nwhen { context.input.amount > 1 }\nwhen { context.input.amount < @N@ }\n"
            + 'unless { context.input.user == "u9" }\nwhen { context.input.amount != 7 };\n'
        },
    ),
    "feat:10:host-functions": (
        ("validate", "replay"),
        {
            "policy.dw": policy("Text::Flag(context.input.user).hit"),
            "providers.json": json.dumps(REGEX_PROVIDER, indent=1) + "\n",
        },
    ),
}


SCRIPT_FILE = "feat:10:scriptfile-unresolved"


def write_script_file_bundle(r, idx, out):
    """A provider whose script is a `scriptFile`: the command line never resolves it, so
    `validate` and `lower` work and `replay` cannot evaluate the provider."""
    decl = json.loads(providers())
    impl = decl["availableProviders"]["Risk::Score"]["implementation"]
    script = impl.pop("script")
    impl["scriptFile"] = "score.rhai"
    d = os.path.join(out, f"fx{idx:03d}")
    os.makedirs(d, exist_ok=True)
    files = {
        "policy.dw": fill(
            policy("Risk::Score(context.input.amount).score > @N@"), r, idx
        ),
        "schema.cedarschema": pairs.SCHEMA,
        "providers.json": json.dumps(decl, indent=1) + "\n",
        "score.rhai": fill(script, r, idx),
        "trace.log": "\n".join(mixed_trace(r)) + "\n",
    }
    for name, text in files.items():
        with open(os.path.join(d, name), "w") as f:
            f.write(text)
    meta = {
        "family": "features",
        "kind": SCRIPT_FILE,
        "cmds": ["validate", "lower", "replay"],
        "keep_script_file": True,
    }
    with open(os.path.join(d, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)


def mixed_trace(r):
    """A short trace: Logins, Transfers and Alerts by two principals, increasing timestamps."""
    c = pairs.Clock(r)
    who = r.sample(pairs.PEOPLE, 2)
    lines = []
    for _ in range(r.randint(4, 7)):
        ev = r.choice(
            [pairs.login(r), pairs.transfer(r), pairs.transfer(r), pairs.ALERT]
        )
        ts, rid = c.tick()
        lines.append(pairs.line(ts, ev[0], ev[1], rid, scope=r.choice(who)))
    return lines


def write_features(seed: int, out, copies: int = 2) -> int:
    r = random.Random(seed)
    idx = 0
    for fid, (cmds, files) in FEATURES.items():
        for _ in range(copies):
            d = os.path.join(out, f"fx{idx:03d}")
            os.makedirs(d, exist_ok=True)
            texts = {name: fill(text, r, idx) for name, text in files.items()}
            texts.setdefault("schema.cedarschema", pairs.SCHEMA)
            if "replay" in cmds:
                texts["trace.log"] = "\n".join(mixed_trace(r)) + "\n"
            for name, text in texts.items():
                with open(os.path.join(d, name), "w") as f:
                    f.write(text)
            with open(os.path.join(d, "meta.json"), "w") as f:
                json.dump(
                    {"family": "features", "kind": fid, "cmds": list(cmds)}, f, indent=1
                )
            idx += 1
    for _ in range(copies):
        write_script_file_bundle(r, idx, out)
        idx += 1
    return idx
