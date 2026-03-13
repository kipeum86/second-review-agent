#!/usr/bin/env python3
"""
Check defined-term usage consistency throughout a document.

Detects: variant spellings, synonyms, abbreviated forms, and terms used without definition.
Usage: python3 term-consistency-checker.py <defined_terms_json> <text_path> <output_path>
"""

import sys
import os
import json
import re


def check_consistency(definitions: list[dict], full_text: str) -> list[dict]:
    """Check term consistency and find potential issues."""
    findings = []
    lines = full_text.split('\n')

    for defn in definitions:
        term = defn['term']
        usages = defn.get('usage_locations', [])

        # 1. Check for unused defined terms
        if not usages:
            findings.append({
                'type': 'unused_term',
                'term': term,
                'severity': 'Minor',
                'description': f'정의된 용어 "{term}"이(가) 문서 내에서 사용되지 않음',
                'recommendation': '정의가 불필요하면 삭제하거나, 해당 용어를 적절히 사용할 것',
                'location': defn.get('definition_location', {}),
            })

    # 2. Check for variant forms of defined terms
    for defn in definitions:
        term = defn['term']
        if len(term) < 3:
            continue

        # Generate potential variants
        variants = _generate_variants(term, defn.get('language', 'KR'))
        for variant in variants:
            if variant == term:
                continue
            # Search for variant in text
            pattern = re.compile(re.escape(variant), re.IGNORECASE if defn.get('language') == 'EN' else 0)
            for line_num, line in enumerate(lines):
                for m in pattern.finditer(line):
                    # Check it's not part of the definition itself
                    if line_num == defn.get('definition_location', {}).get('paragraph_index', -1):
                        continue
                    findings.append({
                        'type': 'variant_usage',
                        'term': term,
                        'variant': variant,
                        'severity': 'Minor',
                        'description': f'정의된 용어 "{term}"의 변형 "{variant}"이(가) 사용됨',
                        'recommendation': f'일관성을 위해 정의된 형태 "{term}"으로 통일할 것',
                        'location': {
                            'line': line_num + 1,
                            'text_excerpt': line[max(0, m.start()-20):m.end()+20].strip(),
                        },
                    })

    # 3. Detect potential undefined terms (quoted terms that look like they should be defined)
    undefined_pattern = re.compile(r'[\""\u201c]\s*([^\""\u201d]{2,30})\s*[\""\u201d]')
    defined_terms_lower = {d['term'].lower() for d in definitions}

    potential_undefined = set()
    for line_num, line in enumerate(lines):
        for m in undefined_pattern.finditer(line):
            candidate = m.group(1).strip()
            if candidate.lower() not in defined_terms_lower and candidate not in potential_undefined:
                # Check if it appears multiple times (suggesting it should be defined)
                count = full_text.lower().count(candidate.lower())
                if count >= 3:
                    potential_undefined.add(candidate)
                    findings.append({
                        'type': 'potential_undefined',
                        'term': candidate,
                        'severity': 'Suggestion',
                        'description': f'인용부호로 표시된 "{candidate}"이(가) {count}회 사용되었으나 정의되지 않음',
                        'recommendation': '반복 사용되는 용어라면 정의 조항에 추가하는 것을 검토',
                        'location': {
                            'line': line_num + 1,
                            'usage_count': count,
                        },
                    })

    return findings


def _generate_variants(term: str, language: str) -> list[str]:
    """Generate potential variant forms of a defined term."""
    variants = set()

    if language == 'KR' or not term.isascii():
        # Korean variants: with/without spaces, with/without quotes
        variants.add(term.replace(' ', ''))
        variants.add(term.replace('  ', ' '))
        # Common abbreviation patterns
        if len(term) > 4:
            # Take first chars of each word-like segment
            parts = re.split(r'[\s·]', term)
            if len(parts) >= 2:
                abbrev = ''.join(p[0] for p in parts if p)
                if len(abbrev) >= 2:
                    variants.add(abbrev)
    else:
        # English variants
        variants.add(term.lower())
        variants.add(term.upper())
        # Plural/singular
        if term.endswith('s'):
            variants.add(term[:-1])
        else:
            variants.add(term + 's')
        # With/without "the"
        if term.lower().startswith('the '):
            variants.add(term[4:])
        else:
            variants.add('the ' + term)

    return list(variants)


def main():
    if len(sys.argv) < 4:
        print(json.dumps({'error': 'Usage: term-consistency-checker.py <defined_terms_json> <text_path> <output_path>'}))
        sys.exit(1)

    terms_path = sys.argv[1]
    text_path = sys.argv[2]
    output_path = sys.argv[3]

    with open(terms_path, 'r', encoding='utf-8') as f:
        terms_data = json.load(f)
    definitions = terms_data.get('definitions', [])

    # Read text
    if text_path.endswith('.json'):
        with open(text_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            full_text = data.get('full_text', '')
    else:
        with open(text_path, 'r', encoding='utf-8') as f:
            full_text = f.read()

    findings = check_consistency(definitions, full_text)

    by_type = {}
    for f_item in findings:
        t = f_item['type']
        by_type[t] = by_type.get(t, 0) + 1

    output = {
        'total_defined_terms': len(definitions),
        'total_findings': len(findings),
        'by_type': by_type,
        'findings': findings,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    result = {
        'success': True,
        'output_path': output_path,
        'total_findings': len(findings),
        'by_type': by_type,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
