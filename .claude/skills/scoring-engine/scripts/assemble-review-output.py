#!/usr/bin/env python3
"""
Normalize or assemble canonical Step 6 outputs.

Usage:
    python3 assemble-review-output.py <working_dir>
        [--legacy-issue-registry <path>]
        [--legacy-scorecard <path>]

Writes:
    <working_dir>/issue-registry.json
    <working_dir>/review-scorecard.json
"""

import argparse
import json
import os
import re

DIMENSION_KEYS = {
    1: "1_citation",
    2: "2_substance",
    3: "3_alignment",
    4: "4_writing",
    5: "5_structure",
    6: "6_formatting",
}

DIMENSION_LABELS = {
    1: "Citation & Fact",
    2: "Legal Substance",
    3: "Client Alignment",
    4: "Writing Quality",
    5: "Structure",
    6: "Formatting",
}

RELEASE_ENUMS = {
    "Pass",
    "Pass with Warnings",
    "Manual Review Required",
    "Release Not Recommended",
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def severity_title(value):
    raw = str(value or "Minor").strip().lower()
    if raw.startswith("crit"):
        return "Critical"
    if raw.startswith("maj"):
        return "Major"
    if raw.startswith("sug"):
        return "Suggestion"
    return "Minor"


def canonicalize_verification_status(value, description=""):
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw in {
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
    }:
        return raw
    upper = raw.upper()
    detail = f"{raw} {description}".lower()
    if upper.startswith("PARTIALLY_VERIFIED"):
        return "Unverifiable_Secondary_Only"
    if upper.startswith("NONEXISTENT"):
        return "Nonexistent"
    if upper.startswith("STALE"):
        return "Stale"
    if upper.startswith("WRONG_DETAIL"):
        if "fabricated" in detail or "존재" in detail or "version" in detail:
            return "Nonexistent"
        if "conflation" in detail or "support" in detail:
            return "Unsupported_Proposition"
        return "Wrong_Pinpoint"
    if "wrong pinpoint" in detail:
        return "Wrong_Pinpoint"
    if "unsupported" in detail:
        return "Unsupported_Proposition"
    if "secondary" in detail:
        return "Unverifiable_Secondary_Only"
    if "unverified" in detail:
        return "Unverifiable_No_Evidence"
    return raw


def normalize_location(value):
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    text = str(value)
    match = re.search(r"para(?:graph)?s?\s*(\d+)", text, re.IGNORECASE)
    if match:
        return {"paragraph_index": int(match.group(1)), "section": text}
    return {"section": text}


def parse_dimension(value, fallback=None):
    if isinstance(value, int):
        return value
    text = str(value or "")
    match = re.search(r"D\s*([1-6])|([1-6])_", text, re.IGNORECASE)
    if match:
        return int(match.group(1) or match.group(2))
    lowered = text.lower()
    if "citation" in lowered:
        return 1
    if "substance" in lowered or "legal accuracy" in lowered:
        return 2
    if "alignment" in lowered:
        return 3
    if "writing" in lowered:
        return 4
    if "structure" in lowered:
        return 5
    if "format" in lowered:
        return 6
    return fallback


def normalize_issue(issue, seq, fallback_dimension=None):
    dimension = parse_dimension(issue.get("dimension"), fallback=fallback_dimension) or fallback_dimension or 2
    evidence = issue.get("evidence", {})
    if not isinstance(evidence, dict):
        evidence = {}
    elif evidence.get("verification_status"):
        evidence["verification_status"] = canonicalize_verification_status(
            evidence.get("verification_status"),
            description=issue.get("description", ""),
        )
    if issue.get("citation_id") and "citation_id" not in evidence:
        evidence["citation_id"] = issue["citation_id"]
    if issue.get("verification_status") and "verification_status" not in evidence:
        evidence["verification_status"] = canonicalize_verification_status(
            issue["verification_status"],
            description=issue.get("description", ""),
        )

    return {
        "issue_id": issue.get("issue_id") or f"ISS-{seq:03d}",
        "dimension": dimension,
        "severity": severity_title(issue.get("severity")),
        "location": normalize_location(issue.get("location")),
        "description": issue.get("description") or issue.get("title") or "Issue detected.",
        "recommendation": issue.get("recommendation") or "Review and revise.",
        "evidence": evidence,
        "recurring_pattern": issue.get("recurring_pattern") or issue.get("pattern_id"),
    }


def normalize_issue_registry(path):
    registry = load_json(path)
    issues = []
    for idx, issue in enumerate(registry.get("issues", []), 1):
        issues.append(normalize_issue(issue, idx))
    meta = {
        "matter_id": registry.get("matter_id"),
        "round": registry.get("round"),
        "review_depth": registry.get("review_depth"),
    }
    return issues, meta


def load_manifest(working_dir):
    manifest_path = os.path.join(working_dir, "review-manifest.json")
    if not os.path.exists(manifest_path):
        return {}
    return load_json(manifest_path)


def collect_dim_findings(working_dir):
    issues = []
    seq = 1
    for dimension in range(2, 7):
        path = os.path.join(working_dir, f"dim{dimension}-findings.json")
        if not os.path.exists(path):
            continue
        payload = load_json(path)
        for finding in payload.get("findings", []):
            issues.append(normalize_issue(finding, seq, fallback_dimension=dimension))
            seq += 1
    return issues


def collect_d1_from_audit(working_dir, start_seq):
    path = os.path.join(working_dir, "verification-audit.json")
    if not os.path.exists(path):
        return []
    payload = load_json(path)
    citations = payload.get("citations", [])
    issues = []
    seq = start_seq
    for citation in citations:
        status = citation.get("verification_status")
        if status == "Verified":
            continue
        severity = "Critical" if status in {"Nonexistent", "Wrong_Pinpoint", "Unsupported_Proposition"} else "Major"
        if status == "Unverifiable_Secondary_Only":
            severity = "Minor"
        description = citation.get("notes") or citation.get("citation_text") or "Citation requires review."
        recommendation = "Verify and correct the citation before release."
        issues.append(
            {
                "issue_id": f"ISS-{seq:03d}",
                "dimension": 1,
                "severity": severity,
                "location": citation.get("location") or {},
                "description": description,
                "recommendation": recommendation,
                "evidence": {
                    "citation_id": citation.get("citation_id"),
                    "verification_status": status,
                },
                "recurring_pattern": None,
            }
        )
        seq += 1
    return issues


def dedupe_issues(issues):
    deduped = []
    seen = set()
    for issue in issues:
        key = (
            issue["dimension"],
            issue["severity"],
            json.dumps(issue["location"], ensure_ascii=False, sort_keys=True),
            issue["description"],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)
    return deduped


def summarize_dimension_issues(issues):
    buckets = {severity: 0 for severity in ("Critical", "Major", "Minor", "Suggestion")}
    for issue in issues:
        buckets[issue["severity"]] += 1
    return buckets


def compute_score(counts):
    critical = counts["Critical"]
    major = counts["Major"]
    minor = counts["Minor"]
    suggestion = counts["Suggestion"]
    if critical:
        return max(1.0, 4.0 - min(critical - 1, 2) - min(major * 0.25, 0.75))
    if major:
        return max(4.0, 7.0 - min(major * 0.5, 3.0) - min(minor * 0.1, 0.5))
    if minor or suggestion:
        return max(7.0, 10.0 - min(minor * 0.5 + suggestion * 0.25, 3.0))
    return 10.0


def normalize_legacy_dimensions(legacy_scorecard):
    result = {}
    if "dimensions" in legacy_scorecard:
        for number, key in DIMENSION_KEYS.items():
            payload = legacy_scorecard["dimensions"].get(key, {})
            result[key] = {
                "score": payload.get("score"),
                "skipped": payload.get("skipped", False),
                "skip_reason": payload.get("skip_reason"),
                "findings_count": payload.get("findings_count", {}),
                "summary": payload.get("summary", ""),
            }
        return result

    scorecard = legacy_scorecard.get("scorecard", {})
    for number, key in DIMENSION_KEYS.items():
        legacy_key = None
        for candidate in scorecard:
            if parse_dimension(candidate) == number:
                legacy_key = candidate
                break
        payload = scorecard.get(legacy_key, {}) if legacy_key else {}
        result[key] = {
            "score": payload.get("score"),
            "skipped": False,
            "skip_reason": None,
            "findings_count": {},
            "summary": payload.get("summary", ""),
        }
    return result


def compute_grade(avg):
    if avg >= 8.5:
        return "A"
    if avg >= 7.0:
        return "B"
    if avg >= 5.0:
        return "C"
    return "D"


def compute_release_recommendation(issues, grade):
    critical_dim_1_3 = [issue for issue in issues if issue["dimension"] in (1, 2, 3) and issue["severity"] == "Critical"]
    nonexistent = [
        issue
        for issue in issues
        if issue["evidence"].get("verification_status") == "Nonexistent"
    ]
    if critical_dim_1_3 or nonexistent:
        return "Release Not Recommended", "Critical finding or nonexistent citation blocks release."

    unverifiable = [
        issue
        for issue in issues
        if issue["dimension"] == 1 and str(issue["evidence"].get("verification_status", "")).startswith("Unverifiable")
    ]
    dim2_major = len([issue for issue in issues if issue["dimension"] == 2 and issue["severity"] == "Major"])
    if unverifiable or dim2_major >= 2:
        return "Manual Review Required", "Key citations remain unverifiable or Dim 2 has multiple Major issues."

    any_major = any(issue["severity"] == "Major" for issue in issues)
    if any_major or grade in {"C", "D"}:
        return "Pass with Warnings", "Major issues remain or overall quality is below B."

    return "Pass", "No Critical or Major issues remain."


def build_scorecard(issues, manifest, legacy_scorecard=None):
    dimensions = normalize_legacy_dimensions(legacy_scorecard or {})
    score_values = []
    for number, key in DIMENSION_KEYS.items():
        dim_issues = [issue for issue in issues if issue["dimension"] == number]
        counts = summarize_dimension_issues(dim_issues)
        entry = dimensions.get(key, {})
        skipped = bool(entry.get("skipped"))
        if number == 3 and manifest.get("review_context", {}).get("dim3_client_alignment", "").startswith("skipped"):
            skipped = True
            entry["skip_reason"] = "No client context provided"
        if not skipped:
            score = entry.get("score")
            if score is None:
                score = compute_score(counts)
            score = round(float(score), 1)
            score_values.append(score)
        else:
            score = None
        summary = entry.get("summary") or (
            "No findings." if not dim_issues else f"{counts['Critical']} Critical, {counts['Major']} Major, {counts['Minor']} Minor."
        )
        dimensions[key] = {
            "score": score,
            "skipped": skipped,
            "skip_reason": entry.get("skip_reason"),
            "findings_count": counts,
            "summary": summary,
        }

    average = round(sum(score_values) / len(score_values), 1) if score_values else 0.0
    grade = compute_grade(average)
    recommendation, rationale = compute_release_recommendation(issues, grade)
    assert recommendation in RELEASE_ENUMS
    return {
        "matter_id": manifest.get("matter_id"),
        "round": manifest.get("round"),
        "review_depth": manifest.get("review_context", {}).get("depth") or manifest.get("review_depth", "standard"),
        "dimensions": dimensions,
        "overall_grade": grade,
        "overall_average": average,
        "release_recommendation": recommendation,
        "release_rationale": rationale,
    }


def build_issue_registry(issues, manifest):
    by_severity = {"Critical": 0, "Major": 0, "Minor": 0, "Suggestion": 0}
    for issue in issues:
        by_severity[issue["severity"]] += 1
    return {
        "matter_id": manifest.get("matter_id"),
        "round": manifest.get("round"),
        "review_depth": manifest.get("review_context", {}).get("depth") or manifest.get("review_depth", "standard"),
        "total_issues": len(issues),
        "by_severity": by_severity,
        "issues": issues,
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("working_dir")
    parser.add_argument("--legacy-issue-registry")
    parser.add_argument("--legacy-scorecard")
    return parser.parse_args()


def main():
    args = parse_args()
    working_dir = args.working_dir
    manifest = load_manifest(working_dir)

    legacy_issue_registry = args.legacy_issue_registry or os.path.join(working_dir, "issue-registry.json")
    legacy_scorecard_path = args.legacy_scorecard or os.path.join(working_dir, "review-scorecard.json")

    issues = []
    legacy_registry_exists = os.path.exists(legacy_issue_registry)
    if legacy_registry_exists:
        issues, meta = normalize_issue_registry(legacy_issue_registry)
        manifest.setdefault("matter_id", meta.get("matter_id"))
        manifest.setdefault("round", meta.get("round"))
    else:
        issues = collect_dim_findings(working_dir)
        issues.extend(collect_d1_from_audit(working_dir, len(issues) + 1))

    if not legacy_registry_exists:
        dim_findings = collect_dim_findings(working_dir)
        issues.extend(dim_findings)
    issues = dedupe_issues(issues)

    for idx, issue in enumerate(issues, 1):
        issue["issue_id"] = f"ISS-{idx:03d}"

    legacy_scorecard = load_json(legacy_scorecard_path) if os.path.exists(legacy_scorecard_path) else None
    issue_registry = build_issue_registry(issues, manifest)
    review_scorecard = build_scorecard(issues, manifest, legacy_scorecard=legacy_scorecard)
    if legacy_scorecard and legacy_scorecard.get("known_issues_matched"):
        review_scorecard["known_issues_matched"] = legacy_scorecard["known_issues_matched"]

    write_json(os.path.join(working_dir, "issue-registry.json"), issue_registry)
    write_json(os.path.join(working_dir, "review-scorecard.json"), review_scorecard)
    print(
        json.dumps(
            {
                "issue_registry": os.path.join(working_dir, "issue-registry.json"),
                "review_scorecard": os.path.join(working_dir, "review-scorecard.json"),
                "total_issues": issue_registry["total_issues"],
                "overall_grade": review_scorecard["overall_grade"],
                "release_recommendation": review_scorecard["release_recommendation"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
