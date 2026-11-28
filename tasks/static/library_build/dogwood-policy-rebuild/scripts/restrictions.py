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

import combos
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


def events(request_extra: str = "", replace_inputs: str | None = None) -> str:
    """The universal event schema, with an extra field line in the request declaration (and its
    spread of the inputs replaced, when given); every copy gets its own note field."""
    text = pairs.UNIVERSAL_EVENTS.replace(
        "    requestId: String,\n}",
        "    requestId: String,\n    note@N@: String,\n}",
        1,
    )
    if replace_inputs is not None:
        text = text.replace("    ...inputs(A),\n", request_extra, 1)
    elif request_extra:
        text = text.replace(
            "    pin callerPrincipal", request_extra + "    pin callerPrincipal", 1
        )
    return text


def enum_providers(
    edit=None, namespace: str = "Risk", declare: bool = True, returns: str = "HIGH"
) -> str:
    """Risk::Score with an enum-typed `level` output; the enum declared in `namespace`, or not at
    all, and the output's enum type changed by `edit`. For a present argument the implementation
    returns the level `returns`, which need not be one of the declared values."""
    decl = json.loads(json.dumps(PROVIDERS))
    score = decl["availableProviders"]["Risk::Score"]
    level = {"paramType": "entity", "entityType": f"{namespace}::Level"}
    if edit:
        edit(level)
    score["outputType"]["fields"]["level"] = level
    score["outputType"]["required"] = ["score", "level"]
    score["implementation"]["script"] = (
        score["implementation"]["script"]
        .replace("#{ score: -1 }", '#{ score: -1, level: "LOW" }')
        .replace(
            "#{ score: amount * @K@ }",
            f'#{{ score: amount * @K@, level: "{returns}" }}',
        )
    )
    if declare:
        decl = {
            "entityTypes": {f"{namespace}::Level": {"enum": ["LOW", "HIGH"]}},
            **decl,
        }
    return json.dumps(decl, indent=1) + "\n"


def method_providers() -> str:
    """Risk::Score with a declared output method `boost`."""
    decl = json.loads(json.dumps(PROVIDERS))
    score = decl["availableProviders"]["Risk::Score"]
    score["availableMethods"] = {
        "boost": {"argumentTypes": [], "outputType": {"paramType": "integer"}}
    }
    score["implementation"]["script"] += (
        "\nfn boost(output) {\n    output.score * 2\n}\n"
    )
    return json.dumps(decl, indent=1) + "\n"


PARSE = ("check-parse", "validate")
VALIDATE = ("validate",)
REPLAY = ("replay",)
EVENT_CMDS = ("schema-event", "validate")

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
    # One side only: with a String (or decimal) on both sides Cedar reports two errors, in an
    # order that changes from run to run.
    "restr:02:string-no-order": (
        VALIDATE,
        {"policy.dw": policy("context.input.user < @N@")},
    ),
    "restr:02:decimal-no-order": (
        VALIDATE,
        {"policy.dw": policy('decimal("1.@K@") < @N@')},
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
                'exists (u: Ledger::User). formerly within @W@ Ledger::Action::"Login"::request{ callerResource: u }'
            ),
            "event.dwschema": pairs.UNIVERSAL_EVENTS,
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
    # Event-schema declarations (chapter 03). The note field and binder names vary per copy.
    "restr:03:binder-must-match": (
        EVENT_CMDS,
        {
            "policy.dw": alert(f"formerly within @W@ {LOGIN_ANCHOR}"),
            "event.dwschema": events("    ...inputs(B@N@),\n", "    ...inputs(A),\n"),
        },
    ),
    "restr:03:brackets-body-mandatory": (
        EVENT_CMDS,
        {
            "policy.dw": alert(f"formerly within @W@ {LOGIN_ANCHOR}"),
            "event.dwschema": events().replace(
                "decision event <A>::request {", "decision event A::request {"
            ),
        },
    ),
    "restr:03:directives-first-once": (
        EVENT_CMDS,
        {
            "policy.dw": alert(f"formerly within @W@ {LOGIN_ANCHOR}"),
            "event.dwschema": events() + "\nmax_window = @W@\n",
        },
    ),
    "restr:03:pin-leaf-only": (
        EVENT_CMDS,
        {
            "policy.dw": alert(f"formerly within @W@ {LOGIN_ANCHOR}"),
            "event.dwschema": events(
                "    pin origin@N@: { server: String } = context.input.server,\n"
            ),
        },
    ),
    "restr:03:pin-needs-value": (
        EVENT_CMDS,
        {
            "policy.dw": alert(f"formerly within @W@ {LOGIN_ANCHOR}"),
            "event.dwschema": events("    pin origin@N@: String,\n"),
        },
    ),
    "restr:03:selector-not-type": (
        ("validate", "lower"),
        {
            "policy.dw": alert(f"formerly within @W@ {LOGIN_ANCHOR}"),
            "event.dwschema": events("    payload@N@: inputs(A),\n"),
        },
    ),
    # Temporal well-formedness (chapter 04).
    "restr:04:aggregate-placement": (
        PARSE,
        {
            "policy.dw": alert(
                'formerly within @W@ Ledger::Action::"Transfer"::request{ input.amount: '
                f"(count for (t: Timepoint). where (formerly within 1h ({LOGIN_ANCHOR} && tp(t)))) }}"
            )
        },
    ),
    "restr:04:binding-equality-correlated": (
        PARSE,
        {
            "policy.dw": alert(
                "exists (u: String). exists (n: Long). (\n"
                '        (count for (t: Timepoint). where (formerly within @W@ (Ledger::Action::"Login"::request{ input.user: u } && tp(t))))\n'
                '        == n && n >= @K@ && formerly within @W@ Ledger::Action::"Login"::request{ input.user: u }\n'
                "    )"
            )
        },
    ),
    "restr:04:closed": (
        PARSE,
        {
            "policy.dw": alert(
                'formerly within @W@ Ledger::Action::"Login"::request{ input.user: u, input.server: "s1" }'
            )
        },
    ),
    "restr:04:for-var-restricted": (
        PARSE,
        {
            "policy.dw": alert(
                '(count for (x: String). where (!(formerly within @W@ Ledger::Action::"Login"::request{ input.user: x }))) == @K@'
            )
        },
    ),
    "restr:04:since-left-consumes": (
        PARSE,
        {
            "policy.dw": alert(
                "exists (u: String). (\n"
                f'        (Ledger::Action::"Transfer"::request{{ input.user: u }} since within @W@ {LOGIN_ANCHOR})\n'
                '        && formerly within 1h Ledger::Action::"Transfer"::request{ input.user: u }\n'
                "    )"
            )
        },
    ),
    "restr:04:summed-var-in-for": (
        PARSE,
        {
            "policy.dw": alert(
                "exists (a: Long). (\n"
                '        formerly within @W@ Ledger::Action::"Transfer"::request{ input.amount: a }\n'
                "        && exists (total: Long). (\n"
                f"            (sum a for (t: Timepoint). where (formerly within @W@ ({LOGIN_ANCHOR} && tp(t)))) == total\n"
                "            && total > @N@\n"
                "        )\n"
                "    )"
            )
        },
    ),
    "restr:08:summand-long": (
        VALIDATE,
        {
            "policy.dw": alert(
                "exists (total: Long). (\n"
                '        (sum u for (u: String). where (formerly within @W@ Ledger::Action::"Login"::request{ input.user: u, input.server: "s1" })) == total\n'
                "        && total > @K@\n"
                "    )"
            )
        },
    ),
    # Macros (chapter 06): each breaks one rule of definitions or calls.
    "restr:06:argument-shape": (
        PARSE,
        {
            "policy.dw": "def temporal once(?w, ?s) { formerly within ?w ?s };\n\n"
            + alert("once(@W@, context.input.level)")
        },
    ),
    "restr:06:condition-as-value": (
        PARSE,
        {
            "policy.dw": 'def temporal seen(?u) { formerly within 1h Ledger::Action::"Login"::request{ input.user: ?u } };\n\n'
            + alert('seen("u@K@") == @K@')
        },
    ),
    "restr:06:dollar-not-condition": (
        PARSE,
        {
            "policy.dw": "def temporal wrap(?w) { formerly within ?w $s };\n\n"
            + alert("wrap(@W@)")
        },
    ),
    "restr:06:duplicate-definitions": (
        PARSE,
        {
            "policy.dw": "def cedar small(?n) { ?n < @N@ };\ndef cedar small(?n) { ?n < 10 };\n\n"
            + policy("small(context.input.amount)")
        },
    ),
    "restr:06:no-temporal-in-cedar-macro": (
        PARSE,
        {
            "policy.dw": "def cedar recent(?s) { temporal { formerly within @W@ "
            'Ledger::Action::"Login"::request{ input.server: ?s } } };\n\n'
            + policy('recent("s1")', scope=ALERT_SCOPE)
        },
    ),
    "restr:06:plain-identifier": (
        PARSE,
        {
            "policy.dw": "def temporal seen(?w) { exists (u: String). formerly within ?w "
            'Ledger::Action::"Login"::request{ input.user: u } };\n\n'
            + alert("seen(@W@)")
        },
    ),
    "restr:06:stray-sigils": (
        PARSE,
        {"policy.dw": policy("context.input.amount < ?limit@K@")},
    ),
    "restr:06:temporal-in-cedar": (
        PARSE,
        {
            "policy.dw": "def temporal seen(?s) { formerly within @W@ "
            'Ledger::Action::"Login"::request{ input.server: ?s } };\n\n'
            + policy('seen("s@K@")', scope=ALERT_SCOPE)
        },
    ),
    "restr:06:undeclared-parameter": (
        PARSE,
        {
            "policy.dw": "def cedar small(?n) { ?x@K@ < @N@ };\n\n"
            + policy("small(context.input.amount)")
        },
    ),
    "restr:06:unknown-macro": (
        PARSE,
        {"policy.dw": alert("recently_seen@K@(@W@)")},
    ),
    "restr:06:value-as-condition": (
        PARSE,
        {
            "policy.dw": "def temporal logins(?w) { count for ($t: Timepoint). where (formerly within ?w "
            f"({LOGIN_ANCHOR} && tp($t))) }};\n\n" + alert("logins(@W@)")
        },
    ),
    "restr:03:field-names-unique": (
        ("validate", "lower"),
        {
            "policy.dw": alert(f"formerly within @W@ {LOGIN_ANCHOR}"),
            "event.dwschema": events("    requestId: String,\n"),
        },
    ),
    "restr:03:selector-misuse-spread": (
        ("validate", "lower"),
        {
            "policy.dw": alert(f"formerly within @W@ {LOGIN_ANCHOR}"),
            "event.dwschema": events("    ...principalType(A),\n"),
        },
    ),
    "restr:03:spread-group-unique": (
        ("validate", "lower"),
        {
            "policy.dw": alert(f"formerly within @W@ {LOGIN_ANCHOR}"),
            "event.dwschema": events("    input: String,\n"),
        },
    ),
    "restr:03:value-needs-pin": (
        EVENT_CMDS,
        {
            "policy.dw": alert(f"formerly within @W@ {LOGIN_ANCHOR}"),
            "event.dwschema": events("    origin@N@: String = context.input.server,\n"),
        },
    ),
    "restr:04:arithmetic-atoms-long": (
        VALIDATE,
        {
            "policy.dw": alert(
                "exists (n: Long). (\n"
                f"        (count for (t: Timepoint). where (formerly within @W@ ({LOGIN_ANCHOR} && tp(t)))) == n\n"
                "        && n + context.input.server > @K@\n"
                "    )"
            )
        },
    ),
    "restr:04:producer-before-consumer": (
        PARSE,
        {
            "policy.dw": alert(
                "exists (a: Long). (\n"
                "        a > @N@\n"
                '        && formerly within @W@ Ledger::Action::"Transfer"::request{ input.amount: a }\n'
                "    )"
            )
        },
    ),
    "restr:04:tp-dependence": (
        VALIDATE,
        {
            "policy.dw": alert(
                f"formerly within @W@ {LOGIN_ANCHOR}\n    && context.input.level > @K@"
            )
        },
    ),
    "restr:06:reserved-names": (
        PARSE,
        {
            "policy.dw": "def cedar count(?n) { ?n < @N@ };\n\n"
            + policy("count(context.input.amount)")
        },
    ),
    # Providers (chapters 05, 08 and 10).
    "restr:05:enum-typo-caught": (
        VALIDATE,
        {
            "policy.dw": policy(
                'Risk::Score(context.input.amount).level == Risk::Level::"HIHG"'
            ),
            "providers.json": enum_providers(),
        },
    ),
    "restr:08:projection-before-method": (
        ("validate", "lower"),
        {
            "policy.dw": policy(
                "Risk::Score(context.input.amount).score.boost() > @N@"
            ),
            "providers.json": method_providers(),
        },
    ),
    "restr:08:undeclared-provider-no-implementation": (
        REPLAY,
        {
            "policy.dw": policy("Risk::Other(context.input.amount).score > @N@"),
            "providers.json": providers(),
        },
    ),
    "restr:10:entity-needs-entity-type": (
        ("validate", "schema-providers"),
        {
            "policy.dw": policy("Risk::Score(context.input.amount).score > @N@"),
            "providers.json": enum_providers(lambda level: level.pop("entityType")),
        },
    ),
    "restr:10:enum-namespace": (
        ("validate", "schema-providers"),
        {
            "policy.dw": policy("Risk::Score(context.input.amount).score > @N@"),
            "providers.json": enum_providers(namespace="Other"),
        },
    ),
    "restr:10:output-enum-declared": (
        ("validate", "schema-providers"),
        {
            "policy.dw": policy("Risk::Score(context.input.amount).score > @N@"),
            "providers.json": enum_providers(declare=False),
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
            if "replay" in cmds:
                texts["trace.log"] = "\n".join(mixed_trace(r)) + "\n"
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
        ("check-parse", "lower", "explain", "replay"),
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
            # Every action is in scope, so the condition reads nothing only some actions' inputs
            # have (the validator lists such errors per action, in hash order).
            "policy.dw": '@id("@RID@")\npermit (resource, principal)\nwhen { principal == Ledger::User::"@WHO@" };\n'
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
    "feat:04:arithmetic-saturates": (
        ("validate", "replay", "lower", "explain"),
        {
            "policy.dw": alert(
                "exists (n: Long). (\n"
                f"        (count for (t: Timepoint). where (formerly within @W@ ({LOGIN_REQ} && tp(t)))) == n\n"
                "        && n * 9223372036854775807 + @N@ > 9223372036854775000\n"
                "    )"
            )
        },
    ),
    "feat:08:type-scope": (
        ("validate", "replay", "explain"),
        {
            "policy.dw": alert(
                "exists (x: Long). (\n"
                '        formerly within @W@ Ledger::Action::"Transfer"::request{ input.amount: x }\n'
                "        && x > @N@\n"
                '        && exists (x: String). formerly within @W@ Ledger::Action::"Login"::request{ input.user: x }\n'
                "    )"
            )
        },
    ),
    "feat:05:call-by-shape": (
        ("check-parse", "lower", "validate"),
        {
            "policy.dw": policy("Risk::Other@K@(context.input.amount).score > @N@"),
            "providers.json": providers(),
        },
    ),
    "feat:06:policy-def-wins": (
        ("check-parse", "replay", "lower"),
        {
            "macros.dw": "def cedar small(?n) { ?n < 10 };\n",
            "policy.dw": "def cedar small(?n) { ?n < @N@ };\n\n"
            + policy("small(context.input.amount)"),
        },
    ),
    "feat:03:key-local-since-left": (
        ("replay",),
        {
            "policy.dw": policy(
                'Ledger::Action::"Transfer"::request{ input.amount: * }\n'
                "    since within @W@\n"
                '    Ledger::Action::"Login"::request{ input.server: "s1" }',
                scope="principal,\n    action,\n    resource",
                temporal=True,
            )
        },
    ),
    "feat:04:since": (
        ("replay",),
        {
            "policy.dw": policy(
                'Ledger::Action::"Transfer"::request{ input.amount: * }\n'
                "    since within @W@\n"
                '    Ledger::Action::"Login"::request{ input.server: "s1" }',
                scope="principal,\n    action,\n    resource",
                temporal=True,
            ),
            # No pin: the global reading, which the default schema's key-local rewrite bypasses.
            "event.dwschema": pairs.event_schema({}),
        },
    ),
    "feat:05:enum-unexpected-denied": (
        ("replay", "validate"),
        {
            "policy.dw": policy(
                'Risk::Score(context.input.amount).level != Risk::Level::"LOW"'
            ),
            "providers.json": enum_providers(returns="MEDIUM"),
        },
    ),
    "feat:12:format-comments": (
        ("format", "check-parse"),
        {
            "policy.dw": "// Small transfers only.\n"
            '@id("@RID@")\npermit (principal,   action == Ledger::Action::"Transfer",   // transfers\n'
            "      resource)\nwhen {   context.input.amount < @N@ };\n"
        },
    ),
    "feat:03:key-local-previous": (
        ("replay",),
        {"policy.dw": alert(f"previous within @W@ {LOGIN_ANCHOR}")},
    ),
    "feat:04:window-closed": (
        ("replay",),
        {"policy.dw": alert(f"formerly within 30m {LOGIN_ANCHOR}")},
    ),
    "restr:08:optional-attribute-guard": (
        ("validate", "lower", "explain"),
        {
            "policy.dw": policy(
                "context.input has note && temporal {\n"
                '        formerly within @W@ Ledger::Action::"Login"::request{ input.user: context.input.note }\n'
                "    }"
            ),
            "schema.cedarschema": pairs.SCHEMA.replace(
                "    amount: Long,\n    user: String",
                "    amount: Long,\n    note?: String,\n    user: String",
                1,
            ),
        },
    ),
    "feat:06:hygiene": (
        ("check-parse", "validate", "replay"),
        {
            "policy.dw": "def temporal seen_after(?w, ?s) {\n"
            "    exists ($t: Timepoint). formerly within ?w (?s && tp($t))\n"
            "};\n\n"
            + alert(
                "exists (t: Timepoint). (\n"
                '        Ledger::Action::"Alert"::request{ input.server: "s1" } && tp(t)\n'
                f"        && seen_after(@W@, ({LOGIN_ANCHOR} && tp(t)))\n"
                "    )"
            )
        },
    ),
    "feat:09:call-checks": (
        PARSE,
        {
            "policy.dw": "def cedar between(?n, ?m) { ?n < ?m };\n\n"
            + policy("between(context.input.amount)")
        },
    ),
}


# Fix round 1 (D-M7): stated features and restrictions that had no case.
EXT_SCHEMA = """namespace Ledger {
  type TransferInput = {
    amount: Long,
    user: String
  };
  type OpenInput = {
    labels: Set<String>,
    note?: {
      tier?: {
        name?: String
      }
    },
    user: String
  };
  type OpenSystem = {
    addr: ipaddr,
    at: datetime,
    rate: decimal,
    span: duration
  };
  type Empty = {  };
  entity Gateway = {
    owner: String
  };
  entity User = {
    id: String
  } tags String;
  action "Transfer" appliesTo {
    principal: [User],
    resource: [Gateway],
    context: {
      input: TransferInput,
      output?: Empty
    }
  };
  action "Open" appliesTo {
    principal: [User],
    resource: [Gateway],
    context: {
      input: OpenInput,
      output?: Empty,
      system: OpenSystem
    }
  };
}
"""
OPEN_SCOPE = 'principal,\n    action == Ledger::Action::"Open",\n    resource'
ADDRS = ("10.0.0.7", "127.0.0.1", "224.0.0.9", "::1", "2001:db8::7", "192.168.4.20")
USERS_EXT = ("u1", "u*", "u7", "café", "café1", "v2")
LABELS = (["a", "b"], ["b"], ["c", "x"], [], ["a", "b", "d"], ["d"])
NOTES = (
    "",
    'note: { tier: { name: "gold" } }, ',
    "note: { tier: {  } }, ",
    "note: {  }, ",
)


def rules(*conds, scope=OPEN_SCOPE):
    """One permit per condition, each with its own @id, so `[rules: …]` shows each one's value."""
    return "\n".join(
        f'@id("@RID@_{i}")\npermit (\n    {scope}\n)\nwhen {{ {c} }};\n'
        for i, c in enumerate(conds)
    )


def open_trace(r):
    """Open requests of two principals, each with its own address, time, span, rate, labels,
    user and optional note: the values the extension, set and pattern rules turn on."""
    who = r.sample(pairs.PEOPLE, 2)
    c = pairs.Clock(r)
    lines = []
    for _ in range(r.randint(5, 7)):
        ts, rid = c.tick()
        p = r.choice(who)
        day = r.choice([1, 1, 2, 30])
        hour, minute = r.randint(0, 23), r.choice([0, 15, 45])
        span = r.choice(["45m", "90m", "2h", "1d2h", "30s", "3h30m"])
        rate = r.choice(["0.75", "1.25", "1.5", "2.0001"])
        labels = r.choice(LABELS)
        user = r.choice(USERS_EXT)
        note = r.choice(NOTES)
        inp = (
            "{ labels: "
            + json.dumps(labels)
            + f", {note}user: {json.dumps(user, ensure_ascii=False)} }}"
        )
        system = (
            f'{{ addr: ip("{r.choice(ADDRS)}"), at: datetime("2026-05-{day:02d}T{hour:02d}:{minute:02d}:00Z"), '
            f'rate: decimal("{rate}"), span: duration("{span}") }}'
        )
        lines.append(
            f'@{ts} scope(principal: Ledger::User::"{p}", resource: Ledger::Gateway::"gw1") '
            f"request_context(input: {inp}, system: {system}) "
            f'Ledger::Action::"Open"::request(input: {inp}, callerPrincipal: Ledger::User::"{p}", '
            f'callerResource: Ledger::Gateway::"gw1", requestId: "{rid}")'
        )
    return lines


def owner_trace(r):
    """Transfers to gateways whose owner the entity store names: the provider reads it."""
    who = r.choice(pairs.PEOPLE)
    c = pairs.Clock(r)
    lines = []
    for _ in range(r.randint(3, 5)):
        ts, rid = c.tick()
        gw = r.choice(["gw1", "gw2"])
        owner = r.choice(["u1", "u22", "ops7", "x"])
        amount, user = r.choice([10, 20, 45]), r.choice(pairs.USERS)
        lines.append(
            f'@{ts} scope(principal: Ledger::User::"{who}", resource: Ledger::Gateway::"{gw}") '
            f'entities(Ledger::Gateway::"{gw}": {{ owner: "{owner}" }}) '
            f'request_context(input: {{ amount: {amount}, user: "{user}" }}) '
            f'Ledger::Action::"Transfer"::request(input: {{ amount: {amount}, user: "{user}" }}, '
            f'callerPrincipal: Ledger::User::"{who}", callerResource: Ledger::Gateway::"{gw}", '
            f'requestId: "{rid}")'
        )
    return lines


OWNER_PROVIDER = {
    "availableProviders": {
        "Text::Owner": {
            "argumentTypes": [{"paramType": "string"}],
            "outputType": {
                "paramType": "record",
                "fields": {
                    "digits": {"paramType": "string"},
                    "ok": {"paramType": "bool"},
                },
                "required": ["digits", "ok"],
            },
            "implementation": {
                "kind": "rhai",
                "script": (
                    "fn evaluate(owner) {\n"
                    '    if type_of(owner) == "()" {\n'
                    '        return #{ digits: "", ok: false };\n'
                    "    }\n"
                    '    let d = regex_find("[0-9]+", owner);\n'
                    '    #{ digits: d, ok: d != "" }\n'
                    "}\n"
                ),
            },
        }
    }
}


def empty_enum_providers() -> str:
    """Risk::Score with an enum-typed `level` output whose enum lists no value."""
    decl = json.loads(enum_providers())
    decl["entityTypes"]["Risk::Level"]["enum"] = []
    return json.dumps(decl, indent=1) + "\n"


EXT = {"schema.cedarschema": EXT_SCHEMA}
NEW_FEATURES = {
    "feat:02:datetime": (
        ("validate", "replay", "lower", "explain"),
        dict(
            EXT,
            **{
                "policy.dw": rules(
                    'context.system.at < datetime("2026-05-02T00:00:00Z")',
                    'context.system.at >= datetime("2026-05-30")',
                )
            },
        ),
    ),
    "feat:02:duration": (
        ("validate", "replay", "lower", "explain"),
        dict(
            EXT,
            **{
                "policy.dw": rules(
                    'context.system.span > duration("1h")',
                    'context.system.span <= duration("90m")',
                )
            },
        ),
    ),
    "feat:02:ipaddr-methods": (
        ("validate", "replay", "lower"),
        dict(
            EXT,
            **{
                "policy.dw": rules(
                    "context.system.addr.isIpv4()",
                    "context.system.addr.isIpv6()",
                    "context.system.addr.isLoopback()",
                    "context.system.addr.isMulticast()",
                    'context.system.addr.isInRange(ip("10.0.0.0/8"))',
                )
            },
        ),
    ),
    "feat:02:datetime-methods": (
        ("validate", "replay", "lower"),
        dict(
            EXT,
            **{
                "policy.dw": rules(
                    'context.system.at.toDate() == datetime("2026-05-01")',
                    'context.system.at.toTime() < duration("12h")',
                    'context.system.at.offset(duration("1d")) > datetime("2026-05-02T12:00:00Z")',
                    'context.system.at.durationSince(datetime("2026-05-01T00:00:00Z")) > duration("6h")',
                )
            },
        ),
    ),
    "feat:02:duration-methods": (
        ("validate", "replay", "lower"),
        dict(
            EXT,
            **{
                "policy.dw": rules(
                    "context.system.span.toMilliseconds() > 3600000",
                    "context.system.span.toSeconds() >= 5400",
                    "context.system.span.toMinutes() < 60",
                    "context.system.span.toHours() >= 2",
                    "context.system.span.toDays() >= 1",
                )
            },
        ),
    ),
    "feat:02:decimal-methods": (
        ("validate", "replay", "lower"),
        dict(
            EXT,
            **{
                "policy.dw": rules(
                    'context.system.rate.lessThanOrEqual(decimal("1.25"))',
                    'context.system.rate.greaterThanOrEqual(decimal("1.5"))',
                )
            },
        ),
    ),
    "feat:02:set-methods": (
        ("validate", "replay", "lower"),
        dict(
            EXT,
            **{
                "policy.dw": rules(
                    'context.input.labels.containsAll(["a", "b"])',
                    'context.input.labels.containsAny(["c", "d"])',
                )
            },
        ),
    ),
    "feat:02:tag-methods": (
        ("validate", "lower", "explain"),
        dict(
            EXT,
            **{
                "policy.dw": rules(
                    'principal.hasTag("role") && principal.getTag("role") == "@WHO@"'
                )
            },
        ),
    ),
    "feat:02:has-path-and-quoted": (
        ("validate", "replay", "lower", "explain"),
        dict(
            EXT,
            **{
                "policy.dw": rules(
                    "context.input has note.tier.name",
                    'context.input has "note"',
                    "context.input has note.tier",
                )
            },
        ),
    ),
    "feat:02:like-escapes": (
        ("validate", "replay", "lower", "explain"),
        dict(
            EXT,
            **{
                "policy.dw": rules(
                    'context.input.user like "u\\*"',
                    'context.input.user like "caf\\u{e9}*"',
                    'context.input.user like "u*"',
                )
            },
        ),
    ),
    "feat:12:evaluation-errors-deny": (
        ("validate", "replay"),
        {
            "policy.dw": rules(
                "context.input.amount * 4611686018427387904 > @N@",
                "context.input.amount < 1000",
                scope=TRANSFER_SCOPE,
            )
        },
    ),
    "feat:10:regex-find-resource-argument": (
        ("validate", "replay", "lower"),
        {
            "schema.cedarschema": EXT_SCHEMA,
            "providers.json": json.dumps(OWNER_PROVIDER, indent=1) + "\n",
            "policy.dw": rules(
                "Text::Owner(resource.owner).ok",
                'Text::Owner(resource.owner).digits == "22"',
                scope=TRANSFER_SCOPE,
            ),
        },
    ),
}
NEW_FEATURE_TRACES = {
    "feat:02:datetime": open_trace,
    "feat:02:duration": open_trace,
    "feat:02:ipaddr-methods": open_trace,
    "feat:02:datetime-methods": open_trace,
    "feat:02:duration-methods": open_trace,
    "feat:02:decimal-methods": open_trace,
    "feat:02:set-methods": open_trace,
    "feat:02:has-path-and-quoted": open_trace,
    "feat:02:like-escapes": open_trace,
    "feat:10:regex-find-resource-argument": owner_trace,
}
NEW_TEMPLATES = {
    "restr:02:record-duplicate-key": (
        PARSE,
        {"policy.dw": policy('{ a: 1, "a": @N@ } == { a: 1 }')},
    ),
    "restr:02:has-quoted-then-path": (
        PARSE,
        {"policy.dw": policy('context has "input".user')},
    ),
    "restr:02:has-index": (
        PARSE,
        {"policy.dw": policy('context has input["user"]')},
    ),
    "restr:02:has-literal-first": (
        PARSE,
        {"policy.dw": policy("context has true.user")},
    ),
    "restr:03:empty-event-schema-no-kinds": (
        ("schema-event", "validate", "replay"),
        {
            "policy.dw": alert(f"formerly within @W@ {LOGIN_ANCHOR}"),
            "event.dwschema": "// The kinds our tools log go here.\n",
        },
    ),
    "restr:04:window-length-overflow": (
        VALIDATE,
        {"policy.dw": alert(f"formerly within 200000000000000d {LOGIN_ANCHOR}")},
    ),
    "restr:10:enum-needs-value": (
        ("schema-providers", "validate"),
        {
            "policy.dw": policy("Risk::Score(context.input.amount).score > @N@"),
            "providers.json": empty_enum_providers(),
        },
    ),
    "restr:10:argument-type-differs": (
        VALIDATE,
        {
            "policy.dw": policy("Risk::Score(principal.dept).score > @N@"),
            "providers.json": providers(),
            "schema.cedarschema": pairs.SCHEMA.replace(
                "  entity User = {\n    id: String\n  };",
                "  entity User = {\n    dept: Long,\n    id: String\n  };\n"
                "  entity Admin = {\n    dept: String,\n    id: String\n  };",
                1,
            ).replace(
                '  action "Transfer" appliesTo {\n    principal: [User],',
                '  action "Transfer" appliesTo {\n    principal: [User, Admin],',
                1,
            ),
        },
    ),
}

FEATURES.update(NEW_FEATURES)
TEMPLATES.update(NEW_TEMPLATES)


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


def since_trace(r):
    """One principal: a Login (the anchor), two Transfers that hold the left of `since`, then an
    Alert decision, at which the left does not hold, then a Transfer and an Alert."""
    who = r.choice(pairs.PEOPLE)
    c = pairs.Clock(r)
    lines = []
    for ev in (
        pairs.login(r),
        pairs.transfer(r),
        pairs.transfer(r),
        pairs.ALERT,
        pairs.transfer(r),
        pairs.ALERT,
    ):
        ts, rid = c.tick()
        lines.append(pairs.line(ts, ev[0], ev[1], rid, scope=who))
    return lines


def transfers_trace(r):
    """Transfers, a Login and an Alert by two principals: every Transfer decision calls the
    provider."""
    who = r.sample(pairs.PEOPLE, 2)
    c = pairs.Clock(r)
    lines = []
    for ev in (pairs.transfer(r), pairs.login(r), pairs.transfer(r), pairs.ALERT):
        ts, rid = c.tick()
        lines.append(pairs.line(ts, ev[0], ev[1], rid, scope=r.choice(who)))
    return lines


def previous_trace(r):
    """One principal: a Login, then a Transfer, then an Alert decision (the key's previous event is
    the Transfer), then a Login and an Alert (now the previous event is the Login)."""
    who = r.choice(pairs.PEOPLE)
    c = pairs.Clock(r)
    lines = []
    for ev in (
        pairs.login(r),
        pairs.transfer(r),
        pairs.ALERT,
        pairs.login(r),
        pairs.ALERT,
    ):
        ts, rid = c.tick()
        lines.append(pairs.line(ts, ev[0], ev[1], rid, scope=who))
    return lines


def window_edge_trace(r):
    """A Login, then Alert decisions exactly 30 minutes and 30 minutes and one second later."""
    who = r.choice(pairs.PEOPLE)
    start = r.randint(10, 500)
    login = pairs.login(r)
    return [
        pairs.line(start, login[0], login[1], "r1", scope=who),
        pairs.line(start + 1800, pairs.ALERT[0], pairs.ALERT[1], "r2", scope=who),
        pairs.line(start + 1801, pairs.ALERT[0], pairs.ALERT[1], "r3", scope=who),
    ]


FEATURE_TRACES = {
    "feat:03:key-local-since-left": since_trace,
    "feat:04:since": since_trace,
    "feat:05:enum-unexpected-denied": transfers_trace,
    "feat:03:key-local-previous": previous_trace,
    "feat:04:window-closed": window_edge_trace,
    "feat:06:hygiene": previous_trace,
    **NEW_FEATURE_TRACES,
}


def history_trace(amounts, edge=False):
    """One principal's Transfers before a Login, inside the 30-minute window after it and once
    it has lapsed, with the given amounts (before, inside..., after): the window's condition is
    false, then true, then false again, so no engine without the history prints this stream.
    With `edge`, the inside Transfers sit exactly 1,800 and 1,801 seconds after the Login."""

    def build(r):
        who, user = r.choice(pairs.PEOPLE), r.choice(pairs.USERS)
        start = r.randint(10, 500)
        before, *inside, after = amounts
        lines = [pairs.line(start, *_transfer(before, user), "r1", scope=who)]
        login = start + r.randint(2, 9)
        lines.append(
            pairs.line(
                login, "Login", [("server", "s1"), ("user", user)], "r2", scope=who
            )
        )
        ts = login + 1800 if edge else login
        for i, amount in enumerate(inside):
            ts = login + 1800 + i if edge else ts + r.randint(1, 20)
            lines.append(
                pairs.line(ts, *_transfer(amount, user), f"r{3 + i}", scope=who)
            )
        late = login + 1801 + r.randint(1, 900)
        lines.append(
            pairs.line(late, *_transfer(after, user), f"r{3 + len(inside)}", scope=who)
        )
        return lines

    return build


def _transfer(amount, user):
    return "Transfer", [("amount", amount), ("user", user)]


WITHIN_LOGIN = f"formerly within 30m {LOGIN_ANCHOR}"


def history_rule(effect, *, cedar=None, temporal=True, n=""):
    """One Transfer rule: an optional Cedar condition, then the 30-minute Login window."""
    body = []
    if cedar:
        body.append(f"when {{ {cedar} }}")
    if temporal:
        body.append(f"when temporal {{\n    {WITHIN_LOGIN}\n}}")
    tail = "\n" + "\n".join(body) if body else ""
    return f'@id("@RID@{n}")\n{effect} (\n    {TRANSFER_SCOPE}\n){tail};\n'


# Replay bundles whose streams need the history (section 4b of `select_cases.py` lets weak
# cases of their family join their units). R: `formerly` with a Cedar condition, and a closed
# window's edge; P: a provider call under `forbid` beside a plain `permit`, and a provider call
# and a temporal condition in one rule; M: a `def temporal` window macro, and a `def cedar` macro
# beside a temporal condition. A score of `amount * K` (K 2-9) is at least 100 for an
# amount of 60 and at most 90 for 10, whatever K is.
HISTORY_ANCHORS = {
    "feat:04:formerly": (
        "R",
        {"policy.dw": history_rule("permit", cedar="context.input.amount > 15")},
        history_trace((45, 45, 10, 45)),
    ),
    "feat:04:window-closed": (
        "R",
        {"policy.dw": history_rule("permit")},
        history_trace((45, 45, 45, 45), edge=True),
    ),
    "feat:05:permit-and-forbid": (
        "P",
        {
            "policy.dw": history_rule(
                "forbid", cedar="Risk::Score(context.input.amount).score >= 100", n="_0"
            )
            + history_rule("permit", temporal=False, n="_1"),
            "providers.json": providers(),
        },
        history_trace((60, 60, 10, 60)),
    ),
    "feat:05:composes": (
        "P",
        {
            "policy.dw": history_rule(
                "permit", cedar="Risk::Score(context.input.amount).score >= 100"
            ),
            "providers.json": providers(),
        },
        history_trace((60, 60, 10, 60)),
    ),
    "feat:06:template-expansion": (
        "M",
        {
            "policy.dw": "def temporal seen_login(?w) { formerly within ?w "
            f"{LOGIN_ANCHOR} }};\n\n"
            + history_rule("permit", cedar="context.input.amount > 15").replace(
                WITHIN_LOGIN, "seen_login(30m)"
            )
        },
        history_trace((45, 45, 10, 45)),
    ),
    "feat:06:cedar-macro": (
        "M",
        {
            "policy.dw": "def cedar big(?n) { ?n > 15 };\n\n"
            + history_rule("permit", cedar="big(context.input.amount)")
        },
        history_trace((45, 45, 10, 45)),
    ),
}


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
                trace = FEATURE_TRACES.get(fid, mixed_trace)
                texts["trace.log"] = "\n".join(trace(r)) + "\n"
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
    for fid, (family, files, trace) in HISTORY_ANCHORS.items():
        for _ in range(2 * copies):
            d = os.path.join(out, f"fx{idx:03d}")
            os.makedirs(d, exist_ok=True)
            texts = {name: fill(text, r, idx) for name, text in files.items()}
            texts.setdefault("schema.cedarschema", pairs.SCHEMA)
            texts["trace.log"] = "\n".join(trace(r)) + "\n"
            for name, text in texts.items():
                with open(os.path.join(d, name), "w") as f:
                    f.write(text)
            meta = {
                "family": "features",
                "kind": fid,
                "cmds": ["replay"],
                "replay_family": family,
            }
            with open(os.path.join(d, "meta.json"), "w") as f:
                json.dump(meta, f, indent=1)
            idx += 1
    # R at a window's edge, the `since` boundary and `previous` (QA 17 F5), after the rest.
    return combos.write_f5(r, idx, out)
