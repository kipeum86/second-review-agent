#!/usr/bin/env python3
"""
Validate a YAML checklist file against the expected schema.

Expected structure:
  document_type: str (required)
  language: str (required)
  description: str (required)
  dimensions: dict of str -> list[str] (required, at least 1 dimension)

Usage: python3 validate-checklist.py <yaml_path>
Output: JSON with validation result
"""

import sys
import os
import json

try:
    import yaml
except ImportError:
    yaml = None


REQUIRED_TOP_KEYS = ['document_type', 'language', 'description', 'dimensions']

VALID_DIMENSION_NAMES = [
    'substance', 'client_alignment', 'writing', 'structure', 'formatting',
    'citation', 'logic', 'completeness', 'terminology', 'general',
]


def validate_checklist(data: dict) -> list[str]:
    """Validate checklist data. Returns list of error messages."""
    errors = []

    if not isinstance(data, dict):
        return ['Root element must be a YAML mapping (dictionary)']

    # Required keys
    for key in REQUIRED_TOP_KEYS:
        if key not in data:
            errors.append(f'Missing required key: {key}')

    # Type checks
    if 'document_type' in data and not isinstance(data['document_type'], str):
        errors.append('document_type must be a string')

    if 'language' in data:
        lang = data['language']
        if not isinstance(lang, str):
            errors.append('language must be a string')
        elif lang not in ('ko', 'en', 'ja', 'zh'):
            errors.append(f'language "{lang}" is unusual — expected: ko, en, ja, zh')

    if 'description' in data and not isinstance(data['description'], str):
        errors.append('description must be a string')

    # Dimensions validation
    if 'dimensions' in data:
        dims = data['dimensions']
        if not isinstance(dims, dict):
            errors.append('dimensions must be a mapping (dict)')
        elif len(dims) == 0:
            errors.append('dimensions must contain at least one dimension')
        else:
            for dim_name, items in dims.items():
                if not isinstance(items, list):
                    errors.append(f'dimension "{dim_name}" must be a list of check items')
                elif len(items) == 0:
                    errors.append(f'dimension "{dim_name}" has no check items')
                else:
                    for i, item in enumerate(items):
                        if not isinstance(item, str):
                            errors.append(f'dimension "{dim_name}" item {i} must be a string')

    return errors


def main():
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: validate-checklist.py <yaml_path>'}))
        sys.exit(1)

    yaml_path = sys.argv[1]

    if not os.path.exists(yaml_path):
        print(json.dumps({'valid': False, 'errors': [f'File not found: {yaml_path}']}))
        sys.exit(1)

    if yaml is None:
        # Fallback: basic YAML parsing without PyYAML
        print(json.dumps({
            'valid': False,
            'errors': ['PyYAML not installed. Run: pip3 install pyyaml']
        }))
        sys.exit(1)

    with open(yaml_path, 'r', encoding='utf-8') as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(json.dumps({'valid': False, 'errors': [f'YAML parse error: {e}']}))
            sys.exit(1)

    errors = validate_checklist(data)

    result = {
        'valid': len(errors) == 0,
        'file': yaml_path,
        'errors': errors,
    }

    if data and isinstance(data, dict):
        result['document_type'] = data.get('document_type', '?')
        result['language'] = data.get('language', '?')
        if 'dimensions' in data and isinstance(data['dimensions'], dict):
            result['dimension_count'] = len(data['dimensions'])
            result['total_items'] = sum(
                len(v) for v in data['dimensions'].values() if isinstance(v, list)
            )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result['valid'] else 1)


if __name__ == '__main__':
    main()
