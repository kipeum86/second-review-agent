"""citation_auditor package."""

from citation_auditor.aggregation import aggregate_verdicts
from citation_auditor.chunking import chunk_markdown, dedupe_claims
from citation_auditor.models import (
    AggregateInput,
    AggregateOutput,
    AggregatedVerdict,
    Claim,
    ClaimList,
    ClaimType,
    ChunkOutput,
    ChunkPayload,
    ChunkSegmentPayload,
    Evidence,
    SentenceSpan,
    Verdict,
    VerdictLabel,
)
from citation_auditor.render import render_markdown
from citation_auditor.settings import AuditSettings

__all__ = [
    "AggregateInput",
    "AggregateOutput",
    "AggregatedVerdict",
    "AuditSettings",
    "Claim",
    "ClaimList",
    "ClaimType",
    "ChunkOutput",
    "ChunkPayload",
    "ChunkSegmentPayload",
    "Evidence",
    "SentenceSpan",
    "Verdict",
    "VerdictLabel",
    "aggregate_verdicts",
    "chunk_markdown",
    "dedupe_claims",
    "render_markdown",
]

__version__ = "0.1.0"

