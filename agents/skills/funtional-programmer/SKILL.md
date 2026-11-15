---
name: funtional-programmer
description: Implement or change repository functions with explicit parameter and return types and useful Google-style docstrings, including helpers and tests.
---

# Function contracts

Annotate every parameter and return value of each function you create or change.
Python's conventional implicit `self` and `cls` types are fine. Use `-> None` for
functions without a result and annotate async functions with their awaited result.
Specify collection element types and use named structured types for records.
Keep dynamic boundaries narrow and validate external values before using them.

Give each function a reasonably detailed Google-style docstring. Start with what
it does, then explain consequential behavior such as mutation, persistence, ordering,
or resource ownership. Include `Args:`, `Returns:` or `Yields:`, and `Raises:` where
they add useful contract information. Avoid boilerplate and repeating annotations.
Use equivalent native types and documentation comments in other languages.

For Orange, `generate(query: str) -> GeneratedAnswer` returns the structured answer
when awaited. JSON encoding belongs at the CLI boundary. Keep that distinction in
the types, implementation, and documentation.

Apply these requirements to tests, private helpers, callbacks, and methods as well
as public functions. Keep the change scoped; do not rewrite unrelated functions.
Run relevant checks and an existing type checker when available. Do not add a new
checker just to satisfy this skill. Confirm docstrings match actual behavior.

## Keep functions and modules cohesive

Organize code by responsibility and dependency boundaries, not by a file-size
quota. A module should have one clear reason to change. Split a module when it
mixes concerns such as domain decisions, process execution, external-service
calls, and report writing. Add subfolders when they group related modules; avoid
empty packages, one-function files without a useful boundary, and generic utility
folders that collect unrelated code.

Prefer pure functions for calculations, validation, and transformations. Pass in
the required values and return explicit results. Keep filesystem, network, process,
and environment side effects in named adapters. Classes are appropriate when they
own resources or coherent state; do not create inheritance or plugin frameworks
just to organize functions.

Keep dependencies pointing toward shared contracts and focused helpers. Sibling
test modules should not import helpers from one another. Put shared test support
below those modules, and keep orchestration separate from individual checks.
Avoid circular imports and broad re-exports that obscure which module owns a
function. Remove obsolete parameters and temporary compatibility wrappers when
all callers can migrate within the requested scope.

Refactor structure separately from behavior changes. Preserve public entry points,
ordering, failure handling, and side-effect boundaries. Update every caller and
resource path when moving a module. Validate the packaged or extracted artifact
from an isolated process when deployment depends on those paths; tests that only
run from the repository can hide missing imports or resources.

For example, a knowledge-assistant verifier can separate acceptance checks,
candidate-process adapters, judge clients, and private-data loading. Its weighted
reward calculation can be pure, while its subprocess probes remain self-contained
because they run without permission to import private verifier files. This is an
example of respecting a deployment boundary, not a required folder template for
other domains.

## Configure policy instead of embedding it in functions

Put tunable thresholds, weights, budgets, and operational settings in explicit
configuration. When environment variables are the project's configuration boundary,
declare their values in deployment configuration and parse them once at startup
into a typed, immutable settings object. Pass that object or the relevant values
to functions; keep calculations independent of environment reads and import-time
state.

Validate missing values, types, finite numbers, ranges, and relationships such as
weights summing to one. Fail clearly before work starts when required configuration
is invalid. Do not silently restore hard-coded policy through default arguments or
`getenv` fallbacks. Document defaults where configuration is declared and record
effective nonsecret settings when reproducibility matters.

Distinguish tunable policy from mathematical constants and explicitly fixed task
requirements. A percentage scale or a protocol invariant does not need an environment
variable. Preserve a deliberately pinned judge or other required invariant unless
the user changes that requirement. Do not expose trusted evaluation configuration
to the submitted application merely because both run in the same environment.

For example, a verifier's target score and component weights can come from its
trusted environment, while `aggregate_results(checks, config)` remains a pure
function. Test alternate configurations, invalid settings, and boundary cases,
not only the default values.
