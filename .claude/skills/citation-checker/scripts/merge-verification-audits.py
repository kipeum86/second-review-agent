#!/usr/bin/env python3
"""
Merge a base verification audit with citation-auditor adapted results.

Usage:
    python3 merge-verification-audits.py \
        --base working/verification-audit.base.json \
        --auditor working/citation-auditor-adapted.json \
        --mode assist \
        --output working/verification-audit.json \
        --diff-output working/citation-auditor-diff.json

Modes:
  shadow: copy base to output; write diff if requested.
  diff:   copy base to output; write richer diff if requested.
  assist: keep base statuses; attach auditor evidence only to Unverifiable_*.
  enforce_limited: permit deterministic primary-source upgrades/downgrades.
  enforce: conservative full merge, still preserving anti-hallucination guards.
"""

from __future__ import annotations

import argparse
import json
import os
from copy import deepcopy
from datetime import datetime, timezone


VALID_MODES = {"shadow", "diff", "assist", "enforce_limited", "enforce"}

ISSUE_STATUSES = {
    "Nonexistent",
    "Wrong_Pinpoint",
    "Unsupported_Proposition",
    "Wrong_Jurisdiction",
    "Stale",
    "Translation_Mismatch",
}
UNVERIFIABLE_STATUSES = {
    "Unverifiable_No_Access",
    "Unverifiable_Secondary_Only",
    "Unverifiable_No_Evidence",
    "Unverifiable_Synthetic_Suspected",
}
CRITICAL_STATUSES = {"Nonexistent", "Wrong_Pinpoint", "Unsupported_Proposition"}

STATUS_RANK = {
    "Nonexistent": 0,
    "Wrong_Pinpoint": 1,
    "Unsupported_Proposition": 2,
    "Wrong_Jurisdiction": 3,
    "Stale": 4,
    "Translation_Mismatch": 5,
    "Unverifiable_No_Access": 6,
    "Unverifiable_No_Evidence": 7,
    "Unverifiable_Secondary_Only": 8,
    "Unverifiable_Synthetic_Suspected": 8,
    "Verified": 9,
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

LIMITED_ENFORCE_SCOPES = {
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


def normalize_audit(payload: object, fallback_depth: str = "standard") -> dict:
    if isinstance(payload, dict) and "citations" in payload:
        audit = deepcopy(payload)
        audit.setdefault("review_depth", fallback_depth)
        audit.setdefault("citations", [])
        return audit
    if isinstance(payload, list):
        return {"review_depth": fallback_depth, "citations": deepcopy(payload)}
    return {"review_depth": fallback_depth, "citations": []}


def citation_lookup(citations: list[dict]) -> dict[str, dict]:
    lookup = {}
    for citation in citations:
        cid = citation.get("citation_id")
        if cid:
            lookup[cid] = citation
    return lookup


def status_rank(status: str | None) -> int:
    return STATUS_RANK.get(status or "Unverifiable_No_Evidence", STATUS_RANK["Unverifiable_No_Evidence"])


def is_unverifiable(status: str | None) -> bool:
    return (status or "") in UNVERIFIABLE_STATUSES or str(status or "").startswith("Unverifiable")


def supplemental_entry(auditor: dict, decision: str) -> dict:
    meta = auditor.get("auditor", {})
    return {
        "name": meta.get("verifier_name") or auditor.get("verification_method", "").replace("citation_auditor:", ""),
        "label": meta.get("label"),
        "adapted_status": auditor.get("verification_status"),
        "reason_code": meta.get("reason_code"),
        "enforce_scope": meta.get("enforce_scope"),
        "enforceable": bool(meta.get("enforceable")),
        "decision": decision,
        "rationale": auditor.get("notes") or auditor.get("evidence", {}).get("auditor_rationale"),
        "evidence": auditor.get("evidence"),
    }


def can_enforce_limited(base: dict, auditor: dict) -> tuple[bool, str]:
    base_status = base.get("verification_status")
    auditor_status = auditor.get("verification_status")
    meta = auditor.get("auditor", {})
    scope = meta.get("enforce_scope")

    if not meta.get("enforceable"):
        return False, "auditor_not_enforceable"
    if scope not in LIMITED_ENFORCE_SCOPES:
        return False, "scope_not_limited_enforceable"
    if auditor_status == "Nonexistent" and meta.get("positive_nonexistence_evidence") is not True:
        return False, "nonexistent_without_positive_evidence"
    if base_status in CRITICAL_STATUSES and auditor_status == "Verified":
        return False, "no_auto_downgrade_of_critical_base"
    if auditor_status in {"Verified", "Wrong_Pinpoint", "Nonexistent"} and is_unverifiable(base_status):
        return True, "limited_enforce_unverifiable_replaced"
    if base_status == "Verified" and auditor_status == "Wrong_Pinpoint":
        return True, "limited_enforce_verified_to_wrong_pinpoint"
    if status_rank(auditor_status) < status_rank(base_status) and auditor_status in {"Wrong_Pinpoint", "Nonexistent"}:
        return True, "limited_enforce_more_severe_primary_finding"
    return False, "limited_enforce_no_rule_matched"


def can_enforce_full(base: dict, auditor: dict) -> tuple[bool, str]:
    base_status = base.get("verification_status")
    auditor_status = auditor.get("verification_status")
    meta = auditor.get("auditor", {})

    if auditor_status == "Nonexistent" and meta.get("positive_nonexistence_evidence") is not True:
        return False, "nonexistent_without_positive_evidence"
    if base_status in CRITICAL_STATUSES and auditor_status == "Verified":
        return False, "no_auto_downgrade_of_critical_base"
    if auditor_status == base_status:
        return False, "same_status"
    if is_unverifiable(base_status) and auditor_status == "Verified" and meta.get("enforceable"):
        return True, "full_enforce_unverifiable_to_verified"
    if status_rank(auditor_status) < status_rank(base_status):
        return True, "full_enforce_more_severe_status"
    return False, "full_enforce_no_rule_matched"


def apply_status(base: dict, auditor: dict, decision: str) -> None:
    prior_status = base.get("verification_status")
    prior_evidence = deepcopy(base.get("evidence"))
    auditor_evidence = deepcopy(auditor.get("evidence"))
    base["verification_status"] = auditor.get("verification_status")
    base["verification_method"] = merge_method(base.get("verification_method"), auditor.get("verification_method"))
    base["authority_tier"] = auditor.get("authority_tier", base.get("authority_tier"))
    base["authority_label"] = auditor.get("authority_label", base.get("authority_label"))
    base["authority_note"] = auditor.get("authority_note", base.get("authority_note"))
    if prior_evidence:
        base["evidence"] = prior_evidence
        if auditor_evidence:
            base["citation_auditor_evidence"] = auditor_evidence
            base["status_evidence_source"] = "citation_auditor"
    elif auditor_evidence:
        base["evidence"] = auditor_evidence
        base["status_evidence_source"] = "citation_auditor"
    base["confidence"] = auditor.get("confidence", base.get("confidence"))
    base["notes"] = auditor.get("notes", base.get("notes", ""))
    base.setdefault("merge_history", []).append(
        {
            "source": "citation_auditor",
            "decision": decision,
            "prior_status": prior_status,
            "new_status": auditor.get("verification_status"),
            "base_evidence_preserved": prior_evidence is not None,
            "auditor": auditor.get("auditor", {}),
        }
    )


def merge_method(base_method: object, auditor_method: object) -> str:
    parts = [str(item) for item in (base_method, auditor_method) if item]
    return " + ".join(dict.fromkeys(parts))


def add_supplemental(base: dict, auditor: dict, decision: str) -> None:
    base.setdefault("supplemental_verifiers", []).append(supplemental_entry(auditor, decision))


def conflict_type(base_status: str | None, auditor_status: str | None) -> str:
    if base_status == auditor_status:
        return "same_status"
    if auditor_status == "Verified" and is_unverifiable(base_status):
        return "auditor_verified_base_unverifiable"
    if status_rank(auditor_status) < status_rank(base_status):
        return "auditor_more_severe"
    if status_rank(auditor_status) > status_rank(base_status):
        return "base_more_severe"
    return "different_status_same_rank"


def merge(base_payload: object, auditor_payload: object, mode: str) -> tuple[dict, dict]:
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid mode: {mode}")

    base_audit = normalize_audit(base_payload)
    auditor_audit = normalize_audit(auditor_payload, fallback_depth=base_audit.get("review_depth", "standard"))
    output = deepcopy(base_audit)
    output["citations"] = [deepcopy(item) for item in base_audit.get("citations", [])]

    base_by_id = citation_lookup(output["citations"])
    auditor_by_id = citation_lookup(auditor_audit.get("citations", []))
    diff_rows = []
    decisions = {"kept_base": 0, "supplemented": 0, "status_changed": 0, "unmatched_auditor": 0}

    for cid, base in base_by_id.items():
        auditor = auditor_by_id.get(cid)
        if not auditor:
            diff_rows.append(
                {
                    "citation_id": cid,
                    "citation_text": base.get("citation_text"),
                    "base_status": base.get("verification_status"),
                    "auditor_status": None,
                    "conflict_type": "missing_auditor",
                    "decision": "kept_base",
                }
            )
            decisions["kept_base"] += 1
            continue

        base_status = base.get("verification_status")
        auditor_status = auditor.get("verification_status")
        decision = "kept_base"

        if mode in {"assist", "enforce_limited", "enforce"} and is_unverifiable(base_status):
            add_supplemental(base, auditor, "supplemental_evidence")
            decision = "supplemented"
            decisions["supplemented"] += 1

        if mode == "enforce_limited":
            allowed, reason = can_enforce_limited(base, auditor)
            if allowed:
                apply_status(base, auditor, reason)
                decision = reason
                decisions["status_changed"] += 1
        elif mode == "enforce":
            allowed, reason = can_enforce_full(base, auditor)
            if allowed:
                apply_status(base, auditor, reason)
                decision = reason
                decisions["status_changed"] += 1

        if decision == "kept_base":
            decisions["kept_base"] += 1

        diff_rows.append(
            {
                "citation_id": cid,
                "citation_text": base.get("citation_text"),
                "base_status": base_status,
                "auditor_status": auditor_status,
                "auditor_verifier": auditor.get("auditor", {}).get("verifier_name"),
                "auditor_reason_code": auditor.get("auditor", {}).get("reason_code"),
                "auditor_enforce_scope": auditor.get("auditor", {}).get("enforce_scope"),
                "conflict_type": conflict_type(base_status, auditor_status),
                "decision": decision,
            }
        )

    for cid, auditor in auditor_by_id.items():
        if cid in base_by_id:
            continue
        decisions["unmatched_auditor"] += 1
        diff_rows.append(
            {
                "citation_id": cid,
                "citation_text": auditor.get("citation_text"),
                "base_status": None,
                "auditor_status": auditor.get("verification_status"),
                "auditor_verifier": auditor.get("auditor", {}).get("verifier_name"),
                "conflict_type": "unmatched_auditor",
                "decision": "diff_only",
            }
        )

    output["summary"] = compute_summary(output["citations"])
    output["total_citations"] = len(output["citations"])
    output["generated_at"] = datetime.now(timezone.utc).isoformat()
    output["citation_auditor_merge"] = {
        "mode": mode,
        "generated_at": output["generated_at"],
        "decisions": decisions,
    }
    if any(citation.get("authority_tier") is not None for citation in output["citations"]):
        output["source_authority_summary"] = compute_source_authority_summary(output["citations"])

    diff = {
        "mode": mode,
        "generated_at": output["generated_at"],
        "total_base_citations": len(base_by_id),
        "total_auditor_citations": len(auditor_by_id),
        "decisions": decisions,
        "by_conflict_type": count_by(diff_rows, "conflict_type"),
        "rows": diff_rows,
    }
    return output, diff


def compute_summary(citations: list[dict]) -> dict:
    summary = {"verified": 0, "issue": 0, "unverifiable": 0, "by_sub_status": {}}
    for citation in citations:
        status = citation.get("verification_status", "Unverifiable_No_Evidence")
        primary = PRIMARY_STATUS_MAP.get(status, "unverifiable")
        summary[primary] += 1
        summary["by_sub_status"][status] = summary["by_sub_status"].get(status, 0) + 1
    return summary


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


def count_by(rows: list[dict], key: str) -> dict:
    counts = {}
    for row in rows:
        value = row.get(key)
        counts[value] = counts.get(value, 0) + 1
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge base verification audit with adapted citation-auditor results.")
    parser.add_argument("--base", required=True)
    parser.add_argument("--auditor", required=True)
    parser.add_argument("--mode", choices=sorted(VALID_MODES), default="shadow")
    parser.add_argument("--output", required=True)
    parser.add_argument("--diff-output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output, diff = merge(load_json(args.base), load_json(args.auditor), args.mode)
    write_json(args.output, output)
    if args.diff_output:
        write_json(args.diff_output, diff)
    print(
        json.dumps(
            {
                "success": True,
                "mode": args.mode,
                "output_path": args.output,
                "diff_output": args.diff_output,
                "decisions": diff["decisions"],
                "by_conflict_type": diff["by_conflict_type"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
