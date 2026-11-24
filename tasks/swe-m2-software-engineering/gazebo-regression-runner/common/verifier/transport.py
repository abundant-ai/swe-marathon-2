"""Choose the least privileged process identity for isolated regression calls."""

import os
import pwd


class Violation(Exception):
    """An observable report did not meet the published behavior."""


def require(condition: bool,message: str) -> None:
    """Stop an independent case with a precise failure cause."""
    if not condition:
        raise Violation(message)


def identity() -> dict:
    """Run candidate code without access to root verifier output."""
    if os.geteuid()!=0:
        return {}
    try:
        user=pwd.getpwnam("candidate")
    except KeyError:
        user=pwd.getpwnam("nobody")
    return {"user":user.pw_uid,"group":user.pw_gid,"extra_groups":[]}
