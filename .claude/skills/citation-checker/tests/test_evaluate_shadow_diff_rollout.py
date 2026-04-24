import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
EVALUATOR = os.path.join(
    REPO,
    ".claude",
    "skills",
    "citation-checker",
    "scripts",
    "evaluate-shadow-diff-rollout.py",
)


def write_review(
    path: str,
    *,
    matter_id: str,
    reviewed: bool,
    assist: bool,
    enforce: bool,
    kr: bool,
    fp_crit: int = 0,
    fp_nonexistent: int = 0,
) -> None:
    payload = {
        "matter_id": matter_id,
        "round": 1,
        "review_status": "human_reviewed" if reviewed else "pending_human_review",
        "summary": {"total_rows": 3, "review_required": 2},
        "rollout_gate_observations": {
            "human_reviewed": reviewed,
            "kr_statute_or_case_matter": kr,
            "false_positive_nonexistent_count": fp_nonexistent,
            "false_positive_critical_count": fp_crit,
            "useful_supplemental_evidence_count": 1 if assist else 0,
            "ready_for_assist": assist,
            "ready_for_enforce_limited": enforce,
            "notes": "",
        },
        "items": [],
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)


class EvaluateShadowDiffRolloutTests(unittest.TestCase):
    def run_evaluator(self, *paths: str, extra_args: list[str] | None = None, cwd: str | None = None) -> dict:
        result = subprocess.run(
            [sys.executable, EVALUATOR, *paths, *(extra_args or [])],
            check=True,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        return json.loads(result.stdout)

    def test_unreviewed_shadow_diffs_keep_shadow(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = os.path.join(tempdir, "shadow-diff-review.json")
            write_review(path, matter_id="M-1", reviewed=False, assist=False, enforce=False, kr=True)

            result = self.run_evaluator(path)

            self.assertEqual(result["recommendation"], "keep_shadow")
            self.assertFalse(result["assist_ready"])
            self.assertIn("Need 5 human-reviewed", result["assist_blockers"][0])

    def test_assist_candidate_after_reviewed_assist_ready_sample(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            paths = []
            for idx in range(5):
                path = os.path.join(tempdir, f"review-{idx}", "shadow-diff-review.json")
                os.makedirs(os.path.dirname(path))
                write_review(path, matter_id=f"M-{idx}", reviewed=True, assist=True, enforce=False, kr=idx < 2)
                paths.append(path)

            result = self.run_evaluator(*paths)

            self.assertEqual(result["recommendation"], "assist_candidate")
            self.assertTrue(result["assist_ready"])
            self.assertFalse(result["enforce_limited_ready"])
            self.assertEqual(result["summary"]["human_reviewed"], 5)

    def test_enforce_limited_candidate_requires_kr_reviews_and_zero_false_positives(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            paths = []
            for idx in range(10):
                path = os.path.join(tempdir, f"review-{idx}", "shadow-diff-review.json")
                os.makedirs(os.path.dirname(path))
                write_review(path, matter_id=f"M-{idx}", reviewed=True, assist=True, enforce=idx < 5, kr=idx < 5)
                paths.append(path)

            result = self.run_evaluator(*paths)

            self.assertEqual(result["recommendation"], "enforce_limited_candidate")
            self.assertTrue(result["assist_ready"])
            self.assertTrue(result["enforce_limited_ready"])
            self.assertEqual(result["summary"]["kr_statute_or_case_reviews"], 5)

    def test_false_positive_critical_blocks_assist_and_enforce(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            paths = []
            for idx in range(10):
                path = os.path.join(tempdir, f"review-{idx}", "shadow-diff-review.json")
                os.makedirs(os.path.dirname(path))
                write_review(
                    path,
                    matter_id=f"M-{idx}",
                    reviewed=True,
                    assist=True,
                    enforce=idx < 5,
                    kr=idx < 5,
                    fp_crit=1 if idx == 0 else 0,
                )
                paths.append(path)

            result = self.run_evaluator(*paths)

            self.assertEqual(result["recommendation"], "keep_shadow")
            self.assertFalse(result["assist_ready"])
            self.assertFalse(result["enforce_limited_ready"])
            self.assertTrue(any("False-positive Critical" in blocker for blocker in result["assist_blockers"]))

    def test_writes_rollout_report_with_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = os.path.join(tempdir, "shadow-diff-review.json")
            output = os.path.join(tempdir, "shadow-diff-rollout-report.json")
            write_review(path, matter_id="M-1", reviewed=False, assist=False, enforce=False, kr=False)

            self.run_evaluator(path, extra_args=["--output", output])

            self.assertTrue(os.path.exists(output))
            self.assertTrue(os.path.exists(os.path.join(tempdir, "shadow-diff-rollout-report.meta.json")))

    def test_output_without_directory_component(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = os.path.join(tempdir, "shadow-diff-review.json")
            write_review(path, matter_id="M-1", reviewed=False, assist=False, enforce=False, kr=False)

            self.run_evaluator(path, extra_args=["--output", "rollout-report.json"], cwd=tempdir)

            self.assertTrue(os.path.exists(os.path.join(tempdir, "rollout-report.json")))
            self.assertTrue(os.path.exists(os.path.join(tempdir, "rollout-report.meta.json")))


if __name__ == "__main__":
    unittest.main()
