#!/usr/bin/env python3
"""
Validate numbering hierarchy in parsed document structure.

Checks for: gaps, duplicates, hierarchy violations in Korean 조/항/호/목 and
general numbered lists.

Usage: python3 numbering-validator.py <parsed_structure_json> <output_path>
"""

import sys
import os
import json
import re


def validate_article_numbering(sections: list[dict]) -> list[dict]:
    """Validate Korean 제X조 article numbering sequence."""
    findings = []
    article_re = re.compile(r'제\s*(\d+)\s*조')

    article_numbers = []
    for sec in sections:
        m = article_re.match(sec['title'])
        if m:
            article_numbers.append({
                'number': int(m.group(1)),
                'title': sec['title'],
                'index': sec['start_index'],
            })

    if not article_numbers:
        return findings

    # Check for gaps
    for i in range(1, len(article_numbers)):
        prev = article_numbers[i-1]['number']
        curr = article_numbers[i]['number']

        if curr != prev + 1:
            if curr == prev:
                findings.append({
                    'check_type': 'numbering_duplicate',
                    'severity': 'Minor',
                    'location': {'paragraph_index': article_numbers[i]['index']},
                    'description': f'번호 중복: 제{curr}조가 두 번 나타남',
                    'recommendation': '번호를 수정하거나 조항을 통합할 것',
                })
            elif curr > prev + 1:
                missing = list(range(prev + 1, curr))
                findings.append({
                    'check_type': 'numbering_gap',
                    'severity': 'Minor',
                    'location': {'paragraph_index': article_numbers[i]['index']},
                    'description': f'번호 갭: 제{prev}조에서 제{curr}조로 건너뜀 (제{", 제".join(str(n) for n in missing)}조 누락)',
                    'recommendation': '삭제된 조항이면 번호 재정렬을 검토하거나, 의도적이면 주석 추가',
                })
            elif curr < prev:
                findings.append({
                    'check_type': 'numbering_order',
                    'severity': 'Major',
                    'location': {'paragraph_index': article_numbers[i]['index']},
                    'description': f'번호 역순: 제{prev}조 다음에 제{curr}조가 나타남',
                    'recommendation': '번호 순서를 확인하고 수정할 것',
                })

    # Check first article starts at 1 (or common starting point)
    if article_numbers and article_numbers[0]['number'] > 2:
        findings.append({
            'check_type': 'numbering_start',
            'severity': 'Suggestion',
            'location': {'paragraph_index': article_numbers[0]['index']},
            'description': f'첫 조항이 제{article_numbers[0]["number"]}조부터 시작 (제1조 부재)',
            'recommendation': '의도적이지 않다면 제1조부터 시작하도록 확인',
        })

    return findings


def validate_heading_hierarchy(paragraphs: list[dict]) -> list[dict]:
    """Validate heading level hierarchy (no jumping from H1 to H3 without H2)."""
    findings = []
    prev_level = 0

    for para in paragraphs:
        level = para.get('heading_level', 0)
        if level == 0:
            continue

        if level > prev_level + 1 and prev_level > 0:
            findings.append({
                'check_type': 'heading_hierarchy',
                'severity': 'Minor',
                'location': {'paragraph_index': para['index']},
                'description': f'제목 계층 건너뜀: 레벨 {prev_level}에서 레벨 {level}로 (레벨 {prev_level+1} 없음)',
                'recommendation': '중간 레벨 제목을 추가하거나 현재 제목의 레벨을 조정할 것',
                'heading_text': para['text'][:50],
            })

        prev_level = level

    return findings


def validate_list_numbering(numbering_sequences: list[dict]) -> list[dict]:
    """Validate numbered list continuity."""
    findings = []

    for seq in numbering_sequences:
        if seq['type'] == 'article' and 'numbers' in seq:
            numbers = seq['numbers']
            for i in range(1, len(numbers)):
                if numbers[i] != numbers[i-1] + 1:
                    findings.append({
                        'check_type': 'list_gap',
                        'severity': 'Minor',
                        'location': {'paragraph_index': seq.get('start_index', 0) + i},
                        'description': f'번호 목록 갭: {numbers[i-1]}에서 {numbers[i]}로',
                        'recommendation': '번호 목록의 연속성을 확인할 것',
                    })

    return findings


def main():
    if len(sys.argv) < 3:
        print(json.dumps({'error': 'Usage: numbering-validator.py <parsed_structure_json> <output_path>'}))
        sys.exit(1)

    parsed_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(parsed_path, 'r', encoding='utf-8') as f:
        parsed = json.load(f)

    sections = parsed.get('sections', [])
    paragraphs = parsed.get('paragraphs', [])
    numbering_sequences = parsed.get('numbering_sequences', [])

    findings = []
    findings.extend(validate_article_numbering(sections))
    findings.extend(validate_heading_hierarchy(paragraphs))
    findings.extend(validate_list_numbering(numbering_sequences))

    by_type = {}
    for f_item in findings:
        t = f_item['check_type']
        by_type[t] = by_type.get(t, 0) + 1

    output = {
        'total_findings': len(findings),
        'by_check_type': by_type,
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
