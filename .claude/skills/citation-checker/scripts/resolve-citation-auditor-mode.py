#!/usr/bin/env python3
"""Resolve the effective citation-auditor native mode for WF1 Step 3."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

VALID_MODES = {"off", "standalone_only", "shadow", "diff", "assist", "enforce_limited", "enforce"}
ENFORCE_MODES = {"enforce_limited", "enforce"}
OPTIONAL_ARTIFACTS = [
    "working/verification-audit.base.json",
    "working/citation-auditor-shadow.json",
    "working/citation-auditor-adapted.json",
    "working/citation-auditor-diff.json",
]


def load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def normalize_mode(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace("-", "_")
    return text or None


def normalize_depth(value: object) -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    if text in {"deep", "deep_review", "precision", "thorough"}:
        return "deep_review"
    if text in {"quick", "quick_scan"}:
        return "quick_scan"
    return text or "standard"


def review_context(manifest: dict[str, Any]) -> dict[str, Any]:
    context = manifest.get("review_context")
    return context if isinstance(context, dict) else {}


def manifest_review_depth(manifest: dict[str, Any]) -> str:
    context = review_context(manifest)
    return normalize_depth(context.get("depth") or manifest.get("review_depth"))


def manifest_mode(manifest: dict[str, Any]) -> str | None:
    context = review_context(manifest)
    return normalize_mode(context.get("citation_auditor_mode") or manifest.get("citation_auditor_mode"))


def manifest_enforce_approved(manifest: dict[str, Any]) -> bool:
    context = review_context(manifest)
    return bool(
        context.get("citation_auditor_enforce_approved")
        or manifest.get("citation_auditor_enforce_approved")
    )


def validate_mode(mode: str | None, source: str) -> list[str]:
    if mode and mode not in VALID_MODES:
        return [f"invalid {source} citation_auditor_mode: {mode}"]
    return []


def resolve_mode(
    manifest: dict[str, Any],
    *,
    requested_mode: str | None = None,
    env_mode: str | None = None,
    allow_enforce: bool = False,
) -> dict[str, Any]:
    requested = normalize_mode(requested_mode)
    manifest_value = manifest_mode(manifest)
    env_value = normalize_mode(env_mode)
    errors = []
    errors.extend(validate_mode(requested, "requested"))
    errors.extend(validate_mode(manifest_value, "manifest"))
    errors.extend(validate_mode(env_value, "environment"))
    if errors:
        return {"success": False, "errors": errors}

    depth = manifest_review_depth(manifest)
    warnings = []

    if requested:
        mode = requested
        source = "requested"
    elif manifest_value:
        mode = manifest_value
        source = "manifest"
    elif env_value:
        mode = env_value
        source = "environment"
    elif depth == "deep_review":
        mode = "shadow"
        source = "depth_default"
    else:
        mode = "off"
        source = "default"

    approved = allow_enforce or manifest_enforce_approved(manifest)
    if mode in ENFORCE_MODES and not approved:
        warnings.append(
            {
                "code": "enforce_requires_approval",
                "message": f"{mode} requires explicit approval; using shadow instead.",
                "requested_mode": mode,
            }
        )
        mode = "shadow"

    return {
        "success": True,
        "effective_mode": mode,
        "source": source,
        "review_depth": depth,
        "requested_mode": requested,
        "manifest_mode": manifest_value,
        "env_mode": env_value,
        "enforce_approved": approved,
        "optional_artifacts": OPTIONAL_ARTIFACTS if mode not in {"off", "standalone_only"} else [],
        "warnings": warnings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve citation-auditor native mode.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--requested-mode")
    parser.add_argument("--env-mode", default=os.environ.get("SECOND_REVIEW_CITATION_AUDITOR_MODE"))
    parser.add_argument("--allow-enforce", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = resolve_mode(
        load_json(args.manifest),
        requested_mode=args.requested_mode,
        env_mode=args.env_mode,
        allow_enforce=args.allow_enforce,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("success") else 2


if __name__ == "__main__":
    raise SystemExit(main())
