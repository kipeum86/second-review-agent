#!/usr/bin/env python3
"""
Adapt citation-auditor verdicts into the canonical citation-checker schema.

Usage:
    python3 adapt-citation-auditor.py \
        --citation-list working/citation-list.json \
        --auditor-results working/citation-auditor-shadow.json \
        --output working/citation-auditor-adapted.json

The adapter is intentionally conservative. A bare `contradicted` label is not
enough to create a Critical status; it needs a reason_code or a high-confidence
reason inferred from the verifier rationale.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from urllib.parse import urlparse

_SHARED_SCRIPTS = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "scripts")
)
if _SHARED_SCRIPTS not in sys.path:
    sys.path.insert(0, _SHARED_SCRIPTS)

from sanitize_fetch import sanitize_evidence  # noqa: E402


PRIMARY_VERIFIERS = {"korean-law", "us-law", "eu-law", "uk-law"}
LOW_TRUST_VERIFIERS = {"general-web", "wikipedia"}

AUTHORITY_TIER_BY_VERIFIER = {
    "korean-law": (1, "Primary Law"),
    "us-law": (1, "Primary Law"),
    "eu-law": (1, "Primary Law"),
    "uk-law": (1, "Primary Law"),
    "scholarly": (3, "Secondary"),
    "general-web": (4, "Tertiary / Low-Reliability"),
    "wikipedia": (4, "Tertiary / Low-Reliability"),
}

STATUS_BY_REASON_CODE = {
    "primary_supports_claim": "Verified",
    "secondary_only": "Unverifiable_Secondary_Only",
    "nonexistent_authority": "Nonexistent",
    "wrong_pinpoint": "Wrong_Pinpoint",
    "unsupported_proposition": "Unsupported_Proposition",
    "wrong_jurisdiction": "Wrong_Jurisdiction",
    "stale_or_superseded": "Stale",
    "translation_mismatch": "Translation_Mismatch",
    "no_access": "Unverifiable_No_Access",
    "no_evidence": "Unverifiable_No_Evidence",
}

ALLOWED_ENFORCE_SCOPES = {
    "kr_statute_article_exists",
    "kr_statute_pinpoint_exists",
    "us_code_section_exists",
    "us_cfr_section_exists",
    "eu_celex_exists",
    "eu_article_exists",
    "uk_legislation_section_exists",
}


def load_json(path: str) -> object:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str, payload: object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def normalize_space(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_key(value: object) -> str:
    return re.sub(r"[\W_]+", "", normalize_space(value).lower())


def load_citation_entries(payload: object) -> tuple[list[dict], str]:
    if isinstance(payload, dict):
        citations = payload.get("citations", [])
        review_depth = payload.get("review_depth", "standard")
    elif isinstance(payload, list):
        citations = payload
        review_depth = "standard"
    else:
        citations = []
        review_depth = "standard"

    normalized = []
    for idx, raw in enumerate(citations, 1):
        if not isinstance(raw, dict):
            continue
        entry = deepcopy(raw)
        entry.setdefault("citation_id", f"CIT-{idx:03d}")
        entry.setdefault("citation_text", entry.get("claim_text") or entry.get("text") or "")
        entry.setdefault("citation_type", "source")
        entry.setdefault("location", {})
        entry.setdefault("claimed_content", entry.get("citation_text", ""))
        normalized.append(entry)
    return normalized, str(review_depth or "standard")


def extract_auditor_records(payload: object) -> list[dict]:
    if isinstance(payload, list):
        records = []
        for item in payload:
            records.extend(extract_auditor_records(item))
        return records

    if not isinstance(payload, dict):
        return []

    if "aggregated" in payload and isinstance(payload["aggregated"], list):
        records = []
        for item in payload["aggregated"]:
            if not isinstance(item, dict):
                continue
            verdict = item.get("verdict") or {}
            claim = item.get("claim") or verdict.get("claim") or {}
            records.append(build_record(item, verdict, claim))
        return records

    if "citations" in payload and isinstance(payload["citations"], list):
        records = []
        for item in payload["citations"]:
            if not isinstance(item, dict):
                continue
            verdict = (
                item.get("auditor_verdict")
                or item.get("auditor_result")
                or item.get("verdict")
                or item
            )
            claim = item.get("claim") or verdict.get("claim") or {"text": item.get("claimed_content") or item.get("citation_text")}
            records.append(build_record(item, verdict, claim))
        return records

    if "verdict" in payload or "auditor_verdict" in payload or "label" in payload:
        verdict = payload.get("auditor_verdict") or payload.get("verdict") or payload
        claim = payload.get("claim") or verdict.get("claim") or {"text": payload.get("claimed_content") or payload.get("citation_text")}
        return [build_record(payload, verdict, claim)]

    return []


def build_record(container: dict, verdict: dict, claim: dict) -> dict:
    supporting_urls = list(verdict.get("supporting_urls") or container.get("supporting_urls") or [])
    evidence = verdict.get("evidence") or container.get("evidence") or []
    if isinstance(evidence, dict):
        evidence = [evidence]
    for item in evidence:
        if isinstance(item, dict) and item.get("url"):
            supporting_urls.append(item["url"])

    return {
        "citation_id": container.get("citation_id") or verdict.get("citation_id"),
        "citation_text": container.get("citation_text") or verdict.get("citation_text"),
        "claim_text": (claim or {}).get("text") or container.get("claimed_content") or container.get("citation_text") or "",
        "label": str(verdict.get("label") or container.get("label") or "unknown").lower(),
        "verifier_name": verdict.get("verifier_name") or container.get("verifier_name") or (claim or {}).get("suggested_verifier") or "unknown",
        "authority": verdict.get("authority", container.get("authority")),
        "rationale": verdict.get("rationale") or container.get("rationale") or "",
        "supporting_urls": dedupe_preserve_order(supporting_urls),
        "reason_code": verdict.get("reason_code") or container.get("reason_code"),
        "reason_confidence": verdict.get("reason_confidence") or container.get("reason_confidence"),
        "source_scope": verdict.get("source_scope") or container.get("source_scope"),
        "enforceable": verdict.get("enforceable", container.get("enforceable")),
    }


def dedupe_preserve_order(values: list[object]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        text = normalize_space(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def find_best_citation(record: dict, citations: list[dict], used_ids: set[str]) -> tuple[dict | None, int]:
    record_id = record.get("citation_id")
    if record_id:
        for citation in citations:
            if citation.get("citation_id") == record_id:
                return citation, 100

    claim_key = normalize_key(record.get("claim_text"))
    record_citation_key = normalize_key(record.get("citation_text"))
    best = None
    best_score = 0

    for citation in citations:
        citation_id = citation.get("citation_id", "")
        citation_key = normalize_key(citation.get("citation_text"))
        claimed_key = normalize_key(citation.get("claimed_content"))

        score = 0
        if record_citation_key and record_citation_key == citation_key:
            score = max(score, 90)
        if citation_key and claim_key and citation_key in claim_key:
            score = max(score, 80)
        if record_citation_key and claimed_key and record_citation_key in claimed_key:
            score = max(score, 75)
        if claim_key and claimed_key and (claim_key in claimed_key or claimed_key in claim_key):
            score = max(score, 70)
        if citation_id in used_ids and score < 90:
            score -= 20
        if score > best_score:
            best = citation
            best_score = score

    if best_score < 60:
        return None, best_score
    return best, best_score


def infer_reason_code(record: dict) -> tuple[str, str]:
    explicit = normalize_space(record.get("reason_code")).lower()
    if explicit:
        return explicit, normalize_space(record.get("reason_confidence")) or "explicit"

    label = record.get("label")
    verifier = record.get("verifier_name")
    rationale = normalize_space(record.get("rationale")).lower()

    if label == "verified":
        if verifier in LOW_TRUST_VERIFIERS:
            return "secondary_only", "inferred"
        return "primary_supports_claim", "inferred"

    if label == "unknown":
        if "원문 조회 실패" in rationale or "no access" in rationale or "network" in rationale or "paywall" in rationale:
            return "no_access", "inferred"
        if "secondary" in rationale or "2차" in rationale:
            return "secondary_only", "inferred"
        return "no_evidence", "inferred"

    if label == "contradicted":
        if any(token in rationale for token in ("번역", "translation")):
            return "translation_mismatch", "inferred"
        if any(token in rationale for token in ("폐지", "개정", "superseded", "repealed", "amended", "stale")):
            return "stale_or_superseded", "inferred"
        if "jurisdiction" in rationale or "관할" in rationale:
            return "wrong_jurisdiction", "inferred"
        if any(token in rationale for token in ("항은 존재하지", "호는 존재하지", "조문은 확인되지만", "wrong pinpoint", "pinpoint", "article exists")):
            return "wrong_pinpoint", "inferred"
        if any(token in rationale for token in ("주장과 다", "support", "holding", "판시", "쟁점이 주장과")):
            return "unsupported_proposition", "inferred"
        if any(token in rationale for token in ("존재하지", "찾을 수 없습니다", "not found", "no match", "does not exist", "404")):
            return "nonexistent_authority", "inferred"
        return "no_evidence", "inferred"

    return "no_evidence", "inferred"


def status_for_record(record: dict, reason_code: str) -> str:
    status = STATUS_BY_REASON_CODE.get(reason_code, "Unverifiable_No_Evidence")
    if record.get("label") == "contradicted" and reason_code == "no_evidence":
        return "Unverifiable_No_Evidence"
    if status == "Nonexistent" and not has_positive_nonexistence_evidence(record):
        return "Unverifiable_No_Evidence"
    return status


def has_positive_nonexistence_evidence(record: dict) -> bool:
    if record.get("positive_nonexistence_evidence") is True:
        return True
    rationale = normalize_space(record.get("rationale")).lower()
    if record.get("supporting_urls"):
        return True
    return any(token in rationale for token in ("db", "database", "no match", "not found", "찾을 수 없습니다", "존재하지", "404"))


def authority_for_record(record: dict) -> tuple[int, str]:
    verifier = record.get("verifier_name")
    tier = record.get("authority_tier")
    label = record.get("authority_label")
    if isinstance(tier, int) and tier in (1, 2, 3, 4):
        return tier, label or authority_label(tier)
    return AUTHORITY_TIER_BY_VERIFIER.get(verifier, (4, "Tertiary / Low-Reliability"))


def authority_label(tier: int) -> str:
    return {
        1: "Primary Law",
        2: "Authoritative Secondary",
        3: "Secondary",
        4: "Tertiary / Low-Reliability",
    }[tier]


def normalize_reference(value: str) -> tuple[str | None, str | None]:
    text = normalize_space(value)
    if not text:
        return None, None
    if text.startswith(("http://", "https://")):
        return text, None
    if " " not in text and "." in text.split("/")[0]:
        return f"https://{text}", None
    return None, text


def build_evidence(record: dict, reason_code: str) -> dict:
    urls = []
    references = []
    for raw in record.get("supporting_urls", []):
        url, reference = normalize_reference(raw)
        if url:
            urls.append(url)
        elif reference:
            references.append(reference)

    evidence = {
        "url": urls[0] if urls else None,
        "search_query": None,
        "excerpt": normalize_space(record.get("rationale")),
        "auditor_verifier": record.get("verifier_name"),
        "auditor_label": record.get("label"),
        "auditor_reason_code": reason_code,
    }
    if references:
        evidence["source_reference"] = "; ".join(references)
    if len(urls) > 1:
        evidence["additional_urls"] = urls[1:]

    sanitized, audit = sanitize_evidence(evidence)
    sanitized["sanitize_audit"] = audit
    return sanitized


def derive_enforce_scope(citation: dict, record: dict, reason_code: str) -> str | None:
    verifier = record.get("verifier_name")
    citation_type = citation.get("citation_type")
    text = f"{citation.get('citation_text', '')} {citation.get('claimed_content', '')}"

    if verifier == "korean-law" and citation_type == "statute":
        if reason_code in {"wrong_pinpoint", "nonexistent_authority"} and re.search(r"제\s*\d+\s*(?:항|호)", text):
            return "kr_statute_pinpoint_exists"
        return "kr_statute_article_exists"
    if verifier == "us-law" and citation_type == "statute":
        return "us_code_section_exists"
    if verifier == "us-law" and citation_type == "regulation":
        return "us_cfr_section_exists"
    if verifier == "eu-law":
        if reason_code == "wrong_pinpoint":
            return "eu_article_exists"
        return "eu_celex_exists"
    if verifier == "uk-law" and citation_type in {"statute", "regulation"}:
        return "uk_legislation_section_exists"
    return None


def is_enforceable(record: dict, citation: dict, status: str, reason_code: str) -> bool:
    explicit = record.get("enforceable")
    if explicit is False:
        return False

    scope = derive_enforce_scope(citation, record, reason_code)
    if scope not in ALLOWED_ENFORCE_SCOPES:
        return False
    if status == "Nonexistent" and not has_positive_nonexistence_evidence(record):
        return False
    if record.get("verifier_name") not in PRIMARY_VERIFIERS:
        return False
    if status in {"Verified", "Nonexistent", "Wrong_Pinpoint"}:
        return True if explicit is None else bool(explicit)
    return False


def adapt_record(record: dict, citation: dict, match_score: int, unmatched_index: int | None = None) -> dict:
    reason_code, reason_confidence = infer_reason_code(record)
    status = status_for_record(record, reason_code)
    tier, tier_label = authority_for_record(record)
    evidence = build_evidence(record, reason_code)
    enforce_scope = derive_enforce_scope(citation, record, reason_code)
    enforceable = is_enforceable(record, citation, status, reason_code)

    adapted = {
        "citation_id": citation.get("citation_id") or f"AUD-{unmatched_index:03d}",
        "citation_text": citation.get("citation_text") or record.get("citation_text") or record.get("claim_text"),
        "citation_type": citation.get("citation_type") or "source",
        "jurisdiction": citation.get("jurisdiction"),
        "location": citation.get("location") or {},
        "claimed_content": citation.get("claimed_content") or record.get("claim_text"),
        "verification_method": f"citation_auditor:{record.get('verifier_name')}",
        "verification_status": status,
        "authority_tier": tier,
        "authority_label": tier_label,
        "authority_note": f"Adapted from citation-auditor verifier `{record.get('verifier_name')}`.",
        "supports_conclusion": citation.get("supports_conclusion", True),
        "conclusion_location": citation.get("conclusion_location") or citation.get("location") or {},
        "evidence": evidence,
        "confidence": "high" if reason_confidence == "explicit" and record.get("label") != "unknown" else "medium",
        "notes": normalize_space(record.get("rationale")),
        "auditor": {
            "label": record.get("label"),
            "verifier_name": record.get("verifier_name"),
            "authority": record.get("authority"),
            "reason_code": reason_code,
            "reason_confidence": reason_confidence,
            "source_scope": record.get("source_scope"),
            "match_score": match_score,
            "enforce_scope": enforce_scope,
            "enforceable": enforceable,
            "positive_nonexistence_evidence": has_positive_nonexistence_evidence(record)
            if status == "Nonexistent" or reason_code == "nonexistent_authority"
            else None,
        },
    }
    if unmatched_index is not None:
        adapted["auditor"]["unmatched"] = True
    return adapted


def adapt(citation_payload: object, auditor_payload: object, review_depth_override: str | None = None) -> dict:
    citations, review_depth = load_citation_entries(citation_payload)
    if review_depth_override:
        review_depth = review_depth_override
    records = extract_auditor_records(auditor_payload)

    adapted = []
    used_ids = set()
    unmatched = 0
    for record in records:
        citation, score = find_best_citation(record, citations, used_ids)
        if citation is None:
            unmatched += 1
            citation = {
                "citation_id": record.get("citation_id") or f"AUD-{unmatched:03d}",
                "citation_text": record.get("citation_text") or record.get("claim_text"),
                "citation_type": "source",
                "location": {},
                "claimed_content": record.get("claim_text"),
            }
            adapted.append(adapt_record(record, citation, score, unmatched_index=unmatched))
            continue
        used_ids.add(citation.get("citation_id", ""))
        adapted.append(adapt_record(record, citation, score))

    return {
        "review_depth": review_depth,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "citations": adapted,
        "adapter_summary": {
            "total_auditor_records": len(records),
            "adapted": len(adapted),
            "unmatched": unmatched,
            "enforceable": sum(1 for item in adapted if item.get("auditor", {}).get("enforceable")),
            "by_status": count_by(adapted, "verification_status"),
        },
    }


def count_by(items: list[dict], key: str) -> dict:
    counts = {}
    for item in items:
        value = item.get(key)
        counts[value] = counts.get(value, 0) + 1
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Adapt citation-auditor output to citation-checker schema.")
    parser.add_argument("--citation-list", required=True)
    parser.add_argument("--auditor-results", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--review-depth")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    citation_payload = load_json(args.citation_list)
    auditor_payload = load_json(args.auditor_results)
    output = adapt(citation_payload, auditor_payload, review_depth_override=args.review_depth)
    write_json(args.output, output)
    print(
        json.dumps(
            {
                "success": True,
                "output_path": args.output,
                **output["adapter_summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
