#!/usr/bin/env python3
"""Append-only occurrence ledger helpers for Known Issues."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date
from typing import Any, Iterable

from known_issue_normalizer import normalize_finding, normalize_text, slugify

LEDGER_SCHEMA_VERSION = 1
DEFAULT_PROPOSAL_THRESHOLD = 3


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalized_round(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    if text.startswith("round_"):
        return text
    return f"round_{text}"


def event_identity_key(event: dict[str, Any]) -> str | None:
    pattern_id = event.get("pattern_id")
    if pattern_id:
        return f"pattern:{pattern_id}"
    signature = event.get("match_signature")
    if signature:
        return f"signature:{signature}"
    return None


def build_event_id(event: dict[str, Any]) -> str:
    parts = [
        str(event.get("agent") or ""),
        str(event.get("matter_id") or ""),
        str(event.get("round") or ""),
        str(event.get("issue_id") or ""),
        str(event.get("pattern_id") or ""),
        str(event.get("match_signature") or ""),
        str(event.get("description_hash") or ""),
    ]
    return sha256_text("|".join(parts))


def build_occurrence_event(
    finding: dict[str, Any],
    *,
    agent: str,
    matter_id: str,
    round_id: Any = None,
    document_type: str | None = None,
    pattern_id: str | None = None,
    occurred_on: str | None = None,
) -> dict[str, Any]:
    metadata = normalize_finding(finding, agent=agent, document_type=document_type)
    description = finding.get("description") or finding.get("title") or ""
    resolved_pattern_id = (
        pattern_id
        or finding.get("recurring_pattern")
        or finding.get("pattern_id")
    )
    event = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "event_id": None,
        "agent": slugify(agent, default="unknown_agent"),
        "matter_id": str(matter_id),
        "round": normalized_round(round_id),
        "issue_id": str(finding.get("issue_id") or ""),
        "pattern_id": str(resolved_pattern_id) if resolved_pattern_id else None,
        "dimension": metadata["dimension"],
        "document_type": metadata["document_type"],
        "defect_type": metadata["defect_type"],
        "match_signature": metadata["match_signature"],
        "description_hash": sha256_text(normalize_text(description)),
        "occurred_on": occurred_on or date.today().isoformat(),
    }
    event["event_id"] = build_event_id(event)
    return event


def build_occurrence_events_from_issue_registry(
    issue_registry: dict[str, Any],
    *,
    agent: str,
    document_type: str | None = None,
    occurred_on: str | None = None,
) -> list[dict[str, Any]]:
    matter_id = issue_registry.get("matter_id")
    if matter_id is None or str(matter_id).strip() == "":
        raise ValueError("issue registry is missing matter_id")

    round_id = issue_registry.get("round")
    resolved_document_type = issue_registry.get("document_type") or document_type
    events = []
    for issue in issue_registry.get("issues", []):
        if not isinstance(issue, dict):
            continue
        events.append(
            build_occurrence_event(
                issue,
                agent=agent,
                matter_id=str(matter_id),
                round_id=round_id,
                document_type=resolved_document_type,
                occurred_on=occurred_on,
            )
        )
    return events


def append_occurrence_events(ledger_path: str, events: Iterable[dict[str, Any]]) -> int:
    event_list = list(events)
    if not event_list:
        return 0
    directory = os.path.dirname(os.path.abspath(ledger_path))
    os.makedirs(directory, exist_ok=True)
    with open(ledger_path, "a", encoding="utf-8") as handle:
        for event in event_list:
            json.dump(event, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
    return len(event_list)


def iter_ledger_events(ledger_path: str) -> Iterable[dict[str, Any]]:
    if not os.path.exists(ledger_path):
        return
    with open(ledger_path, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            if not isinstance(payload, dict):
                raise ValueError(f"ledger line {line_number} is not a JSON object")
            yield payload


def distinct_matter_counts(
    events: Iterable[dict[str, Any]],
    *,
    agent: str | None = None,
) -> dict[str, set[str]]:
    expected_agent = slugify(agent, default="unknown_agent") if agent else None
    matters_by_identity: dict[str, set[str]] = {}
    for event in events:
        if expected_agent and event.get("agent") != expected_agent:
            continue
        identity = event_identity_key(event)
        matter_id = event.get("matter_id")
        if not identity or not matter_id:
            continue
        matters_by_identity.setdefault(identity, set()).add(str(matter_id))
    return matters_by_identity


def count_distinct_matters(
    ledger_path: str,
    *,
    match_signature: str | None = None,
    pattern_id: str | None = None,
    agent: str | None = None,
) -> int:
    identity = f"pattern:{pattern_id}" if pattern_id else f"signature:{match_signature}"
    matters_by_identity = distinct_matter_counts(iter_ledger_events(ledger_path), agent=agent)
    return len(matters_by_identity.get(identity, set()))


def proposal_candidates_for_issue_registry(
    ledger_path: str,
    issue_registry: dict[str, Any],
    *,
    agent: str,
    document_type: str | None = None,
    known_match_signatures: set[str] | None = None,
    threshold: int = DEFAULT_PROPOSAL_THRESHOLD,
) -> list[dict[str, Any]]:
    known_match_signatures = known_match_signatures or set()
    current_events = build_occurrence_events_from_issue_registry(
        issue_registry,
        agent=agent,
        document_type=document_type,
    )
    current_signatures = {
        event["match_signature"]
        for event in current_events
        if not event.get("pattern_id")
        and event.get("match_signature")
        and event.get("match_signature") not in known_match_signatures
    }
    matters_by_identity = distinct_matter_counts(iter_ledger_events(ledger_path), agent=agent)

    proposals = []
    for signature in sorted(current_signatures):
        identity = f"signature:{signature}"
        matter_ids = sorted(matters_by_identity.get(identity, set()))
        if len(matter_ids) >= threshold:
            proposals.append(
                {
                    "match_signature": signature,
                    "frequency": len(matter_ids),
                    "matter_ids": matter_ids,
                }
            )
    return proposals


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append issue-registry findings to a Known Issues occurrence ledger.")
    parser.add_argument("issue_registry_path")
    parser.add_argument("--agent", required=True)
    parser.add_argument("--ledger-path", required=True)
    parser.add_argument("--document-type")
    parser.add_argument("--occurred-on")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    issue_registry = load_json(args.issue_registry_path)
    events = build_occurrence_events_from_issue_registry(
        issue_registry,
        agent=args.agent,
        document_type=args.document_type,
        occurred_on=args.occurred_on,
    )
    appended = append_occurrence_events(args.ledger_path, events)
    print(
        json.dumps(
            {
                "ledger_path": args.ledger_path,
                "events_appended": appended,
                "matter_id": issue_registry.get("matter_id"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
