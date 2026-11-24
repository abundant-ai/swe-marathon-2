---
name: funtional-programmer
description: Use whenever writing, modifying, or refactoring code in any programming language, including scripts, helpers, callbacks, methods, and tests. Write explicit function contracts and detailed documentation of purpose, intended use, arguments, and results; organize code into focused functions with domain logic separated from side effects. Python is only the example language.
---

# Functional programming and function contracts

Apply this skill any time you write or change code, in any language. Python is
used below only to illustrate the principles. Use the target language's native
types, idioms, and documentation conventions, such as JSDoc/TSDoc, Javadoc,
Rust documentation comments, or Go doc comments. For languages without signature
types, document equivalent input and output contracts using the supported tooling.
Do not switch languages or impose Python syntax to follow this skill.

Keep changes scoped to the requested work. Improve functions you create or touch;
leave unrelated code alone. The deliberately poor examples below illustrate what
to avoid and are not templates for implementation.

## Make function contracts explicit

Declare parameter and return types for every function, including helpers,
callbacks, methods, and tests. Specify collection element types and meaningful
record types. Conventional implicit `self` and `cls` are fine in Python. Async
annotations describe the awaited result; document streaming or iterator behavior
when applicable. State when a function returns no value.

Write a useful docstring or documentation comment for every function. In Python,
use Google-style docstrings. Explain:

- What the function does and the core purpose it serves.
- Where it is used: its caller or workflow, when to call it, and what the caller
  must have done first. Refer to actual code or the example being shown; do not
  invent callers or claim a function is deployed when it is not.
- What each argument means, including units, valid values, defaults, ownership,
  or mutation when those affect use. Repeating the parameter name or type is
  insufficient.
- What the return value represents, including units, shape, ordering, rounding,
  missing-result behavior, or whether it is a new or shared object as applicable.
- Relevant errors and side effects, such as writes, network requests, state
  changes, resource lifetime, or partial work before failure.

Use `Args:`, `Returns:` or `Yields:`, and `Raises:` where applicable. Scale detail
to the function; a short helper needs less explanation than a storage adapter.
Document behavior a caller needs to rely on, and keep it consistent with the
implementation. Avoid comments that merely restate individual lines of code.

## Explain the execution flow in the function itself

For every function you create or change, write enough documentation for the user
to follow it without reconstructing its callers and state from the implementation.
Use plain language and the same concrete names as the code. A one-line summary
such as "run the workflow" or "handle the response" is insufficient when the
function coordinates several operations.

For orchestration, asynchronous work, loops, and functions that mutate state,
explain the applicable parts of the flow in the docstring before the argument
sections.

- Say whether one call performs a single operation or runs the entire workflow.
- Identify where the initial input comes from and what happens only on the first
  iteration. Explain what supplies the input for subsequent iterations.
- Follow the main path in execution order. Name what is sent, what is received,
  where the result is stored, and which operation uses it next.
- Explain what an awaited call waits for and what happens when it completes.
- Describe state carried between iterations or calls, including when it resets.
- State the conditions that return, stop the loop, or raise an error. Explain
  consequential meanings of empty strings, null values, and missing results.
- Include a short concrete example when values changing over time are central
  to understanding the function.

Use variable names that show purpose and direction, such as
`outgoing_user_message`, `developer_message`, and `send_command`. Add brief
comments at transitions that are easy to miss, such as initializing the first
message before a loop or replacing it with a generated reply at the loop's end.
For a validator, identify exactly what it checks and where its input comes from.
A reader should be able to distinguish validating an outgoing command from
checking an incoming question.

For example, the conversation function's docstring can explain its behavior this
way, using illustrative messages.

> Run the whole conversation, starting with the project brief.
>
> The first outgoing message is the text from instruction.md. After sending it,
> wait for the developer to finish its turn and return a reply. Store that reply
> in developer_message so message() can generate the user's answer. That answer
> becomes the outgoing message on the next loop iteration.
>
> For example, send "Build Orange", receive "Who owns an unassigned handoff?",
> then send "Release Coordination". The project brief is assigned before the
> loop, so it is sent only once in this conversation.
>
> An empty developer reply ends the conversation. An empty answer from message()
> also ends the conversation. Every exchange uses the same developer session.

Apply this level of clarity across languages. Match the detail to the actual
function. A small calculation may need only its purpose, input meanings, and a
concrete result. Describe the behavior the code implements and keep the example
consistent with it.

## Example: weak and useful docstrings

This docstring repeats the signature without explaining what the values mean or
where the calculation belongs:

```python
def discounted_subtotal(subtotal_cents: int, discount_percent: int) -> int:
    """Calculate the result.

    Args:
        subtotal_cents: The subtotal.
        discount_percent: The discount.

    Returns:
        The result.
    """
    if subtotal_cents < 0 or not 0 <= discount_percent <= 100:
        raise ValueError("Invalid subtotal or discount")
    return subtotal_cents * (100 - discount_percent) // 100
```

The same function with a useful contract explains its purpose, the caller's use,
and the meaning of its inputs and output:

```python
def discounted_subtotal(subtotal_cents: int, discount_percent: int) -> int:
    """Apply a percentage discount to an order's merchandise subtotal.

    Called by price_order when preparing a checkout quote, before adding any
    delivery fee. The caller supplies a subtotal already calculated from item
    prices and quantities. This function performs no I/O and changes no state.

    Args:
        subtotal_cents: Merchandise cost in whole cents, excluding delivery.
            Must be nonnegative; zero represents an order with no item cost.
        discount_percent: Whole percentage to deduct, from 0 through 100
            inclusive. For example, 15 means a fifteen-percent discount.

    Returns:
        Discounted merchandise cost in whole cents. Fractional cents are
        rounded down. A zero-percent discount preserves the subtotal; a
        hundred-percent discount returns zero.

    Raises:
        ValueError: The subtotal is negative or the percentage is outside
            the inclusive range 0 to 100.
    """
    if subtotal_cents < 0 or not 0 <= discount_percent <= 100:
        raise ValueError("Invalid subtotal or discount")
    return subtotal_cents * (100 - discount_percent) // 100
```

The docstring describes the same behavior as the weak version. Its extra detail
lets a caller decide whether the function is appropriate without reverse
engineering the calculation. In another language, express this contract through
that language's documentation format.

## Keep domain logic separate from side effects

Prefer pure functions for calculations, validation, and transformations: accept
explicit inputs, return explicit results, and avoid hidden reads or mutations.
Keep parsing, filesystem operations, database access, network calls, and process
execution in adapters. Use a small orchestration function to connect them when
needed. Classes are appropriate for coherent state and resource ownership.

Group functions and modules by responsibility and dependency boundaries. A
function should have one understandable purpose. Avoid mode flags that select
unrelated workflows, repeated policy branches, and deeply nested code that mixes
business decisions with effects. Ordinary conditionals are appropriate for real
choices and validation; reducing branch count is not itself a design objective.

### Poor structure: branching across unrelated responsibilities

This routine parses input, selects an operation, calculates prices, and writes
files. The pricing branches are duplicated across quote and save paths, so a
policy change must be applied in several places. Error handling is unclear, and
pricing cannot be tested independently of the input format.

```python
import json
from pathlib import Path


def handle_order(raw: str, mode: str, destination: Path) -> int:
    """Handle an order."""
    data = json.loads(raw)
    if mode == "quote":
        if data["fulfillment"] == "delivery":
            if data["member"]:
                return data["subtotal_cents"] * 90 // 100 + 500
            else:
                return data["subtotal_cents"] + 500
        else:
            if data["member"]:
                return data["subtotal_cents"] * 90 // 100
            else:
                return data["subtotal_cents"]
    elif mode == "save":
        if data["fulfillment"] == "delivery":
            if data["member"]:
                total = data["subtotal_cents"] * 90 // 100 + 500
            else:
                total = data["subtotal_cents"] + 500
        else:
            if data["member"]:
                total = data["subtotal_cents"] * 90 // 100
            else:
                total = data["subtotal_cents"]
        destination.write_text(json.dumps({"total_cents": total}))
        return total
    else:
        return -1
```

### Better structure: one pricing rule with a separate output adapter

Here the caller parses and validates external input into typed values. Pricing
has one implementation and takes its policy explicitly. Saving the quote is a
separate operation. This example uses `discounted_subtotal` from the useful
example above. It illustrates a design improvement, not a drop-in refactor: it
also rejects invalid fulfillment values and negative delivery fees that the
poor example does not handle properly.

```python
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class PricingPolicy:
    """Trusted checkout settings: a whole-percent discount and a fee in cents."""

    member_discount_percent: int
    delivery_fee_cents: int


def price_order(
    subtotal_cents: int,
    fulfillment: Literal["pickup", "delivery"],
    is_member: bool,
    policy: PricingPolicy,
) -> int:
    """Calculate the checkout quote from merchandise, membership, and delivery.

    Used by the checkout handler after parsing an order. Both a displayed quote
    and a saved quote use this calculation. The function performs no I/O; the
    handler decides whether to pass its result to save_quote.

    Args:
        subtotal_cents: Nonnegative merchandise cost in whole cents before
            discounts and delivery fees.
        fulfillment: Whether the customer collects the order or receives
            delivery. Only delivery adds the configured fee.
        is_member: Whether the caller has established eligibility for the
            membership discount.
        policy: Trusted pricing settings with a discount from 0 through 100
            and a nonnegative delivery fee. The function does not modify it.

    Returns:
        Total payable in whole cents, with any merchandise discount rounded
        down before adding the delivery fee. The fee itself is not discounted.

    Raises:
        ValueError: The subtotal, fulfillment, or pricing policy is invalid.
    """
    if fulfillment not in ("pickup", "delivery"):
        raise ValueError("Unknown fulfillment method")
    if policy.delivery_fee_cents < 0:
        raise ValueError("Delivery fee must be nonnegative")
    if not 0 <= policy.member_discount_percent <= 100:
        raise ValueError("Membership discount must be between 0 and 100")
    discount = policy.member_discount_percent if is_member else 0
    merchandise_cents = discounted_subtotal(subtotal_cents, discount)
    delivery_cents = policy.delivery_fee_cents if fulfillment == "delivery" else 0
    return merchandise_cents + delivery_cents


def save_quote(destination: Path, total_cents: int) -> None:
    """Write a calculated checkout quote to a JSON file.

    Called by the checkout handler when the user requests a saved quote, after
    price_order succeeds. It overwrites destination; its parent directory must
    already exist. This simple adapter does not provide atomic replacement.

    Args:
        destination: File to receive UTF-8 JSON containing a total_cents field.
        total_cents: Nonnegative payable amount returned by price_order, in
            whole cents. This adapter does not recalculate prices.

    Returns:
        None. The result is the file written at destination.

    Raises:
        ValueError: The supplied total is negative; no file is written.
        OSError: The file cannot be written. A write failure may leave a
            truncated or partially written file.
    """
    if total_cents < 0:
        raise ValueError("Quote total must be nonnegative")
    destination.write_text(json.dumps({"total_cents": total_cents}), encoding="utf-8")
```

For example, a handler can call `price_order(2500, "delivery", True, policy)`
with `PricingPolicy(member_discount_percent=10, delivery_fee_cents=500)` to get
`2750` cents. It can display that value or call `save_quote` with it. Pricing tests
need no files, JSON payloads, or network services; adapter tests cover file output.
The policy values are illustrative, not defaults for other applications.

Keep helpers together when they serve one responsibility. Split modules when
domain logic, external-service clients, or reporting need distinct boundaries.
Avoid one-function files without a reason, generic utility dumping grounds,
circular imports, and sibling-test imports. Keep shared contracts below their
callers and preserve public interfaces when refactoring within the requested
scope. Do not turn a simple workflow into an inheritance or plugin framework.

## Configure policy and verify behavior

Put tunable weights, budgets, and thresholds in explicit configuration. Parse
external settings once into typed values and validate finite numbers, ranges,
and relationships. Pass settings into functions instead of reading environment
variables or mutable global state inside calculations. Preserve fixed task
invariants and keep evaluation configuration trusted.

Run relevant existing checks. Test domain behavior, boundary values, failure
handling, and adapter effects separately. When refactoring, preserve behavior
unless the user requested a change; describe any intentional change. Update all
callers and resource paths, and validate packaged execution when paths change.
Do not add a checker merely to satisfy this skill.

For a v2 verifier or oracle, also use the repository's
[verifier and oracle contracts](../multi-turn-task-structure/SKILL.md). This additional
routing does not limit the skill's application to other code or languages.
