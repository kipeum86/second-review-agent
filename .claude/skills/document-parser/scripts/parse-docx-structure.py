#!/usr/bin/env python3
"""
Parse DOCX structure: extract headings, sections, numbering, cross-references, and full text.

Usage: python3 parse-docx-structure.py <docx_path> <output_dir>
Outputs: parsed-structure.json in output_dir
"""

import sys
import os
import json
import re
import zipfile
import xml.etree.ElementTree as ET

# OOXML namespaces
NSMAP = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}

HEADING_STYLES = {
    'Heading1': 1, 'Heading2': 2, 'Heading3': 3,
    'Heading4': 4, 'Heading5': 5, 'Heading6': 6,
    'heading 1': 1, 'heading 2': 2, 'heading 3': 3,
    'heading 4': 4, 'heading 5': 5, 'heading 6': 6,
    'Title': 1, 'Subtitle': 2,
}

# Korean legal structure patterns
KR_ARTICLE_RE = re.compile(r'^제\s*(\d+)\s*조[\s(]')         # 제1조, 제2조
KR_PARAGRAPH_RE = re.compile(r'^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]')
KR_SUBPARA_RE = re.compile(r'^\d+\.')
KR_ITEM_RE = re.compile(r'^[가나다라마바사아자차카타파하]\.')

# Cross-reference patterns
XREF_KR_RE = re.compile(r'(?:위|본|이|동|상기)\s*제\s*(\d+)\s*조(?:\s*제\s*(\d+)\s*항)?')
XREF_EN_RE = re.compile(r'(?:Section|Article|Clause)\s+(\d+(?:\.\d+)*)', re.IGNORECASE)


def extract_paragraphs(docx_path: str) -> list[dict] | None:
    """Extract all paragraphs from DOCX with metadata."""
    try:
        with zipfile.ZipFile(docx_path, 'r') as z:
            if 'word/document.xml' not in z.namelist():
                return None
            xml_content = z.read('word/document.xml')
    except (zipfile.BadZipFile, KeyError):
        return None

    root = ET.fromstring(xml_content)
    body = root.find(f'{{{NSMAP["w"]}}}body')
    if body is None:
        return None

    paragraphs = []
    para_idx = 0

    for element in body:
        tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag

        if tag == 'p':
            para = _process_paragraph(element, para_idx)
            paragraphs.append(para)
            para_idx += 1
        elif tag == 'tbl':
            table_paras = _process_table(element, para_idx)
            paragraphs.extend(table_paras)
            para_idx += len(table_paras)

    return paragraphs


def _get_style(p_elem) -> str | None:
    """Get paragraph style name."""
    pPr = p_elem.find(f'{{{NSMAP["w"]}}}pPr')
    if pPr is not None:
        pStyle = pPr.find(f'{{{NSMAP["w"]}}}pStyle')
        if pStyle is not None:
            return pStyle.get(f'{{{NSMAP["w"]}}}val', '')
    return None


def _get_text(elem) -> str:
    """Extract all text from an element."""
    texts = []
    for t in elem.iter(f'{{{NSMAP["w"]}}}t'):
        if t.text:
            texts.append(t.text)
    return ''.join(texts)


def _process_paragraph(p_elem, idx: int) -> dict:
    """Process a single <w:p> paragraph element."""
    style = _get_style(p_elem)
    text = _get_text(p_elem).strip()
    heading_level = HEADING_STYLES.get(style, 0) if style else 0

    # Detect Korean article-level headings even without heading style
    if not heading_level and text:
        if KR_ARTICLE_RE.match(text):
            heading_level = 2  # Treat 제X조 as heading level 2
        elif KR_PARAGRAPH_RE.match(text):
            heading_level = 3  # Treat ①②③ as heading level 3

    # Detect numbering
    numbering = None
    pPr = p_elem.find(f'{{{NSMAP["w"]}}}pPr')
    if pPr is not None:
        numPr = pPr.find(f'{{{NSMAP["w"]}}}numPr')
        if numPr is not None:
            ilvl = numPr.find(f'{{{NSMAP["w"]}}}ilvl')
            numId = numPr.find(f'{{{NSMAP["w"]}}}numId')
            numbering = {
                'level': int(ilvl.get(f'{{{NSMAP["w"]}}}val', '0')) if ilvl is not None else 0,
                'numId': numId.get(f'{{{NSMAP["w"]}}}val', '') if numId is not None else '',
            }

    return {
        'index': idx,
        'text': text,
        'style': style,
        'heading_level': heading_level,
        'numbering': numbering,
        'is_table': False,
    }


def _process_table(tbl_elem, start_idx: int) -> list[dict]:
    """Process a <w:tbl> table into paragraph entries."""
    paragraphs = []
    idx = start_idx

    for tr_idx, tr in enumerate(tbl_elem.iter(f'{{{NSMAP["w"]}}}tr')):
        cells = []
        for tc in tr.iter(f'{{{NSMAP["w"]}}}tc'):
            cell_text = _get_text(tc).strip()
            cells.append(cell_text)

        row_text = ' | '.join(cells)
        paragraphs.append({
            'index': idx,
            'text': row_text,
            'style': None,
            'heading_level': 0,
            'numbering': None,
            'is_table': True,
            'table_row': tr_idx,
        })
        idx += 1

    return paragraphs


def build_sections(paragraphs: list[dict]) -> list[dict]:
    """Build section hierarchy from paragraphs."""
    sections = []
    current_section = None

    for para in paragraphs:
        if para['heading_level'] > 0 and para['text']:
            if current_section:
                sections.append(current_section)
            current_section = {
                'title': para['text'],
                'level': para['heading_level'],
                'start_index': para['index'],
                'end_index': para['index'],
                'paragraph_count': 0,
            }
        elif current_section:
            current_section['end_index'] = para['index']
            current_section['paragraph_count'] += 1

    if current_section:
        sections.append(current_section)

    return sections


def extract_cross_references(paragraphs: list[dict]) -> list[dict]:
    """Extract internal cross-references from all paragraphs."""
    xrefs = []

    for para in paragraphs:
        text = para['text']
        if not text:
            continue

        # Korean cross-references
        for m in XREF_KR_RE.finditer(text):
            xref = {
                'source_index': para['index'],
                'target_article': int(m.group(1)),
                'target_paragraph': int(m.group(2)) if m.group(2) else None,
                'reference_text': m.group(0),
                'type': 'korean',
            }
            xrefs.append(xref)

        # English cross-references
        for m in XREF_EN_RE.finditer(text):
            xref = {
                'source_index': para['index'],
                'target_section': m.group(1),
                'reference_text': m.group(0),
                'type': 'english',
            }
            xrefs.append(xref)

    return xrefs


def build_numbering_sequences(paragraphs: list[dict]) -> list[dict]:
    """Extract numbering sequences for validation."""
    sequences = []
    current_seq = None

    for para in paragraphs:
        # Korean article numbering
        m = KR_ARTICLE_RE.match(para['text'])
        if m:
            num = int(m.group(1))
            if current_seq and current_seq['type'] == 'article':
                current_seq['numbers'].append(num)
                current_seq['end_index'] = para['index']
            else:
                if current_seq:
                    sequences.append(current_seq)
                current_seq = {
                    'type': 'article',
                    'numbers': [num],
                    'start_index': para['index'],
                    'end_index': para['index'],
                }
        elif para['numbering'] and not para['heading_level']:
            num_level = para['numbering']['level']
            num_id = para['numbering']['numId']
            if current_seq and current_seq.get('numId') == num_id:
                current_seq['count'] += 1
                current_seq['end_index'] = para['index']
            else:
                if current_seq:
                    sequences.append(current_seq)
                current_seq = {
                    'type': 'list',
                    'numId': num_id,
                    'level': num_level,
                    'count': 1,
                    'start_index': para['index'],
                    'end_index': para['index'],
                }

    if current_seq:
        sequences.append(current_seq)

    return sequences


def parse_docx(docx_path: str, output_dir: str) -> dict:
    """Main parsing function."""
    result = {
        'source_file': os.path.abspath(docx_path),
        'success': False,
        'error': None,
    }

    if not os.path.exists(docx_path):
        result['error'] = f"File not found: {docx_path}"
        return result

    paragraphs = extract_paragraphs(docx_path)
    if paragraphs is None:
        result['error'] = "Failed to extract paragraphs from DOCX"
        return result

    sections = build_sections(paragraphs)
    cross_references = extract_cross_references(paragraphs)
    numbering_sequences = build_numbering_sequences(paragraphs)

    # Build full text
    full_text = '\n'.join(p['text'] for p in paragraphs if p['text'])

    # Assemble output
    structure = {
        'source_file': os.path.abspath(docx_path),
        'paragraph_count': len(paragraphs),
        'section_count': len(sections),
        'cross_reference_count': len(cross_references),
        'paragraphs': paragraphs,
        'sections': sections,
        'cross_references': cross_references,
        'numbering_sequences': numbering_sequences,
        'full_text': full_text,
    }

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'parsed-structure.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(structure, f, indent=2, ensure_ascii=False)

    result['success'] = True
    result['output_path'] = output_path
    result['paragraph_count'] = len(paragraphs)
    result['section_count'] = len(sections)
    result['cross_reference_count'] = len(cross_references)
    return result


def main():
    if len(sys.argv) < 3:
        print(json.dumps({'error': 'Usage: parse-docx-structure.py <docx_path> <output_dir>'}))
        sys.exit(1)

    docx_path = sys.argv[1]
    output_dir = sys.argv[2]
    result = parse_docx(docx_path, output_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not result['success']:
        sys.exit(1)


if __name__ == '__main__':
    main()
