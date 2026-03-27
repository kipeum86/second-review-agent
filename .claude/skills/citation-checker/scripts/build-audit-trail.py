#!/usr/bin/env python3
"""
Assemble per-citation verification results into verification-audit.json.

Reads individual citation result files from a directory, validates schema,
computes summary statistics, and writes the consolidated audit trail.

Usage: python3 build-audit-trail.py <results_dir> <output_path>
Alternative: python3 build-audit-trail.py --stdin <output_path>

The input may be either:
- canonical flat citation entries, or
- a legacy `verification_audit` structure with grouped categories/findings.
"""

import glob
import json
import os
import sys
from datetime import datetime, timezone

VALID_STATUSES = {
    "Verified",
    "Nonexistent",
    "Wrong_Pinpoint",
    "Unsupported_Proposition",
    "Wrong_Jurisdiction",
    "Stale",
    "Translation_Mismatch",
    "Unverifiable_No_Access",
    "Unverifiable_Secondary_Only",
    "Unverifiable_No_Evidence",
    "Unverifiable_Synthetic_Suspected",
}

PRIMARY_STATUS_MAP = {
    "Verified": "verified",
    "Nonexistent": "issue",
    "Wrong_Pinpoint": "issue",
    "Unsupported_Proposition": "issue",
    "Wrong_Jurisdiction": "issue",
    "Stale": "issue",
    "Translation_Mismatch": "issue",
    "Unverifiable_No_Access": "unverifiable",
    "Unverifiable_Secondary_Only": "unverifiable",
    "Unverifiable_No_Evidence": "unverifiable",
    "Unverifiable_Synthetic_Suspected": "unverifiable",
}

REQUIRED_FIELDS = ["citation_text", "citation_type", "verification_status"]


def guess_citation_type(bucket_name: str) -> str:
    lowered = bucket_name.lower()
    if "legislation" in lowered or "statute" in lowered:
        return "statute"
    if "case" in lowered or "law" in lowered:
        return "case"
    if "regulation" in lowered or "guidance" in lowered:
        return "regulation"
    return "source"


def canonicalize_status(raw_status, detail=None):
    if not raw_status:
        return "Unverifiable_No_Evidence"
    text = str(raw_status).strip()
    if text in VALID_STATUSES:
        return text

    upper = text.upper()
    detail_text = f"{detail or ''} {text}".lower()

    if upper.startswith("VERIFIED"):
        return "Verified"
    if upper.startswith("NONEXISTENT"):
        return "Nonexistent"
    if upper.startswith("STALE"):
        return "Stale"
    if upper.startswith("PARTIALLY_VERIFIED"):
        return "Unverifiable_Secondary_Only"
    if upper.startswith("UNVERIFIED"):
        return "Unverifiable_No_Evidence"
    if upper.startswith("WRONG_DETAIL"):
        if "fabricated" in detail_text or "존재" in detail_text or "version" in detail_text:
            return "Nonexistent"
        if "conflation" in detail_text or "support" in detail_text:
            return "Unsupported_Proposition"
        if "jurisdiction" in detail_text:
            return "Wrong_Jurisdiction"
        return "Wrong_Pinpoint"
    if "wrong pinpoint" in detail_text:
        return "Wrong_Pinpoint"
    if "unsupported" in detail_text:
        return "Unsupported_Proposition"
    if "secondary" in detail_text:
        return "Unverifiable_Secondary_Only"
    if "unverified" in detail_text:
        return "Unverifiable_No_Evidence"
    return "Unverifiable_No_Evidence"


def normalize_location(value):
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    text = str(value)
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits:
        return {"paragraph_index": int(digits), "section": text}
    return {"section": text}


def normalize_legacy_entry(bucket_name: str, entry: dict) -> list[dict]:
    citation_type = guess_citation_type(bucket_name)
    findings = entry.get("findings") or []
    source = entry.get("source") or bucket_name
    entry_status = entry.get("status")
    citations = []

    if not findings:
        findings = [{"claim": source, "result": entry_status or "UNVERIFIED"}]

    for idx, finding in enumerate(findings, 1):
        raw_status = finding.get("revised_status") if finding.get("retracted") else finding.get("result", entry_status)
        canonical_status = canonicalize_status(raw_status, detail=finding.get("detail_error") or finding.get("evidence"))
        citation = {
            "citation_id": f"{entry.get('id', bucket_name[:3].upper())}-{idx:02d}",
            "citation_text": finding.get("claim") or source,
            "citation_type": citation_type,
            "jurisdiction": entry.get("jurisdiction"),
            "location": normalize_location(finding.get("location") or finding.get("typo_flag", {}).get("location")),
            "claimed_content": finding.get("claim") or source,
            "verification_method": "legacy_import",
            "verification_status": canonical_status,
            "evidence": {
                "url": finding.get("url"),
                "search_query": finding.get("search_query"),
                "excerpt": finding.get("evidence"),
            },
            "confidence": entry.get("confidence"),
            "notes": finding.get("detail_error") or "",
        }
        if finding.get("recommendation"):
            citation["notes"] = (citation["notes"] + " " + finding["recommendation"]).strip()
        if entry.get("authority_tier") is not None:
            citation["authority_tier"] = entry["authority_tier"]
            citation["authority_label"] = entry.get("authority_label")
        citations.append(citation)

    return citations


def normalize_input_data(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict) and "verification_audit" in data:
        legacy = data["verification_audit"]
        citations = []
        for key, value in legacy.items():
            if key == "metadata" or not isinstance(value, list):
                continue
            for entry in value:
                citations.extend(normalize_legacy_entry(key, entry))
        review_depth = legacy.get("metadata", {}).get("review_depth", "standard")
        return {
            "review_depth": review_depth,
            "citations": citations,
        }

    if isinstance(data, dict) and "citations" in data:
        return data

    if isinstance(data, dict):
        return [data]

    return []


def validate_entry(entry: dict, idx: int) -> list[str]:
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in entry:
            errors.append(f"Citation {idx}: missing required field '{field}'")

    status = entry.get("verification_status", "")
    if status and status not in VALID_STATUSES:
        errors.append(f"Citation {idx}: invalid status '{status}'. Valid: {sorted(VALID_STATUSES)}")

    if status == "Nonexistent":
        evidence = entry.get("evidence", {})
        if not evidence or (not evidence.get("url") and not evidence.get("search_query") and not evidence.get("excerpt")):
            errors.append(
                f"Citation {idx}: 'Nonexistent' status requires documented evidence "
                f"(search query, URL, or excerpt). Consider 'Unverifiable_No_Evidence' instead."
            )

    tier = entry.get("authority_tier")
    if tier is not None:
        if not isinstance(tier, int) or tier not in (1, 2, 3, 4):
            errors.append(f"Citation {idx}: authority_tier must be integer 1-4, got '{tier}'")
        if "authority_label" not in entry:
            errors.append(f"Citation {idx}: authority_tier present but authority_label missing")

    return errors


def compute_source_authority_summary(citations: list[dict]) -> dict:
    tier_dist = {"tier_1": 0, "tier_2": 0, "tier_3": 0, "tier_4": 0}
    conclusion_by_tier = {"tier_1": 0, "tier_2": 0, "tier_3": 0, "tier_4": 0}
    high_risk = []

    for citation in citations:
        tier = citation.get("authority_tier")
        if tier is None:
            continue
        tier_key = f"tier_{tier}"
        if tier_key in tier_dist:
            tier_dist[tier_key] += 1
        if citation.get("supports_conclusion") and tier_key in conclusion_by_tier:
            conclusion_by_tier[tier_key] += 1
            if tier >= 3:
                high_risk.append(
                    {
                        "citation_id": citation.get("citation_id", ""),
                        "authority_tier": tier,
                        "supports_conclusion": True,
                        "conclusion_location": citation.get("conclusion_location"),
                        "risk": f"Tier {tier} source used to support conclusion",
                    }
                )

    return {
        "tier_distribution": tier_dist,
        "conclusion_support_by_tier": conclusion_by_tier,
        "high_risk_citations": high_risk,
    }


def compute_summary(citations: list[dict]) -> dict:
    summary = {"verified": 0, "issue": 0, "unverifiable": 0, "by_sub_status": {}}
    for citation in citations:
        status = citation.get("verification_status", "Unverifiable_No_Evidence")
        primary = PRIMARY_STATUS_MAP.get(status, "unverifiable")
        summary[primary] += 1
        summary["by_sub_status"][status] = summary["by_sub_status"].get(status, 0) + 1
    return summary


def build_audit_trail(citations: list[dict], review_depth: str = "standard") -> dict:
    all_errors = []
    for idx, citation in enumerate(citations):
        citation.setdefault("citation_id", f"CIT-{idx + 1:03d}")
        all_errors.extend(validate_entry(citation, idx))

    summary = compute_summary(citations)
    has_authority = any(citation.get("authority_tier") is not None for citation in citations)
    audit = {
        "review_depth": review_depth,
        "total_citations": len(citations),
        "summary": summary,
        "validation_errors": all_errors,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "citations": citations,
    }
    if has_authority:
        audit["source_authority_summary"] = compute_source_authority_summary(citations)
    return audit


def load_citations(source):
    if source == "--stdin":
        data = json.load(sys.stdin)
        normalized = normalize_input_data(data)
        if isinstance(normalized, dict):
            return normalized.get("citations", []), normalized.get("review_depth", "standard")
        return normalized, "standard"

    if os.path.isdir(source):
        citations = []
        review_depth = "standard"
        for path in sorted(glob.glob(os.path.join(source, "*.json"))):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            normalized = normalize_input_data(data)
            if isinstance(normalized, dict):
                review_depth = normalized.get("review_depth", review_depth)
                citations.extend(normalized.get("citations", []))
            elif isinstance(normalized, list):
                citations.extend(normalized)
        return citations, review_depth

    if os.path.isfile(source):
        with open(source, "r", encoding="utf-8") as f:
            data = json.load(f)
        normalized = normalize_input_data(data)
        if isinstance(normalized, dict):
            return normalized.get("citations", []), normalized.get("review_depth", "standard")
        return normalized, "standard"

    return [], "standard"


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: build-audit-trail.py <results_dir|--stdin> <output_path>"}))
        sys.exit(1)

    source = sys.argv[1]
    output_path = sys.argv[2]
    citations, review_depth = load_citations(source)
    audit = build_audit_trail(citations, review_depth=review_depth)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2, ensure_ascii=False)

    result = {
        "success": len(audit["validation_errors"]) == 0,
        "output_path": output_path,
        "total_citations": audit["total_citations"],
        "summary": audit["summary"],
        "validation_errors": audit["validation_errors"],
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if audit["validation_errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
