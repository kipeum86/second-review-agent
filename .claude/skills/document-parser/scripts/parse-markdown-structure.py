#!/usr/bin/env python3
"""
Parse Markdown text (from MarkItDown conversion) into the same parsed-structure.json
format used by the DOCX parser.

This script is the non-DOCX entry point: PDF, PPTX, XLSX, HTML, etc. are first
converted to Markdown via the MarkItDown MCP tool, then this script extracts
structure, headings, sections, cross-references, and numbering sequences.

Usage: python3 parse-markdown-structure.py <markdown_path> <output_dir> [--source <original_file>]
Outputs: parsed-structure.json in output_dir
"""

import sys
import os
import json
import re

# ── Heading detection ──────────────────────────────────────────────────────────

ATX_HEADING_RE = re.compile(r'^(#{1,6})\s+(.+?)(?:\s+#+)?\s*$')

# Korean legal structure patterns (same as DOCX parser)
KR_ARTICLE_RE = re.compile(r'^제\s*(\d+)\s*조[\s(]')
KR_PARAGRAPH_RE = re.compile(r'^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]')
KR_SUBPARA_RE = re.compile(r'^\d+\.')
KR_ITEM_RE = re.compile(r'^[가나다라마바사아자차카타파하]\.')

# Cross-reference patterns (same as DOCX parser)
XREF_KR_RE = re.compile(r'(?:위|본|이|동|상기)\s*제\s*(\d+)\s*조(?:\s*제\s*(\d+)\s*항)?')
XREF_EN_RE = re.compile(r'(?:Section|Article|Clause)\s+(\d+(?:\.\d+)*)', re.IGNORECASE)

# Table row detection
TABLE_ROW_RE = re.compile(r'^\|(.+)\|$')
TABLE_SEP_RE = re.compile(r'^\|[\s:]*-+[\s:]*')


def parse_markdown_lines(lines: list[str]) -> list[dict]:
    """Parse Markdown lines into paragraph dicts matching DOCX parser output format."""
    paragraphs = []
    para_idx = 0
    in_table = False
    table_row_counter = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip('\n').rstrip('\r')

        # Skip blank lines
        if not stripped.strip():
            in_table = False
            i += 1
            continue

        # Table separator row (---|---) — skip
        if TABLE_SEP_RE.match(stripped.strip()):
            i += 1
            continue

        # Table row
        if TABLE_ROW_RE.match(stripped.strip()):
            cells = [c.strip() for c in stripped.strip().strip('|').split('|')]
            row_text = ' | '.join(cells)
            if not in_table:
                in_table = True
                table_row_counter = 0
            paragraphs.append({
                'index': para_idx,
                'text': row_text,
                'style': None,
                'heading_level': 0,
                'numbering': None,
                'is_table': True,
                'table_row': table_row_counter,
            })
            table_row_counter += 1
            para_idx += 1
            i += 1
            continue

        in_table = False

        # ATX heading (# Heading)
        m = ATX_HEADING_RE.match(stripped)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            paragraphs.append({
                'index': para_idx,
                'text': text,
                'style': f'Heading{level}',
                'heading_level': level,
                'numbering': None,
                'is_table': False,
            })
            para_idx += 1
            i += 1
            continue

        # Setext heading (underline with === or ---)
        if i + 1 < len(lines):
            next_line = lines[i + 1].rstrip('\n').rstrip('\r').strip()
            if next_line and re.match(r'^=+$', next_line):
                paragraphs.append({
                    'index': para_idx,
                    'text': stripped.strip(),
                    'style': 'Heading1',
                    'heading_level': 1,
                    'numbering': None,
                    'is_table': False,
                })
                para_idx += 1
                i += 2
                continue
            if next_line and re.match(r'^-+$', next_line) and len(next_line) >= 3:
                paragraphs.append({
                    'index': para_idx,
                    'text': stripped.strip(),
                    'style': 'Heading2',
                    'heading_level': 2,
                    'numbering': None,
                    'is_table': False,
                })
                para_idx += 1
                i += 2
                continue

        # Regular paragraph
        text = stripped.strip()
        heading_level = 0

        # Detect Korean legal headings
        if KR_ARTICLE_RE.match(text):
            heading_level = 2
        elif KR_PARAGRAPH_RE.match(text):
            heading_level = 3

        paragraphs.append({
            'index': para_idx,
            'text': text,
            'style': None,
            'heading_level': heading_level,
            'numbering': None,
            'is_table': False,
        })
        para_idx += 1
        i += 1

    return paragraphs


def build_sections(paragraphs: list[dict]) -> list[dict]:
    """Build section hierarchy from paragraphs (same logic as DOCX parser)."""
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
    """Extract internal cross-references (same logic as DOCX parser)."""
    xrefs = []

    for para in paragraphs:
        text = para['text']
        if not text:
            continue

        for m in XREF_KR_RE.finditer(text):
            xrefs.append({
                'source_index': para['index'],
                'target_article': int(m.group(1)),
                'target_paragraph': int(m.group(2)) if m.group(2) else None,
                'reference_text': m.group(0),
                'type': 'korean',
            })

        for m in XREF_EN_RE.finditer(text):
            xrefs.append({
                'source_index': para['index'],
                'target_section': m.group(1),
                'reference_text': m.group(0),
                'type': 'english',
            })

    return xrefs


def build_numbering_sequences(paragraphs: list[dict]) -> list[dict]:
    """Extract numbering sequences (same logic as DOCX parser)."""
    sequences = []
    current_seq = None

    for para in paragraphs:
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


def parse_markdown(md_path: str, output_dir: str, source_file: str | None = None) -> dict:
    """Main parsing function."""
    result = {
        'source_file': os.path.abspath(source_file or md_path),
        'converted_from': os.path.abspath(md_path),
        'conversion_method': 'markitdown',
        'success': False,
        'error': None,
    }

    if not os.path.exists(md_path):
        result['error'] = f"File not found: {md_path}"
        return result

    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    paragraphs = parse_markdown_lines(lines)
    sections = build_sections(paragraphs)
    cross_references = extract_cross_references(paragraphs)
    numbering_sequences = build_numbering_sequences(paragraphs)

    full_text = '\n'.join(p['text'] for p in paragraphs if p['text'])

    structure = {
        'source_file': os.path.abspath(source_file or md_path),
        'converted_from': os.path.abspath(md_path),
        'conversion_method': 'markitdown',
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
        print(json.dumps({
            'error': 'Usage: parse-markdown-structure.py <markdown_path> <output_dir> [--source <original_file>]'
        }))
        sys.exit(1)

    md_path = sys.argv[1]
    output_dir = sys.argv[2]

    source_file = None
    if '--source' in sys.argv:
        idx = sys.argv.index('--source')
        if idx + 1 < len(sys.argv):
            source_file = sys.argv[idx + 1]

    result = parse_markdown(md_path, output_dir, source_file)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not result['success']:
        sys.exit(1)


if __name__ == '__main__':
    main()
