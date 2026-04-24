import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET

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
ASSEMBLER = os.path.join(
    REPO,
    ".claude",
    "skills",
    "scoring-engine",
    "scripts",
    "assemble-review-output.py",
)
REDLINE = os.path.join(
    REPO,
    ".claude",
    "skills",
    "redline-generator",
    "scripts",
    "add-docx-comments.py",
)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)


def write_docx(path: str) -> None:
    paragraphs = [
        "Intro paragraph.",
        "민법 제103조는 반사회질서 법률행위를 무효로 한다.",
        "민법 제999조 제1항은 손해배상 기준을 정한다.",
        "대법원 2099다999999 판결은 이 결론을 지지한다.",
        "15 U.S.C. § 78j(b)는 증권 사기를 금지한다.",
        "GDPR Article 99 sets data processing consent requirements.",
        "The 2023 market grew by 15%.",
        "The paywalled article supports the factual claim.",
        "California Civil Code § 1636 states the rule under New York law.",
        "민법 제390조의 영문 번역은 punitive damages를 인정한다고 한다.",
        "민법 제750조 제1항은 불법행위 책임을 정한다.",
        "A vendor blog proves the legal conclusion.",
    ]
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    document_xml = f'<w:document xmlns:w="{W_NS}"><w:body>{body}</w:body></w:document>'
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", document_xml)


def read_comment_texts(path: str) -> list[str]:
    with zipfile.ZipFile(path, "r") as zf:
        root = ET.fromstring(zf.read("word/comments.xml"))
    texts = []
    for comment in root.findall(f".//{{{W_NS}}}comment"):
        parts = [node.text or "" for node in comment.findall(f".//{{{W_NS}}}t")]
        texts.append("".join(parts))
    return texts


class RedlineDocxE2ETests(unittest.TestCase):
    def test_golden_citation_auditor_results_reach_docx_redline(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            working = os.path.join(tempdir, "working")
            deliverables = os.path.join(tempdir, "deliverables")
            os.makedirs(working)
            os.makedirs(deliverables)
            input_docx = os.path.join(tempdir, "input.docx")
            write_docx(input_docx)
            write_json(
                os.path.join(working, "review-manifest.json"),
                {
                    "matter_id": "GOLDEN-REDLINE",
                    "round": 1,
                    "review_context": {
                        "depth": "deep_review",
                        "citation_auditor_mode": "enforce_limited",
                    },
                    "document": {"language": "ko"},
                },
            )

            adapted_path = os.path.join(working, "citation-auditor-adapted.json")
            verification_path = os.path.join(working, "verification-audit.json")
            diff_path = os.path.join(working, "citation-auditor-diff.json")
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
                    "enforce_limited",
                    "--output",
                    verification_path,
                    "--diff-output",
                    diff_path,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run([sys.executable, ASSEMBLER, working], check=True, capture_output=True, text=True)

            issue_registry_path = os.path.join(working, "issue-registry.json")
            redline_path = os.path.join(deliverables, "matter_redline_v1.docx")
            mapping_path = os.path.join(working, "redline-mapping-report.json")
            result = subprocess.run(
                [
                    sys.executable,
                    REDLINE,
                    input_docx,
                    issue_registry_path,
                    redline_path,
                    "--verification-audit",
                    verification_path,
                    "--mapping-report",
                    mapping_path,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            summary = json.loads(result.stdout)

            with open(issue_registry_path, "r", encoding="utf-8") as handle:
                issue_registry = json.load(handle)
            with open(mapping_path, "r", encoding="utf-8") as handle:
                mapping_report = json.load(handle)
            comments = "\n".join(read_comment_texts(redline_path))

            self.assertEqual(summary["total_issues"], issue_registry["total_issues"])
            self.assertEqual(summary["unmapped"], 0)
            self.assertEqual(mapping_report["summary"]["critical_major_unmapped"], 0)
            self.assertGreaterEqual(mapping_report["summary"]["critical_major_total"], 4)
            self.assertIn("[CRITICAL — WRONG PINPOINT]", comments)
            self.assertIn("[CRITICAL — UNSUPPORTED]", comments)
            self.assertIn("[MAJOR — UNVERIFIED]", comments)
            self.assertIn("[MINOR — SECONDARY ONLY]", comments)


if __name__ == "__main__":
    unittest.main()
