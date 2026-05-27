import json
import os
import sys
import tempfile
import unittest

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from known_issue_index import (  # type: ignore  # noqa: E402
    build_index_for_registry_path,
    build_known_issue_index,
    candidate_pattern_ids_from_index,
    load_index_if_current,
    select_candidate_pattern_ids,
)
from known_issue_normalizer import normalize_finding  # type: ignore  # noqa: E402


def load_fixture(name: str):
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


class KnownIssueIndexTests(unittest.TestCase):
    def test_exact_signature_lookup_returns_one_candidate(self) -> None:
        entries = load_fixture("multi-pattern-registry.json")
        index = build_known_issue_index(entries, agent="legal-writing-agent")
        finding = {
            "dimension": 4,
            "document_type": "advisory",
            "defect_type": "passive_by_overuse",
            "description": "Passive construction overuse appears throughout the advice.",
        }
        metadata = normalize_finding(finding, agent="legal-writing-agent")

        pattern_ids, source = candidate_pattern_ids_from_index(index, metadata)

        self.assertEqual(pattern_ids, ["KI-001"])
        self.assertEqual(source, "signature")

    def test_index_reduces_candidate_count_for_multi_pattern_registry(self) -> None:
        entries = load_fixture("multi-pattern-registry.json")
        index = build_known_issue_index(entries, agent="legal-writing-agent")
        result = select_candidate_pattern_ids(
            entries,
            {
                "dimension": 4,
                "document_type": "advisory",
                "defect_type": "passive_by_overuse",
                "description": "Passive construction overuse appears throughout the advice.",
            },
            agent="legal-writing-agent",
            index=index,
        )

        self.assertEqual(result["candidate_pattern_ids"], ["KI-001"])
        self.assertLess(result["candidate_count"], len(entries))
        self.assertFalse(result["fallback_used"])

    def test_missing_index_falls_back_to_legacy_dimension_scan(self) -> None:
        entries = load_fixture("multi-pattern-registry.json")
        result = select_candidate_pattern_ids(
            entries,
            {
                "dimension": 4,
                "document_type": "advisory",
                "defect_type": "unseen_defect",
                "description": "Unseen defect still needs legacy candidates.",
            },
            agent="legal-writing-agent",
            index=None,
        )

        self.assertEqual(result["source"], "legacy_dimension_scan")
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["candidate_pattern_ids"], ["KI-001", "KI-002", "KI-003"])

    def test_index_file_stale_detection_uses_registry_hash(self) -> None:
        entries = load_fixture("v2-registry.json")
        with tempfile.TemporaryDirectory() as tmp:
            registry_path = os.path.join(tmp, "legal-writing-agent.json")
            index_path = os.path.join(tmp, "legal-writing-agent.index.json")
            with open(registry_path, "w", encoding="utf-8") as handle:
                json.dump(entries, handle, ensure_ascii=False)

            build_index_for_registry_path(registry_path, index_path=index_path)
            self.assertIsNotNone(load_index_if_current(registry_path, index_path=index_path))

            entries[0]["frequency"] = 99
            with open(registry_path, "w", encoding="utf-8") as handle:
                json.dump(entries, handle, ensure_ascii=False)

            self.assertIsNone(load_index_if_current(registry_path, index_path=index_path))


if __name__ == "__main__":
    unittest.main()
