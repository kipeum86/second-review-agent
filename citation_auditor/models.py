from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClaimType(str, Enum):
    FACTUAL = "factual"
    CITATION = "citation"
    QUANTITATIVE = "quantitative"
    TEMPORAL = "temporal"
    OTHER = "other"


class VerdictLabel(str, Enum):
    VERIFIED = "verified"
    CONTRADICTED = "contradicted"
    UNKNOWN = "unknown"


class SentenceSpan(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_bounds(self) -> "SentenceSpan":
        if self.end < self.start:
            raise ValueError("sentence_span.end must be greater than or equal to sentence_span.start")
        return self

    @property
    def length(self) -> int:
        return max(0, self.end - self.start)


class Claim(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=1)
    sentence_span: SentenceSpan
    claim_type: ClaimType
    suggested_verifier: str | None = None


class ClaimList(BaseModel):
    claims: list[Claim] = Field(default_factory=list)


class Evidence(BaseModel):
    url: str = Field(min_length=1)
    title: str | None = None
    snippet: str | None = None
    extracted_text: str | None = None


class Verdict(BaseModel):
    claim: Claim
    label: VerdictLabel
    verifier_name: str
    authority: float = Field(ge=0.0, le=1.0)
    rationale: str
    evidence: list[Evidence] = Field(default_factory=list)


class ChunkSegmentPayload(BaseModel):
    chunk_start: int = Field(ge=0)
    chunk_end: int = Field(ge=0)
    document_start: int = Field(ge=0)
    document_end: int = Field(ge=0)


class ChunkPayload(BaseModel):
    index: int = Field(ge=0)
    text: str
    segments: list[ChunkSegmentPayload] = Field(default_factory=list)


class ChunkOutput(BaseModel):
    chunks: list[ChunkPayload] = Field(default_factory=list)


class AggregateVerdictBundle(BaseModel):
    chunk: ChunkPayload
    claim: Claim
    candidates: list[Verdict] = Field(default_factory=list)


class AggregateInput(BaseModel):
    verdicts: list[AggregateVerdictBundle] = Field(default_factory=list)


class AggregatedVerdict(BaseModel):
    claim: Claim
    verdict: Verdict


class AggregateOutput(BaseModel):
    aggregated: list[AggregatedVerdict] = Field(default_factory=list)
