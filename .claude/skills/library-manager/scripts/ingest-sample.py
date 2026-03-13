#!/usr/bin/env python3
"""
Ingest a writing sample into the library.

Extracts text from DOCX/PDF/MD/TXT, computes style metrics,
and outputs a JSON record for storage in library/samples/.

Usage: python3 ingest-sample.py <file_path>
Output: JSON to stdout
"""

import sys
import os
import json
import re
import math
import zipfile
from datetime import datetime, timezone

try:
    from xml.etree import ElementTree as ET
except ImportError:
    ET = None

WORD_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def extract_text_from_docx(path: str) -> str:
    """Extract plain text from a DOCX file."""
    paragraphs = []
    with zipfile.ZipFile(path, 'r') as z:
        if 'word/document.xml' not in z.namelist():
            return ''
        with z.open('word/document.xml') as f:
            tree = ET.parse(f)
    root = tree.getroot()
    for p_elem in root.iter(f'{{{WORD_NS}}}p'):
        texts = []
        for t_elem in p_elem.iter(f'{{{WORD_NS}}}t'):
            if t_elem.text:
                texts.append(t_elem.text)
        if texts:
            paragraphs.append(''.join(texts))
    return '\n\n'.join(paragraphs)


def extract_text_from_file(path: str) -> str:
    """Extract text based on file extension."""
    ext = os.path.splitext(path)[1].lower()

    if ext == '.docx':
        return extract_text_from_docx(path)
    elif ext == '.pdf':
        # Minimal PDF text extraction — best-effort
        try:
            with open(path, 'rb') as f:
                content = f.read()
            # Extract text between BT/ET operators (very basic)
            text_parts = []
            for match in re.finditer(rb'\((.*?)\)', content):
                try:
                    text_parts.append(match.group(1).decode('utf-8', errors='ignore'))
                except Exception:
                    pass
            return '\n'.join(text_parts) if text_parts else ''
        except Exception:
            return ''
    else:
        # MD, TXT, or any plain text
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()


def compute_metrics(text: str) -> dict:
    """Compute writing style metrics from text."""
    sentences = re.split(r'[.。!?]\s*', text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]

    if not sentences:
        return {'error': 'No sentences found in text'}

    is_korean = any('\uac00' <= c <= '\ud7a3' for c in text[:200])

    if is_korean:
        sent_lengths = [len(s) for s in sentences]
    else:
        sent_lengths = [len(s.split()) for s in sentences]

    avg_sent_length = sum(sent_lengths) / len(sent_lengths)
    sent_length_std = (
        math.sqrt(sum((l - avg_sent_length) ** 2 for l in sent_lengths) / len(sent_lengths))
        if len(sent_lengths) > 1 else 0
    )

    # Passive voice ratio
    if is_korean:
        passive_count = len(re.findall(r'(?:되다|되었다|된다|되는|되어|에\s*의해)', text))
    else:
        passive_count = len(re.findall(r'\b(?:is|are|was|were|been|being)\s+\w+ed\b', text, re.IGNORECASE))
    passive_ratio = passive_count / len(sentences) if sentences else 0

    # Formality markers
    if is_korean:
        formal_count = len(re.findall(r'(?:합니다|입니다|됩니다|있습니다|한다|이다|된다)', text))
        informal_count = len(re.findall(r'(?:해요|에요|거든요|잖아요|인데요)', text))
    else:
        formal_count = len(re.findall(
            r'\b(?:therefore|furthermore|moreover|accordingly|pursuant|notwithstanding|herein)\b',
            text, re.IGNORECASE
        ))
        informal_count = len(re.findall(
            r"\b(?:basically|actually|really|pretty|kind of|sort of|don't|can't|won't)\b",
            text, re.IGNORECASE
        ))
    formality_score = formal_count / max(formal_count + informal_count, 1)

    # Paragraph lengths
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    para_lengths = [len(p) for p in paragraphs] if paragraphs else [0]
    avg_para_length = sum(para_lengths) / len(para_lengths)

    # Citation density (per 1000 chars)
    citation_count = len(re.findall(r'(?:제\d+조|§\s*\d+|Article\s+\d+|\d+\s*U\.S\.C)', text))
    citation_density = citation_count / max(len(text) / 1000, 1)

    return {
        'language': 'ko' if is_korean else 'en',
        'total_sentences': len(sentences),
        'total_paragraphs': len(paragraphs),
        'avg_sentence_length': round(avg_sent_length, 1),
        'sentence_length_std': round(sent_length_std, 1),
        'passive_voice_ratio': round(passive_ratio, 3),
        'formality_score': round(formality_score, 3),
        'avg_paragraph_length': round(avg_para_length, 1),
        'citation_density': round(citation_density, 2),
    }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: ingest-sample.py <file_path>'}))
        sys.exit(1)

    file_path = sys.argv[1]

    if not os.path.exists(file_path):
        print(json.dumps({'error': f'File not found: {file_path}'}))
        sys.exit(1)

    text = extract_text_from_file(file_path)

    if not text or len(text.strip()) < 50:
        print(json.dumps({'error': 'Insufficient text extracted from file'}))
        sys.exit(1)

    metrics = compute_metrics(text)

    result = {
        'filename': os.path.basename(file_path),
        'source_path': os.path.abspath(file_path),
        'ingested_at': datetime.now(timezone.utc).isoformat(),
        'text_length': len(text),
        'metrics': metrics,
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
