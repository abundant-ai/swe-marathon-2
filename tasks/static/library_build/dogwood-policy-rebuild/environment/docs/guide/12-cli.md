# The command line

The `dogwood` CLI runs the whole Dogwood pipeline — parse, macro expansion,
lowering, type-checking, and stateful replay — over plain files. It is the
quickest way to check a policy or watch a temporal policy decide across an event
trace: everything is a file in, a verdict (or a diagnostic) out.

Every policy-level example in this guide is a complete, runnable **bundle** in
`examples/`, with what the CLI prints for it: `explain.out` is the output of
`dogwood explain` for the bundle's policy and, where the bundle has a
`trace.log`, `expected.out` is the output of `dogwood replay` for that trace.
Both are run with the bundle's own files — `--policy-schema schema.cedarschema`,
plus `--event-schema`, `--providers` and `--macros` for a bundle that has an
event schema, a `providers.json` or a `macros.dw`.

## The two schema halves

A Dogwood schema comes in two parts, and the CLI mirrors that split:

- **The action schema** — a Cedar `.cedarschema` declaring entities, actions,
  and each action's `context` shape. Required wherever a schema is needed;
  passed with `--policy-schema`.
- **The service schema** — the event schema, information-provider declarations,
  and macro library. All optional; each defaults sensibly. Supplied with
  `--event-schema`, `--providers`, and `--macros` when a policy needs a
  non-default one.

See [The policy language](02-policy-language.md) for the action schema, and
[The event schema](03-event-schema.md) / [The provider schema](10-provider-schema.md)
/ [Macros](06-macros.md) for the service-side pieces.

## Commands

Every policy command takes the policy set as a positional argument (a `.dw`
file, or `-` to read stdin). Every other file a command reads (`--policy-schema`,
`--event-schema`, `--providers`, `--macros`, `--trace`, and the file of a
`schema` command) may be `-` too; stdin is read once, so it can stand for one of
them. Every command except `format` also accepts `--format human|json` (human
is the default; JSON is the stable machine shape, described under
[JSON output](#json-output)). `validate`, `lower` and `replay` need
`--policy-schema`, and `replay` also needs `--trace`; `check-parse` takes no
`--policy-schema`, and `format` takes nothing but the policy file. A missing
or unknown option is a usage error.

Every command uses the same exit codes.

- `0` is success.
- `1` is an I/O error. An input file or stdin cannot be read (it is missing,
  is a directory, or is not UTF-8), or an output file cannot be written.
- `2` is a usage error (an unknown flag or subcommand, or a missing
  argument), input that the command cannot process (for example, a policy,
  schema, or trace that does not parse), or a `validate` run that
  finds errors.

Except in `format`, which prints a policy set it cannot parse as it is, an
input that cannot be parsed, macro-expanded or lowered (a policy set, a macro
library, an action or event schema, a providers file or a trace) stops the
command before it prints anything. With `--format human` the diagnostic
goes to stderr and stdout stays empty; with `--format json` the command prints
that diagnostic, as one JSON object, instead of its usual output. Either way
it exits 2. A policy set that lowers is then checked: `validate`'s `error:`
and `FAILED:` lines report those checks' findings.

A build without the `mcp-schema` feature has no `schema mcp` subcommand, so
`dogwood schema mcp` exits 2 there. `lower`, `explain`, and `replay` do not run
the validator, so they can exit 0 for a policy that fails `validate`. `replay`
also exits 0 when it denies a request or rejects an event of the trace.
`format` exits 0 for any input that it can read.

`dogwood --help` (or `dogwood help`) prints the list of commands, and
`dogwood <command> --help` prints that command's usage, arguments and options:
`dogwood schema --help` lists the schema parts, and `dogwood schema event --help`
describes one of them. `dogwood --version` (or `-V`) prints the name and version,
`dogwood 1.2.0`. They all print to stdout and exit 0.

### `format` — pretty-print authored policy source

```text
dogwood format policy.dw
```

Writes a consistently laid-out policy set to stdout: annotations and condition
clauses get their own lines, long comma-separated or boolean groups are
indented, and top-level declarations and policies are separated by a blank
line. Formatting changes whitespace only, so strings, macro definitions, and
token spelling are preserved. Standalone top-level comments are preserved too;
when a comment occurs inside a statement, the formatter leaves the source
unchanged rather than risk moving the comment unexpectedly.

Use `-` for stdin, or redirect stdout to a new file:

```text
dogwood format policy.dw > policy.formatted.dw
cat policy.dw | dogwood format -
```

### `validate`

```text
dogwood validate policy.dw --policy-schema schema.cedarschema \
    [--event-schema events.dwschema] [--providers providers.json] [--macros macros.dw]
```

Parses, lowers against the schema, and type-checks in one shot — the two error
classes (syntax/macro/lowering failures, and schema-aware type errors) are both
covered, so a clean `validate` means the policy is fully accepted. A syntax,
macro or lowering failure is reported as every command reports one (see
[Commands](#commands)). A policy set that lowers is type-checked: on success
`validate` prints `OK: validation passed …` and exits 0; when the checks find
errors it prints each finding on a line of its own (`error: …`, then any
`warning: …`), then `FAILED: <n> error(s), <m> warning(s).`, and exits 2.

```text
$ dogwood validate examples/write_after_read/policy.dw \
    --policy-schema examples/write_after_read/schema.cedarschema
OK: validation passed with no errors or warnings.
```

Add `--format json` for findings as structured data (each with a `message` and a
byte-offset `labels` span) instead of rendered snippets — the form a CI job
wants.

**`--providers` and `scriptFile`: inline your Rhai for CLI use.** A
`providers.json` `implementation` carries its Rhai two ways: inline
**`script`** (source as a JSON string) or **`scriptFile`** (a path to an
external `.rhai`, resolved relative to the declarations file). The CLI reads
`--providers` **as text**, so a `scriptFile` reference is never resolved:
`validate` and `lower` still work (they don't evaluate providers), but
`replay` fails at every provider evaluation, with an error saying that the rhai
implementation has no script. When a bundle will be driven through the CLI, put the Rhai inline
under `implementation.script` — every runnable bundle in
[`examples/`](../examples/) does exactly this. (An `implementation`-less,
interface-only declaration validates and lowers through the CLI too, but
`replay` cannot evaluate it.)

### `replay` — watch a temporal policy decide

Validation proves a policy is *legal*; `replay` shows what it *does*. It feeds a
whole event trace through a stateful authorizer, so temporal operators see the
accumulated history, and prints one verdict per decision point:

```text
dogwood replay policy.dw --policy-schema schema.cedarschema --trace trace.log
```

```text
$ dogwood replay examples/write_after_read/policy.dw \
    --policy-schema examples/write_after_read/schema.cedarschema \
    --trace examples/write_after_read/trace.log
@0 (time point 0): DENY
@100 (time point 1): ALLOW  [rules: 0]
@5000 (time point 2): DENY
```

Each line is `@<timestamp> (time point <index>): ALLOW|DENY`, optionally followed
by `[rules: …]` — the indices of the `.dw` rules that determined the decision.
The `<index>` counts the trace's decision points from 0.
A decision that failed closed is a `DENY` followed by one `    error: …` line
per error, such as `nonconforming request: …` for a request context that lacks
an attribute its action's context requires. History-only events (a non-decision
event kind) update the history but produce no line. A history event that does
not conform to the event schema is rejected, and not ingested; it is reported
in trace order as `@<timestamp> (event <position> of the trace): REJECTED, not
ingested`, followed by its `    error: nonconforming event: …` line; the
`<position>` counts all the trace's events from 0. This is the
way to catch a policy that validates but does not *mean* what you intended — a
mis-pinned "same user" correlation, or a window that is too narrow — and a trace
whose data does not match its schemas. `--format json` emits a structured
verdict stream, with the rejected events under `rejected` when there are any.

A trace is one event per line. The events in `examples/write_after_read/trace.log`
look like:

```text
@0 scope(principal: Drupe::OAuthUser::"alice", resource: Drupe::Gateway::"gw1") request_context(input: { shares: 5, stock: "AMZN" }, system: { now: datetime("1970-01-01T00:00:00Z") }) Drupe::Action::"ApproveSale"::request(input: { shares: 5, stock: "AMZN" }, callerPrincipal: Drupe::OAuthUser::"alice", callerResource: Drupe::Gateway::"gw1", requestId: "u1")
```

— a timestamp, optional request envelopes (`scope(...)`, and here
`request_context(...)` — the context the Cedar request is built from, with the
`system` record the Drupe template requires, its `now` written as Cedar writes a
`datetime`), and the fully-qualified action with its explicit `::request` (or
other) kind and its logged record. See
[The trace file format](#the-trace-file-format) below for the whole format, and
[The event schema](03-event-schema.md) for the event model.

### `lower` — see the generated Cedar

```text
dogwood lower policy.dw --policy-schema schema.cedarschema --emit both
```

Lowers the `.dw` to Cedar and emits the artifacts: the Cedar policies, the
augmented action schema (with the hoisted `context.*` fields Dogwood adds for
temporal leaves and providers), or — with `--emit cedar-json` — the schema as
Cedar JSON (suitable for any Cedar-based policy store). `--emit` is one of
`cedar-policies`, `cedar-schema`, `cedar-json`, or `both` (the default). When the
lowered Cedar is not self-contained — because temporal or provider fields were
hoisted and need Dogwood at authorize time — `lower` says so on stderr.

### `check-parse` — syntax only

```text
dogwood check-parse policy.dw
```

Parses and macro-expands, reporting only syntax and macro errors — no schema
required. Useful as a fast first pass, or when you do not yet have the action
schema. It reports each policy's temporal-leaf and provider-call counts, and
flags any provider a policy calls that the service schema does not declare.

### `explain` — read a policy set back in semi-English

```text
dogwood explain policy.dw --policy-schema schema.cedarschema
```

Prints each rule as structured prose, so a policy can be checked against the
requirement it came from:

```text
Only past events from this request's principal count.

@id("access_not_revoked_since_grant")
PERMIT any principal to perform Access on any resource
  when:
    a Grant response with this request's user and resource occurred within the last 1 hour
    and no Revoke response for that user and resource has occurred since then
```

The translation is deterministic — a pure function of the parsed,
macro-expanded policy plus the schemas, with no language model — and
meaning-preserving: read literally, it states the same condition as the
policy. It follows the policy's structure, so the nesting of the prose is the
nesting of the policy, except for a few rewrites of common shapes, each made
only when it is exact:

- `since` reads in time order (see below);
- fields compared with the request's own merge into one phrase ("with this
  request's user and stock");
- a count or sum that uses a timepoint only to count each event once reads
  "the number of Transfer requests within the last 1 hour" / "the total
  amount of …";
- an `exists` variable that only names an aggregate for one comparison, or
  only carries one event field to a comparison, is folded into it ("… <= 3",
  "a Transfer request with amount > 100").

Schema identifiers are reproduced verbatim; only the language's own structure
is verbalized. Because of the rewrites, the `--format json` phrase tree is not
one phrase per AST node: a rewritten construct is one phrase carrying the span
of the outermost node it covers. A few things to notice when reading the
output:

- **`@id("…")`** opens each rule on its own line; a rule without an `@id`
  reads `Rule N`.
- **The first line** (`Only past events from this request's principal
  count.`) is not in the policy text: it states the *event schema's*
  pins, which silently restrict every look-back match, because they change
  verdicts.
- **`since` reads in time order** — the anchor event and its window first,
  then what has (or has not) happened since then.
- **A `count` whose body is not under a past operator** reads "the number of
  …, counting only this request itself": only the event being decided is
  matched, so it is at most 1 — compare
  `examples/alert_heartbeat_and_login_rate/` with
  `examples/alert_login_in_last_hour/`.

`--policy-schema` is optional: with it, a single declared namespace is dropped
from names (`Drupe::Action::"Read"` → `Read`). Nothing is validated — run `validate` for that. `--format json` emits the phrase trees, each phrase with
its `.dw` byte span.

For more sample output, see the `explain.out` next to each bundle under
[`examples/`](../examples/).

### `schema` — check a schema part on its own

```text
dogwood schema action    schema.cedarschema
dogwood schema event     events.dwschema
dogwood schema providers providers.json
```

Each checks one schema artifact in isolation — that it parses and is
well-formed — so you can tell "my schema is broken" from "my policy is broken"
before running `validate`.

## The trace file format

`dogwood replay` reads the event trace named by `--trace`, a `.log` file. Each non-blank line is one timepoint of the form `@<ts> [envelopes] <Action>(<field>: <value>, …)`: `<ts>` is a signed 64-bit integer, a count of seconds that may be negative, and the optional `scope` / `entities` / `request_context` envelopes are described below. Values use Cedar surface forms (entity refs `Ns::Type::"id"`, strings, integers, decimals, `true`/`false`, arrays, objects, and the extension constructors `datetime("…")`, `duration("…")`, `ip("…")`, `decimal("…")`). `replay` feeds the events to the authorizer in the order of their lines. A trace that does not parse is an error, and `replay` exits 2.

```text
@0 scope(principal: Drupe::OAuthUser::"alice", resource: Drupe::Gateway::"gw1") request_context(input: { user: "alice" }) Drupe::Action::"Login"::request(input: { user: "alice" }, callerPrincipal: Drupe::OAuthUser::"alice", callerResource: Drupe::Gateway::"gw1")
@10 scope(principal: Drupe::OAuthUser::"alice", resource: Drupe::Gateway::"gw1") request_context(input: { user: "alice" }) Drupe::Action::"Read"::request(input: { user: "alice" }, callerPrincipal: Drupe::OAuthUser::"alice", callerResource: Drupe::Gateway::"gw1")
@7200 scope(principal: Drupe::OAuthUser::"alice", resource: Drupe::Gateway::"gw1") request_context(input: { user: "alice" }) Drupe::Action::"Read"::request(input: { user: "alice" }, callerPrincipal: Drupe::OAuthUser::"alice", callerResource: Drupe::Gateway::"gw1")
```

Each `.log` line is: the `@<timestamp>`, then up to three optional **request-supplement envelopes** in a fixed order, then the event itself — a **quoted, fully-qualified** action id (`Drupe::Action::"Read"`) with an explicit **`::<kind>`** segment (`::request`) and its trailing `(<field>: …)` group. That trailing group is the **logged** record (the temporal-history fields a predicate correlates on); the envelopes carry the request-only supplements, each parsed positionally when present:

- `scope(principal: …, resource: …)` — the request's principal and resource entities. (A decision-kind event omitting `scope(...)` has no principal/resource and fails closed to `Deny`.) The envelope does not log them: the trailing logged group writes `callerPrincipal` / `callerResource` itself, and the default event schema requires them, since it pins `callerPrincipal` and a logged caller field must hold the request's own.
- `entities(<uid>: { <attr>: … }, …)` — the entity attribute store: each `uid` (e.g. `Drupe::OAuthUser::"alice"`) maps to its attributes, so a policy can read `principal.<attr>` / `resource.<attr>` or a provider can resolve one. A uid `"id"` containing `"` or `\` is escaped as in Cedar (`"a\"b"`). An entry may end with `in [ <parent uid>, … ]`, its direct parents, so that `in` sees the hierarchy: `Drupe::OAuthUser::"alice": { } in [Drupe::Team::"ops"]`.
- `request_context(<attribute>: <value>, …)` — the request-only context the Cedar request is built from, distinct from the trailing logged group: each top-level attribute of the context, most often a record (`input: { … }`, `system: { … }`), and otherwise whatever value the action's context type gives it (`session: "s-1"`, `level: 2`). A field a policy reads via `context.<group>.<name>` must appear here; a field a temporal predicate correlates on must appear in the trailing logged group. A field both need (`input`) is supplied in both. The context must be an instance of the action's context record type: every attribute it requires, such as the Drupe template's `system: { now: datetime }`, and no other. A value of an extension type is written as Cedar writes it: `system: { now: datetime("2024-01-01T00:00:00Z") }`, or `duration("1h")`, `ip("10.0.0.1")`, `decimal("1.50")`.

The envelopes appear in that order (`scope`, then `entities`, then `request_context`) before the event group, and any may be omitted. Parsing is **strict**: an unterminated envelope, or a **duplicate key** within any group (a repeated uid in `entities(...)`, a repeated group in `scope`/`request_context`, a repeated field in the logged group or a nested record), is a parse error rather than a silent last-wins — so a hand-written trace cannot mis-decide on an accidental duplicate.

## Event kinds, decisions, and failure handling

Two behaviors thread through every replay and deserve to be stated plainly.

**Event kind is data, not convention.** The event schema marks certain kinds as `decision`. With the default event schema, `request` is a decision kind and `response` is history-only. From that single fact everything else follows:

- A **decision-kind event** observes the event *and* decides: `replay` prints a verdict line for it.
- A **history-only event** observes the event to update temporal state but yields no verdict, and contributes no verdict line in `replay`.
- **Statelessness is just a special case:** a single stateless decision is a trace of one `request`-kind event.

**For an enforcing integration, the caller is the enforcement point.** Verdicts are computed over events in the order they are passed in, which for `replay` is the order of the trace. An integration, and a trace that records one, should:

- **run the action only after an `Allow` verdict** for its decision event;
- **report history-only events** (`response`, `error` by default) promptly and reliably once the action resolves, **with the principal and resource of the request they report on** (under the default schema's pin, an event without a principal is no one's history, and one that logs a caller it does not carry is rejected);
- **supply increasing timestamps**, each greater than the previous one, in the order events are passed in. A trace with repeated or decreasing timestamps is out of contract, and its behaviour is unspecified.

See the [observed-sequence example](04-temporal-expressions.md#evaluation-semantics)
for how delayed or missing history-only events can flip a verdict despite
correctly increasing timestamps.

**Authorization never aborts, and this implementation resolves evaluation failures to `Deny`.** Any evaluation failure — a provider that errors, the temporal engine erroring, a decision event missing a principal/resource — yields a `Deny` with the reason recorded among the decision's errors: `replay` prints each one as an `error:` line under the `DENY` line (and in the verdict's `errors` with `--format json`). (For provider errors this deny is a description of this implementation, not a semantic guarantee: an erroring provider is undefined behavior under [the provider contract](05-information-providers.md#the-provider-contract), so a policy set must never rely on deny-on-error.) So a reader who wants to distinguish "denied by policy" from "denied because something broke" should always look at the errors, not just the verdict.

## Retries and event ids

`dogwood replay` has no notion of an event id: every event of the trace is a new submission, and an event that a trace submits twice is ingested twice. An implementation that accepts event ids follows the event-log contract of [A formal specification of Dogwood](08-formal-specification.md#66-the-event-log-contract-and-retries): its retry window, and when a resubmission is a retry or a duplicate.

## JSON output

With `--format json` every command except `format` prints one JSON object (key
order and layout carry no meaning), and its exit status is the same as in human
form. A fatal diagnostic, from any command, is `{ "message", "severity",
"spanned" }` plus, when it has them, `"labels"` (each `{ "start", "len" }`, byte
offsets into the input, with a `"message"` when the label has one), `"help"`
and `"related"` (further diagnostics of the same shape). Otherwise:

- `check-parse`: `{ "policy_count", "policies" }`, with one entry per policy:
  `{ "uses_temporal", "temporal_count", "provider_invocations",
  "undeclared_providers" }` (the providers it calls, and those of them the
  service schema does not declare).
- `validate`: `{ "passed", "passed_without_warnings", "errors", "warnings" }`;
  each finding is a diagnostic as above with a `"code"` (`cedar` for Cedar's
  validator, `extension` for Dogwood's own checks).
- `lower`: `{ "cedar_policies", "cedar_schema", "cedar_schema_json",
  "self_contained", "temporal_fields", "provider_fields", "decision_kinds" }` —
  the three texts that `--emit` chooses among, whatever `--emit` says, then
  whether the Cedar is self-contained, the hoisted fields and the decision
  kinds. The texts are strings, exactly as `--emit` prints them.
- `explain`: `{ "text", "informalization" }` — the human text, and the phrase
  trees: `"preamble"` (the pins line, or `null`) and `"rules"`, each phrase
  `{ "template", "layout", "span", "children" }`, where `"template"` holds
  `{0}`, `{1}`, … for its children, `"layout"` is `Inline`, `Block` or
  `Hanging`, and `"span"` is the phrase's `[start, end]` byte range in the
  policy (`null` when it has none).
- `replay`: `{ "verdicts" }`, and `"rejected"` when the trace has rejected
  events. Each verdict is `{ "index", "timestamp", "verdict",
  "determining_rules", "errors" }` (`verdict` is `allow` or `deny`, `errors`
  the messages of a decision that failed closed); each rejected event is
  `{ "position", "timestamp", "reason" }`.
- `schema action|event|providers`: `{ "kind", "ok" }`, with `"warnings"` when
  there are any.

Field names and value shapes are those of the build; as everywhere, every
message is the build's own text.

## Pipelines and stdin

`-` reads stdin or writes stdout, so commands compose. To lower a policy and
hand the Cedar straight to Cedar's own tooling:

```text
dogwood lower policy.dw --policy-schema schema.cedarschema --emit cedar-policies | cedar validate ...
```

