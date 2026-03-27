#!/usr/bin/env python3
"""
Build RR-2 rereview-diff.json from original/revised parsed structures.

Usage:
    python3 build-rereview-diff.py <original_parsed_json> <revised_parsed_json>
        <prior_issue_registry_json> <output_path>
"""

import difflib
import json
import os
import re
import sys


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def normalize_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def extract_paragraph_index(location):
    if isinstance(location, dict):
        para = location.get("paragraph_index")
        if isinstance(para, int):
            return para
        if isinstance(para, str):
            match = re.search(r"(\d+)", para)
            if match:
                return int(match.group(1))
        section = location.get("section", "")
        match = re.search(r"para(?:graph)?s?\s*(\d+)", section, re.IGNORECASE)
        if match:
            return int(match.group(1))
    elif isinstance(location, str):
        match = re.search(r"para(?:graph)?s?\s*(\d+)", location, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def similarity(a, b):
    return difflib.SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def find_best_match(text, revised_paragraphs):
    best_idx = None
    best_score = 0.0
    for idx, paragraph in enumerate(revised_paragraphs):
        candidate = paragraph.get("text", "")
        if not candidate:
            continue
        score = similarity(text, candidate)
        if score > best_score:
            best_idx = idx
            best_score = score
    return best_idx, best_score


def main():
    if len(sys.argv) != 5:
        print(json.dumps({"error": "Usage: build-rereview-diff.py <original_parsed_json> <revised_parsed_json> <prior_issue_registry_json> <output_path>"}))
        sys.exit(1)

    original = load_json(sys.argv[1])
    revised = load_json(sys.argv[2])
    prior_registry = load_json(sys.argv[3])
    output_path = sys.argv[4]

    original_paragraphs = original.get("paragraphs", [])
    revised_paragraphs = revised.get("paragraphs", [])
    mappings = []
    mapped_revised = set()

    for issue in prior_registry.get("issues", []):
        original_para = extract_paragraph_index(issue.get("location"))
        excerpt = ""
        if original_para is not None and 0 <= original_para < len(original_paragraphs):
            excerpt = original_paragraphs[original_para].get("text", "")
        else:
            excerpt = issue.get("description") or issue.get("title") or ""

        revised_para, best_score = find_best_match(excerpt, revised_paragraphs)
        if revised_para is not None and best_score >= 0.8:
            status = "mapped"
            mapped_revised.add(revised_para)
        elif revised_para is not None and best_score >= 0.35:
            status = "changed"
        else:
            status = "removed"
            revised_para = None

        mappings.append(
            {
                "prior_finding_id": issue.get("issue_id") or issue.get("id"),
                "original_para": original_para,
                "revised_para": revised_para,
                "mapping_status": status,
                "similarity": round(best_score, 3),
                "excerpt": excerpt[:240],
            }
        )

    new_paragraphs = []
    for idx, paragraph in enumerate(revised_paragraphs):
        text = normalize_text(paragraph.get("text", ""))
        if not text or idx in mapped_revised:
            continue
        best_score = 0.0
        for original_para in original_paragraphs:
            best_score = max(best_score, similarity(text, original_para.get("text", "")))
        if best_score < 0.8:
            new_paragraphs.append(
                {
                    "revised_para": idx,
                    "similarity_to_original": round(best_score, 3),
                    "text_excerpt": text[:240],
                }
            )

    payload = {
        "mappings": mappings,
        "new_or_changed_paragraphs": new_paragraphs,
        "summary": {
            "mapped": len([item for item in mappings if item["mapping_status"] == "mapped"]),
            "changed": len([item for item in mappings if item["mapping_status"] == "changed"]),
            "removed": len([item for item in mappings if item["mapping_status"] == "removed"]),
            "new_paragraphs": len(new_paragraphs),
        },
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    write_json(output_path, payload)
    print(json.dumps({"output_path": output_path, "summary": payload["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
