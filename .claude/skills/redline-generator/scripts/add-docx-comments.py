#!/usr/bin/env python3
"""
Generate a DOCX redline with comments and tracked changes, plus an optional clean
DOCX with accepted textual corrections applied.

Usage:
    python3 add-docx-comments.py <input_docx> <issue_registry_json> <output_redline_docx>
        [--clean-output <output_clean_docx>]
        [--verification-audit <verification_audit_json>]
        [--fallback-markdown <fallback_md_path>]

Output:
    Prints JSON summary to stdout.
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from copy import deepcopy
from datetime import datetime, timezone

_SHARED_SCRIPTS = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "scripts")
)
if _SHARED_SCRIPTS not in sys.path:
    sys.path.insert(0, _SHARED_SCRIPTS)

from artifact_meta import validate_artifacts, write_artifact_meta  # noqa: E402

# --- OOXML Namespaces ---
NAMESPACES = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "xml": "http://www.w3.org/XML/1998/namespace",
}

W_NS = NAMESPACES["w"]
R_NS = NAMESPACES["r"]
REL_NS = NAMESPACES["rel"]
CT_NS = NAMESPACES["ct"]
XML_NS = NAMESPACES["xml"]

COMMENT_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
COMMENT_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"

AUTHOR_KO = "시니어 리뷰 스페셜리스트"
AUTHOR_EN = "Senior Review Specialist"
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

COMMENT_STYLE_DEFS = """\
  <w:style w:type="character" w:styleId="CommentReference" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:name w:val="annotation reference"/>
    <w:basedOn w:val="DefaultParagraphFont"/>
    <w:uiPriority w:val="99"/>
    <w:semiHidden/>
    <w:unhideWhenUsed/>
    <w:rPr><w:sz w:val="16"/><w:szCs w:val="16"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="CommentText" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:name w:val="annotation text"/>
    <w:basedOn w:val="Normal"/>
    <w:link w:val="CommentTextChar"/>
    <w:uiPriority w:val="99"/>
    <w:semiHidden/>
    <w:unhideWhenUsed/>
    <w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>
  </w:style>
  <w:style w:type="character" w:customStyle="1" w:styleId="CommentTextChar" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:name w:val="Comment Text Char"/>
    <w:basedOn w:val="DefaultParagraphFont"/>
    <w:link w:val="CommentText"/>
    <w:uiPriority w:val="99"/>
    <w:semiHidden/>
    <w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>
  </w:style>"""

STATUS_PREFIX_MAP = {
    "Nonexistent": "[CRITICAL — NONEXISTENT]",
    "Wrong_Pinpoint": "[CRITICAL — WRONG PINPOINT]",
    "Unsupported_Proposition": "[CRITICAL — UNSUPPORTED]",
    "Wrong_Jurisdiction": "[MAJOR — WRONG JURISDICTION]",
    "Stale": "[MAJOR — STALE]",
    "Translation_Mismatch": "[MAJOR — TRANSLATION MISMATCH]",
    "Unverifiable_No_Access": "[MAJOR — UNVERIFIED]",
    "Unverifiable_No_Evidence": "[MAJOR — UNVERIFIED]",
    "Unverifiable_Secondary_Only": "[MINOR — SECONDARY ONLY]",
    "Unverifiable_Synthetic_Suspected": "[MAJOR — UNVERIFIED]",
}

LEGACY_STATUS_MAP = {
    "VERIFIED": "Verified",
    "NONEXISTENT": "Nonexistent",
    "STALE": "Stale",
    "UNVERIFIED": "Unverifiable_No_Evidence",
    "PARTIALLY_VERIFIED": "Unverifiable_Secondary_Only",
}


def register_namespaces():
    ns_map = {
        "w": W_NS,
        "r": R_NS,
        "wp": NAMESPACES["wp"],
        "mc": NAMESPACES["mc"],
        "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
        "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
        "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
        "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
        "v": "urn:schemas-microsoft-com:vml",
        "o": "urn:schemas-microsoft-com:office:office",
    }
    for prefix, uri in ns_map.items():
        ET.register_namespace(prefix, uri)


def normalize_ws(text):
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_quotes(text):
    return (
        (text or "")
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )


def sanitize_text_fragment(text):
    return normalize_ws(normalize_quotes(text)).strip("[](){}.,;: ")


def severity_title(value):
    if not value:
        return "Minor"
    raw = str(value).strip().lower()
    if raw.startswith("crit"):
        return "Critical"
    if raw.startswith("maj"):
        return "Major"
    if raw.startswith("sug"):
        return "Suggestion"
    return "Minor"


def severity_upper(value):
    return severity_title(value).upper()


def status_to_canonical(status, detail=None, title=None):
    raw = (status or "").strip()
    if not raw:
        return None
    if raw in STATUS_PREFIX_MAP:
        return raw
    upper = raw.upper()
    if upper in LEGACY_STATUS_MAP:
        mapped = LEGACY_STATUS_MAP[upper]
        if mapped == "Verified":
            return mapped
        if mapped == "Unverifiable_Secondary_Only" and detail and "upgradeable" in detail.lower():
            return "Unverifiable_Secondary_Only"
        return mapped
    if upper.startswith("WRONG_DETAIL"):
        detail_key = (detail or title or raw).lower()
        if "fabricated" in detail_key or "존재" in detail_key or "nonexistent" in detail_key:
            return "Nonexistent"
        if "conflation" in detail_key or "unsupported" in detail_key:
            return "Unsupported_Proposition"
        return "Wrong_Pinpoint"
    if "wrong pinpoint" in upper:
        return "Wrong_Pinpoint"
    if "nonexistent" in upper:
        return "Nonexistent"
    if "unsupported" in upper:
        return "Unsupported_Proposition"
    if "wrong jurisdiction" in upper:
        return "Wrong_Jurisdiction"
    if "translation mismatch" in upper:
        return "Translation_Mismatch"
    if "secondary" in upper:
        return "Unverifiable_Secondary_Only"
    if "unverified" in upper:
        return "Unverifiable_No_Evidence"
    return None


def get_author(language):
    return AUTHOR_KO if str(language).lower().startswith("ko") else AUTHOR_EN


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fail_artifact_validation(errors):
    print(
        json.dumps(
            {
                "error": "Artifact validation failed",
                "validation_errors": errors,
            },
            ensure_ascii=False,
        )
    )
    sys.exit(1)


def validate_input_artifacts(entries):
    errors = validate_artifacts(entries, require_meta=False)
    if errors:
        fail_artifact_validation(errors)


def load_issue_registry(path):
    registry = load_json(path)
    return registry, registry.get("issues", [])


def load_verification_lookup(path):
    if not path or not os.path.exists(path):
        return {}
    audit = load_json(path)
    lookup = {}
    citations = audit.get("citations", [])
    for entry in citations:
        cid = entry.get("citation_id")
        if cid:
            lookup[cid] = entry
    return lookup


def get_paragraph_text(p_elem):
    texts = []
    for t in p_elem.iter(f"{{{W_NS}}}t"):
        if t.text:
            texts.append(t.text)
    return "".join(texts)


def get_all_paragraphs(body):
    return list(body.iter(f"{{{W_NS}}}p"))


def clone(elem):
    return deepcopy(elem) if elem is not None else None


def extract_paragraph_index(location):
    if isinstance(location, dict):
        pi = location.get("paragraph_index")
        if isinstance(pi, int):
            return pi
        if isinstance(pi, str):
            match = re.search(r"(\d+)", pi)
            if match:
                return int(match.group(1))
        for key in ("section", "location", "text_excerpt"):
            value = location.get(key, "")
            if isinstance(value, str):
                match = re.search(r"para(?:graph)?s?\s*(\d+)", value, re.IGNORECASE)
                if match:
                    return int(match.group(1))
    if isinstance(location, str):
        match = re.search(r"para(?:graph)?s?\s*(\d+)", location, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def keyword_search(paragraphs, text_query, min_match=3):
    query = normalize_ws(text_query).lower()
    if not query:
        return None
    keywords = set(re.findall(r"[\w가-힣]{3,}", query))
    if len(keywords) < min_match:
        keywords = set(re.findall(r"[\w가-힣]{2,}", query))
    if not keywords:
        return None

    best_idx = None
    best_score = 0
    for idx, paragraph in enumerate(paragraphs):
        p_text = normalize_ws(get_paragraph_text(paragraph)).lower()
        if not p_text:
            continue
        p_words = set(re.findall(r"[\w가-힣]{2,}", p_text))
        overlap = len(keywords & p_words)
        if overlap > best_score and overlap >= min(min_match, len(keywords)):
            best_score = overlap
            best_idx = idx
    return best_idx


def find_paragraph_containing(paragraphs, needle):
    target = sanitize_text_fragment(needle)
    if not target:
        return None
    lowered = target.lower()
    for idx, paragraph in enumerate(paragraphs):
        p_text = normalize_ws(get_paragraph_text(paragraph)).lower()
        if lowered and lowered in p_text:
            return idx
    return keyword_search(paragraphs, target, min_match=2)


def issue_identifier(issue, fallback_index):
    return issue.get("issue_id") or issue.get("id") or issue.get("title") or f"issue-{fallback_index}"


def extract_anchor_text(issue):
    location = issue.get("location", {})
    if isinstance(location, dict):
        for key in ("anchor_text", "text", "text_excerpt"):
            value = sanitize_text_fragment(location.get(key))
            if value:
                return value
    evidence = issue.get("evidence", {})
    if isinstance(evidence, dict):
        for key in ("citation_text", "anchor_text"):
            value = sanitize_text_fragment(evidence.get(key))
            if value:
                return value
    return sanitize_text_fragment(issue.get("citation_text"))


def map_issue_to_paragraph_detail(issue, paragraphs):
    location = issue.get("location", {})
    idx = extract_paragraph_index(location)
    if idx is not None and 0 <= idx < len(paragraphs):
        paragraph_text = normalize_ws(get_paragraph_text(paragraphs[idx]))
        anchor_text = extract_anchor_text(issue)
        if isinstance(location, dict):
            start = location.get("char_start")
            end = location.get("char_end")
            if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(paragraph_text):
                return {
                    "paragraph_index": idx,
                    "mapping_status": "exact",
                    "reason": "location_char_span",
                    "anchor_text": paragraph_text[start:end],
                }
        if anchor_text and anchor_text.lower() in paragraph_text.lower():
            return {
                "paragraph_index": idx,
                "mapping_status": "exact",
                "reason": "location_anchor_text",
                "anchor_text": anchor_text,
            }
        return {
            "paragraph_index": idx,
            "mapping_status": "paragraph",
            "reason": "location_paragraph_index",
            "anchor_text": anchor_text,
        }

    for field in (issue.get("title", ""), issue.get("description", ""), issue.get("recommendation", "")):
        match = re.search(r"para(?:graph)?s?\s*(\d+)", str(field), re.IGNORECASE)
        if match:
            idx = int(match.group(1))
            if 0 <= idx < len(paragraphs):
                return {
                    "paragraph_index": idx,
                    "mapping_status": "paragraph",
                    "reason": "textual_paragraph_reference",
                    "anchor_text": extract_anchor_text(issue),
                }

    for field in (issue.get("title", ""), issue.get("description", "")):
        idx = keyword_search(paragraphs, field)
        if idx is not None:
            return {
                "paragraph_index": idx,
                "mapping_status": "fallback",
                "reason": "keyword_search",
                "anchor_text": extract_anchor_text(issue),
            }

    return {
        "paragraph_index": None,
        "mapping_status": "unmapped",
        "reason": "no_location_or_keyword_match",
        "anchor_text": extract_anchor_text(issue),
    }


def map_issue_to_paragraph(issue, paragraphs):
    return map_issue_to_paragraph_detail(issue, paragraphs).get("paragraph_index")


def extract_text_corrections(issue):
    corrections = []
    for typo in issue.get("typo_list", []):
        current = sanitize_text_fragment(typo.get("current"))
        correct = sanitize_text_fragment(typo.get("correct"))
        if current and correct:
            corrections.append({
                "old": current,
                "new": correct,
                "source": "typo_list",
            })

    candidates = [
        issue.get("recommendation", ""),
        issue.get("description", ""),
        issue.get("title", ""),
    ]
    quoted_pattern = re.compile(
        r"""["'](?P<old>[^"'\\]{1,80})["']\s*(?:→|->|=>)\s*["'](?P<new>[^"'\\]{1,80})["']"""
    )
    bare_pattern = re.compile(
        r"""(?P<old>[^\n]{1,60}?)\s*(?:→|->|=>)\s*(?P<new>[^\n]{1,60})"""
    )

    for text in candidates:
        if not text:
            continue
        normalized = normalize_quotes(text)
        for match in quoted_pattern.finditer(normalized):
            old = sanitize_text_fragment(match.group("old"))
            new = sanitize_text_fragment(match.group("new"))
            if old and new and old != new:
                corrections.append({"old": old, "new": new, "source": "quoted_arrow"})
        if corrections:
            continue
        for match in bare_pattern.finditer(normalized):
            old = sanitize_text_fragment(match.group("old"))
            new = sanitize_text_fragment(match.group("new"))
            if not old or not new or old == new:
                continue
            if len(old) > 60 or len(new) > 60:
                continue
            if "정정" not in normalized and "replace" not in normalized.lower():
                continue
            corrections.append({"old": old, "new": new, "source": "arrow"})
        if corrections:
            break

    deduped = []
    seen = set()
    for correction in corrections:
        key = (correction["old"], correction["new"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(correction)
    return deduped


def extract_comment_prefix_from_title(title):
    if not title:
        return None
    match = re.match(r"^\s*(\[[^\]]+\])", str(title))
    if not match:
        return None
    return match.group(1)


def build_comment_prefix(issue, verification_lookup):
    title_prefix = extract_comment_prefix_from_title(issue.get("title"))
    if title_prefix:
        return title_prefix

    evidence = issue.get("evidence", {})
    citation_id = evidence.get("citation_id") if isinstance(evidence, dict) else None
    if citation_id and citation_id in verification_lookup:
        status = verification_lookup[citation_id].get("verification_status")
        canonical = status_to_canonical(status)
        if canonical and canonical in STATUS_PREFIX_MAP:
            return STATUS_PREFIX_MAP[canonical]

    canonical = status_to_canonical(
        issue.get("verification_status"),
        detail=issue.get("description"),
        title=issue.get("title"),
    )
    if canonical and canonical in STATUS_PREFIX_MAP:
        return STATUS_PREFIX_MAP[canonical]

    return f"[{severity_upper(issue.get('severity'))}]"


def format_comment_text(issue, verification_lookup):
    prefix = build_comment_prefix(issue, verification_lookup)
    description = normalize_ws(issue.get("description", ""))
    recommendation = normalize_ws(issue.get("recommendation", ""))
    recurring_pattern = issue.get("recurring_pattern") or issue.get("pattern_id")

    parts = [prefix]
    if description:
        parts.append(description.rstrip(".") + ".")
    if recommendation:
        parts.append(recommendation.rstrip(".") + ".")
    if recurring_pattern:
        parts.append(f"[Recurring: {recurring_pattern}]")
    return " ".join(parts)


def get_first_run_properties(p_elem):
    for run in p_elem.findall(f"{{{W_NS}}}r"):
        rpr = run.find(f"{{{W_NS}}}rPr")
        if rpr is not None:
            return clone(rpr)
    return None


def clear_paragraph_content(p_elem):
    children = list(p_elem)
    for child in children:
        if child.tag != f"{{{W_NS}}}pPr":
            p_elem.remove(child)


def append_text_run(parent, text, template_rpr=None):
    if text == "":
        return
    run = ET.SubElement(parent, f"{{{W_NS}}}r")
    if template_rpr is not None:
        run.append(clone(template_rpr))
    t = ET.SubElement(run, f"{{{W_NS}}}t")
    if text != text.strip():
        t.set(f"{{{XML_NS}}}space", "preserve")
    t.text = text


def append_deleted_run(parent, text, change_id, template_rpr=None, author=AUTHOR_KO):
    if text == "":
        return
    deletion = ET.SubElement(parent, f"{{{W_NS}}}del")
    deletion.set(f"{{{W_NS}}}id", str(change_id))
    deletion.set(f"{{{W_NS}}}author", author)
    deletion.set(f"{{{W_NS}}}date", DATE)
    run = ET.SubElement(deletion, f"{{{W_NS}}}r")
    if template_rpr is not None:
        run.append(clone(template_rpr))
    del_text = ET.SubElement(run, f"{{{W_NS}}}delText")
    if text != text.strip():
        del_text.set(f"{{{XML_NS}}}space", "preserve")
    del_text.text = text


def append_inserted_run(parent, text, change_id, template_rpr=None, author=AUTHOR_KO):
    if text == "":
        return
    insertion = ET.SubElement(parent, f"{{{W_NS}}}ins")
    insertion.set(f"{{{W_NS}}}id", str(change_id))
    insertion.set(f"{{{W_NS}}}author", author)
    insertion.set(f"{{{W_NS}}}date", DATE)
    run = ET.SubElement(insertion, f"{{{W_NS}}}r")
    if template_rpr is not None:
        run.append(clone(template_rpr))
    t = ET.SubElement(run, f"{{{W_NS}}}t")
    if text != text.strip():
        t.set(f"{{{XML_NS}}}space", "preserve")
    t.text = text


def build_operations(text, corrections):
    operations = []
    occupied = []
    for correction in corrections:
        old = correction["old"]
        start = text.find(old)
        if start == -1:
            continue
        end = start + len(old)
        if any(not (end <= used_start or start >= used_end) for used_start, used_end in occupied):
            continue
        operations.append({
            "start": start,
            "end": end,
            "old": old,
            "new": correction["new"],
            "issue_ref": correction.get("issue_ref"),
        })
        occupied.append((start, end))
    operations.sort(key=lambda item: item["start"])
    return operations


def apply_operations_to_redline(paragraph, operations, author):
    if not operations:
        return 0
    original_text = get_paragraph_text(paragraph)
    if not original_text:
        return 0
    template_rpr = get_first_run_properties(paragraph)
    clear_paragraph_content(paragraph)

    cursor = 0
    next_change_id = 1
    for operation in operations:
        append_text_run(paragraph, original_text[cursor:operation["start"]], template_rpr)
        append_deleted_run(paragraph, operation["old"], next_change_id, template_rpr, author=author)
        append_inserted_run(paragraph, operation["new"], next_change_id, template_rpr, author=author)
        cursor = operation["end"]
        next_change_id += 1
    append_text_run(paragraph, original_text[cursor:], template_rpr)
    return len(operations)


def apply_operations_to_clean(paragraph, operations):
    if not operations:
        return 0
    original_text = get_paragraph_text(paragraph)
    if not original_text:
        return 0
    template_rpr = get_first_run_properties(paragraph)
    clear_paragraph_content(paragraph)

    cursor = 0
    updated_text = []
    for operation in operations:
        updated_text.append(original_text[cursor:operation["start"]])
        updated_text.append(operation["new"])
        cursor = operation["end"]
    updated_text.append(original_text[cursor:])
    append_text_run(paragraph, "".join(updated_text), template_rpr)
    return len(operations)


def insert_comment_markers(p_elem, comment_id):
    id_str = str(comment_id)
    range_start = ET.SubElement(p_elem, f"{{{W_NS}}}commentRangeStart")
    range_start.set(f"{{{W_NS}}}id", id_str)
    range_end = ET.SubElement(p_elem, f"{{{W_NS}}}commentRangeEnd")
    range_end.set(f"{{{W_NS}}}id", id_str)
    ref_run = ET.SubElement(p_elem, f"{{{W_NS}}}r")
    ref_rpr = ET.SubElement(ref_run, f"{{{W_NS}}}rPr")
    ref_style = ET.SubElement(ref_rpr, f"{{{W_NS}}}rStyle")
    ref_style.set(f"{{{W_NS}}}val", "CommentReference")
    ref_ref = ET.SubElement(ref_run, f"{{{W_NS}}}commentReference")
    ref_ref.set(f"{{{W_NS}}}id", id_str)

    p_elem.remove(range_start)
    p_elem.remove(range_end)
    p_elem.remove(ref_run)
    p_elem.insert(0, range_start)
    p_elem.append(range_end)
    p_elem.append(ref_run)


def build_comments_xml(comments_data, author):
    root = ET.Element(f"{{{W_NS}}}comments")
    root.set("xmlns:r", R_NS)
    for comment_id, text in comments_data:
        comment = ET.SubElement(root, f"{{{W_NS}}}comment")
        comment.set(f"{{{W_NS}}}id", str(comment_id))
        comment.set(f"{{{W_NS}}}author", author)
        comment.set(f"{{{W_NS}}}date", DATE)
        p = ET.SubElement(comment, f"{{{W_NS}}}p")
        r = ET.SubElement(p, f"{{{W_NS}}}r")
        t = ET.SubElement(r, f"{{{W_NS}}}t")
        t.text = text
    return root


def ensure_comments_relationship(rels_path):
    ET.register_namespace("", REL_NS)
    tree = ET.parse(rels_path)
    root = tree.getroot()
    for rel in root:
        if rel.get("Type", "") == COMMENT_REL_TYPE:
            return
    max_id = 0
    for rel in root:
        rid = rel.get("Id", "")
        match = re.search(r"rId(\d+)", rid)
        if match:
            max_id = max(max_id, int(match.group(1)))
    new_rel = ET.SubElement(root, "Relationship")
    new_rel.set("Id", f"rId{max_id + 1}")
    new_rel.set("Type", COMMENT_REL_TYPE)
    new_rel.set("Target", "comments.xml")
    tree.write(rels_path, xml_declaration=True, encoding="UTF-8")


def ensure_content_type(content_types_path):
    ET.register_namespace("", CT_NS)
    tree = ET.parse(content_types_path)
    root = tree.getroot()
    for override in root:
        if override.get("PartName", "") == "/word/comments.xml":
            return
    new_override = ET.SubElement(root, "Override")
    new_override.set("PartName", "/word/comments.xml")
    new_override.set("ContentType", COMMENT_CONTENT_TYPE)
    tree.write(content_types_path, xml_declaration=True, encoding="UTF-8")


def capture_original_document_tag(doc_xml_path):
    with open(doc_xml_path, "r", encoding="utf-8") as f:
        head = f.read(8192)
    match = re.search(r"(<w:document\s[^>]+>)", head, re.DOTALL)
    return match.group(1) if match else None


def restore_original_document_tag(doc_xml_path, original_tag):
    if not original_tag:
        return
    with open(doc_xml_path, "r", encoding="utf-8") as f:
        content = f.read()
    content = re.sub(r"<w:document\s[^>]+>", original_tag, content, count=1)
    with open(doc_xml_path, "w", encoding="utf-8") as f:
        f.write(content)


def ensure_comment_styles(styles_xml_path):
    if not os.path.exists(styles_xml_path):
        return
    with open(styles_xml_path, "r", encoding="utf-8") as f:
        content = f.read()
    if "CommentReference" in content:
        return
    content = content.replace("</w:styles>", COMMENT_STYLE_DEFS + "\n</w:styles>")
    with open(styles_xml_path, "w", encoding="utf-8") as f:
        f.write(content)


def sanitize_xml_bytes(content):
    return re.sub(rb"[\x00-\x08\x0B\x0C\x0E-\x1F]", b"", content)


def parse_xml_with_repair(xml_path):
    try:
        return ET.parse(xml_path), False
    except ET.ParseError:
        with open(xml_path, "rb") as f:
            repaired = sanitize_xml_bytes(f.read())
        with open(xml_path, "wb") as f:
            f.write(repaired)
        return ET.parse(xml_path), True


def repack_docx(tmpdir, output_docx):
    with zipfile.ZipFile(output_docx, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, _, filenames in os.walk(tmpdir):
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                arcname = os.path.relpath(full_path, tmpdir)
                zf.write(full_path, arcname)


def write_fallback_markdown(path, input_docx, issues, reason):
    if not path:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [
        "# Redline Generation Fallback",
        "",
        f"- Source DOCX: `{input_docx}`",
        f"- Failure reason: {reason}",
        "",
        "## Issues",
        "",
    ]
    if not issues:
        lines.append("- No issues supplied.")
    else:
        for issue in issues:
            lines.append(
                f"- {build_comment_prefix(issue, {})} "
                f"{normalize_ws(issue.get('description') or issue.get('title') or 'Issue')}"
            )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def build_mapping_report(total_issues, mapping_items):
    summary = {
        "total_issues": total_issues,
        "exact_mapped": 0,
        "paragraph_mapped": 0,
        "fallback_mapped": 0,
        "unmapped": 0,
        "critical_major_total": 0,
        "critical_major_exact": 0,
        "critical_major_unmapped": 0,
        "critical_major_exact_rate": 1.0,
    }
    for item in mapping_items:
        status = item.get("mapping_status")
        severity = item.get("severity")
        if status == "exact":
            summary["exact_mapped"] += 1
        elif status == "paragraph":
            summary["paragraph_mapped"] += 1
        elif status == "fallback":
            summary["fallback_mapped"] += 1
        else:
            summary["unmapped"] += 1

        if severity in {"Critical", "Major"}:
            summary["critical_major_total"] += 1
            if status == "exact":
                summary["critical_major_exact"] += 1
            if status == "unmapped":
                summary["critical_major_unmapped"] += 1

    if summary["critical_major_total"]:
        summary["critical_major_exact_rate"] = (
            summary["critical_major_exact"] / summary["critical_major_total"]
        )
    return {
        "generated_at": DATE,
        "summary": summary,
        "items": mapping_items,
    }


def write_mapping_report(path, report):
    if not path:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    write_artifact_meta(
        path,
        artifact_type="redline_mapping_report",
        producer={"step": "WF1_STEP_7", "skill": "redline-generator", "script": "add-docx-comments.py"},
    )


def prepare_issue_mappings(issues, redline_paragraphs):
    issue_para_map = {}
    comment_para_map = {}
    corrections_by_para = {}
    unmapped_issues = []
    mapping_items = []

    for idx, issue in enumerate(issues, 1):
        issue_ref = issue_identifier(issue, idx)
        detail = map_issue_to_paragraph_detail(issue, redline_paragraphs)
        base_para = detail.get("paragraph_index")
        mapping_status = detail.get("mapping_status", "unmapped")
        mapping_reason = detail.get("reason")
        corrections = extract_text_corrections(issue)
        correction_para = None

        for correction in corrections:
            target_para = find_paragraph_containing(redline_paragraphs, correction["old"])
            if target_para is None and base_para is not None:
                paragraph_text = get_paragraph_text(redline_paragraphs[base_para])
                if correction["old"] in paragraph_text:
                    target_para = base_para
            if target_para is None:
                continue
            correction_para = target_para if correction_para is None else correction_para
            correction["issue_ref"] = issue_ref
            corrections_by_para.setdefault(target_para, []).append(correction)

        chosen_para = base_para if base_para is not None else correction_para
        if base_para is None and correction_para is not None:
            mapping_status = "exact"
            mapping_reason = "text_correction_match"
        if chosen_para is not None:
            issue_para_map[issue_ref] = chosen_para
            comment_para_map[issue_ref] = chosen_para
        else:
            unmapped_issues.append(issue)

        mapping_items.append(
            {
                "issue_id": issue_ref,
                "severity": severity_title(issue.get("severity")),
                "mapping_status": mapping_status if chosen_para is not None else "unmapped",
                "target_paragraph_index": chosen_para,
                "reason": mapping_reason if chosen_para is not None else "no_location_or_keyword_match",
                "anchor_text": detail.get("anchor_text"),
                "has_text_correction": bool(corrections),
            }
        )

    return issue_para_map, comment_para_map, corrections_by_para, unmapped_issues, mapping_items


def process_docx(input_docx, redline_output, clean_output, issues, verification_lookup, language):
    author = get_author(language)
    shutil.copy2(input_docx, redline_output)
    if clean_output:
        shutil.copy2(input_docx, clean_output)

    with tempfile.TemporaryDirectory() as redline_tmp:
        with zipfile.ZipFile(redline_output, "r") as zf:
            zf.extractall(redline_tmp)

        clean_tmp = None
        if clean_output:
            clean_tmp = tempfile.TemporaryDirectory()
            with zipfile.ZipFile(clean_output, "r") as zf:
                zf.extractall(clean_tmp.name)

        doc_xml_path = os.path.join(redline_tmp, "word", "document.xml")
        rels_path = os.path.join(redline_tmp, "word", "_rels", "document.xml.rels")
        content_types_path = os.path.join(redline_tmp, "[Content_Types].xml")
        styles_xml_path = os.path.join(redline_tmp, "word", "styles.xml")

        if not os.path.exists(doc_xml_path):
            raise FileNotFoundError("document.xml not found in DOCX")

        register_namespaces()
        original_doc_tag = capture_original_document_tag(doc_xml_path)
        redline_tree, repaired = parse_xml_with_repair(doc_xml_path)
        redline_root = redline_tree.getroot()
        redline_body = redline_root.find(f"{{{W_NS}}}body")
        if redline_body is None:
            raise ValueError("No <w:body> found in document.xml")
        redline_paragraphs = get_all_paragraphs(redline_body)
        if not redline_paragraphs:
            raise ValueError("No paragraphs found in document")

        clean_tree = None
        clean_root = None
        clean_body = None
        clean_paragraphs = None
        clean_repaired = False
        clean_original_doc_tag = None
        if clean_tmp is not None:
            clean_doc_xml_path = os.path.join(clean_tmp.name, "word", "document.xml")
            clean_original_doc_tag = capture_original_document_tag(clean_doc_xml_path)
            clean_tree, clean_repaired = parse_xml_with_repair(clean_doc_xml_path)
            clean_root = clean_tree.getroot()
            clean_body = clean_root.find(f"{{{W_NS}}}body")
            clean_paragraphs = get_all_paragraphs(clean_body) if clean_body is not None else []

        issue_para_map, comment_para_map, corrections_by_para, unmapped_issues, mapping_items = prepare_issue_mappings(
            issues,
            redline_paragraphs,
        )

        tracked_changes_applied = 0
        clean_changes_applied = 0
        for para_idx, corrections in corrections_by_para.items():
            paragraph_text = get_paragraph_text(redline_paragraphs[para_idx])
            operations = build_operations(paragraph_text, corrections)
            if not operations:
                continue
            tracked_changes_applied += apply_operations_to_redline(redline_paragraphs[para_idx], operations, author)
            if clean_paragraphs is not None and para_idx < len(clean_paragraphs):
                clean_changes_applied += apply_operations_to_clean(clean_paragraphs[para_idx], operations)

        comments_data = []
        comment_id = 1
        mapped_comment_count = 0
        for issue in issues:
            issue_ref = issue.get("issue_id") or issue.get("id") or issue.get("title") or f"issue-{comment_id}"
            para_idx = comment_para_map.get(issue_ref)
            comment_text = format_comment_text(issue, verification_lookup)
            if para_idx is None:
                continue
            insert_comment_markers(redline_paragraphs[para_idx], comment_id)
            comments_data.append((comment_id, comment_text))
            mapped_comment_count += 1
            comment_id += 1

        if unmapped_issues:
            combined = "아래 이슈들은 문서 내 위치를 특정하지 못했습니다:\n" + "\n".join(
                f"({idx}) {format_comment_text(issue, verification_lookup)}"
                for idx, issue in enumerate(unmapped_issues, 1)
            )
            insert_comment_markers(redline_paragraphs[-1], comment_id)
            comments_data.append((comment_id, combined))

        if comments_data:
            comments_root = build_comments_xml(comments_data, author)
            comments_path = os.path.join(redline_tmp, "word", "comments.xml")
            ET.ElementTree(comments_root).write(comments_path, xml_declaration=True, encoding="UTF-8")
            if os.path.exists(rels_path):
                ensure_comments_relationship(rels_path)
            if os.path.exists(content_types_path):
                ensure_content_type(content_types_path)

        redline_tree.write(doc_xml_path, xml_declaration=True, encoding="UTF-8")
        restore_original_document_tag(doc_xml_path, original_doc_tag)
        ensure_comment_styles(styles_xml_path)
        repack_docx(redline_tmp, redline_output)

        if clean_tree is not None:
            clean_doc_xml_path = os.path.join(clean_tmp.name, "word", "document.xml")
            clean_tree.write(clean_doc_xml_path, xml_declaration=True, encoding="UTF-8")
            restore_original_document_tag(clean_doc_xml_path, clean_original_doc_tag)
            repack_docx(clean_tmp.name, clean_output)
            clean_tmp.cleanup()

    return {
        "repaired_xml": repaired or clean_repaired,
        "mapped_comments": mapped_comment_count,
        "unmapped_issues": len(unmapped_issues),
        "mapping_report": build_mapping_report(len(issues), mapping_items),
        "tracked_changes_applied": tracked_changes_applied,
        "clean_changes_applied": clean_changes_applied,
        "redline_output": redline_output,
        "clean_output": clean_output,
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_docx")
    parser.add_argument("issue_registry_json")
    parser.add_argument("output_redline_docx")
    parser.add_argument("--clean-output", dest="clean_output")
    parser.add_argument("--verification-audit", dest="verification_audit")
    parser.add_argument("--fallback-markdown", dest="fallback_markdown")
    parser.add_argument("--mapping-report", dest="mapping_report")
    return parser.parse_args()


def main():
    args = parse_args()

    if not os.path.exists(args.input_docx):
        print(json.dumps({"error": f"Input DOCX not found: {args.input_docx}"}, ensure_ascii=False))
        sys.exit(1)
    if not zipfile.is_zipfile(args.input_docx):
        print(json.dumps({"error": f"Input is not a valid DOCX/ZIP file: {args.input_docx}"}, ensure_ascii=False))
        sys.exit(1)

    validate_input_artifacts(
        [
            (args.issue_registry_json, "issue_registry"),
            (args.verification_audit, "verification_audit"),
        ]
    )
    registry, issues = load_issue_registry(args.issue_registry_json)
    verification_lookup = load_verification_lookup(args.verification_audit)
    mapping_report_path = args.mapping_report or os.path.join(
        os.path.dirname(args.issue_registry_json),
        "redline-mapping-report.json",
    )
    manifest_path = os.path.join(os.path.dirname(args.issue_registry_json), "review-manifest.json")
    language = "ko"
    if os.path.exists(manifest_path):
        manifest = load_json(manifest_path)
        language = manifest.get("document", {}).get("language", language)

    os.makedirs(os.path.dirname(args.output_redline_docx), exist_ok=True)
    if args.clean_output:
        os.makedirs(os.path.dirname(args.clean_output), exist_ok=True)

    if not issues:
        shutil.copy2(args.input_docx, args.output_redline_docx)
        if args.clean_output:
            shutil.copy2(args.input_docx, args.clean_output)
        mapping_report = build_mapping_report(0, [])
        write_mapping_report(mapping_report_path, mapping_report)
        summary = {
            "total_issues": 0,
            "mapped": 0,
            "unmapped": 0,
            "mapping_rate": "100.0%",
            "tracked_changes_applied": 0,
            "clean_changes_applied": 0,
            "redline_output": args.output_redline_docx,
            "clean_output": args.clean_output,
            "mapping_report": mapping_report_path,
            "fallback_markdown": None,
        }
        print(json.dumps(summary, ensure_ascii=False))
        return

    try:
        result = process_docx(
            args.input_docx,
            args.output_redline_docx,
            args.clean_output,
            issues,
            verification_lookup,
            language,
        )
        write_mapping_report(mapping_report_path, result["mapping_report"])
        summary = {
            "total_issues": len(issues),
            "mapped": result["mapped_comments"],
            "unmapped": result["unmapped_issues"],
            "mapping_rate": f"{result['mapped_comments'] / len(issues) * 100:.1f}%",
            "tracked_changes_applied": result["tracked_changes_applied"],
            "clean_changes_applied": result["clean_changes_applied"],
            "repaired_xml": result["repaired_xml"],
            "redline_output": result["redline_output"],
            "clean_output": result["clean_output"],
            "mapping_report": mapping_report_path,
            "fallback_markdown": None,
        }
        print(json.dumps(summary, ensure_ascii=False))
    except Exception as exc:
        fallback_path = args.fallback_markdown
        if not fallback_path:
            base, _ = os.path.splitext(args.output_redline_docx)
            fallback_path = base + "_fallback.md"
        write_fallback_markdown(fallback_path, args.input_docx, issues, str(exc))
        print(
            json.dumps(
                {
                    "error": str(exc),
                    "redline_output": args.output_redline_docx,
                    "clean_output": args.clean_output,
                    "fallback_markdown": fallback_path,
                },
                ensure_ascii=False,
            )
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
