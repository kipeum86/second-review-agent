#!/usr/bin/env python3
"""
Validate register and detect translation smells (번역투) in legal documents.

Usage: python3 register-validator.py <text_path> <language> <output_path>
  - text_path: path to plain text or full_text extracted from parsed-structure.json
  - language: 'ko' or 'en'
  - output_path: path to write findings JSON
"""

import sys
import os
import json
import re

# ── Korean Translation Smell Patterns (번역투) ──

KR_TRANSLATION_PATTERNS = [
    {
        'id': 'passive_by',
        'pattern': r'에\s*의해(?:\s*서)?',
        'description': '번역투: "~에 의해" 수동태 구문',
        'recommendation': '능동태로 재구성. 예: "A에 의해 B가 수행되었다" → "A가 B를 수행하였다"',
        'severity': 'Minor',
    },
    {
        'id': 'in_doing',
        'pattern': r'함에\s*있어서',
        'description': '번역투: "~함에 있어서" — 영어 "in doing" 직역',
        'recommendation': '"~할 때", "~하는 경우" 등으로 대체',
        'severity': 'Minor',
    },
    {
        'id': 'in_case_of',
        'pattern': r'의\s*경우에\s*있어서',
        'description': '번역투: "~의 경우에 있어서" — 불필요한 중복 표현',
        'recommendation': '"~인 경우" 또는 "~할 때"로 간결하게 대체',
        'severity': 'Minor',
    },
    {
        'id': 'passive_become',
        'pattern': r'(?:되어|되었|된)\s*(?:지다|진다|졌다)',
        'description': '번역투: 이중 수동태 ("~되어지다")',
        'recommendation': '단일 수동태 ("~되다") 또는 능동태로 수정',
        'severity': 'Minor',
    },
    {
        'id': 'regarding',
        'pattern': r'에\s*관하여(?:\s*는)?',
        'description': '번역투: "~에 관하여(는)" 과다 사용 가능',
        'recommendation': '문맥에 따라 "~에 대해", "~의" 등으로 대체 검토',
        'severity': 'Suggestion',
    },
    {
        'id': 'through',
        'pattern': r'을\s*통해(?:서)?',
        'description': '번역투: "~을 통해(서)" — "through" 직역 가능',
        'recommendation': '문맥에 따라 "~으로", "~에 의해" 등 자연스러운 표현 검토',
        'severity': 'Suggestion',
    },
    {
        'id': 'it_is',
        'pattern': r'것이\s*(?:필요하다|요구된다|예상된다|기대된다)',
        'description': '번역투: "~것이 [형용사]" — "it is [adj]" 직역',
        'recommendation': '주어를 명시하여 능동태로 재구성',
        'severity': 'Minor',
    },
    {
        'id': 'based_on',
        'pattern': r'에\s*기반하여|에\s*기초하여|을\s*기반으로',
        'description': '번역투: "~에 기반하여" — "based on" 직역',
        'recommendation': '"~에 따라", "~을 근거로" 등 자연스러운 표현 검토',
        'severity': 'Suggestion',
    },
    {
        'id': 'not_limited_to',
        'pattern': r'에?\s*한정되지\s*(?:않|아니)',
        'description': '번역투: "~에 한정되지 않는" — "not limited to" 직역',
        'recommendation': '"~을 포함하되 이에 한하지 아니한다" (법률 관용표현) 사용',
        'severity': 'Suggestion',
    },
    {
        'id': 'notwithstanding',
        'pattern': r'에도?\s*불구하고',
        'description': '번역투 가능: "~에도 불구하고" 과다 사용',
        'recommendation': '문맥에 따라 "~이지만", "~이나" 등 자연스러운 접속 표현 검토',
        'severity': 'Suggestion',
    },
]

# Korean colloquial intrusion patterns (구어체)
KR_COLLOQUIAL_PATTERNS = [
    {
        'id': 'informal_ending_yo',
        'pattern': r'(?:해요|하세요|되요|에요|거든요|잖아요|네요)\s*[.。]',
        'description': '구어체: 격식체 문서에 해요체 사용',
        'recommendation': '합니다체 또는 문어체(~한다, ~이다)로 수정',
        'severity': 'Major',
    },
    {
        'id': 'informal_ending_geo',
        'pattern': r'(?:거든|잖아|건데|는데요)\s*[.。]',
        'description': '구어체: 비격식 종결어미 사용',
        'recommendation': '격식체 종결어미(~이다, ~한다, ~합니다)로 수정',
        'severity': 'Major',
    },
    {
        'id': 'slang_abbrev',
        'pattern': r'(?:걍|좀|되게|엄청|진짜|완전)',
        'description': '구어체: 구어/속어 표현 사용',
        'recommendation': '격식체 표현으로 대체',
        'severity': 'Major',
    },
]

# ── English Register Patterns ──

EN_ARCHAIC_PATTERNS = [
    {
        'id': 'witnesseth',
        'pattern': r'\bwitnesseth\b',
        'description': 'Archaic legalese: "witnesseth"',
        'recommendation': 'Consider modern plain language alternative',
        'severity': 'Suggestion',
    },
    {
        'id': 'hereinbefore',
        'pattern': r'\b(?:hereinbefore|hereinafter|hereinabove|hereinbelow|heretofore|hereunder)\b',
        'description': 'Archaic legalese: consider simpler reference',
        'recommendation': 'Replace with specific section reference or "above"/"below"',
        'severity': 'Suggestion',
    },
    {
        'id': 'whereas_overuse',
        'pattern': r'\bWHEREAS\b',
        'description': 'Recital marker — check if overused outside recital section',
        'recommendation': 'Limit "WHEREAS" to the recitals section only',
        'severity': 'Suggestion',
    },
]

EN_INFORMAL_PATTERNS = [
    {
        'id': 'contraction',
        'pattern': r"\b(?:don't|can't|won't|isn't|aren't|shouldn't|couldn't|wouldn't|it's|that's|there's)\b",
        'description': 'Informal: contraction in formal legal document',
        'recommendation': 'Expand contraction (e.g., "don\'t" → "do not")',
        'severity': 'Minor',
    },
]


def load_text_units(text_path: str) -> tuple[str, list[dict]]:
    """Load either paragraph-aware units from parsed-structure.json or line-aware text."""
    if text_path.endswith('.json'):
        with open(text_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        paragraphs = data.get('paragraphs')
        if isinstance(paragraphs, list) and paragraphs:
            units = []
            texts = []
            for idx, para in enumerate(paragraphs):
                para_text = str(para.get('text', ''))
                if not para_text:
                    continue
                texts.append(para_text)
                units.append({
                    'paragraph_index': para.get('index', idx),
                    'text': para_text,
                })
            return '\n'.join(texts), units
        return data.get('full_text', ''), [
            {'line': i + 1, 'text': line}
            for i, line in enumerate(data.get('full_text', '').split('\n'))
        ]

    with open(text_path, 'r', encoding='utf-8') as f:
        text = f.read()
    return text, [{'line': i + 1, 'text': line} for i, line in enumerate(text.split('\n'))]


def validate_text(units: list[dict], language: str) -> list[dict]:
    """Run register validation on paragraph- or line-based text units."""
    findings = []

    if language == 'ko':
        patterns = KR_TRANSLATION_PATTERNS + KR_COLLOQUIAL_PATTERNS
    elif language == 'en':
        patterns = EN_ARCHAIC_PATTERNS + EN_INFORMAL_PATTERNS
    else:
        return findings

    for unit in units:
        unit_text = unit.get('text', '')
        for pat_def in patterns:
            for m in re.finditer(pat_def['pattern'], unit_text, re.IGNORECASE):
                # Get surrounding context
                start = max(0, m.start() - 30)
                end = min(len(unit_text), m.end() + 30)
                context = unit_text[start:end]

                location = {'column': m.start(), 'text_excerpt': context.strip()}
                if 'paragraph_index' in unit:
                    location['paragraph_index'] = unit['paragraph_index']
                else:
                    location['line'] = unit.get('line', 1)

                findings.append({
                    'pattern_id': pat_def['id'],
                    'severity': pat_def['severity'],
                    'description': pat_def['description'],
                    'recommendation': pat_def['recommendation'],
                    'location': location,
                    'matched_text': m.group(0),
                })

    return findings


def main():
    if len(sys.argv) < 4:
        print(json.dumps({'error': 'Usage: register-validator.py <text_path> <language> <output_path>'}))
        sys.exit(1)

    text_path = sys.argv[1]
    language = sys.argv[2]
    output_path = sys.argv[3]

    text, units = load_text_units(text_path)

    findings = validate_text(units, language)

    # Summary by pattern
    by_pattern = {}
    by_severity = {}
    for f in findings:
        pid = f['pattern_id']
        sev = f['severity']
        by_pattern[pid] = by_pattern.get(pid, 0) + 1
        by_severity[sev] = by_severity.get(sev, 0) + 1

    output = {
        'language': language,
        'total_findings': len(findings),
        'by_severity': by_severity,
        'by_pattern': by_pattern,
        'findings': findings,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    result = {
        'success': True,
        'output_path': output_path,
        'total_findings': len(findings),
        'by_severity': by_severity,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
