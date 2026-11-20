"""Optional remote tracing for author experiments; never persist trajectories."""

from __future__ import annotations

import os
from contextlib import nullcontext
from typing import Any, ContextManager

_enabled = False


def configure() -> None:
    """Enable remote-only Logfire export when the caller explicitly requests it.

    LOGFIRE_SERVICE_NAME selects the experiment. A token and the optional logfire
    package must already be available; neither is installed or discovered here.
    PydanticAI instrumentation exports model/tool spans alongside application
    spans. With no service name this function has no side effects.
    """
    global _enabled
    service = os.environ.get("LOGFIRE_SERVICE_NAME")
    if not service:
        return
    if not os.environ.get("LOGFIRE_TOKEN"):
        raise RuntimeError("Requested tracing requires LOGFIRE_TOKEN")
    import logfire

    logfire.configure(service_name=service, environment="development", console=False,
                      send_to_logfire=True)
    logfire.instrument_pydantic_ai()
    _enabled = True


def span(name: str, **attributes: Any) -> ContextManager[Any]:
    """Create a remote span, or a no-op when author tracing is disabled.

    Args:
        name: Stable operation name, without credential values.
        attributes: Public question, evidence, or model output; never HTTP headers.

    Returns:
        Context manager inheriting the current question's trace.
    """
    if not _enabled:
        return nullcontext()
    import logfire

    return logfire.span(name, **attributes)


def flush() -> None:
    """Finish exporting queued spans before the CLI process exits.

    Raises:
        RuntimeError: Telemetry cannot be flushed within 30 seconds.
    """
    if _enabled:
        import logfire

        if not logfire.force_flush(timeout_millis=30000):
            raise RuntimeError("Logfire export did not flush")
