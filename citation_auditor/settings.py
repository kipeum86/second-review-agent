from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AuditSettings(BaseModel):
    """Deterministic runtime settings for the CC-native utility layer."""

    model_config = ConfigDict(extra="ignore")

    max_chunk_tokens: int = Field(default=3000, ge=1)
