#!/usr/bin/env python3
"""
Extract defined terms from parsed document structure.

Detects definition patterns in Korean and English legal documents.
Usage: python3 extract-defined-terms.py <parsed_structure_json> <output_path>
"""

import sys
import os
import json
import re

# ── Korean Definition Patterns ──

# "이하 'X'라 한다", "이하 "X"이라 한다", "이하 "X"라 함"
KR_DEF_SINGLE_RE = re.compile(
    r'이하\s*[\'\"\'\"「]\s*([^\'\"\'\"」]{1,50})\s*[\'\"\'\"」]\s*(?:이?라\s*(?:한다|함|칭한다|약칭한다))'
)

# "X"(이하 "약칭")  or  X(이하 '약칭'이라 한다)
KR_DEF_PAREN_RE = re.compile(
    r'[(（]\s*이하\s*[\'\"\'\"「]\s*([^\'\"\'\"」]{1,50})\s*[\'\"\'\"」]\s*(?:이?라\s*(?:한다|함|칭한다))?[)）]'
)

# 「X」means / 「X」란 ... 을 말한다
KR_DEF_MEANS_RE = re.compile(
    r'[\"\'\"\'「]\s*([^\"\'\"\'」]{1,50})\s*[\"\'\"\'」]\s*(?:이?란?|은|는)\s+.{5,100}(?:을|를)\s*말한다'
)

# ── English Definition Patterns ──

# "Term" means / "Term" shall mean
EN_DEF_MEANS_RE = re.compile(
    r'[\""\u201c]\s*([^\""\u201d]{1,60})\s*[\""\u201d]\s*(?:shall\s+)?mean[s]?\b',
    re.IGNORECASE
)

# hereinafter referred to as "Term"
EN_DEF_HEREIN_RE = re.compile(
    r'hereinafter\s+(?:referred\s+to\s+as|called|the)\s+[\""\u201c]\s*([^\""\u201d]{1,60})\s*[\""\u201d]',
    re.IGNORECASE
)

# (the "Term") / ("Term")
EN_DEF_PAREN_RE = re.compile(
    r'[(]\s*(?:the\s+)?[\""\u201c]\s*([^\""\u201d]{1,60})\s*[\""\u201d]\s*[)]'
)

# "Term" has the meaning given in / as defined in
EN_DEF_GIVEN_RE = re.compile(
    r'[\""\u201c]\s*([^\""\u201d]{1,60})\s*[\""\u201d]\s*(?:has\s+the\s+meaning|as\s+defined)',
    re.IGNORECASE
)


def extract_definitions(paragraphs: list[dict]) -> list[dict]:
    """Extract defined term definitions from paragraphs."""
    definitions = []
    seen_terms = {}  # term_lower -> index in definitions

    patterns = [
        ('KR', KR_DEF_SINGLE_RE),
        ('KR', KR_DEF_PAREN_RE),
        ('KR', KR_DEF_MEANS_RE),
        ('EN', EN_DEF_MEANS_RE),
        ('EN', EN_DEF_HEREIN_RE),
        ('EN', EN_DEF_PAREN_RE),
        ('EN', EN_DEF_GIVEN_RE),
    ]

    for para in paragraphs:
        text = para.get('text', '')
        if not text:
            continue

        for lang, pattern in patterns:
            for m in pattern.finditer(text):
                term = m.group(1).strip()
                if not term or len(term) < 2:
                    continue

                term_lower = term.lower()
                if term_lower in seen_terms:
                    # Already found — skip duplicate definition
                    continue

                seen_terms[term_lower] = len(definitions)
                definitions.append({
                    'term': term,
                    'language': lang,
                    'definition_location': {
                        'paragraph_index': para['index'],
                        'context': text[:200],
                    },
                    'usage_locations': [],
                })

    return definitions


def find_usages(paragraphs: list[dict], definitions: list[dict]) -> list[dict]:
    """Find all usage locations for each defined term."""
    for defn in definitions:
        term = defn['term']
        def_para_idx = defn['definition_location']['paragraph_index']

        # Build regex for the term (case-insensitive for English, exact for Korean)
        if defn['language'] == 'EN':
            pattern = re.compile(re.escape(term), re.IGNORECASE)
        else:
            pattern = re.compile(re.escape(term))

        for para in paragraphs:
            text = para.get('text', '')
            if not text:
                continue
            para_idx = para['index']

            # Skip the definition paragraph itself
            if para_idx == def_para_idx:
                continue

            matches = list(pattern.finditer(text))
            if matches:
                defn['usage_locations'].append({
                    'paragraph_index': para_idx,
                    'count': len(matches),
                })

    return definitions


def main():
    if len(sys.argv) < 3:
        print(json.dumps({'error': 'Usage: extract-defined-terms.py <parsed_structure_json> <output_path>'}))
        sys.exit(1)

    parsed_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(parsed_path, 'r', encoding='utf-8') as f:
        parsed_structure = json.load(f)

    paragraphs = parsed_structure.get('paragraphs', [])
    definitions = extract_definitions(paragraphs)
    definitions = find_usages(paragraphs, definitions)

    # Identify potential issues
    unused_terms = [d['term'] for d in definitions if not d['usage_locations']]
    usage_count = sum(len(d['usage_locations']) for d in definitions)

    output = {
        'source_file': parsed_structure.get('source_file', ''),
        'total_defined_terms': len(definitions),
        'total_usages': usage_count,
        'unused_terms': unused_terms,
        'definitions': definitions,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    result = {
        'success': True,
        'output_path': output_path,
        'total_defined_terms': len(definitions),
        'unused_terms': unused_terms,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
