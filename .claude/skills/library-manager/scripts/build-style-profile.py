#!/usr/bin/env python3
"""
Build a style fingerprint profile from ingested writing samples.

Aggregates metrics across all samples in the samples directory,
computing mean and standard deviation for each metric.

Usage: python3 build-style-profile.py <samples_dir> <output_path>
"""

import sys
import os
import json
import math
from datetime import datetime, timezone


METRIC_KEYS = [
    'avg_sentence_length',
    'passive_voice_ratio',
    'formality_score',
    'avg_paragraph_length',
    'citation_density',
]


def load_samples(samples_dir: str) -> list[dict]:
    """Load all sample JSON files from the directory."""
    samples = []
    if not os.path.isdir(samples_dir):
        return samples

    for fname in sorted(os.listdir(samples_dir)):
        if not fname.endswith('.json'):
            continue
        fpath = os.path.join(samples_dir, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if 'metrics' in data and 'error' not in data.get('metrics', {}):
                samples.append(data)
        except (json.JSONDecodeError, IOError):
            continue

    return samples


def compute_aggregate(samples: list[dict]) -> tuple[dict, dict]:
    """Compute mean and std dev for each metric across samples."""
    metric_values = {k: [] for k in METRIC_KEYS}

    for sample in samples:
        metrics = sample.get('metrics', {})
        for key in METRIC_KEYS:
            val = metrics.get(key)
            if val is not None:
                metric_values[key].append(val)

    means = {}
    stds = {}

    for key in METRIC_KEYS:
        values = metric_values[key]
        if not values:
            means[key] = None
            stds[key] = None
            continue

        mean = sum(values) / len(values)
        means[key] = round(mean, 3)

        if len(values) > 1:
            variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
            stds[key] = round(math.sqrt(variance), 3)
        else:
            stds[key] = 0

    return means, stds


def main():
    if len(sys.argv) < 3:
        print(json.dumps({'error': 'Usage: build-style-profile.py <samples_dir> <output_path>'}))
        sys.exit(1)

    samples_dir = sys.argv[1]
    output_path = sys.argv[2]

    samples = load_samples(samples_dir)
    sample_count = len(samples)

    if sample_count < 5:
        result = {
            'error': f'Insufficient samples: {sample_count} found, minimum 5 required',
            'sample_count': sample_count,
            'samples_found': [s.get('filename', '?') for s in samples],
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(2)

    means, stds = compute_aggregate(samples)

    # Detect dominant language
    languages = [s.get('metrics', {}).get('language', 'unknown') for s in samples]
    dominant_language = max(set(languages), key=languages.count)

    profile = {
        'profile_name': 'default',
        'sample_count': sample_count,
        'dominant_language': dominant_language,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'sample_files': [s.get('filename', '?') for s in samples],
        'metrics': means,
        'standard_deviations': stds,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)

    result = {
        'success': True,
        'sample_count': sample_count,
        'dominant_language': dominant_language,
        'metrics': means,
        'standard_deviations': stds,
        'output_path': output_path,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
