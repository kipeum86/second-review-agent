#!/usr/bin/env python3
"""Evaluate whether reviewed shadow diffs satisfy citation-auditor rollout gates."""

from __future__ import annotations

import argparse
import glob
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


def load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def write_json(path: str, payload: dict[str, Any]) -> None:
    output_dir = os.path.dirname(path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def int_value(value: object) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def collect_paths(paths: list[str], review_dir: str | None = None) -> list[str]:
    result = []
    for path in paths:
        if os.path.isdir(path):
            result.extend(sorted(glob.glob(os.path.join(path, "**", "shadow-diff-review.json"), recursive=True)))
        else:
            result.append(path)
    if review_dir:
        result.extend(sorted(glob.glob(os.path.join(review_dir, "**", "shadow-diff-review.json"), recursive=True)))
    return sorted(dict.fromkeys(result))


def observation(review: dict[str, Any]) -> dict[str, Any]:
    value = review.get("rollout_gate_observations")
    return value if isinstance(value, dict) else {}


def review_row(path: str, review: dict[str, Any]) -> dict[str, Any]:
    obs = observation(review)
    return {
        "path": path,
        "matter_id": review.get("matter_id"),
        "round": review.get("round"),
        "review_status": review.get("review_status"),
        "human_reviewed": obs.get("human_reviewed") is True,
        "kr_statute_or_case_matter": obs.get("kr_statute_or_case_matter") is True,
        "false_positive_nonexistent_count": int_value(obs.get("false_positive_nonexistent_count")),
        "false_positive_critical_count": int_value(obs.get("false_positive_critical_count")),
        "useful_supplemental_evidence_count": int_value(obs.get("useful_supplemental_evidence_count")),
        "ready_for_assist": obs.get("ready_for_assist") is True,
        "ready_for_enforce_limited": obs.get("ready_for_enforce_limited") is True,
        "review_required": int_value((review.get("summary") or {}).get("review_required")),
        "total_rows": int_value((review.get("summary") or {}).get("total_rows")),
    }


def build_blockers(
    rows: list[dict[str, Any]],
    *,
    min_assist_reviews: int,
    min_enforce_reviews: int,
    min_kr_reviews: int,
) -> tuple[list[str], list[str]]:
    reviewed = [row for row in rows if row["human_reviewed"]]
    reviewed_count = len(reviewed)
    fp_nonexistent = sum(row["false_positive_nonexistent_count"] for row in reviewed)
    fp_critical = sum(row["false_positive_critical_count"] for row in reviewed)
    assist_ready_count = sum(1 for row in reviewed if row["ready_for_assist"])
    enforce_ready_count = sum(1 for row in reviewed if row["ready_for_enforce_limited"])
    kr_reviewed_count = sum(1 for row in reviewed if row["kr_statute_or_case_matter"])

    assist_blockers = []
    if reviewed_count < min_assist_reviews:
        assist_blockers.append(f"Need {min_assist_reviews} human-reviewed shadow diffs; have {reviewed_count}.")
    if assist_ready_count < min_assist_reviews:
        assist_blockers.append(f"Need {min_assist_reviews} reviews explicitly marked ready_for_assist; have {assist_ready_count}.")
    if fp_critical:
        assist_blockers.append(f"False-positive Critical findings must be 0; have {fp_critical}.")

    enforce_blockers = list(assist_blockers)
    if reviewed_count < min_enforce_reviews:
        enforce_blockers.append(f"Need {min_enforce_reviews} human-reviewed shadow diffs; have {reviewed_count}.")
    if kr_reviewed_count < min_kr_reviews:
        enforce_blockers.append(f"Need {min_kr_reviews} KR statute/case matters; have {kr_reviewed_count}.")
    if enforce_ready_count < min_kr_reviews:
        enforce_blockers.append(
            f"Need {min_kr_reviews} reviews explicitly marked ready_for_enforce_limited; have {enforce_ready_count}."
        )
    if fp_nonexistent:
        enforce_blockers.append(f"False-positive Nonexistent findings must be 0; have {fp_nonexistent}.")
    return assist_blockers, enforce_blockers


def evaluate(
    reviews: list[tuple[str, dict[str, Any]]],
    *,
    min_assist_reviews: int = 5,
    min_enforce_reviews: int = 10,
    min_kr_reviews: int = 5,
) -> dict[str, Any]:
    rows = [review_row(path, review) for path, review in reviews]
    reviewed = [row for row in rows if row["human_reviewed"]]
    assist_blockers, enforce_blockers = build_blockers(
        rows,
        min_assist_reviews=min_assist_reviews,
        min_enforce_reviews=min_enforce_reviews,
        min_kr_reviews=min_kr_reviews,
    )
    assist_ready = not assist_blockers
    enforce_ready = not enforce_blockers
    recommendation = "keep_shadow"
    if enforce_ready:
        recommendation = "enforce_limited_candidate"
    elif assist_ready:
        recommendation = "assist_candidate"

    return {
        "schema_version": "2026-04-25",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "recommendation": recommendation,
        "assist_ready": assist_ready,
        "enforce_limited_ready": enforce_ready,
        "thresholds": {
            "min_assist_reviews": min_assist_reviews,
            "min_enforce_reviews": min_enforce_reviews,
            "min_kr_reviews": min_kr_reviews,
        },
        "summary": {
            "total_reviews": len(rows),
            "human_reviewed": len(reviewed),
            "kr_statute_or_case_reviews": sum(1 for row in reviewed if row["kr_statute_or_case_matter"]),
            "ready_for_assist": sum(1 for row in reviewed if row["ready_for_assist"]),
            "ready_for_enforce_limited": sum(1 for row in reviewed if row["ready_for_enforce_limited"]),
            "false_positive_nonexistent_count": sum(row["false_positive_nonexistent_count"] for row in reviewed),
            "false_positive_critical_count": sum(row["false_positive_critical_count"] for row in reviewed),
            "useful_supplemental_evidence_count": sum(row["useful_supplemental_evidence_count"] for row in reviewed),
        },
        "assist_blockers": assist_blockers,
        "enforce_limited_blockers": enforce_blockers,
        "reviews": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate citation-auditor shadow diff rollout readiness.")
    parser.add_argument("paths", nargs="*", help="shadow-diff-review.json files or directories containing them")
    parser.add_argument("--review-dir")
    parser.add_argument("--output")
    parser.add_argument("--min-assist-reviews", type=int, default=5)
    parser.add_argument("--min-enforce-reviews", type=int, default=10)
    parser.add_argument("--min-kr-reviews", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = collect_paths(args.paths, review_dir=args.review_dir)
    reviews = [(path, load_json(path)) for path in paths]
    result = evaluate(
        reviews,
        min_assist_reviews=args.min_assist_reviews,
        min_enforce_reviews=args.min_enforce_reviews,
        min_kr_reviews=args.min_kr_reviews,
    )
    if args.output:
        write_json(args.output, result)
        write_artifact_meta(
            args.output,
            artifact_type="shadow_diff_rollout_report",
            producer={"step": "WF1_STEP_3", "skill": "citation-checker", "script": "evaluate-shadow-diff-rollout.py"},
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
