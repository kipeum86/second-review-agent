#!/usr/bin/env python3
"""Sidecar index helpers for Known Issues registries."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Any

from known_issue_normalizer import (
    ANY_DOCUMENT_TYPE,
    normalize_document_type,
    normalize_finding,
    normalize_pattern_entry,
    slugify,
)

INDEX_SCHEMA_VERSION = 1


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json_atomic(path: str, payload: Any) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp-known-issues-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def default_index_path(registry_path: str) -> str:
    root, ext = os.path.splitext(registry_path)
    if ext.lower() == ".json":
        return root + ".index.json"
    return registry_path + ".index.json"


def append_unique(mapping: dict[str, list[str]], key: str | None, pattern_id: str | None) -> None:
    if not key or not pattern_id:
        return
    bucket = mapping.setdefault(str(key), [])
    if pattern_id not in bucket:
        bucket.append(pattern_id)


def build_known_issue_index(
    registry_entries: list[dict[str, Any]],
    *,
    agent: str | None = None,
    source_file: str | None = None,
    source_sha256: str | None = None,
) -> dict[str, Any]:
    normalized_entries = [normalize_pattern_entry(entry) for entry in registry_entries]
    resolved_agent = agent or next(
        (str(entry.get("agent")) for entry in normalized_entries if entry.get("agent")),
        "",
    )

    patterns_by_signature: dict[str, list[str]] = {}
    patterns_by_dimension_document_type: dict[str, list[str]] = {}
    patterns_by_dimension: dict[str, list[str]] = {}

    for entry in normalized_entries:
        pattern_id = entry.get("pattern_id")
        dimension = entry.get("dimension")
        document_type = entry.get("document_type") or ANY_DOCUMENT_TYPE
        append_unique(patterns_by_signature, entry.get("match_signature"), pattern_id)
        append_unique(
            patterns_by_dimension_document_type,
            dimension_document_key(dimension, document_type),
            pattern_id,
        )
        append_unique(patterns_by_dimension, str(dimension), pattern_id)

    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "agent": slugify(resolved_agent, default="unknown_agent"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_file": source_file,
        "source_sha256": source_sha256,
        "patterns_total": len(normalized_entries),
        "patterns_by_signature": patterns_by_signature,
        "patterns_by_dimension_document_type": patterns_by_dimension_document_type,
        "patterns_by_dimension": patterns_by_dimension,
    }


def build_index_for_registry_path(registry_path: str, *, index_path: str | None = None) -> dict[str, Any]:
    entries = load_json(registry_path)
    if not isinstance(entries, list):
        raise ValueError(f"registry must be a JSON array: {registry_path}")
    index = build_known_issue_index(
        entries,
        source_file=os.path.relpath(registry_path),
        source_sha256=sha256_file(registry_path),
    )
    write_json_atomic(index_path or default_index_path(registry_path), index)
    return index


def load_index_if_current(registry_path: str, index_path: str | None = None) -> dict[str, Any] | None:
    resolved_index_path = index_path or default_index_path(registry_path)
    if not os.path.exists(resolved_index_path):
        return None
    index = load_json(resolved_index_path)
    if not isinstance(index, dict):
        return None
    if index.get("schema_version") != INDEX_SCHEMA_VERSION:
        return None
    try:
        current_hash = sha256_file(registry_path)
    except FileNotFoundError:
        return None
    if index.get("source_sha256") != current_hash:
        return None
    return index


def dimension_document_key(dimension: Any, document_type: Any) -> str:
    dimension_part = f"d{dimension}" if dimension is not None else "d0"
    return f"{dimension_part}|{normalize_document_type(document_type)}"


def candidate_pattern_ids_from_index(
    index: dict[str, Any] | None,
    finding_metadata: dict[str, Any],
) -> tuple[list[str], str]:
    if not index:
        return [], "missing_index"

    signature = finding_metadata.get("match_signature")
    by_signature = index.get("patterns_by_signature") or {}
    if signature and by_signature.get(signature):
        return list(by_signature[signature]), "signature"

    dimension = finding_metadata.get("dimension")
    document_type = finding_metadata.get("document_type") or ANY_DOCUMENT_TYPE
    dim_doc_key = dimension_document_key(dimension, document_type)
    by_dim_doc = index.get("patterns_by_dimension_document_type") or {}
    if by_dim_doc.get(dim_doc_key):
        return list(by_dim_doc[dim_doc_key]), "dimension_document_type"

    wildcard_key = dimension_document_key(dimension, ANY_DOCUMENT_TYPE)
    if by_dim_doc.get(wildcard_key):
        return list(by_dim_doc[wildcard_key]), "dimension_document_type_wildcard"

    by_dimension = index.get("patterns_by_dimension") or {}
    dimension_key = str(dimension)
    if by_dimension.get(dimension_key):
        return list(by_dimension[dimension_key]), "dimension"

    return [], "no_candidates"


def select_candidate_pattern_ids(
    registry_entries: list[dict[str, Any]],
    finding: dict[str, Any],
    *,
    agent: str,
    document_type: str | None = None,
    index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = normalize_finding(finding, agent=agent, document_type=document_type)
    candidate_ids, source = candidate_pattern_ids_from_index(index, metadata)
    fallback_used = False

    if not candidate_ids:
        fallback_used = True
        normalized_entries = [normalize_pattern_entry(entry) for entry in registry_entries]
        dimension = metadata.get("dimension")
        candidate_ids = [
            entry["pattern_id"]
            for entry in normalized_entries
            if entry.get("pattern_id") and entry.get("dimension") == dimension
        ]
        source = "legacy_dimension_scan"

    return {
        "candidate_pattern_ids": candidate_ids,
        "candidate_count": len(candidate_ids),
        "finding_metadata": metadata,
        "fallback_used": fallback_used,
        "source": source,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Known Issues sidecar index.")
    parser.add_argument("registry_path")
    parser.add_argument("--index-path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    index = build_index_for_registry_path(args.registry_path, index_path=args.index_path)
    print(
        json.dumps(
            {
                "index_path": args.index_path or default_index_path(args.registry_path),
                "patterns_total": index["patterns_total"],
                "source_sha256": index["source_sha256"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
