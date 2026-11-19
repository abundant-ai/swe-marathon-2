"""Load the application's public resource configuration and operating limits."""

from pathlib import Path

from openai.types.shared import ReasoningEffort
from pydantic import BaseModel, ConfigDict, Field, model_validator

# Deliberately fixed by the baseline request, including the RRF denominator.
TOP_K = 20
RRF_K = 20


class Settings(BaseModel):
    """Nonsecret baseline policy, installed alongside the application."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    resources_path: Path
    chunk_chars: int = Field(gt=0)
    chunk_overlap: int = Field(ge=0)
    ingest_batch_size: int = Field(gt=0)
    max_search_rounds: int = Field(gt=0)
    max_tool_calls: int = Field(gt=0)
    question_timeout_seconds: float = Field(gt=0, le=1800)
    request_timeout_seconds: float = Field(gt=0)
    max_output_tokens: int = Field(gt=0)
    reasoning_effort: ReasoningEffort
    output_retries: int = Field(ge=0)
    transport_retries: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_overlap(self) -> "Settings":
        """Reject chunks that cannot advance through the document.

        Returns:
            This immutable configuration when the stride is positive.

        Raises:
            ValueError: Overlap is at least the chunk size.
        """
        if self.chunk_overlap >= self.chunk_chars:
            raise ValueError("chunk_overlap must be smaller than chunk_chars")
        return self


class GenerationResource(BaseModel):
    """The public Responses API endpoint, model, and credential variable name."""

    model: str
    base_url: str
    credential_env: str


class Resources(BaseModel):
    """The subset of the supplied resource manifest used by generation."""

    generation: GenerationResource


def load_settings(app_root: Path) -> Settings:
    """Read the installed baseline policy before an application operation.

    Args:
        app_root: Workspace containing oracle-config.json.

    Returns:
        Validated nonsecret runtime settings; no environment policy defaults.
    """
    return Settings.model_validate_json((app_root / "oracle-config.json").read_text())
