#!/usr/bin/env python3
"""Validate or create metadata sidecars for workflow JSON artifacts."""

from __future__ import annotations

import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(__file__)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from artifact_meta import validate_artifact, write_artifact_meta  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate workflow artifact metadata.")
    parser.add_argument("artifact_path")
    parser.add_argument("--artifact-type")
    parser.add_argument("--manifest")
    parser.add_argument("--require-meta", action="store_true")
    parser.add_argument("--write-meta", action="store_true")
    parser.add_argument("--source-file")
    parser.add_argument("--producer-step")
    parser.add_argument("--producer-skill")
    parser.add_argument("--producer-script")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    meta_path = None
    if args.write_meta:
        if not args.artifact_type:
            print(json.dumps({"success": False, "errors": ["--artifact-type is required with --write-meta"]}))
            return 2
        producer = {
            key: value
            for key, value in {
                "step": args.producer_step,
                "skill": args.producer_skill,
                "script": args.producer_script,
            }.items()
            if value
        }
        meta_path = write_artifact_meta(
            args.artifact_path,
            artifact_type=args.artifact_type,
            producer=producer,
            manifest_path=args.manifest,
            source_file=args.source_file,
        )

    errors = validate_artifact(
        args.artifact_path,
        artifact_type=args.artifact_type,
        manifest_path=args.manifest,
        require_meta=args.require_meta or args.write_meta,
    )
    payload = {
        "success": not errors,
        "artifact_path": args.artifact_path,
        "meta_path": meta_path,
        "errors": errors,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
