#!/usr/bin/env python3
"""
Insert margin comments into a DOCX file based on issue-registry.json findings.

Phase 1 implementation: comment-only redline (no tracked changes).
Uses only Python stdlib — no python-docx dependency.

Usage:
    python3 add-docx-comments.py <input_docx> <issue_registry_json> <output_docx>

Output:
    Prints JSON summary to stdout: {"total_issues": N, "mapped": M, "unmapped": U, "output_path": "..."}
"""

import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# --- OOXML Namespaces ---
NAMESPACES = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

W_NS = NAMESPACES["w"]
R_NS = NAMESPACES["r"]
REL_NS = NAMESPACES["rel"]
CT_NS = NAMESPACES["ct"]

COMMENT_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
COMMENT_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"

AUTHOR = "10년차 파트너 변호사 반성문"
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def register_namespaces():
    """Register all known namespaces to preserve them on write-back."""
    # Common OOXML namespaces that may appear in document.xml
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


def get_paragraph_text(p_elem):
    """Extract plain text from a <w:p> element."""
    texts = []
    for t in p_elem.iter(f"{{{W_NS}}}t"):
        if t.text:
            texts.append(t.text)
    return "".join(texts)


def get_all_paragraphs(body):
    """Get all <w:p> elements directly under <w:body>."""
    return list(body.iter(f"{{{W_NS}}}p"))


def extract_paragraph_index(location):
    """Try to extract a paragraph index from issue location data."""
    if isinstance(location, dict):
        pi = location.get("paragraph_index")
        if isinstance(pi, int):
            return pi
        if isinstance(pi, str):
            m = re.search(r"(\d+)", pi)
            if m:
                return int(m.group(1))
        # Try section field
        for key in ("section", "location"):
            val = location.get(key, "")
            if isinstance(val, str):
                m = re.search(r"para(?:graph)?\s*(\d+)", val, re.IGNORECASE)
                if m:
                    return int(m.group(1))
    if isinstance(location, str):
        m = re.search(r"para(?:graph)?\s*(\d+)", location, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None


def keyword_search(paragraphs, text_query, min_match=3):
    """Find the best matching paragraph for a text query using keyword overlap."""
    if not text_query:
        return None
    # Extract keywords (3+ char words)
    keywords = set(re.findall(r"[\w가-힣]{3,}", text_query.lower()))
    if len(keywords) < min_match:
        keywords = set(re.findall(r"[\w가-힣]{2,}", text_query.lower()))
    if not keywords:
        return None

    best_idx = None
    best_score = 0
    for i, p in enumerate(paragraphs):
        p_text = get_paragraph_text(p).lower()
        if not p_text:
            continue
        p_words = set(re.findall(r"[\w가-힣]{2,}", p_text))
        overlap = len(keywords & p_words)
        if overlap > best_score and overlap >= min(min_match, len(keywords)):
            best_score = overlap
            best_idx = i
    return best_idx


def map_issue_to_paragraph(issue, paragraphs):
    """Map an issue to a paragraph index using 3 fallback strategies."""
    location = issue.get("location", {})

    # Strategy 1: Direct paragraph_index
    idx = extract_paragraph_index(location)
    if idx is not None and 0 <= idx < len(paragraphs):
        return idx

    # Strategy 2: Parse from string fields
    for field in [issue.get("description", ""), issue.get("recommendation", "")]:
        m = re.search(r"para(?:graph)?\s*(\d+)", str(field), re.IGNORECASE)
        if m:
            idx = int(m.group(1))
            if 0 <= idx < len(paragraphs):
                return idx

    # Strategy 3: Keyword search using description
    desc = issue.get("description", "")
    idx = keyword_search(paragraphs, desc)
    if idx is not None:
        return idx

    return None


def format_comment_text(issue):
    """Format the comment text with severity prefix."""
    severity = issue.get("severity", "MINOR").upper()
    desc = issue.get("description", "")
    rec = issue.get("recommendation", "")

    prefix = f"[{severity}]"
    parts = [prefix]
    if desc:
        parts.append(desc.rstrip(".") + ".")
    if rec:
        parts.append(rec.rstrip(".") + ".")
    return " ".join(parts)


def insert_comment_markers(p_elem, comment_id):
    """Insert comment range markers into a paragraph element."""
    id_str = str(comment_id)

    # Create commentRangeStart
    range_start = ET.SubElement(p_elem, f"{{{W_NS}}}commentRangeStart")
    range_start.set(f"{{{W_NS}}}id", id_str)

    # Create commentRangeEnd
    range_end = ET.SubElement(p_elem, f"{{{W_NS}}}commentRangeEnd")
    range_end.set(f"{{{W_NS}}}id", id_str)

    # Create run with commentReference
    ref_run = ET.SubElement(p_elem, f"{{{W_NS}}}r")
    ref_rpr = ET.SubElement(ref_run, f"{{{W_NS}}}rPr")
    ref_style = ET.SubElement(ref_rpr, f"{{{W_NS}}}rStyle")
    ref_style.set(f"{{{W_NS}}}val", "CommentReference")
    ref_ref = ET.SubElement(ref_run, f"{{{W_NS}}}commentReference")
    ref_ref.set(f"{{{W_NS}}}id", id_str)

    # Reorder: commentRangeStart should be FIRST, then existing content, then end+ref
    children = list(p_elem)
    # Remove our newly added elements
    p_elem.remove(range_start)
    p_elem.remove(range_end)
    p_elem.remove(ref_run)

    # Re-insert: start at beginning, end+ref at end
    p_elem.insert(0, range_start)
    p_elem.append(range_end)
    p_elem.append(ref_run)


def build_comments_xml(comments_data):
    """Build word/comments.xml from a list of (id, text) tuples."""
    root = ET.Element(f"{{{W_NS}}}comments")
    root.set("xmlns:w", W_NS)
    root.set("xmlns:r", R_NS)

    for cid, text in comments_data:
        comment = ET.SubElement(root, f"{{{W_NS}}}comment")
        comment.set(f"{{{W_NS}}}id", str(cid))
        comment.set(f"{{{W_NS}}}author", AUTHOR)
        comment.set(f"{{{W_NS}}}date", DATE)
        p = ET.SubElement(comment, f"{{{W_NS}}}p")
        r = ET.SubElement(p, f"{{{W_NS}}}r")
        t = ET.SubElement(r, f"{{{W_NS}}}t")
        t.text = text

    return root


def ensure_comments_relationship(rels_path):
    """Add comments.xml relationship to document.xml.rels if not present."""
    ET.register_namespace("", REL_NS)
    tree = ET.parse(rels_path)
    root = tree.getroot()

    # Check if relationship already exists
    for rel in root:
        rel_type = rel.get("Type", "")
        if rel_type == COMMENT_REL_TYPE:
            return  # Already exists

    # Find max rId
    max_id = 0
    for rel in root:
        rid = rel.get("Id", "")
        m = re.search(r"rId(\d+)", rid)
        if m:
            max_id = max(max_id, int(m.group(1)))

    # Add new relationship
    new_rel = ET.SubElement(root, "Relationship")
    new_rel.set("Id", f"rId{max_id + 1}")
    new_rel.set("Type", COMMENT_REL_TYPE)
    new_rel.set("Target", "comments.xml")

    tree.write(rels_path, xml_declaration=True, encoding="UTF-8")


def ensure_content_type(content_types_path):
    """Add comments content type to [Content_Types].xml if not present."""
    ET.register_namespace("", CT_NS)
    tree = ET.parse(content_types_path)
    root = tree.getroot()

    # Check if override already exists
    for override in root:
        part = override.get("PartName", "")
        if part == "/word/comments.xml":
            return  # Already exists

    # Add override
    new_override = ET.SubElement(root, "Override")
    new_override.set("PartName", "/word/comments.xml")
    new_override.set("ContentType", COMMENT_CONTENT_TYPE)

    tree.write(content_types_path, xml_declaration=True, encoding="UTF-8")


def main():
    if len(sys.argv) != 4:
        print(json.dumps({"error": "Usage: add-docx-comments.py <input_docx> <issue_registry_json> <output_docx>"}))
        sys.exit(1)

    input_docx = sys.argv[1]
    issue_registry_path = sys.argv[2]
    output_docx = sys.argv[3]

    # Validate input
    if not os.path.exists(input_docx):
        print(json.dumps({"error": f"Input DOCX not found: {input_docx}"}))
        sys.exit(1)
    if not zipfile.is_zipfile(input_docx):
        print(json.dumps({"error": f"Input is not a valid DOCX/ZIP file: {input_docx}"}))
        sys.exit(1)

    # Load issue registry
    try:
        with open(issue_registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
        issues = registry.get("issues", [])
    except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
        print(json.dumps({"error": f"Failed to load issue registry: {e}"}))
        sys.exit(1)

    if not issues:
        print(json.dumps({"error": "No issues found in issue registry", "total_issues": 0}))
        sys.exit(1)

    # Copy input to output
    shutil.copy2(input_docx, output_docx)

    # Work in temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # Unzip
        with zipfile.ZipFile(output_docx, "r") as zf:
            zf.extractall(tmpdir)

        doc_xml_path = os.path.join(tmpdir, "word", "document.xml")
        rels_path = os.path.join(tmpdir, "word", "_rels", "document.xml.rels")
        content_types_path = os.path.join(tmpdir, "[Content_Types].xml")

        if not os.path.exists(doc_xml_path):
            print(json.dumps({"error": "document.xml not found in DOCX"}))
            sys.exit(1)

        # Register namespaces before parsing
        register_namespaces()

        # Parse document.xml
        tree = ET.parse(doc_xml_path)
        root = tree.getroot()
        body = root.find(f"{{{W_NS}}}body")
        if body is None:
            print(json.dumps({"error": "No <w:body> found in document.xml"}))
            sys.exit(1)

        paragraphs = get_all_paragraphs(body)
        if not paragraphs:
            print(json.dumps({"error": "No paragraphs found in document"}))
            sys.exit(1)

        # Map issues to paragraphs and insert comments
        comments_data = []
        mapped_count = 0
        unmapped_issues = []
        comment_id = 1

        for issue in issues:
            para_idx = map_issue_to_paragraph(issue, paragraphs)
            comment_text = format_comment_text(issue)

            if para_idx is not None:
                try:
                    insert_comment_markers(paragraphs[para_idx], comment_id)
                    comments_data.append((comment_id, comment_text))
                    mapped_count += 1
                    comment_id += 1
                except Exception:
                    unmapped_issues.append(issue)
            else:
                unmapped_issues.append(issue)

        # Handle unmapped issues — attach as a single comment to last paragraph
        if unmapped_issues:
            unmapped_texts = []
            for i, issue in enumerate(unmapped_issues, 1):
                unmapped_texts.append(f"({i}) {format_comment_text(issue)}")
            combined = "아래 이슈들은 문서 내 위치를 특정하지 못했습니다:\n" + "\n".join(unmapped_texts)
            last_para = paragraphs[-1]
            try:
                insert_comment_markers(last_para, comment_id)
                comments_data.append((comment_id, combined))
                comment_id += 1
            except Exception:
                pass  # Last resort — skip if even this fails

        # Build comments.xml
        if comments_data:
            comments_root = build_comments_xml(comments_data)
            comments_path = os.path.join(tmpdir, "word", "comments.xml")
            comments_tree = ET.ElementTree(comments_root)
            comments_tree.write(comments_path, xml_declaration=True, encoding="UTF-8")

            # Update relationships
            if os.path.exists(rels_path):
                ensure_comments_relationship(rels_path)

            # Update content types
            if os.path.exists(content_types_path):
                ensure_content_type(content_types_path)

        # Write modified document.xml
        tree.write(doc_xml_path, xml_declaration=True, encoding="UTF-8")

        # Repack DOCX
        with zipfile.ZipFile(output_docx, "w", zipfile.ZIP_DEFLATED) as zf:
            for dirpath, dirnames, filenames in os.walk(tmpdir):
                for fn in filenames:
                    full_path = os.path.join(dirpath, fn)
                    arcname = os.path.relpath(full_path, tmpdir)
                    zf.write(full_path, arcname)

    # Output summary
    summary = {
        "total_issues": len(issues),
        "mapped": mapped_count,
        "unmapped": len(unmapped_issues),
        "mapping_rate": f"{mapped_count / len(issues) * 100:.1f}%" if issues else "0%",
        "output_path": output_docx,
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
