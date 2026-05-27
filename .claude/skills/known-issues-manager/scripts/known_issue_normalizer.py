#!/usr/bin/env python3
"""Normalization helpers for Known Issues matching metadata."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

SCHEMA_VERSION_V2 = 2
ANY_DOCUMENT_TYPE = "*"
UNKNOWN_SIGNATURE_PART = "unknown"
MAX_KEYWORDS = 8
DEFAULT_EXAMPLES_MAX = 3

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
}


def normalize_text(value: Any) -> str:
    """Return a stable lowercase text form for similarity comparisons."""
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = re.sub(r"[^\w\s가-힣]", " ", text, flags=re.UNICODE)
    text = re.sub(r"_+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def slugify(value: Any, *, default: str = UNKNOWN_SIGNATURE_PART) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    if not text:
        return default
    text = re.sub(r"[^\w\s가-힣-]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_-")
    text = re.sub(r"[^0-9a-z가-힣_-]+", "", text)
    return text or default


def normalize_document_type(value: Any) -> str:
    if value is None or str(value).strip() == "":
        return ANY_DOCUMENT_TYPE
    return slugify(value)


def parse_dimension(value: Any) -> int | None:
    if isinstance(value, int):
        return value if 1 <= value <= 7 else None
    text = str(value or "")
    match = re.search(r"(?:dimension|dim|d)?\s*([1-7])\b|([1-7])_", text, re.IGNORECASE)
    if match:
        return int(match.group(1) or match.group(2))
    return None


def extract_keywords(value: Any, *, max_keywords: int = MAX_KEYWORDS) -> list[str]:
    normalized = normalize_text(value)
    if not normalized:
        return []

    keywords: list[str] = []
    seen: set[str] = set()
    for token in normalized.split():
        if token in STOPWORDS or len(token) < 2:
            continue
        if token in seen:
            continue
        seen.add(token)
        keywords.append(token)
        if len(keywords) >= max_keywords:
            break
    return keywords


def keyword_overlap(left: list[str], right: list[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def example_limit(entry: dict[str, Any], *, default_max: int = DEFAULT_EXAMPLES_MAX) -> int:
    raw = entry.get("examples_max", default_max)
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        limit = default_max
    return max(0, limit)


def cap_examples(entry: dict[str, Any], *, default_max: int = DEFAULT_EXAMPLES_MAX) -> tuple[dict[str, Any], int]:
    """Return a copy with examples capped and the number of trimmed examples."""
    normalized = dict(entry)
    examples = normalized.get("examples")
    if not isinstance(examples, list):
        normalized.setdefault("examples_max", default_max)
        return normalized, 0

    limit = example_limit(normalized, default_max=default_max)
    trimmed = max(0, len(examples) - limit)
    normalized["examples"] = examples[:limit]
    normalized.setdefault("examples_max", limit)
    return normalized, trimmed


def infer_defect_type(payload: dict[str, Any]) -> str | None:
    for key in ("defect_type", "finding_type", "check_id", "category"):
        value = payload.get(key)
        if value:
            return slugify(value)

    evidence = payload.get("evidence")
    if isinstance(evidence, dict):
        for key in ("defect_type", "finding_type", "check_id", "category"):
            value = evidence.get(key)
            if value:
                return slugify(value)

    return None


def build_match_signature(
    *,
    agent: str,
    dimension: int | None,
    document_type: str | None = None,
    defect_type: str | None = None,
    keywords: list[str] | None = None,
) -> str:
    agent_part = slugify(agent, default="unknown_agent")
    dimension_part = f"d{dimension}" if dimension is not None else "d0"
    document_part = normalize_document_type(document_type)

    if defect_type:
        match_part = slugify(defect_type)
    else:
        keyword_part = "_".join((keywords or [])[:4])
        match_part = f"kw:{keyword_part or UNKNOWN_SIGNATURE_PART}"

    return "|".join([agent_part, dimension_part, document_part, match_part])


def normalize_pattern_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a registry entry enriched with v2 matching metadata."""
    normalized = dict(entry)
    agent = str(normalized.get("agent") or "")
    dimension = parse_dimension(normalized.get("dimension"))
    document_type = normalize_document_type(normalized.get("document_type"))
    defect_type = infer_defect_type(normalized)
    pattern_normalized = normalize_text(normalized.get("pattern"))
    keywords = list(normalized.get("keywords") or extract_keywords(normalized.get("pattern")))
    match_signature = normalized.get("match_signature") or build_match_signature(
        agent=agent,
        dimension=dimension,
        document_type=document_type,
        defect_type=defect_type,
        keywords=keywords,
    )

    normalized.setdefault("schema_version", SCHEMA_VERSION_V2)
    normalized["document_type"] = document_type
    normalized["dimension"] = dimension
    if defect_type:
        normalized["defect_type"] = defect_type
    normalized["pattern_normalized"] = pattern_normalized
    normalized["keywords"] = keywords
    normalized["match_signature"] = match_signature
    normalized, _trimmed = cap_examples(normalized)
    return normalized


def normalize_finding(
    finding: dict[str, Any],
    *,
    agent: str,
    document_type: str | None = None,
) -> dict[str, Any]:
    """Return normalized matching fields for one issue-registry finding."""
    dimension = parse_dimension(finding.get("dimension"))
    resolved_document_type = normalize_document_type(
        finding.get("document_type") or document_type
    )
    defect_type = infer_defect_type(finding)
    description = finding.get("description") or finding.get("title") or ""
    keywords = extract_keywords(description)
    signature = build_match_signature(
        agent=agent,
        dimension=dimension,
        document_type=resolved_document_type,
        defect_type=defect_type,
        keywords=keywords,
    )
    return {
        "agent": slugify(agent, default="unknown_agent"),
        "dimension": dimension,
        "document_type": resolved_document_type,
        "defect_type": defect_type,
        "description_normalized": normalize_text(description),
        "keywords": keywords,
        "match_signature": signature,
    }
