#!/usr/bin/env python3
"""
Extract legal citations from parsed document structure.

Supports Korean, US, and EU citation formats.
Usage: python3 extract-citations.py <parsed_structure_json> <output_path>
"""

import os
import json
import re
import sys

_SHARED_SCRIPTS = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "_shared", "scripts")
)
if _SHARED_SCRIPTS not in sys.path:
    sys.path.insert(0, _SHARED_SCRIPTS)

from artifact_meta import write_artifact_meta  # noqa: E402

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

# Simplified Korean case pattern: NNNN다NNNNN, NNNN고단NNNN, NNNN구합NNNNN
# Matches: 2024다12345, 2024고단1234, 2024구합12345
# Rejects: 2024A12345, 24다12
KR_CASE_SIMPLE_RE = re.compile(
    r'(\d{4})\s*([가-힣]{1,3})\s*(\d{2,6})'
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


SENTENCE_END_RE = re.compile(r'[.!?。]\s+|[.!?。]$')


def get_context(paragraphs: list[dict], para_idx: int, match_start: int, match_end: int) -> str:
    """Get surrounding sentence context for a citation."""
    if para_idx < len(paragraphs) and paragraphs[para_idx].get('index') == para_idx:
        paragraph = paragraphs[para_idx]
    else:
        paragraph = next((item for item in paragraphs if item.get('index') == para_idx), {})
    text = paragraph.get('text', '')
    sent_start = 0
    for boundary in SENTENCE_END_RE.finditer(text[:match_start]):
        sent_start = boundary.end()
    next_boundary = SENTENCE_END_RE.search(text[match_end:])
    sent_end = match_end + next_boundary.end() if next_boundary else len(text)
    return text[sent_start:sent_end].strip()


def normalize_citation_key(citation_type: str, jurisdiction: str, citation_text: str) -> str:
    """Create a grouping key without collapsing separate occurrences."""
    normalized = re.sub(r'\s+', '', citation_text or '').lower()
    normalized = normalized.replace('「', '').replace('」', '')
    normalized = re.sub(r'[^\w가-힣§./()-]+', '', normalized)
    return f'{citation_type}:{jurisdiction}:{normalized}'


def add_citation(
    citations: list[dict],
    *,
    citation_text: str,
    citation_type: str,
    jurisdiction: str,
    para_idx: int,
    match_start: int,
    match_end: int,
    paragraphs: list[dict],
    **extra,
) -> None:
    """Append one citation occurrence while preserving legacy fields."""
    sequence = len(citations) + 1
    normalized_key = normalize_citation_key(citation_type, jurisdiction, citation_text)
    source_location = {
        'paragraph_index': para_idx,
        'char_start': match_start,
        'char_end': match_end,
    }
    citation = {
        'citation_id': f'CIT-{sequence:03d}',
        'occurrence_id': f'OCC-{sequence:03d}',
        'normalized_citation_key': normalized_key,
        'dedupe_group': normalized_key,
        'citation_text': citation_text,
        'citation_type': citation_type,
        'jurisdiction': jurisdiction,
        'location': dict(source_location),
        'source_location': dict(source_location),
        'claimed_content': get_context(paragraphs, para_idx, match_start, match_end),
    }
    citation.update(extra)
    citations.append(citation)


def spans_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def extract_citations(parsed_structure: dict) -> list[dict]:
    """Extract all citations from parsed paragraphs."""
    paragraphs = parsed_structure.get('paragraphs', [])
    citations = []

    for para in paragraphs:
        text = para.get('text', '')
        if not text:
            continue
        para_idx = para['index']
        occupied_case_spans = []

        # Korean statutes by number
        for m in KR_STATUTE_NUM_RE.finditer(text):
            add_citation(
                citations,
                citation_text=m.group(0),
                citation_type='statute',
                jurisdiction='KR',
                para_idx=para_idx,
                match_start=m.start(),
                match_end=m.end(),
                paragraphs=paragraphs,
            )

        # Korean named statutes
        for m in KR_STATUTE_NAME_RE.finditer(text):
            name = m.group(1)
            # Filter out non-statute bracket usage (too short or common phrases)
            if len(name) < 3:
                continue
            # Check if it looks like a law name (ends with 법, 령, 규칙, etc.)
            if re.search(r'(?:법|령|규칙|조약|협약|협정|규정|지침|고시|훈령)$', name):
                # Also look for article references near this statute name
                article_match = KR_ARTICLE_REF_RE.search(text[m.end():m.end()+50])
                article_ref = article_match.group(0) if article_match else None
                match_end = m.end() + article_match.end() if article_match else m.end()
                add_citation(
                    citations,
                    citation_text=m.group(0) + (f' {article_ref}' if article_ref else ''),
                    citation_type='statute',
                    jurisdiction='KR',
                    para_idx=para_idx,
                    match_start=m.start(),
                    match_end=match_end,
                    paragraphs=paragraphs,
                    statute_name=name,
                    article_ref=article_ref,
                )

        # Korean case numbers
        for m in KR_CASE_RE.finditer(text):
            occupied_case_spans.append((m.start(), m.end()))
            add_citation(
                citations,
                citation_text=m.group(0).strip(),
                citation_type='case',
                jurisdiction='KR',
                para_idx=para_idx,
                match_start=m.start(),
                match_end=m.end(),
                paragraphs=paragraphs,
            )

        # Simplified Korean case pattern (fallback)
        for m in KR_CASE_SIMPLE_RE.finditer(text):
            if any(spans_overlap((m.start(), m.end()), span) for span in occupied_case_spans):
                continue
            # Only if preceded by court name context
            prefix = text[max(0, m.start()-20):m.start()]
            if re.search(r'(?:대법원|법원|판결|선고)', prefix):
                add_citation(
                    citations,
                    citation_text=m.group(0).strip(),
                    citation_type='case',
                    jurisdiction='KR',
                    para_idx=para_idx,
                    match_start=m.start(),
                    match_end=m.end(),
                    paragraphs=paragraphs,
                )

        # US Code
        for m in US_CODE_RE.finditer(text):
            add_citation(
                citations,
                citation_text=m.group(0).strip(),
                citation_type='statute',
                jurisdiction='US',
                para_idx=para_idx,
                match_start=m.start(),
                match_end=m.end(),
                paragraphs=paragraphs,
                title=m.group(1),
                section=m.group(2),
            )

        # US CFR
        for m in US_CFR_RE.finditer(text):
            add_citation(
                citations,
                citation_text=m.group(0).strip(),
                citation_type='regulation',
                jurisdiction='US',
                para_idx=para_idx,
                match_start=m.start(),
                match_end=m.end(),
                paragraphs=paragraphs,
            )

        # US cases
        for m in US_CASE_RE.finditer(text):
            add_citation(
                citations,
                citation_text=m.group(0).strip(),
                citation_type='case',
                jurisdiction='US',
                para_idx=para_idx,
                match_start=m.start(),
                match_end=m.end(),
                paragraphs=paragraphs,
            )

        # EU regulations/directives
        for m in EU_REG_RE.finditer(text):
            add_citation(
                citations,
                citation_text=m.group(0).strip(),
                citation_type='regulation',
                jurisdiction='EU',
                para_idx=para_idx,
                match_start=m.start(),
                match_end=m.end(),
                paragraphs=paragraphs,
            )

        # EU treaty articles
        for m in EU_TREATY_RE.finditer(text):
            add_citation(
                citations,
                citation_text=m.group(0).strip(),
                citation_type='treaty',
                jurisdiction='EU',
                para_idx=para_idx,
                match_start=m.start(),
                match_end=m.end(),
                paragraphs=paragraphs,
            )

    citations.sort(key=lambda c: (c['location']['paragraph_index'], c['location'].get('char_start', 0)))
    for idx, citation in enumerate(citations, 1):
        citation['citation_id'] = f'CIT-{idx:03d}'
        citation['occurrence_id'] = f'OCC-{idx:03d}'

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

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    write_artifact_meta(
        output_path,
        artifact_type='citation_list',
        producer={'step': 'WF1_STEP_2', 'skill': 'document-parser', 'script': 'extract-citations.py'},
        source_file=parsed_structure.get('source_file'),
    )

    if output_dir and os.path.basename(output_path) != 'citation-occurrences.json':
        occurrence_path = os.path.join(output_dir, 'citation-occurrences.json')
        with open(occurrence_path, 'w', encoding='utf-8') as f:
            json.dump({**output, 'artifact_type': 'citation_occurrences'}, f, indent=2, ensure_ascii=False)
        write_artifact_meta(
            occurrence_path,
            artifact_type='citation_occurrences',
            producer={'step': 'WF1_STEP_2', 'skill': 'document-parser', 'script': 'extract-citations.py'},
            source_file=parsed_structure.get('source_file'),
        )

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
