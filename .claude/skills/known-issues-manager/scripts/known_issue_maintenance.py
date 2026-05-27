#!/usr/bin/env python3
"""Maintenance commands for Known Issues generated artifacts."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any

from known_issue_index import (
    build_index_for_registry_path,
    default_index_path,
    load_index_if_current,
    load_json,
    sha256_file,
    write_json_atomic,
)
from known_issue_ledger import distinct_matter_counts, iter_ledger_events
from known_issue_normalizer import cap_examples, normalize_pattern_entry

FREQUENCY_CACHE_SCHEMA_VERSION = 1
FREQUENCY_CACHE_NAME = "frequency-cache.json"


def find_registry_files(registry_dir: str) -> list[str]:
    registry_paths: list[str] = []
    for name in sorted(os.listdir(registry_dir)):
        path = os.path.join(registry_dir, name)
        if not os.path.isfile(path):
            continue
        if not name.endswith(".json"):
            continue
        if name.endswith(".index.json") or name == FREQUENCY_CACHE_NAME:
            continue
        registry_paths.append(path)
    return registry_paths


def registry_entry_stats(entries: list[Any]) -> dict[str, int]:
    missing_metadata = 0
    examples_over_cap = 0
    invalid_entries = 0
    for entry in entries:
        if not isinstance(entry, dict):
            invalid_entries += 1
            continue
        normalized = normalize_pattern_entry(entry)
        if not entry.get("schema_version") or not entry.get("match_signature"):
            missing_metadata += 1
        _capped, trimmed = cap_examples(normalized)
        if trimmed:
            examples_over_cap += 1
    return {
        "invalid_entries": invalid_entries,
        "missing_metadata": missing_metadata,
        "examples_over_cap": examples_over_cap,
    }


def diagnose_registry_file(registry_path: str) -> dict[str, Any]:
    index_path = default_index_path(registry_path)
    try:
        entries = load_json(registry_path)
    except Exception as exc:
        return {
            "registry_path": registry_path,
            "status": "invalid_json",
            "error": str(exc),
            "index_path": index_path,
            "index_status": "not_checked",
        }

    if not isinstance(entries, list):
        return {
            "registry_path": registry_path,
            "status": "invalid_schema",
            "error": "registry must be a JSON array",
            "index_path": index_path,
            "index_status": "not_checked",
        }

    index_exists = os.path.exists(index_path)
    index_current = load_index_if_current(registry_path, index_path=index_path) is not None
    if not index_exists:
        index_status = "missing"
    elif index_current:
        index_status = "current"
    else:
        index_status = "stale"

    return {
        "registry_path": registry_path,
        "status": "ok",
        "patterns_total": len(entries),
        "source_sha256": sha256_file(registry_path),
        "index_path": index_path,
        "index_status": index_status,
        **registry_entry_stats(entries),
    }


def build_frequency_cache(
    ledger_path: str,
    *,
    agent: str | None = None,
) -> dict[str, Any]:
    events = list(iter_ledger_events(ledger_path))
    matters_by_identity = distinct_matter_counts(events, agent=agent)
    frequencies = {
        identity: {"frequency": len(matter_ids)}
        for identity, matter_ids in sorted(matters_by_identity.items())
    }
    return {
        "schema_version": FREQUENCY_CACHE_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_file": os.path.relpath(ledger_path),
        "source_sha256": sha256_file(ledger_path),
        "agent": agent,
        "events_total": len(events),
        "frequencies": frequencies,
    }


def diagnose_ledger_file(ledger_path: str | None) -> dict[str, Any] | None:
    if not ledger_path:
        return None
    if not os.path.exists(ledger_path):
        return {
            "ledger_path": ledger_path,
            "status": "missing",
        }
    try:
        events = list(iter_ledger_events(ledger_path))
    except Exception as exc:
        return {
            "ledger_path": ledger_path,
            "status": "invalid_jsonl",
            "error": str(exc),
        }
    identities = distinct_matter_counts(events)
    return {
        "ledger_path": ledger_path,
        "status": "ok",
        "events_total": len(events),
        "identity_count": len(identities),
        "source_sha256": sha256_file(ledger_path),
    }


def rebuild_known_issue_artifacts(
    registry_dir: str,
    *,
    write_indexes: bool = True,
    ledger_path: str | None = None,
    write_frequency_cache: bool = False,
    cache_path: str | None = None,
    agent: str | None = None,
) -> dict[str, Any]:
    registry_paths = find_registry_files(registry_dir)
    registries = []
    for registry_path in registry_paths:
        before = diagnose_registry_file(registry_path)
        if write_indexes and before.get("status") == "ok":
            build_index_for_registry_path(registry_path)
        after = diagnose_registry_file(registry_path)
        registries.append(
            {
                **after,
                "index_rebuilt": bool(write_indexes and before.get("status") == "ok"),
            }
        )

    ledger = diagnose_ledger_file(ledger_path)
    frequency_cache = None
    if write_frequency_cache:
        if not ledger_path:
            raise ValueError("--write-frequency-cache requires --ledger-path")
        frequency_cache = build_frequency_cache(ledger_path, agent=agent)
        resolved_cache_path = cache_path or os.path.join(registry_dir, FREQUENCY_CACHE_NAME)
        write_json_atomic(resolved_cache_path, frequency_cache)
        frequency_cache = {
            "cache_path": resolved_cache_path,
            "identity_count": len(frequency_cache["frequencies"]),
            "events_total": frequency_cache["events_total"],
        }

    return {
        "registry_dir": registry_dir,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "registries": registries,
        "ledger": ledger,
        "frequency_cache": frequency_cache,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild or check Known Issues generated artifacts.")
    parser.add_argument("registry_dir")
    parser.add_argument("--check", action="store_true", help="Report status without writing indexes.")
    parser.add_argument("--ledger-path")
    parser.add_argument("--write-frequency-cache", action="store_true")
    parser.add_argument("--cache-path")
    parser.add_argument("--agent")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = rebuild_known_issue_artifacts(
        args.registry_dir,
        write_indexes=not args.check,
        ledger_path=args.ledger_path,
        write_frequency_cache=args.write_frequency_cache,
        cache_path=args.cache_path,
        agent=args.agent,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
