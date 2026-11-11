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
