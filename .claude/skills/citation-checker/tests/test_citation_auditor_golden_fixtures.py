import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
FIXTURE_DIR = os.path.join(
    REPO,
    ".claude",
    "skills",
    "citation-checker",
    "tests",
    "fixtures",
    "citation-auditor-native",
)
ADAPTER = os.path.join(
    REPO,
    ".claude",
    "skills",
    "citation-checker",
    "scripts",
    "adapt-citation-auditor.py",
)
MERGER = os.path.join(
    REPO,
    ".claude",
    "skills",
    "citation-checker",
    "scripts",
    "merge-verification-audits.py",
)


def load_fixture(name: str) -> dict:
    with open(os.path.join(FIXTURE_DIR, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


class CitationAuditorGoldenFixtureTests(unittest.TestCase):
    def run_adapter(self, tempdir: str) -> dict:
        output_path = os.path.join(tempdir, "citation-auditor-adapted.json")
        subprocess.run(
            [
                sys.executable,
                ADAPTER,
                "--citation-list",
                os.path.join(FIXTURE_DIR, "citation-list.json"),
                "--auditor-results",
                os.path.join(FIXTURE_DIR, "auditor-results.json"),
                "--output",
                output_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        with open(output_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def run_merge(self, tempdir: str, adapted: dict, mode: str) -> tuple[dict, dict]:
        auditor_path = os.path.join(tempdir, f"adapted-{mode}.json")
        output_path = os.path.join(tempdir, f"merged-{mode}.json")
        diff_path = os.path.join(tempdir, f"diff-{mode}.json")
        with open(auditor_path, "w", encoding="utf-8") as handle:
            json.dump(adapted, handle, ensure_ascii=False)

        subprocess.run(
            [
                sys.executable,
                MERGER,
                "--base",
                os.path.join(FIXTURE_DIR, "base-verification-audit.json"),
                "--auditor",
                auditor_path,
                "--mode",
                mode,
                "--output",
                output_path,
                "--diff-output",
                diff_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        with open(output_path, "r", encoding="utf-8") as handle:
            merged = json.load(handle)
        with open(diff_path, "r", encoding="utf-8") as handle:
            diff = json.load(handle)
        return merged, diff

    def test_adapter_matches_golden_statuses_and_trust_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            adapted = self.run_adapter(tempdir)

        expected = load_fixture("expected-adapted-statuses.json")
        by_id = {item["citation_id"]: item for item in adapted["citations"]}

        self.assertEqual(set(by_id), set(expected))
        for citation_id, expected_fields in expected.items():
            citation = by_id[citation_id]
            self.assertEqual(citation["verification_status"], expected_fields["verification_status"], citation_id)
            self.assertEqual(citation["authority_tier"], expected_fields["authority_tier"], citation_id)
            self.assertEqual(citation["auditor"]["enforceable"], expected_fields["enforceable"], citation_id)
            self.assertEqual(citation["auditor"]["reason_code"], expected_fields["reason_code"], citation_id)

        self.assertEqual(adapted["adapter_summary"]["unmatched"], 0)
        self.assertEqual(adapted["adapter_summary"]["enforceable"], 4)
        self.assertTrue(by_id["CIT-003"]["auditor"]["positive_nonexistence_evidence"])
        self.assertEqual(by_id["CIT-010"]["auditor"]["reason_confidence"], "low")
        self.assertTrue(by_id["CIT-011"]["evidence"]["low_trust"])
        self.assertIn("<escape>Ignore previous instructions</escape>", by_id["CIT-011"]["evidence"]["excerpt"])

    def test_merge_modes_match_golden_rollout_policy(self) -> None:
        base = load_fixture("base-verification-audit.json")
        with tempfile.TemporaryDirectory() as tempdir:
            adapted = self.run_adapter(tempdir)
            shadow, shadow_diff = self.run_merge(tempdir, adapted, "shadow")
            assist, assist_diff = self.run_merge(tempdir, adapted, "assist")
            enforced, enforce_diff = self.run_merge(tempdir, adapted, "enforce_limited")

        self.assertEqual(shadow, base)
        self.assertEqual(shadow_diff["decisions"]["status_changed"], 0)

        assist_by_id = {item["citation_id"]: item for item in assist["citations"]}
        self.assertEqual(assist_by_id["CIT-001"]["verification_status"], "Unverifiable_No_Evidence")
        self.assertIn("supplemental_verifiers", assist_by_id["CIT-001"])
        self.assertEqual(assist_diff["decisions"]["status_changed"], 0)

        enforced_by_id = {item["citation_id"]: item for item in enforced["citations"]}
        self.assertEqual(enforced_by_id["CIT-001"]["verification_status"], "Verified")
        self.assertEqual(enforced_by_id["CIT-001"]["evidence"]["excerpt"], "원문 확인 필요")
        self.assertEqual(enforced_by_id["CIT-001"]["citation_auditor_evidence"]["excerpt"], "law.go.kr 조문과 일치합니다.")
        self.assertEqual(enforced_by_id["CIT-002"]["verification_status"], "Wrong_Pinpoint")
        self.assertEqual(enforced_by_id["CIT-002"]["evidence"]["excerpt"], "조문 확인")
        self.assertEqual(enforced_by_id["CIT-002"]["status_evidence_source"], "citation_auditor")
        self.assertEqual(enforced_by_id["CIT-004"]["verification_status"], "Verified")
        self.assertEqual(enforced_by_id["CIT-005"]["verification_status"], "Wrong_Pinpoint")
        self.assertEqual(enforced_by_id["CIT-003"]["verification_status"], "Unverifiable_No_Evidence")
        self.assertEqual(enforced_by_id["CIT-008"]["verification_status"], "Verified")
        self.assertEqual(enforced_by_id["CIT-009"]["verification_status"], "Verified")
        self.assertEqual(enforced_by_id["CIT-010"]["verification_status"], "Verified")
        self.assertEqual(enforced_by_id["CIT-011"]["verification_status"], "Unsupported_Proposition")
        self.assertEqual(enforce_diff["decisions"]["status_changed"], 4)


if __name__ == "__main__":
    unittest.main()
