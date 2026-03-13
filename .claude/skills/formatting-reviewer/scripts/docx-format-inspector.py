#!/usr/bin/env python3
"""
Inspect DOCX formatting via XML analysis.

Checks font consistency, heading styles, table formatting, margins, and page breaks.
Usage: python3 docx-format-inspector.py <docx_path> <output_path>
"""

import sys
import os
import json
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter

NSMAP = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}


def inspect_docx(docx_path: str) -> dict:
    """Inspect DOCX formatting and return findings."""
    findings = []

    try:
        with zipfile.ZipFile(docx_path, 'r') as z:
            doc_xml = z.read('word/document.xml')
            styles_xml = z.read('word/styles.xml') if 'word/styles.xml' in z.namelist() else None
    except (zipfile.BadZipFile, KeyError) as e:
        return {'error': f'Failed to open DOCX: {e}', 'findings': []}

    root = ET.fromstring(doc_xml)
    body = root.find(f'{{{NSMAP["w"]}}}body')
    if body is None:
        return {'error': 'No body element found in document.xml', 'findings': []}

    # 1. Font consistency check
    font_findings = _check_font_consistency(body)
    findings.extend(font_findings)

    # 2. Font size consistency check
    size_findings = _check_size_consistency(body)
    findings.extend(size_findings)

    # 3. Heading style check
    if styles_xml:
        heading_findings = _check_heading_styles(ET.fromstring(styles_xml))
        findings.extend(heading_findings)

    # 4. Table formatting check
    table_findings = _check_tables(body)
    findings.extend(table_findings)

    # 5. Margin check
    margin_findings = _check_margins(body)
    findings.extend(margin_findings)

    # 6. Page break check
    break_findings = _check_page_breaks(body)
    findings.extend(break_findings)

    return {
        'source_file': os.path.abspath(docx_path),
        'total_findings': len(findings),
        'findings': findings,
    }


def _check_font_consistency(body) -> list[dict]:
    """Check for mixed fonts in body text."""
    findings = []
    font_counter = Counter()
    para_idx = 0

    for p in body.iter(f'{{{NSMAP["w"]}}}p'):
        for r in p.iter(f'{{{NSMAP["w"]}}}r'):
            rPr = r.find(f'{{{NSMAP["w"]}}}rPr')
            if rPr is not None:
                rFonts = rPr.find(f'{{{NSMAP["w"]}}}rFonts')
                if rFonts is not None:
                    for attr in ['ascii', 'eastAsia', 'hAnsi']:
                        val = rFonts.get(f'{{{NSMAP["w"]}}}{attr}')
                        if val:
                            font_counter[val] += 1
        para_idx += 1

    if len(font_counter) > 3:
        top_fonts = font_counter.most_common(5)
        findings.append({
            'check_type': 'font_consistency',
            'severity': 'Minor',
            'description': f'글꼴 불일치: {len(font_counter)}종의 글꼴 사용 (주요: {", ".join(f[0] for f in top_fonts[:3])})',
            'recommendation': '본문 텍스트의 글꼴을 통일할 것',
            'detail': {k: v for k, v in top_fonts},
        })

    return findings


def _check_size_consistency(body) -> list[dict]:
    """Check for mixed font sizes in body text (excluding headings)."""
    findings = []
    size_counter = Counter()

    for p in body.iter(f'{{{NSMAP["w"]}}}p'):
        # Skip headings
        pPr = p.find(f'{{{NSMAP["w"]}}}pPr')
        if pPr is not None:
            pStyle = pPr.find(f'{{{NSMAP["w"]}}}pStyle')
            if pStyle is not None:
                style = pStyle.get(f'{{{NSMAP["w"]}}}val', '')
                if 'heading' in style.lower() or 'title' in style.lower():
                    continue

        for r in p.iter(f'{{{NSMAP["w"]}}}r'):
            rPr = r.find(f'{{{NSMAP["w"]}}}rPr')
            if rPr is not None:
                sz = rPr.find(f'{{{NSMAP["w"]}}}sz')
                if sz is not None:
                    size_val = sz.get(f'{{{NSMAP["w"]}}}val', '')
                    if size_val:
                        size_counter[size_val] += 1

    if len(size_counter) > 3:
        top_sizes = size_counter.most_common(5)
        # Convert half-points to points
        size_desc = [(f'{int(s[0])//2}pt', s[1]) for s in top_sizes if s[0].isdigit()]
        findings.append({
            'check_type': 'size_consistency',
            'severity': 'Minor',
            'description': f'글꼴 크기 불일치: 본문 내 {len(size_counter)}종의 크기 사용',
            'recommendation': '본문 텍스트의 글꼴 크기를 통일할 것',
            'detail': {s[0]: s[1] for s in size_desc},
        })

    return findings


def _check_heading_styles(styles_root) -> list[dict]:
    """Check heading style definitions for consistency."""
    findings = []
    heading_fonts = {}
    heading_sizes = {}

    for style in styles_root.iter(f'{{{NSMAP["w"]}}}style'):
        style_id = style.get(f'{{{NSMAP["w"]}}}styleId', '')
        if 'heading' not in style_id.lower() and 'Heading' not in style_id:
            continue

        rPr = style.find(f'{{{NSMAP["w"]}}}rPr')
        if rPr is not None:
            rFonts = rPr.find(f'{{{NSMAP["w"]}}}rFonts')
            if rFonts is not None:
                font = rFonts.get(f'{{{NSMAP["w"]}}}ascii', '')
                if font:
                    heading_fonts[style_id] = font

            sz = rPr.find(f'{{{NSMAP["w"]}}}sz')
            if sz is not None:
                heading_sizes[style_id] = sz.get(f'{{{NSMAP["w"]}}}val', '')

    # Check heading font consistency
    if len(set(heading_fonts.values())) > 1:
        findings.append({
            'check_type': 'heading_font_consistency',
            'severity': 'Suggestion',
            'description': f'제목 스타일 글꼴 불일치: {heading_fonts}',
            'recommendation': '모든 제목 스타일이 동일한 글꼴 사용하도록 통일',
        })

    return findings


def _check_tables(body) -> list[dict]:
    """Check table formatting consistency."""
    findings = []
    tables = list(body.iter(f'{{{NSMAP["w"]}}}tbl'))

    for tbl_idx, tbl in enumerate(tables):
        rows = list(tbl.iter(f'{{{NSMAP["w"]}}}tr'))
        if not rows:
            continue

        # Check column count consistency
        col_counts = []
        for tr in rows:
            cells = list(tr.iter(f'{{{NSMAP["w"]}}}tc'))
            col_counts.append(len(cells))

        if len(set(col_counts)) > 1:
            findings.append({
                'check_type': 'table_column_consistency',
                'severity': 'Minor',
                'description': f'표 {tbl_idx+1}: 행별 열 수 불일치 ({set(col_counts)})',
                'recommendation': '표 구조를 확인하고 셀 병합이 의도적인지 검토',
            })

    return findings


def _check_margins(body) -> list[dict]:
    """Check page margin consistency across sections."""
    findings = []
    margins = []

    for sectPr in body.iter(f'{{{NSMAP["w"]}}}sectPr'):
        pgMar = sectPr.find(f'{{{NSMAP["w"]}}}pgMar')
        if pgMar is not None:
            margin = {
                'top': pgMar.get(f'{{{NSMAP["w"]}}}top', ''),
                'bottom': pgMar.get(f'{{{NSMAP["w"]}}}bottom', ''),
                'left': pgMar.get(f'{{{NSMAP["w"]}}}left', ''),
                'right': pgMar.get(f'{{{NSMAP["w"]}}}right', ''),
            }
            margins.append(margin)

    if len(margins) > 1:
        # Check if margins are consistent across sections
        if len(set(json.dumps(m, sort_keys=True) for m in margins)) > 1:
            findings.append({
                'check_type': 'margin_consistency',
                'severity': 'Minor',
                'description': '섹션 간 여백 불일치',
                'recommendation': '의도적인 변경이 아니라면 전체 문서의 여백을 통일할 것',
            })

    return findings


def _check_page_breaks(body) -> list[dict]:
    """Check for problematic page break placement."""
    findings = []
    para_idx = 0

    for p in body.iter(f'{{{NSMAP["w"]}}}p'):
        # Check for page break before heading
        pPr = p.find(f'{{{NSMAP["w"]}}}pPr')
        if pPr is not None:
            # Check for explicit page break
            for r in p.iter(f'{{{NSMAP["w"]}}}r'):
                br = r.find(f'{{{NSMAP["w"]}}}br')
                if br is not None and br.get(f'{{{NSMAP["w"]}}}type') == 'page':
                    # Check if next paragraph is empty (orphan break)
                    texts = []
                    for t in p.iter(f'{{{NSMAP["w"]}}}t'):
                        if t.text:
                            texts.append(t.text)
                    if not ''.join(texts).strip():
                        findings.append({
                            'check_type': 'orphan_page_break',
                            'severity': 'Suggestion',
                            'location': {'paragraph_index': para_idx},
                            'description': '빈 단락에 페이지 나누기가 포함됨',
                            'recommendation': '페이지 나누기를 다음 섹션 시작 부분으로 이동하는 것을 검토',
                        })
        para_idx += 1

    return findings


def main():
    if len(sys.argv) < 3:
        print(json.dumps({'error': 'Usage: docx-format-inspector.py <docx_path> <output_path>'}))
        sys.exit(1)

    docx_path = sys.argv[1]
    output_path = sys.argv[2]

    result = inspect_docx(docx_path)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    summary = {
        'success': 'error' not in result,
        'output_path': output_path,
        'total_findings': result.get('total_findings', 0),
    }
    if 'error' in result:
        summary['error'] = result['error']
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if 'error' in result:
        sys.exit(1)


if __name__ == '__main__':
    main()
