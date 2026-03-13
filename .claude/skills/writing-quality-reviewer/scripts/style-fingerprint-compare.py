#!/usr/bin/env python3
"""
Compare document writing style against a user's style fingerprint profile.

Computes document metrics and compares against profile if available.
Usage: python3 style-fingerprint-compare.py <text_path> <style_profile_json> <output_path>

Exit codes:
  0 = comparison done (profile found and compared)
  1 = no profile available (file not found or empty)
  2 = insufficient samples (profile exists but <5 samples)
"""

import sys
import os
import json
import re
import math


def compute_metrics(text: str) -> dict:
    """Compute writing style metrics from text."""
    # Split into sentences (Korean and English)
    sentences = re.split(r'[.。!?]\s*', text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]

    if not sentences:
        return {'error': 'No sentences found in text'}

    # Sentence lengths (in characters for Korean, words for English)
    is_korean = any('\uac00' <= c <= '\ud7a3' for c in text[:100])

    if is_korean:
        sent_lengths = [len(s) for s in sentences]
    else:
        sent_lengths = [len(s.split()) for s in sentences]

    avg_sent_length = sum(sent_lengths) / len(sent_lengths)
    sent_length_std = math.sqrt(sum((l - avg_sent_length) ** 2 for l in sent_lengths) / len(sent_lengths)) if len(sent_lengths) > 1 else 0

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
        formal_count = len(re.findall(r'\b(?:therefore|furthermore|moreover|accordingly|pursuant|notwithstanding|herein)\b', text, re.IGNORECASE))
        informal_count = len(re.findall(r"\b(?:basically|actually|really|pretty|kind of|sort of|don't|can't|won't)\b", text, re.IGNORECASE))

    formality_score = formal_count / max(formal_count + informal_count, 1)

    # Paragraph lengths
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    para_lengths = [len(p) for p in paragraphs] if paragraphs else [0]
    avg_para_length = sum(para_lengths) / len(para_lengths)

    # Citation density (citations per 1000 chars)
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


def compare_with_profile(doc_metrics: dict, profile: dict, threshold: float = 1.5) -> list[dict]:
    """Compare document metrics against style profile. Return deviations."""
    deviations = []
    profile_metrics = profile.get('metrics', {})
    profile_stds = profile.get('standard_deviations', {})

    metric_labels = {
        'avg_sentence_length': '평균 문장 길이' if doc_metrics.get('language') == 'ko' else 'Average sentence length',
        'passive_voice_ratio': '수동태 비율' if doc_metrics.get('language') == 'ko' else 'Passive voice ratio',
        'formality_score': '격식체 점수' if doc_metrics.get('language') == 'ko' else 'Formality score',
        'avg_paragraph_length': '평균 단락 길이' if doc_metrics.get('language') == 'ko' else 'Average paragraph length',
        'citation_density': '인용 밀도' if doc_metrics.get('language') == 'ko' else 'Citation density',
    }

    for metric_key, label in metric_labels.items():
        doc_val = doc_metrics.get(metric_key)
        prof_val = profile_metrics.get(metric_key)
        prof_std = profile_stds.get(metric_key, 0)

        if doc_val is None or prof_val is None or prof_std == 0:
            continue

        deviation = abs(doc_val - prof_val) / prof_std
        if deviation > threshold:
            direction = '높음' if doc_val > prof_val else '낮음'
            if doc_metrics.get('language') != 'ko':
                direction = 'higher' if doc_val > prof_val else 'lower'

            deviations.append({
                'metric': metric_key,
                'label': label,
                'document_value': doc_val,
                'profile_value': prof_val,
                'profile_std': prof_std,
                'deviation_sigma': round(deviation, 1),
                'direction': direction,
                'severity': 'Suggestion' if deviation < 2.5 else 'Minor',
            })

    return deviations


def main():
    if len(sys.argv) < 4:
        print(json.dumps({'error': 'Usage: style-fingerprint-compare.py <text_path> <style_profile_json> <output_path>'}))
        sys.exit(1)

    text_path = sys.argv[1]
    profile_path = sys.argv[2]
    output_path = sys.argv[3]

    # Read text
    if text_path.endswith('.json'):
        with open(text_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            text = data.get('full_text', '')
    else:
        with open(text_path, 'r', encoding='utf-8') as f:
            text = f.read()

    doc_metrics = compute_metrics(text)

    # Check profile availability
    if not os.path.exists(profile_path):
        output = {
            'status': 'no_profile',
            'message': 'Style profile not found — comparison skipped',
            'document_metrics': doc_metrics,
            'deviations': [],
        }
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(json.dumps({'success': True, 'status': 'no_profile'}, indent=2))
        sys.exit(1)

    with open(profile_path, 'r', encoding='utf-8') as f:
        profile = json.load(f)

    # Check sample count
    sample_count = profile.get('sample_count', 0)
    if sample_count < 5:
        output = {
            'status': 'insufficient_samples',
            'message': f'Style profile has {sample_count} samples (minimum 5 required) — comparison skipped',
            'document_metrics': doc_metrics,
            'deviations': [],
        }
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(json.dumps({'success': True, 'status': 'insufficient_samples', 'sample_count': sample_count}, indent=2))
        sys.exit(2)

    # Compare
    deviations = compare_with_profile(doc_metrics, profile)

    output = {
        'status': 'compared',
        'document_metrics': doc_metrics,
        'profile_sample_count': sample_count,
        'deviation_threshold': 1.5,
        'total_deviations': len(deviations),
        'deviations': deviations,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    result = {
        'success': True,
        'status': 'compared',
        'total_deviations': len(deviations),
        'deviations': deviations,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == '__main__':
    main()
