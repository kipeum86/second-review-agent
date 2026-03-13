#!/usr/bin/env python3
"""
Assemble per-citation verification results into verification-audit.json.

Reads individual citation result files from a directory, validates schema,
computes summary statistics, and writes the consolidated audit trail.

Usage: python3 build-audit-trail.py <results_dir> <output_path>
  - results_dir: directory containing per-citation JSON result files
  - output_path: path to write verification-audit.json

Alternative: python3 build-audit-trail.py --stdin <output_path>
  - Reads a JSON array of citation results from stdin
"""

import sys
import os
import json
import glob
from datetime import datetime, timezone

VALID_STATUSES = {
    'Verified',
    'Nonexistent', 'Wrong_Pinpoint', 'Unsupported_Proposition',
    'Wrong_Jurisdiction', 'Stale', 'Translation_Mismatch',
    'Unverifiable_No_Access', 'Unverifiable_Secondary_Only', 'Unverifiable_No_Evidence',
}

PRIMARY_STATUS_MAP = {
    'Verified': 'verified',
    'Nonexistent': 'issue',
    'Wrong_Pinpoint': 'issue',
    'Unsupported_Proposition': 'issue',
    'Wrong_Jurisdiction': 'issue',
    'Stale': 'issue',
    'Translation_Mismatch': 'issue',
    'Unverifiable_No_Access': 'unverifiable',
    'Unverifiable_Secondary_Only': 'unverifiable',
    'Unverifiable_No_Evidence': 'unverifiable',
}

REQUIRED_FIELDS = ['citation_text', 'citation_type', 'verification_status']


def validate_entry(entry: dict, idx: int) -> list[str]:
    """Validate a single citation audit entry. Returns list of errors."""
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in entry:
            errors.append(f"Citation {idx}: missing required field '{field}'")

    status = entry.get('verification_status', '')
    if status and status not in VALID_STATUSES:
        errors.append(f"Citation {idx}: invalid status '{status}'. Valid: {VALID_STATUSES}")

    # Nonexistent requires evidence
    if status == 'Nonexistent':
        evidence = entry.get('evidence', {})
        if not evidence or (not evidence.get('url') and not evidence.get('search_query')):
            errors.append(
                f"Citation {idx}: 'Nonexistent' status requires documented evidence "
                f"(search query and/or URL). Consider 'Unverifiable_No_Evidence' instead."
            )

    return errors


def compute_summary(citations: list[dict]) -> dict:
    """Compute summary statistics from citation results."""
    summary = {
        'verified': 0,
        'issue': 0,
        'unverifiable': 0,
        'by_sub_status': {},
    }

    for c in citations:
        status = c.get('verification_status', 'Unverifiable_No_Evidence')
        primary = PRIMARY_STATUS_MAP.get(status, 'unverifiable')
        summary[primary] += 1
        summary['by_sub_status'][status] = summary['by_sub_status'].get(status, 0) + 1

    return summary


def build_audit_trail(citations: list[dict], review_depth: str = 'standard') -> dict:
    """Build the complete verification audit trail."""
    # Validate all entries
    all_errors = []
    for i, c in enumerate(citations):
        errors = validate_entry(c, i)
        all_errors.extend(errors)

    # Assign citation IDs if missing
    for i, c in enumerate(citations):
        if 'citation_id' not in c:
            c['citation_id'] = f'CIT-{i+1:03d}'

    summary = compute_summary(citations)

    audit = {
        'review_depth': review_depth,
        'total_citations': len(citations),
        'summary': summary,
        'validation_errors': all_errors,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'citations': citations,
    }

    return audit


def main():
    if len(sys.argv) < 3:
        print(json.dumps({
            'error': 'Usage: build-audit-trail.py <results_dir|--stdin> <output_path>'
        }))
        sys.exit(1)

    source = sys.argv[1]
    output_path = sys.argv[2]

    citations = []

    if source == '--stdin':
        citations = json.load(sys.stdin)
    else:
        # Read all JSON files from results directory
        if os.path.isdir(source):
            for fpath in sorted(glob.glob(os.path.join(source, '*.json'))):
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        citations.extend(data)
                    else:
                        citations.append(data)
        elif os.path.isfile(source):
            with open(source, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and 'citations' in data:
                    citations = data['citations']
                elif isinstance(data, list):
                    citations = data
                else:
                    citations = [data]

    audit = build_audit_trail(citations)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(audit, f, indent=2, ensure_ascii=False)

    result = {
        'success': len(audit['validation_errors']) == 0,
        'output_path': output_path,
        'total_citations': audit['total_citations'],
        'summary': audit['summary'],
        'validation_errors': audit['validation_errors'],
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if audit['validation_errors']:
        sys.exit(1)


if __name__ == '__main__':
    main()
