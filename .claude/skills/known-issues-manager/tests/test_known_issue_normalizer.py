import json
import os
import sys
import unittest

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from known_issue_normalizer import (  # type: ignore  # noqa: E402
    cap_examples,
    keyword_overlap,
    normalize_finding,
    normalize_pattern_entry,
)


def load_fixture(name: str):
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


class KnownIssueNormalizerTests(unittest.TestCase):
    def test_legacy_entry_gets_v2_matching_metadata(self) -> None:
        legacy = load_fixture("legacy-registry.json")[0]
        normalized = normalize_pattern_entry(legacy)

        self.assertEqual(normalized["schema_version"], 2)
        self.assertEqual(normalized["dimension"], 4)
        self.assertEqual(normalized["document_type"], "advisory")
        self.assertEqual(
            normalized["match_signature"],
            "legal-writing-agent|d4|advisory|kw:passive_construction_overuse_formal",
        )
        self.assertIn("passive", normalized["keywords"])
        self.assertEqual(normalized["examples_max"], 3)

    def test_v2_entry_preserves_curated_signature(self) -> None:
        entry = load_fixture("v2-registry.json")[0]
        normalized = normalize_pattern_entry(entry)

        self.assertEqual(normalized["schema_version"], 2)
        self.assertEqual(normalized["defect_type"], "passive_by_overuse")
        self.assertEqual(
            normalized["match_signature"],
            "legal-writing-agent|d4|advisory|passive_by_overuse",
        )
        self.assertEqual(
            normalized["keywords"],
            ["passive", "construction", "overuse", "formal", "advice"],
        )

    def test_finding_signature_is_stable(self) -> None:
        registry = load_fixture("issue-registry.json")
        finding = registry["issues"][0]

        first = normalize_finding(
            finding,
            agent="legal-writing-agent",
            document_type=registry["review_depth"],
        )
        second = normalize_finding(
            dict(finding),
            agent="legal-writing-agent",
            document_type=registry["review_depth"],
        )

        self.assertEqual(first, second)
        self.assertEqual(
            first["match_signature"],
            "legal-writing-agent|d4|advisory|passive_by_overuse",
        )

    def test_keyword_overlap_supports_legacy_similarity(self) -> None:
        legacy = normalize_pattern_entry(load_fixture("legacy-registry.json")[0])
        finding = normalize_finding(
            {
                "dimension": "Dimension 4",
                "document_type": "advisory",
                "description": "Passive construction overuse appears throughout the advice.",
            },
            agent="legal-writing-agent",
        )

        self.assertGreaterEqual(
            keyword_overlap(legacy["keywords"], finding["keywords"]),
            0.5,
        )

    def test_examples_are_capped_by_default(self) -> None:
        entry = {
            "pattern_id": "KI-999",
            "examples": ["one", "two", "three", "four"],
        }

        capped, trimmed = cap_examples(entry)

        self.assertEqual(trimmed, 1)
        self.assertEqual(capped["examples"], ["one", "two", "three"])
        self.assertEqual(capped["examples_max"], 3)

    def test_examples_respect_entry_specific_cap(self) -> None:
        entry = {
            "pattern_id": "KI-999",
            "examples_max": 2,
            "examples": ["one", "two", "three"],
        }

        capped, trimmed = cap_examples(entry)

        self.assertEqual(trimmed, 1)
        self.assertEqual(capped["examples"], ["one", "two"])


if __name__ == "__main__":
    unittest.main()
