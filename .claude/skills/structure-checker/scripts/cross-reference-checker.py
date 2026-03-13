#!/usr/bin/env python3
"""
Validate internal cross-references in parsed document structure.

Checks that all cross-references point to existing sections/articles.
Usage: python3 cross-reference-checker.py <parsed_structure_json> <output_path>
"""

import sys
import os
import json
import re


def check_cross_references(parsed: dict) -> list[dict]:
    """Check all cross-references resolve to existing targets."""
    findings = []
    cross_refs = parsed.get('cross_references', [])
    sections = parsed.get('sections', [])

    # Build set of existing article numbers (Korean)
    article_re = re.compile(r'제\s*(\d+)\s*조')
    existing_articles = set()
    for sec in sections:
        m = article_re.match(sec['title'])
        if m:
            existing_articles.add(int(m.group(1)))

    # Build set of existing section numbers (English)
    section_re = re.compile(r'(?:Section|Article|Clause)\s+(\d+(?:\.\d+)*)', re.IGNORECASE)
    existing_sections = set()
    for sec in sections:
        m = section_re.match(sec['title'])
        if m:
            existing_sections.add(m.group(1))

    # Check each cross-reference
    for xref in cross_refs:
        if xref['type'] == 'korean':
            target_article = xref.get('target_article')
            if target_article and target_article not in existing_articles:
                findings.append({
                    'check_type': 'orphaned_reference',
                    'severity': 'Major',
                    'location': {'paragraph_index': xref['source_index']},
                    'description': f'교차참조 오류: "{xref["reference_text"]}" — 제{target_article}조가 문서에 존재하지 않음',
                    'recommendation': f'제{target_article}조 참조가 올바른지 확인하고 수정할 것',
                    'reference_text': xref['reference_text'],
                    'target': f'제{target_article}조',
                })

        elif xref['type'] == 'english':
            target_section = xref.get('target_section')
            if target_section and target_section not in existing_sections:
                # Also check if base section exists (e.g., "3.1" when only "3" is a heading)
                base_section = target_section.split('.')[0]
                if base_section not in existing_sections:
                    findings.append({
                        'check_type': 'orphaned_reference',
                        'severity': 'Major',
                        'location': {'paragraph_index': xref['source_index']},
                        'description': f'Cross-reference error: "{xref["reference_text"]}" — Section {target_section} not found in document',
                        'recommendation': f'Verify Section {target_section} reference is correct',
                        'reference_text': xref['reference_text'],
                        'target': f'Section {target_section}',
                    })

    # Find unreferenced articles/sections (informational)
    referenced_articles = set()
    referenced_sections = set()
    for xref in cross_refs:
        if xref['type'] == 'korean' and xref.get('target_article'):
            referenced_articles.add(xref['target_article'])
        elif xref['type'] == 'english' and xref.get('target_section'):
            referenced_sections.add(xref['target_section'])

    unreferenced_articles = existing_articles - referenced_articles
    unreferenced_sections = existing_sections - referenced_sections

    # Only flag if there are many articles and some are never referenced
    if len(existing_articles) > 5 and unreferenced_articles:
        for art in sorted(unreferenced_articles):
            findings.append({
                'check_type': 'unreferenced_section',
                'severity': 'Suggestion',
                'location': {},
                'description': f'미참조 조항: 제{art}조는 문서 내 다른 곳에서 참조되지 않음',
                'recommendation': '참조가 필요한 조항인지 확인 (정보 제공 목적 — 수정 불필요할 수 있음)',
                'target': f'제{art}조',
            })

    return findings


def main():
    if len(sys.argv) < 3:
        print(json.dumps({'error': 'Usage: cross-reference-checker.py <parsed_structure_json> <output_path>'}))
        sys.exit(1)

    parsed_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(parsed_path, 'r', encoding='utf-8') as f:
        parsed = json.load(f)

    findings = check_cross_references(parsed)

    by_type = {}
    by_severity = {}
    for f_item in findings:
        t = f_item['check_type']
        s = f_item['severity']
        by_type[t] = by_type.get(t, 0) + 1
        by_severity[s] = by_severity.get(s, 0) + 1

    output = {
        'total_cross_references': len(parsed.get('cross_references', [])),
        'total_findings': len(findings),
        'by_check_type': by_type,
        'by_severity': by_severity,
        'findings': findings,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    result = {
        'success': True,
        'output_path': output_path,
        'total_findings': len(findings),
        'by_check_type': by_type,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
