# Getting Started

*This page walks you through your first Dogwood authorization end to end — a
schema, a policy, and the `dogwood` commands that decide a request. It starts
with the simplest possible policy and then adds a decision that depends on
history. The two policies here are the `permit_read_anyone` and
`read_after_login` example bundles, and they validate and replay as shown.*

If you have not read [the introduction](00-introduction.md), skim it first — it
explains the five concepts (policies, events, schemas, temporal expressions and
information providers, and the authorizer) this tutorial puts into practice.

## The shape of the workflow

Every use of Dogwood runs the same pipeline:

- **Gather the two schema halves** — the service schema (macros, providers,
  and the event-schema DSL — the fixed, service-provided inputs) and the
  policy schema (your action schema).
- **Parse and lower** your policy source against those two schemas.
- **(Optionally) validate** the lowered policy set.
- **Feed events** to a stateful authorizer, getting a **response** — a
  decision — back for each decision event.

The tutorial below writes the schema and policy first, then runs that whole
pipeline in Step 3.

## Step 1 — a schema

The schema declares the entity types and actions in your world. It is a standard
Cedar `.cedarschema`. Here is a minimal one for an agent that can `Login` and
`Read`, each taking a `user` input field:

```text
namespace Drupe {
  type LoginInput = { user: String };
  type ReadInput = { user: String };
  entity Gateway;
  entity OAuthUser = { id: String } tags String;
  action "Login" appliesTo {
    principal: [OAuthUser],
    resource: [Gateway],
    context: { input: LoginInput }
  };
  action "Read" appliesTo {
    principal: [OAuthUser],
    resource: [Gateway],
    context: { input: ReadInput }
  };
}
```

Two things to notice, both Dogwood conventions covered in
[The policy language](02-policy-language.md):

- Each action's parameters live under a **`context.input`** record
  (`context: { input: ReadInput }`). This is where a policy reads the request's
  fields from (`context.input.user`).
- We only wrote the **action schema**. Dogwood's other two schemas — the event
  schema and provider declarations — have sensible defaults, so a simple policy
  needs nothing more.

## Step 2 — a policy

A policy is a `permit` or `forbid` rule. The simplest useful one: *permit `Read`
for anyone, on any resource.*

```text
permit (
    principal,
    action == Drupe::Action::"Read",
    resource
);
```

> Runnable: [`examples/permit_read_anyone/`](../examples/permit_read_anyone/) —
> `dogwood validate` and `dogwood replay`.

- `permit` is the effect. (`forbid` is the other; a `forbid` always wins over a
  `permit`.)
- The parenthesized part is the **scope**: bare `principal` and `resource` mean
  "any", and `action == Drupe::Action::"Read"` restricts this rule to the
  `Read` action.
- No `when` clause means no extra condition — this rule applies whenever its
  scope matches.

The full policy syntax — scope constraints, `when`/`unless` conditions, the
whole expression language — is [The policy language](02-policy-language.md).

## Step 3 — decide, on the command line

Here is the whole pipeline on the command line. With the schema saved as
`schema.cedarschema` and the policy as `policy.dw`, validate the policy, then
replay a trace of events through the authorizer:

```text
dogwood validate policy.dw --policy-schema schema.cedarschema
dogwood replay   policy.dw --policy-schema schema.cedarschema --trace trace.log
```

A trace holds one event per line. The `permit_read_anyone` bundle's
`trace.log` holds three: alice's `Login` at t=0, alice's `Read` at t=10, and
bob's `Read` at t=20. Here is alice's `Read`:

```text
@10 scope(principal: Drupe::OAuthUser::"alice", resource: Drupe::Gateway::"gw1") request_context(input: { user: "alice" }) Drupe::Action::"Read"::request(input: { user: "alice" }, callerPrincipal: Drupe::OAuthUser::"alice", callerResource: Drupe::Gateway::"gw1", requestId: "u2")
```

`dogwood replay` prints one verdict per decision:

```text
@0 (time point 0): DENY
@10 (time point 1): ALLOW  [rules: 0]
@20 (time point 2): ALLOW  [rules: 0]
```

- You authorize an *event*, not a bare request. An event is a timestamped
  occurrence of an action with a *kind* (here `request`), a principal and a
  resource: the line's `@10`, the `::request` after the action, and the
  `scope(...)` envelope.
- The event carries `input.user` in two places. The group after the action is
  the logged record, which the history keeps and temporal conditions match
  against. `request_context(...)` sets a field of the Cedar request context,
  which policies read as `context.input.user`. If a `request` event lacks the
  logged field or the request context, the authorizer denies it and reports an
  error.
- A *decision-kind* event (like `request`) gets a verdict, and a history-only
  event gets none. With the default event schema, `request` is a decision kind
  — so each event of this trace gets one. The `Login` is denied because the
  policy permits only `Read`.
- The authorizer is stateful: it remembers every event of the trace. That does
  not matter for this pure-Cedar policy, but the next step depends on it.

The trace format is in [The command line](12-cli.md#the-trace-file-format).

## Step 4 — a decision that depends on history

The next requirement depends on the past. Change it to:
*permit `Read` only if the same user logged in within the last hour.* That is a
statement about the **past**, so it uses a `when temporal { … }` clause:

```text
permit (
    principal,
    action == Drupe::Action::"Read",
    resource
)
when temporal {
    formerly within 1h Drupe::Action::"Login"::response{ input.user: context.input.user }
};
```

> Runnable: [`examples/read_after_login/`](../examples/read_after_login/) —
> `dogwood validate` and `dogwood replay`.

Read the temporal clause as: *"there was formerly, within the last 1 hour, a
successful `Login` whose `input.user` equals this request's `context.input.user`."*
The `formerly within 1h …` operator scans the event history; the
`{ input.user: context.input.user }` part correlates the past login's user with
the current request's user. This is the subject of
[Temporal expressions](04-temporal-expressions.md).

Because the decision now depends on history, we feed the authorizer a **stream**
of events and watch the verdicts change over time. The `read_after_login`
bundle's `trace.log` holds four events: a `Login` request at t=0; the `Login`
response at t=5, which records that the login succeeded; a `Read` at t=10, 5s
after the login response, well within the 1h window; and a `Read` at t=7200,
two hours later, when the login has expired:

```text
@0 scope(principal: Drupe::OAuthUser::"alice", resource: Drupe::Gateway::"gw1") request_context(input: { user: "alice" }) Drupe::Action::"Login"::request(input: { user: "alice" }, callerPrincipal: Drupe::OAuthUser::"alice", callerResource: Drupe::Gateway::"gw1", requestId: "u1")
@5 scope(principal: Drupe::OAuthUser::"alice", resource: Drupe::Gateway::"gw1") request_context(input: { user: "alice" }) Drupe::Action::"Login"::response(input: { user: "alice" }, callerPrincipal: Drupe::OAuthUser::"alice", callerResource: Drupe::Gateway::"gw1", requestId: "u1")
@10 scope(principal: Drupe::OAuthUser::"alice", resource: Drupe::Gateway::"gw1") request_context(input: { user: "alice" }) Drupe::Action::"Read"::request(input: { user: "alice" }, callerPrincipal: Drupe::OAuthUser::"alice", callerResource: Drupe::Gateway::"gw1", requestId: "u2")
@7200 scope(principal: Drupe::OAuthUser::"alice", resource: Drupe::Gateway::"gw1") request_context(input: { user: "alice" }) Drupe::Action::"Read"::request(input: { user: "alice" }, callerPrincipal: Drupe::OAuthUser::"alice", callerResource: Drupe::Gateway::"gw1", requestId: "u3")
```

Replaying it with `dogwood replay` prints:

```text
@0 (time point 0): DENY
@10 (time point 1): ALLOW  [rules: 0]
@7200 (time point 2): DENY
```

- `@0` Login → Deny. The policy gates `Read`, not `Login`, so no `permit`
  matches the login request.
- `@5` Login response → no output. In the default event schema, `response` is
  a history-only kind, so it gets no verdict. The authorizer still
  adds the event to the history. The temporal condition matches this event.
- `@10` Read → Allow. The `Login` response for `alice` occurred 5 seconds
  ago, inside the 1-hour window, so the temporal condition holds.
- `@7200` Read → Deny. The only `Login` response occurred 7195 seconds ago,
  outside the window, so the condition does not hold.

Same policy, same command — the verdict changes because the **history** changed.

## Run it yourself

The `dogwood` CLI drives the whole pipeline over plain files. Save the policy
above to `policy.dw` and its schema to `schema.cedarschema`, then validate and
replay a trace:

```text
dogwood validate policy.dw --policy-schema schema.cedarschema
dogwood replay   policy.dw --policy-schema schema.cedarschema --trace trace.log
```

Every policy-level example in this guide is a complete, runnable bundle under
the `examples/` directory — a `policy.dw`, its `schema.cedarschema`, and (where
the example is history-dependent) a `trace.log` and the verdict stream
`dogwood replay` prints for it. The two policies above are the
`permit_read_anyone` and `read_after_login` bundles. See
[The command line](12-cli.md) for the full CLI.

## Where to go next

- **The core syntax** — scopes, conditions, operators, types:
  [The policy language](02-policy-language.md).
- **History-based conditions** — the `temporal` sublanguage in full:
  [Temporal expressions](04-temporal-expressions.md).
- **Computed conditions** — information providers, called from an ordinary
  `when { … }`: [Information providers](05-information-providers.md).
- **Customizing the fixed inputs** — the event schema and providers:
  [The event schema](03-event-schema.md) and
  [The provider schema](10-provider-schema.md).

## See also

- [Introduction](00-introduction.md) — the concepts behind this tutorial.
- [The policy language](02-policy-language.md) — the next step in learning the
  language.
