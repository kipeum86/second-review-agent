import json
import os
import sys
import tempfile
import unittest

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from known_issue_ledger import (  # type: ignore  # noqa: E402
    append_occurrence_events,
    build_occurrence_event,
    build_occurrence_events_from_issue_registry,
    count_distinct_matters,
    iter_ledger_events,
    proposal_candidates_for_issue_registry,
)


def load_fixture(name: str):
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


class KnownIssueLedgerTests(unittest.TestCase):
    def test_build_occurrence_event_uses_normalized_signature(self) -> None:
        registry = load_fixture("issue-registry.json")
        event = build_occurrence_event(
            registry["issues"][0],
            agent="legal-writing-agent",
            matter_id=registry["matter_id"],
            round_id=registry["round"],
            occurred_on="2026-05-27",
        )

        self.assertEqual(event["schema_version"], 1)
        self.assertEqual(event["agent"], "legal-writing-agent")
        self.assertEqual(event["matter_id"], "SYN-004")
        self.assertEqual(event["round"], "round_1")
        self.assertEqual(
            event["match_signature"],
            "legal-writing-agent|d4|advisory|passive_by_overuse",
        )
        self.assertTrue(event["description_hash"].startswith("sha256:"))
        self.assertTrue(event["event_id"].startswith("sha256:"))

    def test_append_jsonl_does_not_truncate_existing_events(self) -> None:
        registry = load_fixture("issue-registry.json")
        event = build_occurrence_events_from_issue_registry(
            registry,
            agent="legal-writing-agent",
            occurred_on="2026-05-27",
        )[0]
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = os.path.join(tmp, "occurrence-ledger.jsonl")
            with open(ledger_path, "w", encoding="utf-8") as handle:
                json.dump({"schema_version": 1, "event_id": "seed"}, handle)
                handle.write("\n")

            appended = append_occurrence_events(ledger_path, [event])

            self.assertEqual(appended, 1)
            events = list(iter_ledger_events(ledger_path))
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["event_id"], "seed")
            self.assertEqual(events[1]["event_id"], event["event_id"])

    def test_distinct_matter_count_ignores_re_review_rounds(self) -> None:
        registries = load_fixture("repeated-round-issue-registries.json")
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = os.path.join(tmp, "occurrence-ledger.jsonl")
            for registry in registries[:3]:
                append_occurrence_events(
                    ledger_path,
                    build_occurrence_events_from_issue_registry(
                        registry,
                        agent="legal-writing-agent",
                        occurred_on="2026-05-27",
                    ),
                )

            self.assertEqual(
                count_distinct_matters(
                    ledger_path,
                    match_signature="legal-writing-agent|d4|advisory|passive_by_overuse",
                    agent="legal-writing-agent",
                ),
                2,
            )

    def test_proposal_candidates_require_three_distinct_matters(self) -> None:
        registries = load_fixture("repeated-round-issue-registries.json")
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = os.path.join(tmp, "occurrence-ledger.jsonl")
            for registry in registries:
                append_occurrence_events(
                    ledger_path,
                    build_occurrence_events_from_issue_registry(
                        registry,
                        agent="legal-writing-agent",
                        occurred_on="2026-05-27",
                    ),
                )

            proposals = proposal_candidates_for_issue_registry(
                ledger_path,
                registries[-1],
                agent="legal-writing-agent",
                threshold=3,
            )

            self.assertEqual(len(proposals), 1)
            self.assertEqual(
                proposals[0]["match_signature"],
                "legal-writing-agent|d4|advisory|passive_by_overuse",
            )
            self.assertEqual(proposals[0]["frequency"], 3)
            self.assertEqual(proposals[0]["matter_ids"], ["SYN-101", "SYN-102", "SYN-103"])

    def test_known_signature_suppresses_proposal(self) -> None:
        registries = load_fixture("repeated-round-issue-registries.json")
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = os.path.join(tmp, "occurrence-ledger.jsonl")
            for registry in registries:
                append_occurrence_events(
                    ledger_path,
                    build_occurrence_events_from_issue_registry(
                        registry,
                        agent="legal-writing-agent",
                        occurred_on="2026-05-27",
                    ),
                )

            proposals = proposal_candidates_for_issue_registry(
                ledger_path,
                registries[-1],
                agent="legal-writing-agent",
                known_match_signatures={"legal-writing-agent|d4|advisory|passive_by_overuse"},
                threshold=3,
            )

            self.assertEqual(proposals, [])

    def test_matched_pattern_suppresses_new_pattern_proposal(self) -> None:
        registries = load_fixture("repeated-round-issue-registries.json")
        current = json.loads(json.dumps(registries[-1]))
        current["issues"][0]["recurring_pattern"] = "KI-001"
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = os.path.join(tmp, "occurrence-ledger.jsonl")
            for registry in registries:
                append_occurrence_events(
                    ledger_path,
                    build_occurrence_events_from_issue_registry(
                        registry,
                        agent="legal-writing-agent",
                        occurred_on="2026-05-27",
                    ),
                )

            proposals = proposal_candidates_for_issue_registry(
                ledger_path,
                current,
                agent="legal-writing-agent",
                threshold=3,
            )

            self.assertEqual(proposals, [])


if __name__ == "__main__":
    unittest.main()
