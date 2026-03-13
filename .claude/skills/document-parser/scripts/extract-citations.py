#!/usr/bin/env python3
"""
Extract legal citations from parsed document structure.

Supports Korean, US, and EU citation formats.
Usage: python3 extract-citations.py <parsed_structure_json> <output_path>
"""

import sys
import os
import json
import re

# ── Korean Citation Patterns ──

# 법률 제NNNNN호 (Korean statutes by law number)
KR_STATUTE_NUM_RE = re.compile(
    r'(?:법률|시행령|시행규칙|대통령령)\s*제\s*(\d+)\s*호'
)

# Named statutes: 「법률명」
KR_STATUTE_NAME_RE = re.compile(
    r'「([^」]{2,50})」'
)

# Article/paragraph/item references: 제N조, 제N조제N항, 제N조제N항제N호
KR_ARTICLE_REF_RE = re.compile(
    r'제\s*(\d+)\s*조(?:\s*의\s*(\d+))?'
    r'(?:\s*제\s*(\d+)\s*항)?'
    r'(?:\s*제\s*(\d+)\s*호)?'
    r'(?:\s*제\s*(\d+)\s*목)?'
)

# Korean case numbers: 대법원 2020다12345, 서울고등법원 2021나67890
KR_CASE_RE = re.compile(
    r'(?:대법원|고등법원|지방법원|서울고등법원|서울중앙지방법원|'
    r'부산고등법원|대구고등법원|광주고등법원|대전고등법원|'
    r'서울행정법원|헌법재판소|특허법원)'
    r'\s*(\d{4})\s*[.\s]*\s*(\d{1,2})\s*[.\s]*\s*(\d{1,2})\s*[.\s]*'
    r'(?:선고\s*)?(\d{2,4})\s*([가-힣]{1,3})\s*(\d+)\s*(?:판결|결정|전원합의체)?'
)

# Simplified Korean case pattern: NNNN다NNNNN
KR_CASE_SIMPLE_RE = re.compile(
    r'(\d{2,4})\s*([다나마바가라카타파하두누구무부주후루추투푸]{1,2})\s*(\d{2,6})'
)

# ── US Citation Patterns ──

# US Code: 42 U.S.C. § 1983, 15 USC § 78j(b)
US_CODE_RE = re.compile(
    r'(\d{1,2})\s*(?:U\.?S\.?C\.?|United States Code)\s*§?\s*(\d+[a-z]?(?:\([a-z0-9]+\))*)',
    re.IGNORECASE
)

# Code of Federal Regulations: 17 C.F.R. § 240.10b-5
US_CFR_RE = re.compile(
    r'(\d{1,2})\s*(?:C\.?F\.?R\.?|Code of Federal Regulations)\s*§?\s*([\d.]+[a-z]?(?:-\d+)?)',
    re.IGNORECASE
)

# US case reporters: 410 U.S. 113, 550 F.3d 450
US_CASE_RE = re.compile(
    r'(\d{1,3})\s*(U\.S\.|S\.Ct\.|L\.Ed\.|F\.(?:2d|3d|4th)|F\.Supp\.(?:2d|3d)?)\s*(\d+)'
)

# ── EU Citation Patterns ──

# EU Regulations/Directives: Regulation (EU) 2016/679, Directive 2006/123/EC
EU_REG_RE = re.compile(
    r'(?:Regulation|Directive|Decision)\s*\(?(?:EU|EC|EEC)\)?\s*(?:No\.?\s*)?(\d{4}/\d+(?:/[A-Z]{2,3})?|\d+/\d{4})',
    re.IGNORECASE
)

# EU Treaty articles: Article 101 TFEU
EU_TREATY_RE = re.compile(
    r'Article\s+(\d+)\s*(?:of\s+the\s+)?(?:TFEU|TEU|ECHR)',
    re.IGNORECASE
)


def get_context(paragraphs: list[dict], para_idx: int, match_start: int, match_end: int) -> str:
    """Get surrounding sentence context for a citation."""
    text = paragraphs[para_idx]['text'] if para_idx < len(paragraphs) else ''
    # Find sentence boundaries
    sent_start = max(0, text.rfind('.', 0, match_start) + 1)
    sent_end = text.find('.', match_end)
    if sent_end == -1:
        sent_end = len(text)
    else:
        sent_end += 1
    return text[sent_start:sent_end].strip()


def extract_citations(parsed_structure: dict) -> list[dict]:
    """Extract all citations from parsed paragraphs."""
    paragraphs = parsed_structure.get('paragraphs', [])
    citations = []
    seen = set()  # Deduplicate identical citations

    for para in paragraphs:
        text = para.get('text', '')
        if not text:
            continue
        para_idx = para['index']

        # Korean statutes by number
        for m in KR_STATUTE_NUM_RE.finditer(text):
            key = ('kr_statute_num', m.group(0))
            if key not in seen:
                seen.add(key)
                citations.append({
                    'citation_text': m.group(0),
                    'citation_type': 'statute',
                    'jurisdiction': 'KR',
                    'location': {'paragraph_index': para_idx},
                    'claimed_content': get_context(paragraphs, para_idx, m.start(), m.end()),
                })

        # Korean named statutes
        for m in KR_STATUTE_NAME_RE.finditer(text):
            name = m.group(1)
            # Filter out non-statute bracket usage (too short or common phrases)
            if len(name) < 3:
                continue
            # Check if it looks like a law name (ends with 법, 령, 규칙, etc.)
            if re.search(r'(?:법|령|규칙|조약|협약|협정|규정|지침|고시|훈령)$', name):
                key = ('kr_statute_name', name)
                if key not in seen:
                    seen.add(key)
                    # Also look for article references near this statute name
                    article_match = KR_ARTICLE_REF_RE.search(text[m.end():m.end()+50])
                    article_ref = article_match.group(0) if article_match else None
                    citations.append({
                        'citation_text': m.group(0) + (f' {article_ref}' if article_ref else ''),
                        'citation_type': 'statute',
                        'jurisdiction': 'KR',
                        'statute_name': name,
                        'article_ref': article_ref,
                        'location': {'paragraph_index': para_idx},
                        'claimed_content': get_context(paragraphs, para_idx, m.start(), m.end()),
                    })

        # Korean case numbers
        for m in KR_CASE_RE.finditer(text):
            key = ('kr_case', m.group(0))
            if key not in seen:
                seen.add(key)
                citations.append({
                    'citation_text': m.group(0).strip(),
                    'citation_type': 'case',
                    'jurisdiction': 'KR',
                    'location': {'paragraph_index': para_idx},
                    'claimed_content': get_context(paragraphs, para_idx, m.start(), m.end()),
                })

        # Simplified Korean case pattern (fallback)
        for m in KR_CASE_SIMPLE_RE.finditer(text):
            # Only if preceded by court name context
            prefix = text[max(0, m.start()-20):m.start()]
            if re.search(r'(?:대법원|법원|판결|선고)', prefix):
                key = ('kr_case_simple', m.group(0))
                if key not in seen:
                    seen.add(key)
                    citations.append({
                        'citation_text': m.group(0).strip(),
                        'citation_type': 'case',
                        'jurisdiction': 'KR',
                        'location': {'paragraph_index': para_idx},
                        'claimed_content': get_context(paragraphs, para_idx, m.start(), m.end()),
                    })

        # US Code
        for m in US_CODE_RE.finditer(text):
            key = ('us_code', m.group(0))
            if key not in seen:
                seen.add(key)
                citations.append({
                    'citation_text': m.group(0).strip(),
                    'citation_type': 'statute',
                    'jurisdiction': 'US',
                    'title': m.group(1),
                    'section': m.group(2),
                    'location': {'paragraph_index': para_idx},
                    'claimed_content': get_context(paragraphs, para_idx, m.start(), m.end()),
                })

        # US CFR
        for m in US_CFR_RE.finditer(text):
            key = ('us_cfr', m.group(0))
            if key not in seen:
                seen.add(key)
                citations.append({
                    'citation_text': m.group(0).strip(),
                    'citation_type': 'regulation',
                    'jurisdiction': 'US',
                    'location': {'paragraph_index': para_idx},
                    'claimed_content': get_context(paragraphs, para_idx, m.start(), m.end()),
                })

        # US cases
        for m in US_CASE_RE.finditer(text):
            key = ('us_case', m.group(0))
            if key not in seen:
                seen.add(key)
                citations.append({
                    'citation_text': m.group(0).strip(),
                    'citation_type': 'case',
                    'jurisdiction': 'US',
                    'location': {'paragraph_index': para_idx},
                    'claimed_content': get_context(paragraphs, para_idx, m.start(), m.end()),
                })

        # EU regulations/directives
        for m in EU_REG_RE.finditer(text):
            key = ('eu_reg', m.group(0))
            if key not in seen:
                seen.add(key)
                citations.append({
                    'citation_text': m.group(0).strip(),
                    'citation_type': 'regulation',
                    'jurisdiction': 'EU',
                    'location': {'paragraph_index': para_idx},
                    'claimed_content': get_context(paragraphs, para_idx, m.start(), m.end()),
                })

        # EU treaty articles
        for m in EU_TREATY_RE.finditer(text):
            key = ('eu_treaty', m.group(0))
            if key not in seen:
                seen.add(key)
                citations.append({
                    'citation_text': m.group(0).strip(),
                    'citation_type': 'treaty',
                    'jurisdiction': 'EU',
                    'location': {'paragraph_index': para_idx},
                    'claimed_content': get_context(paragraphs, para_idx, m.start(), m.end()),
                })

    # Sort by priority: statutes & cases first, then regulations, then others
    type_priority = {'statute': 0, 'case': 1, 'regulation': 2, 'treaty': 3}
    citations.sort(key=lambda c: (type_priority.get(c['citation_type'], 9), c['location']['paragraph_index']))

    return citations


def main():
    if len(sys.argv) < 3:
        print(json.dumps({'error': 'Usage: extract-citations.py <parsed_structure_json> <output_path>'}))
        sys.exit(1)

    parsed_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(parsed_path, 'r', encoding='utf-8') as f:
        parsed_structure = json.load(f)

    citations = extract_citations(parsed_structure)

    output = {
        'source_file': parsed_structure.get('source_file', ''),
        'total_citations': len(citations),
        'by_type': {},
        'by_jurisdiction': {},
        'citations': citations,
    }

    # Summary counts
    for c in citations:
        ctype = c['citation_type']
        jur = c['jurisdiction']
        output['by_type'][ctype] = output['by_type'].get(ctype, 0) + 1
        output['by_jurisdiction'][jur] = output['by_jurisdiction'].get(jur, 0) + 1

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Print summary to stdout
    result = {
        'success': True,
        'output_path': output_path,
        'total_citations': len(citations),
        'by_type': output['by_type'],
        'by_jurisdiction': output['by_jurisdiction'],
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
