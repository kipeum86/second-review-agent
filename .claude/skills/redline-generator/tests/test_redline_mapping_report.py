import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
SHARED = os.path.join(REPO, ".claude", "skills", "_shared", "scripts")
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

from artifact_meta import write_artifact_meta  # noqa: E402

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


def write_minimal_docx(path: str) -> None:
    paragraphs = [
        "민법 제103조는 반사회질서 법률행위를 무효로 한다.",
        "이 문단에는 위치만 있는 이슈가 붙는다.",
        "시장 규모는 전년 대비 증가하였다.",
    ]
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    document_xml = f'<w:document xmlns:w="{W_NS}"><w:body>{body}</w:body></w:document>'
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", document_xml)


class RedlineMappingReportTests(unittest.TestCase):
    def test_mapping_report_classifies_exact_paragraph_fallback_and_unmapped(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            input_docx = os.path.join(tempdir, "input.docx")
            issue_path = os.path.join(tempdir, "issue-registry.json")
            output_docx = os.path.join(tempdir, "redline.docx")
            report_path = os.path.join(tempdir, "redline-mapping-report.json")
            write_minimal_docx(input_docx)
            write_json(
                issue_path,
                {
                    "issues": [
                        {
                            "issue_id": "ISS-1",
                            "severity": "Critical",
                            "location": {"paragraph_index": 0, "anchor_text": "민법 제103조"},
                            "description": "인용 검증 필요",
                            "recommendation": "원문을 확인하십시오.",
                        },
                        {
                            "issue_id": "ISS-2",
                            "severity": "Major",
                            "location": {"paragraph_index": 1},
                            "description": "위치 기반 이슈",
                            "recommendation": "문단을 정리하십시오.",
                        },
                        {
                            "issue_id": "ISS-3",
                            "severity": "Minor",
                            "description": "시장 규모 전년 대비 표현이 모호합니다.",
                            "recommendation": "표현을 구체화하십시오.",
                        },
                        {
                            "issue_id": "ISS-4",
                            "severity": "Critical",
                            "description": "문서에 없는 주제입니다.",
                            "recommendation": "확인하십시오.",
                        },
                    ]
                },
            )

            subprocess.run(
                [
                    sys.executable,
                    REDLINE,
                    input_docx,
                    issue_path,
                    output_docx,
                    "--mapping-report",
                    report_path,
                ],
                check=True,
            )

            with open(report_path, "r", encoding="utf-8") as handle:
                report = json.load(handle)
            by_id = {item["issue_id"]: item for item in report["items"]}

            self.assertEqual(by_id["ISS-1"]["mapping_status"], "exact")
            self.assertEqual(by_id["ISS-2"]["mapping_status"], "paragraph")
            self.assertEqual(by_id["ISS-3"]["mapping_status"], "fallback")
            self.assertEqual(by_id["ISS-4"]["mapping_status"], "unmapped")
            self.assertEqual(report["summary"]["critical_major_unmapped"], 1)

    def test_stale_issue_registry_meta_fails_before_redline(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            input_docx = os.path.join(tempdir, "input.docx")
            issue_path = os.path.join(tempdir, "issue-registry.json")
            output_docx = os.path.join(tempdir, "redline.docx")
            write_minimal_docx(input_docx)
            write_json(os.path.join(tempdir, "review-manifest.json"), {"matter_id": "M-1", "round": 1})
            write_json(issue_path, {"issues": []})
            write_artifact_meta(issue_path, artifact_type="issue_registry")
            write_json(
                issue_path,
                {
                    "issues": [
                        {
                            "issue_id": "ISS-1",
                            "severity": "Critical",
                            "location": {"paragraph_index": 0},
                            "description": "변경된 이슈",
                        }
                    ]
                },
            )

            with self.assertRaises(subprocess.CalledProcessError) as ctx:
                subprocess.run(
                    [sys.executable, REDLINE, input_docx, issue_path, output_docx],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            output = (ctx.exception.stdout or "") + (ctx.exception.stderr or "")
            self.assertIn("artifact_sha256 mismatch", output)


if __name__ == "__main__":
    unittest.main()
