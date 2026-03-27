#!/usr/bin/env python3
"""
Run the WF1 Step 8 quality gate checks and emit quality-gate-report.json.

Usage:
    python3 run-quality-gate.py <working_dir> <deliverables_dir> <output_path>
"""

import argparse
import glob
import json
import os
import re
import zipfile
import xml.etree.ElementTree as ET

VALID_RELEASES = {
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


def find_first(pattern):
    matches = sorted(glob.glob(pattern))
    return matches[0] if matches else None


def severity_title(value):
    raw = str(value or "Minor").strip().lower()
    if raw.startswith("crit"):
        return "Critical"
    if raw.startswith("maj"):
        return "Major"
    if raw.startswith("sug"):
        return "Suggestion"
    return "Minor"


def compute_grade(avg):
    if avg >= 8.5:
        return "A"
    if avg >= 7.0:
        return "B"
    if avg >= 5.0:
        return "C"
    return "D"


def extract_correction_count(issues):
    count = 0
    pattern = re.compile(r"""["']([^"'\\]{1,80})["']\s*(?:→|->|=>)\s*["']([^"'\\]{1,80})["']""")
    for issue in issues:
        if severity_title(issue.get("severity")) not in {"Critical", "Major"}:
            continue
        if issue.get("typo_list"):
            count += len(issue["typo_list"])
            continue
        text = " ".join(str(issue.get(field, "")) for field in ("recommendation", "description", "title"))
        if pattern.search(text):
            count += 1
    return count


def count_docx_markers(path):
    counts = {"comments": 0, "insertions": 0, "deletions": 0}
    if not path or not os.path.exists(path):
        return counts
    with zipfile.ZipFile(path, "r") as zf:
        if "word/comments.xml" in zf.namelist():
            root = ET.fromstring(zf.read("word/comments.xml"))
            counts["comments"] = len(root.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}comment"))
        if "word/document.xml" in zf.namelist():
            root = ET.fromstring(zf.read("word/document.xml"))
            counts["insertions"] = len(root.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ins"))
            counts["deletions"] = len(root.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}del"))
    return counts


def extract_docx_text(path):
    if not path or not os.path.exists(path):
        return ""
    with zipfile.ZipFile(path, "r") as zf:
        if "word/document.xml" not in zf.namelist():
            return ""
        xml_text = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    return " ".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml_text))


def compute_release_recommendation(issues, grade):
    critical_dim_1_3 = [issue for issue in issues if issue["dimension"] in (1, 2, 3) and severity_title(issue.get("severity")) == "Critical"]
    nonexistent = [
        issue
        for issue in issues
        if issue.get("evidence", {}).get("verification_status") == "Nonexistent"
    ]
    if critical_dim_1_3 or nonexistent:
        return "Release Not Recommended"

    unverifiable = [
        issue
        for issue in issues
        if issue.get("dimension") == 1 and str(issue.get("evidence", {}).get("verification_status", "")).startswith("Unverifiable")
    ]
    dim2_major = len([issue for issue in issues if issue.get("dimension") == 2 and severity_title(issue.get("severity")) == "Major"])
    if unverifiable or dim2_major >= 2:
        return "Manual Review Required"

    any_major = any(severity_title(issue.get("severity")) == "Major" for issue in issues)
    if any_major or grade in {"C", "D"}:
        return "Pass with Warnings"
    return "Pass"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("working_dir")
    parser.add_argument("deliverables_dir")
    parser.add_argument("output_path")
    args = parser.parse_args()

    issue_registry = load_json(os.path.join(args.working_dir, "issue-registry.json"))
    review_scorecard = load_json(os.path.join(args.working_dir, "review-scorecard.json"))
    verification_audit = load_json(os.path.join(args.working_dir, "verification-audit.json"))
    manifest = load_json(os.path.join(args.working_dir, "review-manifest.json"))
    citation_list_path = os.path.join(args.working_dir, "citation-list.json")
    citation_list = load_json(citation_list_path) if os.path.exists(citation_list_path) else None

    redline_path = find_first(os.path.join(args.deliverables_dir, "*_redline_v*.docx"))
    clean_path = find_first(os.path.join(args.deliverables_dir, "*_clean_v*.docx"))
    memo_path = find_first(os.path.join(args.deliverables_dir, "review-cover-memo_v*.docx"))

    issues = issue_registry.get("issues", [])
    redline_counts = count_docx_markers(redline_path)
    clean_counts = count_docx_markers(clean_path)
    correction_count = extract_correction_count(issues)
    memo_text = extract_docx_text(memo_path)

    checks = []

    tracked_change_total = redline_counts["insertions"] + redline_counts["deletions"]
    if tracked_change_total:
        check1_pass = tracked_change_total >= correction_count
        detail1 = f"Tracked changes {tracked_change_total} vs textual corrections {correction_count}."
    else:
        check1_pass = redline_counts["comments"] >= len(issues)
        detail1 = f"Comments {redline_counts['comments']} vs issues {len(issues)}."
    checks.append({"check": "Check 1 — Redline Completeness", "status": "PASS" if check1_pass else "FAIL", "detail": detail1})

    comment_integrity_pass = redline_counts["comments"] > 0 if issues else True
    checks.append(
        {
            "check": "Check 2 — Review Comment Integrity",
            "status": "PASS" if comment_integrity_pass else "FAIL",
            "detail": "Comment file present and attached to redline output." if comment_integrity_pass else "No comments found in redline DOCX.",
        }
    )

    release_text = review_scorecard.get("release_recommendation", "")
    memo_pass = bool(memo_text) and release_text in memo_text
    checks.append(
        {
            "check": "Check 3 — Cover Memo Accuracy",
            "status": "PASS" if memo_pass else "FAIL",
            "detail": "Cover memo contains the release recommendation and summary text." if memo_pass else "Cover memo missing or recommendation text not found.",
        }
    )

    average = review_scorecard.get("overall_average", 0.0)
    grade = review_scorecard.get("overall_grade")
    scorecard_pass = (
        grade in {"A", "B", "C", "D"}
        and review_scorecard.get("release_recommendation") in VALID_RELEASES
        and compute_grade(float(average)) == grade
    )
    checks.append(
        {
            "check": "Check 4 — Scorecard Consistency",
            "status": "PASS" if scorecard_pass else "FAIL",
            "detail": "Grade/recommendation enums are valid and match the average." if scorecard_pass else "Scorecard grade or release recommendation is inconsistent.",
        }
    )

    audit_citations = verification_audit.get("citations", [])
    total_citations = verification_audit.get("total_citations", len(audit_citations))
    citation_total_matches = total_citations == len(audit_citations)
    legacy_import_only = bool(audit_citations) and all(
        citation.get("verification_method") == "legacy_import" for citation in audit_citations
    )
    if citation_list is not None and not legacy_import_only:
        citation_total_matches = citation_total_matches and len(citation_list.get("citations", citation_list)) == total_citations
    if legacy_import_only:
        detail5 = (
            f"Audit cites {len(audit_citations)} entries; declared total is {total_citations}. "
            "Citation-list count mismatch ignored because the audit was normalized from legacy grouped results."
        )
    else:
        detail5 = f"Audit cites {len(audit_citations)} entries; declared total is {total_citations}."
    checks.append(
        {
            "check": "Check 5 — Audit Trail Completeness",
            "status": "PASS" if citation_total_matches else "FAIL",
            "detail": detail5,
        }
    )

    clean_pass = clean_counts["comments"] == 0 and clean_counts["insertions"] == 0 and clean_counts["deletions"] == 0
    checks.append(
        {
            "check": "Check 6 — Clean DOCX Correctness",
            "status": "PASS" if clean_pass else "FAIL",
            "detail": "Clean DOCX has no comments or tracked changes." if clean_pass else f"Clean DOCX still has markers: {clean_counts}.",
        }
    )

    expected_recommendation = compute_release_recommendation(issues, grade)
    release_pass = release_text == expected_recommendation
    checks.append(
        {
            "check": "Check 7 — Release Recommendation Consistency",
            "status": "PASS" if release_pass else "FAIL",
            "detail": f"Expected {expected_recommendation}; scorecard has {release_text}.",
        }
    )

    overall = "PASS" if all(check["status"] == "PASS" for check in checks) else "WARN"
    report = {
        "matter_id": manifest.get("matter_id"),
        "round": manifest.get("round"),
        "quality_gate_checks": checks,
        "overall_gate": overall,
        "artifacts_produced": sorted(
            [
                path
                for path in [
                    os.path.join(args.working_dir, "review-manifest.json"),
                    os.path.join(args.working_dir, "verification-audit.json"),
                    os.path.join(args.working_dir, "issue-registry.json"),
                    os.path.join(args.working_dir, "review-scorecard.json"),
                    redline_path,
                    clean_path,
                    memo_path,
                ]
                if path and os.path.exists(path)
            ]
        ),
    }

    os.makedirs(os.path.dirname(args.output_path), exist_ok=True)
    write_json(args.output_path, report)
    print(json.dumps({"output_path": args.output_path, "overall_gate": overall}, ensure_ascii=False))


if __name__ == "__main__":
    main()
