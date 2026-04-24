import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
SHARED = os.path.join(REPO, ".claude", "skills", "_shared", "scripts")
VALIDATOR = os.path.join(SHARED, "validate-artifact.py")
sys.path.insert(0, SHARED)

from artifact_meta import meta_path_for, validate_artifact, validate_artifacts, write_artifact_meta  # noqa: E402


class ArtifactMetaTests(unittest.TestCase):
    def test_write_and_validate_meta_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            artifact_path = os.path.join(tempdir, "verification-audit.json")
            manifest_path = os.path.join(tempdir, "review-manifest.json")
            with open(artifact_path, "w", encoding="utf-8") as handle:
                json.dump({"citations": []}, handle)
            with open(manifest_path, "w", encoding="utf-8") as handle:
                json.dump({"matter_id": "M-1", "round": 2, "source_doc_hash": "sha256:abc"}, handle)

            meta_path = write_artifact_meta(
                artifact_path,
                artifact_type="verification_audit",
                producer={"step": "step_3"},
                manifest_path=manifest_path,
            )

            self.assertEqual(meta_path, meta_path_for(artifact_path))
            self.assertEqual(validate_artifact(artifact_path, artifact_type="verification_audit", manifest_path=manifest_path), [])
            with open(meta_path, "r", encoding="utf-8") as handle:
                meta = json.load(handle)
            self.assertEqual(meta["run_id"], "M-1:round-2")
            self.assertEqual(meta["source_doc_hash"], "sha256:abc")

    def test_validator_detects_stale_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            artifact_path = os.path.join(tempdir, "issue-registry.json")
            with open(artifact_path, "w", encoding="utf-8") as handle:
                json.dump({"issues": []}, handle)
            write_artifact_meta(artifact_path, artifact_type="issue_registry")
            with open(artifact_path, "w", encoding="utf-8") as handle:
                json.dump({"issues": [{"issue_id": "ISS-1"}]}, handle)

            errors = validate_artifact(artifact_path, artifact_type="issue_registry")
            self.assertIn("artifact_sha256 mismatch", errors)

    def test_batch_validator_allows_missing_grace_but_reports_stale_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            artifact_path = os.path.join(tempdir, "issue-registry.json")
            with open(artifact_path, "w", encoding="utf-8") as handle:
                json.dump({"issues": []}, handle)
            write_artifact_meta(artifact_path, artifact_type="issue_registry")
            with open(artifact_path, "w", encoding="utf-8") as handle:
                json.dump({"issues": [{"issue_id": "ISS-1"}]}, handle)

            errors = validate_artifacts(
                [
                    (artifact_path, "issue_registry"),
                    (os.path.join(tempdir, "legacy-without-meta.json"), "issue_registry"),
                ],
                require_meta=False,
            )
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0]["path"], artifact_path)
            self.assertEqual(errors[0]["error"], "artifact_sha256 mismatch")

    def test_cli_write_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            artifact_path = os.path.join(tempdir, "quality-gate-report.json")
            with open(artifact_path, "w", encoding="utf-8") as handle:
                json.dump({"overall_gate": "PASS"}, handle)

            result = subprocess.run(
                [
                    sys.executable,
                    VALIDATOR,
                    artifact_path,
                    "--artifact-type",
                    "quality_gate_report",
                    "--write-meta",
                    "--producer-script",
                    "run-quality-gate.py",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(result.stdout)
            self.assertTrue(payload["success"])
            self.assertTrue(os.path.exists(meta_path_for(artifact_path)))


if __name__ == "__main__":
    unittest.main()
