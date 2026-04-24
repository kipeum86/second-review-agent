import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
MERGER = os.path.join(
    REPO,
    ".claude",
    "skills",
    "citation-checker",
    "scripts",
    "merge-verification-audits.py",
)


class MergeVerificationAuditsTests(unittest.TestCase):
    def run_merge(self, base: dict, auditor: dict, mode: str) -> tuple[dict, dict]:
        with tempfile.TemporaryDirectory() as tempdir:
            base_path = os.path.join(tempdir, "base.json")
            auditor_path = os.path.join(tempdir, "auditor.json")
            output_path = os.path.join(tempdir, "merged.json")
            diff_path = os.path.join(tempdir, "diff.json")
            with open(base_path, "w", encoding="utf-8") as handle:
                json.dump(base, handle, ensure_ascii=False)
            with open(auditor_path, "w", encoding="utf-8") as handle:
                json.dump(auditor, handle, ensure_ascii=False)

            subprocess.run(
                [
                    sys.executable,
                    MERGER,
                    "--base",
                    base_path,
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
            )
            with open(output_path, "r", encoding="utf-8") as handle:
                merged = json.load(handle)
            with open(diff_path, "r", encoding="utf-8") as handle:
                diff = json.load(handle)
            return merged, diff

    def fixture_payloads(self) -> tuple[dict, dict]:
        base = {
            "review_depth": "deep_review",
            "citations": [
                {
                    "citation_id": "CIT-001",
                    "citation_text": "민법 제103조",
                    "citation_type": "statute",
                    "verification_status": "Unverifiable_No_Evidence",
                    "location": {"paragraph_index": 1},
                    "evidence": {"url": None, "excerpt": "원문 확인 필요", "search_query": ""},
                },
                {
                    "citation_id": "CIT-002",
                    "citation_text": "민법 제999조",
                    "citation_type": "statute",
                    "verification_status": "Verified",
                    "location": {"paragraph_index": 2},
                    "evidence": {"url": "https://law.go.kr/x", "excerpt": "확인", "search_query": ""},
                },
                {
                    "citation_id": "CIT-003",
                    "citation_text": "대법원 2023다302036",
                    "citation_type": "case",
                    "verification_status": "Unsupported_Proposition",
                    "location": {"paragraph_index": 3},
                    "evidence": {"url": "https://law.go.kr/y", "excerpt": "불일치", "search_query": ""},
                },
            ],
        }
        auditor = {
            "review_depth": "deep_review",
            "citations": [
                {
                    "citation_id": "CIT-001",
                    "citation_text": "민법 제103조",
                    "citation_type": "statute",
                    "verification_status": "Verified",
                    "verification_method": "citation_auditor:korean-law",
                    "authority_tier": 1,
                    "authority_label": "Primary Law",
                    "evidence": {"url": "https://law.go.kr/법령/민법/제103조", "excerpt": "일치", "search_query": ""},
                    "auditor": {
                        "verifier_name": "korean-law",
                        "label": "verified",
                        "reason_code": "primary_supports_claim",
                        "enforce_scope": "kr_statute_article_exists",
                        "enforceable": True,
                    },
                },
                {
                    "citation_id": "CIT-002",
                    "citation_text": "민법 제999조",
                    "citation_type": "statute",
                    "verification_status": "Wrong_Pinpoint",
                    "verification_method": "citation_auditor:korean-law",
                    "authority_tier": 1,
                    "authority_label": "Primary Law",
                    "evidence": {"url": "https://law.go.kr/법령/민법/제999조", "excerpt": "pinpoint mismatch", "search_query": ""},
                    "auditor": {
                        "verifier_name": "korean-law",
                        "label": "contradicted",
                        "reason_code": "wrong_pinpoint",
                        "enforce_scope": "kr_statute_pinpoint_exists",
                        "enforceable": True,
                    },
                },
                {
                    "citation_id": "CIT-003",
                    "citation_text": "대법원 2023다302036",
                    "citation_type": "case",
                    "verification_status": "Verified",
                    "verification_method": "citation_auditor:korean-law",
                    "authority_tier": 1,
                    "authority_label": "Primary Law",
                    "evidence": {"url": None, "excerpt": "사건번호 확인", "search_query": ""},
                    "auditor": {
                        "verifier_name": "korean-law",
                        "label": "verified",
                        "reason_code": "primary_supports_claim",
                        "enforce_scope": None,
                        "enforceable": True,
                    },
                },
            ],
        }
        return base, auditor

    def test_assist_only_adds_supplemental_evidence(self) -> None:
        base, auditor = self.fixture_payloads()
        merged, diff = self.run_merge(base, auditor, "assist")
        by_id = {item["citation_id"]: item for item in merged["citations"]}

        self.assertEqual(by_id["CIT-001"]["verification_status"], "Unverifiable_No_Evidence")
        self.assertEqual(by_id["CIT-002"]["verification_status"], "Verified")
        self.assertIn("supplemental_verifiers", by_id["CIT-001"])
        self.assertNotIn("supplemental_verifiers", by_id["CIT-002"])
        self.assertEqual(diff["by_conflict_type"]["auditor_verified_base_unverifiable"], 1)

    def test_enforce_limited_applies_only_allowed_deterministic_changes(self) -> None:
        base, auditor = self.fixture_payloads()
        merged, _ = self.run_merge(base, auditor, "enforce_limited")
        by_id = {item["citation_id"]: item for item in merged["citations"]}

        self.assertEqual(by_id["CIT-001"]["verification_status"], "Verified")
        self.assertEqual(by_id["CIT-002"]["verification_status"], "Wrong_Pinpoint")
        self.assertEqual(by_id["CIT-003"]["verification_status"], "Unsupported_Proposition")
        self.assertGreaterEqual(merged["summary"]["issue"], 2)


if __name__ == "__main__":
    unittest.main()
