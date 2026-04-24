#!/usr/bin/env python3
"""Create a human-review worksheet from citation-auditor shadow diff output."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

_SHARED_SCRIPTS = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "scripts")
)
if _SHARED_SCRIPTS not in sys.path:
    sys.path.insert(0, _SHARED_SCRIPTS)

from artifact_meta import write_artifact_meta  # noqa: E402

NO_ACTION_CONFLICTS = {"same_status", "missing_auditor"}

ACTION_BY_CONFLICT = {
    "auditor_more_severe": "review_auditor_finding_for_false_positive",
    "auditor_verified_base_unverifiable": "review_possible_base_false_negative_or_assist_evidence",
    "base_more_severe": "review_base_finding_and_do_not_auto_downgrade",
    "different_status_same_rank": "review_status_taxonomy",
    "unmatched_auditor": "review_unmatched_auditor_claim",
    "missing_auditor": "no_auditor_result",
    "same_status": "no_action",
}


def load_json(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def write_json(path: str, payload: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def manifest_identity(manifest: dict[str, Any]) -> dict[str, Any]:
    context = manifest.get("review_context") if isinstance(manifest.get("review_context"), dict) else {}
    return {
        "matter_id": manifest.get("matter_id"),
        "round": manifest.get("round"),
        "review_depth": context.get("depth") or manifest.get("review_depth"),
        "citation_auditor_mode": context.get("citation_auditor_mode") or manifest.get("citation_auditor_mode"),
    }


def recommended_action(row: dict[str, Any]) -> str:
    conflict = str(row.get("conflict_type") or "unknown")
    return ACTION_BY_CONFLICT.get(conflict, "review_unclassified_conflict")


def needs_review(row: dict[str, Any]) -> bool:
    return str(row.get("conflict_type") or "unknown") not in NO_ACTION_CONFLICTS


def review_item(row: dict[str, Any]) -> dict[str, Any]:
    action = recommended_action(row)
    return {
        "citation_id": row.get("citation_id"),
        "citation_text": row.get("citation_text"),
        "base_status": row.get("base_status"),
        "auditor_status": row.get("auditor_status"),
        "auditor_verifier": row.get("auditor_verifier"),
        "auditor_reason_code": row.get("auditor_reason_code"),
        "auditor_enforce_scope": row.get("auditor_enforce_scope"),
        "conflict_type": row.get("conflict_type"),
        "merge_decision": row.get("decision"),
        "recommended_action": action,
        "requires_human_review": needs_review(row),
        "human_review": {
            "result": "pending",
            "false_positive": None,
            "false_negative": None,
            "useful_supplemental_evidence": None,
            "would_change_canonical_status": None,
            "notes": "",
        },
    }


def build_review(diff: dict[str, Any], manifest: dict[str, Any], reviewer: str | None = None) -> dict[str, Any]:
    rows = [row for row in diff.get("rows", []) if isinstance(row, dict)]
    items = [review_item(row) for row in rows]
    review_required = sum(1 for item in items if item["requires_human_review"])
    action_counts = count_by(items, "recommended_action")
    generated_at = datetime.now(timezone.utc).isoformat()
    identity = manifest_identity(manifest)

    return {
        "schema_version": "2026-04-25",
        "generated_at": generated_at,
        "review_status": "pending_human_review",
        "reviewer": reviewer,
        **identity,
        "diff_mode": diff.get("mode"),
        "total_base_citations": diff.get("total_base_citations"),
        "total_auditor_citations": diff.get("total_auditor_citations"),
        "summary": {
            "total_rows": len(rows),
            "review_required": review_required,
            "by_conflict_type": diff.get("by_conflict_type") or count_by(rows, "conflict_type"),
            "by_recommended_action": action_counts,
            "merge_decisions": diff.get("decisions") or {},
            "run_metrics": diff.get("run_metrics") or {},
        },
        "rollout_gate_observations": {
            "human_reviewed": False,
            "kr_statute_or_case_matter": None,
            "false_positive_nonexistent_count": None,
            "false_positive_critical_count": None,
            "useful_supplemental_evidence_count": None,
            "ready_for_assist": False,
            "ready_for_enforce_limited": False,
            "notes": "",
        },
        "items": items,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare shadow diff review worksheet.")
    parser.add_argument("--diff", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest")
    parser.add_argument("--reviewer")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    review = build_review(load_json(args.diff), load_json(args.manifest), reviewer=args.reviewer)
    write_json(args.output, review)
    write_artifact_meta(
        args.output,
        artifact_type="shadow_diff_review",
        producer={"step": "WF1_STEP_3", "skill": "citation-checker", "script": "prepare-shadow-diff-review.py"},
    )
    print(
        json.dumps(
            {
                "success": True,
                "output_path": args.output,
                "review_required": review["summary"]["review_required"],
                "total_rows": review["summary"]["total_rows"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
