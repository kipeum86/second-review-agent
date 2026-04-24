import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
SHARED = os.path.join(REPO, ".claude", "skills", "_shared", "scripts")
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

from artifact_meta import write_artifact_meta  # noqa: E402

ASSEMBLER = os.path.join(
    REPO,
    ".claude",
    "skills",
    "scoring-engine",
    "scripts",
    "assemble-review-output.py",
)


def write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


class AssembleReviewOutputTests(unittest.TestCase):
    def run_assembler(self, working_dir: str, *extra_args: str) -> dict:
        result = subprocess.run(
            [sys.executable, ASSEMBLER, working_dir, *extra_args],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    def seed_manifest(self, working_dir: str) -> None:
        write_json(
            os.path.join(working_dir, "review-manifest.json"),
            {"matter_id": "M-1", "round": 1, "review_context": {"depth": "standard"}},
        )

    def test_collects_current_findings_once(self) -> None:
        with tempfile.TemporaryDirectory() as working:
            self.seed_manifest(working)
            write_json(
                os.path.join(working, "dim2-findings.json"),
                {
                    "findings": [
                        {
                            "severity": "Major",
                            "location": {"paragraph_index": 2},
                            "description": "Dim 2 issue",
                            "recommendation": "Fix Dim 2.",
                        }
                    ]
                },
            )
            write_json(
                os.path.join(working, "verification-audit.json"),
                {
                    "citations": [
                        {
                            "citation_id": "CIT-001",
                            "citation_text": "Fake Case",
                            "verification_status": "Nonexistent",
                            "location": {"paragraph_index": 1},
                            "notes": "Citation issue",
                        }
                    ]
                },
            )

            self.run_assembler(working)
            registry = load_json(os.path.join(working, "issue-registry.json"))

            self.assertEqual(registry["total_issues"], 2)
            descriptions = [issue["description"] for issue in registry["issues"]]
            self.assertEqual(descriptions.count("Dim 2 issue"), 1)
            self.assertEqual(descriptions.count("Citation issue"), 1)

    def test_existing_outputs_are_not_implicit_legacy_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as working:
            self.seed_manifest(working)
            write_json(
                os.path.join(working, "issue-registry.json"),
                {
                    "matter_id": "OLD",
                    "round": 99,
                    "issues": [
                        {
                            "issue_id": "OLD-1",
                            "dimension": 2,
                            "severity": "Critical",
                            "description": "STALE ISSUE",
                            "recommendation": "Do not keep.",
                        }
                    ],
                },
            )
            write_json(
                os.path.join(working, "review-scorecard.json"),
                {
                    "dimensions": {
                        "2_substance": {
                            "score": 1,
                            "summary": "STALE SCORE",
                        }
                    },
                    "overall_grade": "D",
                    "overall_average": 1,
                    "release_recommendation": "Release Not Recommended",
                },
            )
            write_json(
                os.path.join(working, "dim2-findings.json"),
                {
                    "findings": [
                        {
                            "severity": "Major",
                            "description": "Fresh issue",
                            "recommendation": "Use fresh issue.",
                        }
                    ]
                },
            )
            write_json(os.path.join(working, "verification-audit.json"), {"citations": []})

            self.run_assembler(working)
            registry = load_json(os.path.join(working, "issue-registry.json"))
            scorecard = load_json(os.path.join(working, "review-scorecard.json"))

            self.assertEqual(registry["total_issues"], 1)
            self.assertEqual(registry["issues"][0]["description"], "Fresh issue")
            self.assertNotEqual(scorecard["dimensions"]["2_substance"]["summary"], "STALE SCORE")

    def test_explicit_legacy_issue_registry_is_honored(self) -> None:
        with tempfile.TemporaryDirectory() as working:
            self.seed_manifest(working)
            legacy_path = os.path.join(working, "legacy-issue-registry.json")
            write_json(
                legacy_path,
                {
                    "matter_id": "LEGACY",
                    "round": 3,
                    "issues": [
                        {
                            "issue_id": "LEG-1",
                            "dimension": 2,
                            "severity": "Critical",
                            "description": "Legacy issue",
                            "recommendation": "Normalize legacy issue.",
                        }
                    ],
                },
            )
            write_json(
                os.path.join(working, "dim2-findings.json"),
                {
                    "findings": [
                        {
                            "severity": "Major",
                            "description": "Fresh issue should be ignored in explicit legacy mode",
                        }
                    ]
                },
            )

            self.run_assembler(working, "--legacy-issue-registry", legacy_path)
            registry = load_json(os.path.join(working, "issue-registry.json"))

            self.assertEqual(registry["total_issues"], 1)
            self.assertEqual(registry["issues"][0]["description"], "Legacy issue")

    def test_stale_verification_audit_meta_fails_before_scoring(self) -> None:
        with tempfile.TemporaryDirectory() as working:
            self.seed_manifest(working)
            audit_path = os.path.join(working, "verification-audit.json")
            write_json(
                audit_path,
                {
                    "total_citations": 1,
                    "citations": [
                        {
                            "citation_id": "CIT-001",
                            "citation_text": "Valid Case",
                            "verification_status": "Verified",
                        }
                    ],
                },
            )
            write_artifact_meta(audit_path, artifact_type="verification_audit")
            write_json(
                audit_path,
                {
                    "total_citations": 1,
                    "citations": [
                        {
                            "citation_id": "CIT-001",
                            "citation_text": "Changed Case",
                            "verification_status": "Nonexistent",
                        }
                    ],
                },
            )

            with self.assertRaises(subprocess.CalledProcessError) as ctx:
                self.run_assembler(working)
            output = (ctx.exception.stdout or "") + (ctx.exception.stderr or "")
            self.assertIn("artifact_sha256 mismatch", output)


if __name__ == "__main__":
    unittest.main()
