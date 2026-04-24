import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
ADAPTER = os.path.join(
    REPO,
    ".claude",
    "skills",
    "citation-checker",
    "scripts",
    "adapt-citation-auditor.py",
)


class CitationAuditorAdapterTests(unittest.TestCase):
    def run_adapter(self, citation_list: dict, auditor_results: dict) -> dict:
        with tempfile.TemporaryDirectory() as tempdir:
            citation_path = os.path.join(tempdir, "citation-list.json")
            auditor_path = os.path.join(tempdir, "auditor.json")
            output_path = os.path.join(tempdir, "adapted.json")
            with open(citation_path, "w", encoding="utf-8") as handle:
                json.dump(citation_list, handle, ensure_ascii=False)
            with open(auditor_path, "w", encoding="utf-8") as handle:
                json.dump(auditor_results, handle, ensure_ascii=False)

            subprocess.run(
                [
                    sys.executable,
                    ADAPTER,
                    "--citation-list",
                    citation_path,
                    "--auditor-results",
                    auditor_path,
                    "--output",
                    output_path,
                ],
                check=True,
            )
            with open(output_path, "r", encoding="utf-8") as handle:
                return json.load(handle)

    def test_adapter_maps_explicit_reason_codes(self) -> None:
        citation_list = {
            "review_depth": "deep_review",
            "citations": [
                {
                    "citation_id": "CIT-001",
                    "citation_text": "민법 제103조",
                    "citation_type": "statute",
                    "jurisdiction": "KR",
                    "location": {"paragraph_index": 3},
                    "claimed_content": "민법 제103조는 반사회질서 법률행위를 무효로 한다.",
                },
                {
                    "citation_id": "CIT-002",
                    "citation_text": "민법 제999조",
                    "citation_type": "statute",
                    "jurisdiction": "KR",
                    "location": {"paragraph_index": 4},
                    "claimed_content": "민법 제999조는 손해배상을 규정한다.",
                },
                {
                    "citation_id": "CIT-003",
                    "citation_text": "시장 규모 15%",
                    "citation_type": "source",
                    "jurisdiction": "KR",
                    "location": {"paragraph_index": 5},
                    "claimed_content": "2023년 시장 규모는 15% 성장하였다.",
                },
            ],
        }
        auditor_results = {
            "citations": [
                {
                    "citation_id": "CIT-001",
                    "auditor_verdict": {
                        "label": "verified",
                        "reason_code": "primary_supports_claim",
                        "verifier_name": "korean-law",
                        "rationale": "law.go.kr 조문과 일치합니다.",
                        "supporting_urls": ["law.go.kr/법령/민법/제103조"],
                        "authority": 1.0,
                    },
                },
                {
                    "citation_id": "CIT-002",
                    "auditor_verdict": {
                        "label": "contradicted",
                        "reason_code": "wrong_pinpoint",
                        "verifier_name": "korean-law",
                        "rationale": "조문은 확인되지만 해당 조문은 주장과 다릅니다.",
                        "supporting_urls": ["law.go.kr/법령/민법/제999조"],
                        "authority": 1.0,
                    },
                },
                {
                    "citation_id": "CIT-003",
                    "auditor_verdict": {
                        "label": "verified",
                        "verifier_name": "general-web",
                        "rationale": "일반 웹 자료로만 확인되었습니다.",
                        "supporting_urls": ["https://example.com/report"],
                        "authority": 0.5,
                    },
                },
            ]
        }

        adapted = self.run_adapter(citation_list, auditor_results)
        by_id = {item["citation_id"]: item for item in adapted["citations"]}

        self.assertEqual(by_id["CIT-001"]["verification_status"], "Verified")
        self.assertEqual(by_id["CIT-001"]["authority_tier"], 1)
        self.assertTrue(by_id["CIT-001"]["auditor"]["enforceable"])
        self.assertEqual(by_id["CIT-002"]["verification_status"], "Wrong_Pinpoint")
        self.assertEqual(by_id["CIT-003"]["verification_status"], "Unverifiable_Secondary_Only")
        self.assertEqual(by_id["CIT-003"]["authority_tier"], 4)
        self.assertEqual(adapted["run_metrics"]["input_citations"], 3)
        self.assertEqual(adapted["run_metrics"]["auditor_records"], 3)
        self.assertFalse(adapted["run_metrics"]["token_estimate_available"])

    def test_bare_contradicted_without_reason_is_not_critical(self) -> None:
        citation_list = {
            "citations": [
                {
                    "citation_id": "CIT-001",
                    "citation_text": "Some Case",
                    "citation_type": "case",
                    "location": {"paragraph_index": 1},
                    "claimed_content": "Some Case supports the rule.",
                }
            ]
        }
        auditor_results = {
            "citations": [
                {
                    "citation_id": "CIT-001",
                    "auditor_verdict": {
                        "label": "contradicted",
                        "verifier_name": "general-web",
                        "rationale": "결론을 내리기 어렵습니다.",
                        "supporting_urls": [],
                    },
                }
            ]
        }

        adapted = self.run_adapter(citation_list, auditor_results)
        citation = adapted["citations"][0]
        self.assertEqual(citation["verification_status"], "Unverifiable_No_Evidence")
        self.assertFalse(citation["auditor"]["enforceable"])

    def test_nonexistent_requires_positive_evidence_not_just_url(self) -> None:
        citation_list = {
            "citations": [
                {
                    "citation_id": "CIT-001",
                    "citation_text": "대법원 2099다999999",
                    "citation_type": "case",
                    "jurisdiction": "KR",
                    "location": {"paragraph_index": 1},
                    "claimed_content": "대법원 2099다999999 판결은 이 결론을 지지한다.",
                }
            ]
        }
        auditor_results = {
            "citations": [
                {
                    "citation_id": "CIT-001",
                    "auditor_verdict": {
                        "label": "contradicted",
                        "reason_code": "nonexistent_authority",
                        "verifier_name": "korean-law",
                        "rationale": "일반 참고 URL만 있습니다.",
                        "supporting_urls": ["https://example.com/search"],
                    },
                }
            ]
        }

        adapted = self.run_adapter(citation_list, auditor_results)
        citation = adapted["citations"][0]
        self.assertEqual(citation["verification_status"], "Unverifiable_No_Evidence")
        self.assertFalse(citation["auditor"]["enforceable"])

    def test_verifier_cannot_self_assign_authority_tier(self) -> None:
        citation_list = {
            "citations": [
                {
                    "citation_id": "CIT-001",
                    "citation_text": "시장 규모 15%",
                    "citation_type": "source",
                    "location": {"paragraph_index": 1},
                    "claimed_content": "시장 규모는 15% 성장하였다.",
                }
            ]
        }
        auditor_results = {
            "citations": [
                {
                    "citation_id": "CIT-001",
                    "auditor_verdict": {
                        "label": "verified",
                        "verifier_name": "general-web",
                        "authority_tier": 1,
                        "authority_label": "Primary Law",
                        "rationale": "웹 자료입니다.",
                        "evidence": [{"url": "https://example.com/report", "excerpt": "15% growth"}],
                    },
                }
            ]
        }

        adapted = self.run_adapter(citation_list, auditor_results)
        citation = adapted["citations"][0]
        self.assertEqual(citation["authority_tier"], 4)
        self.assertEqual(citation["verification_status"], "Unverifiable_Secondary_Only")
        self.assertEqual(citation["evidence"]["excerpt"], "15% growth")
        self.assertEqual(citation["evidence"]["auditor_rationale"], "웹 자료입니다.")


if __name__ == "__main__":
    unittest.main()
