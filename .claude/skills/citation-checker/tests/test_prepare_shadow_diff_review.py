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
ADAPTER = os.path.join(REPO, ".claude", "skills", "citation-checker", "scripts", "adapt-citation-auditor.py")
MERGER = os.path.join(REPO, ".claude", "skills", "citation-checker", "scripts", "merge-verification-audits.py")
REVIEWER = os.path.join(REPO, ".claude", "skills", "citation-checker", "scripts", "prepare-shadow-diff-review.py")


def write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)


class PrepareShadowDiffReviewTests(unittest.TestCase):
    def test_prepares_human_review_template_from_shadow_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = os.path.join(tempdir, "review-manifest.json")
            adapted_path = os.path.join(tempdir, "citation-auditor-adapted.json")
            merged_path = os.path.join(tempdir, "verification-audit.json")
            diff_path = os.path.join(tempdir, "citation-auditor-diff.json")
            review_path = os.path.join(tempdir, "shadow-diff-review.json")
            write_json(
                manifest_path,
                {
                    "matter_id": "MATTER-SHADOW-1",
                    "round": 1,
                    "review_context": {
                        "depth": "deep_review",
                        "citation_auditor_mode": "shadow",
                    },
                },
            )

            subprocess.run(
                [
                    sys.executable,
                    ADAPTER,
                    "--citation-list",
                    os.path.join(FIXTURE_DIR, "citation-list.json"),
                    "--auditor-results",
                    os.path.join(FIXTURE_DIR, "auditor-results.json"),
                    "--output",
                    adapted_path,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    MERGER,
                    "--base",
                    os.path.join(FIXTURE_DIR, "base-verification-audit.json"),
                    "--auditor",
                    adapted_path,
                    "--mode",
                    "shadow",
                    "--output",
                    merged_path,
                    "--diff-output",
                    diff_path,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            result = subprocess.run(
                [
                    sys.executable,
                    REVIEWER,
                    "--diff",
                    diff_path,
                    "--manifest",
                    manifest_path,
                    "--output",
                    review_path,
                    "--reviewer",
                    "qa-reviewer",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            cli = json.loads(result.stdout)
            with open(review_path, "r", encoding="utf-8") as handle:
                review = json.load(handle)

            self.assertTrue(cli["success"])
            self.assertEqual(review["matter_id"], "MATTER-SHADOW-1")
            self.assertEqual(review["reviewer"], "qa-reviewer")
            self.assertEqual(review["review_status"], "pending_human_review")
            self.assertEqual(review["summary"]["total_rows"], 11)
            self.assertEqual(review["summary"]["review_required"], 10)
            self.assertEqual(review["rollout_gate_observations"]["human_reviewed"], False)
            self.assertEqual(review["rollout_gate_observations"]["ready_for_enforce_limited"], False)
            self.assertTrue(os.path.exists(os.path.join(tempdir, "shadow-diff-review.meta.json")))

            by_id = {item["citation_id"]: item for item in review["items"]}
            self.assertEqual(
                by_id["CIT-001"]["recommended_action"],
                "review_possible_base_false_negative_or_assist_evidence",
            )
            self.assertEqual(
                by_id["CIT-011"]["recommended_action"],
                "review_base_finding_and_do_not_auto_downgrade",
            )
            self.assertEqual(by_id["CIT-006"]["recommended_action"], "no_action")
            self.assertFalse(by_id["CIT-006"]["requires_human_review"])
            self.assertEqual(by_id["CIT-002"]["human_review"]["result"], "pending")


if __name__ == "__main__":
    unittest.main()
