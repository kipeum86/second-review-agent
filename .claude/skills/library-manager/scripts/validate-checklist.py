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


def _parse_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def load_checklist_yaml(yaml_path: str) -> dict:
    """Load checklist YAML using PyYAML when available, with a stdlib fallback."""
    if yaml is not None:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    data = {}
    current_parent = None
    current_list_key = None

    with open(yaml_path, 'r', encoding='utf-8') as f:
        for lineno, raw_line in enumerate(f, 1):
            line = raw_line.rstrip('\n').rstrip('\r')
            if not line.strip() or line.lstrip().startswith('#'):
                continue

            indent = len(line) - len(line.lstrip(' '))
            stripped = line.lstrip(' ')

            if indent == 0:
                current_parent = None
                current_list_key = None
                if stripped.endswith(':'):
                    key = stripped[:-1].strip()
                    data[key] = {}
                    current_parent = key
                else:
                    if ':' not in stripped:
                        raise ValueError(f'Line {lineno}: expected "key: value"')
                    key, value = stripped.split(':', 1)
                    data[key.strip()] = _parse_scalar(value)
            elif indent == 2 and current_parent:
                if not stripped.endswith(':'):
                    raise ValueError(f'Line {lineno}: expected nested "key:" under {current_parent}')
                key = stripped[:-1].strip()
                if not isinstance(data.get(current_parent), dict):
                    raise ValueError(f'Line {lineno}: parent "{current_parent}" is not a mapping')
                data[current_parent][key] = []
                current_list_key = key
            elif indent >= 4 and current_parent and current_list_key:
                if not stripped.startswith('- '):
                    raise ValueError(f'Line {lineno}: expected list item under {current_parent}.{current_list_key}')
                data[current_parent][current_list_key].append(_parse_scalar(stripped[2:]))
            else:
                raise ValueError(f'Line {lineno}: unsupported indentation pattern')

    return data


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
        elif lang not in ('ko', 'en', 'ja', 'zh', 'any'):
            errors.append(f'language "{lang}" is unusual — expected: ko, en, ja, zh, any')

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

    try:
        data = load_checklist_yaml(yaml_path)
    except Exception as e:
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
