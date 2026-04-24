import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
RESOLVER = os.path.join(
    REPO,
    ".claude",
    "skills",
    "citation-checker",
    "scripts",
    "resolve-citation-auditor-mode.py",
)


def write_manifest(path: str, manifest: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False)


class ResolveCitationAuditorModeTests(unittest.TestCase):
    def run_resolver(self, manifest: dict, *extra_args: str, env: dict | None = None) -> tuple[dict, int]:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest_path = os.path.join(tempdir, "review-manifest.json")
            write_manifest(manifest_path, manifest)
            run_env = env or os.environ.copy()
            if env is None:
                run_env.pop("SECOND_REVIEW_CITATION_AUDITOR_MODE", None)
            result = subprocess.run(
                [sys.executable, RESOLVER, "--manifest", manifest_path, *extra_args],
                capture_output=True,
                text=True,
                env=run_env,
            )
            return json.loads(result.stdout), result.returncode

    def test_deep_review_defaults_to_shadow(self) -> None:
        payload, code = self.run_resolver({"review_context": {"depth": "deep_review"}})

        self.assertEqual(code, 0)
        self.assertEqual(payload["effective_mode"], "shadow")
        self.assertEqual(payload["source"], "depth_default")
        self.assertTrue(payload["optional_artifacts"])

    def test_standard_review_defaults_to_off(self) -> None:
        payload, code = self.run_resolver({"review_context": {"depth": "standard"}})

        self.assertEqual(code, 0)
        self.assertEqual(payload["effective_mode"], "off")
        self.assertEqual(payload["optional_artifacts"], [])

    def test_manifest_override_beats_deep_review_default(self) -> None:
        payload, code = self.run_resolver(
            {
                "review_context": {
                    "depth": "deep_review",
                    "citation_auditor_mode": "off",
                    "citation_auditor_reason": "User requested fastest review.",
                }
            }
        )

        self.assertEqual(code, 0)
        self.assertEqual(payload["effective_mode"], "off")
        self.assertEqual(payload["source"], "manifest")

    def test_standalone_only_does_not_emit_wf1_optional_artifacts(self) -> None:
        payload, code = self.run_resolver(
            {"review_context": {"depth": "deep_review", "citation_auditor_mode": "standalone_only"}}
        )

        self.assertEqual(code, 0)
        self.assertEqual(payload["effective_mode"], "standalone_only")
        self.assertEqual(payload["optional_artifacts"], [])

    def test_requested_mode_beats_manifest_and_environment(self) -> None:
        env = os.environ.copy()
        env["SECOND_REVIEW_CITATION_AUDITOR_MODE"] = "shadow"
        payload, code = self.run_resolver(
            {"review_context": {"depth": "standard", "citation_auditor_mode": "off"}},
            "--requested-mode",
            "assist",
            env=env,
        )

        self.assertEqual(code, 0)
        self.assertEqual(payload["effective_mode"], "assist")
        self.assertEqual(payload["source"], "requested")

    def test_environment_mode_applies_when_manifest_is_silent(self) -> None:
        env = os.environ.copy()
        env["SECOND_REVIEW_CITATION_AUDITOR_MODE"] = "diff"
        payload, code = self.run_resolver({"review_context": {"depth": "standard"}}, env=env)

        self.assertEqual(code, 0)
        self.assertEqual(payload["effective_mode"], "diff")
        self.assertEqual(payload["source"], "environment")

    def test_enforce_limited_requires_explicit_approval(self) -> None:
        payload, code = self.run_resolver(
            {"review_context": {"depth": "deep_review", "citation_auditor_mode": "enforce_limited"}}
        )

        self.assertEqual(code, 0)
        self.assertEqual(payload["effective_mode"], "shadow")
        self.assertEqual(payload["warnings"][0]["code"], "enforce_requires_approval")

    def test_enforce_limited_honors_manifest_approval(self) -> None:
        payload, code = self.run_resolver(
            {
                "review_context": {
                    "depth": "deep_review",
                    "citation_auditor_mode": "enforce_limited",
                    "citation_auditor_enforce_approved": True,
                }
            }
        )

        self.assertEqual(code, 0)
        self.assertEqual(payload["effective_mode"], "enforce_limited")
        self.assertEqual(payload["warnings"], [])

    def test_invalid_manifest_mode_fails_closed(self) -> None:
        payload, code = self.run_resolver({"review_context": {"citation_auditor_mode": "surprise_me"}})

        self.assertEqual(code, 2)
        self.assertFalse(payload["success"])
        self.assertIn("invalid manifest citation_auditor_mode", payload["errors"][0])


if __name__ == "__main__":
    unittest.main()
