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

QUALITY_GATE = os.path.join(
    REPO,
    ".claude",
    "skills",
    "quality-gate",
    "scripts",
    "run-quality-gate.py",
)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)


def write_minimal_docx(path: str, *, text: str = "", comments: int = 0, insertions: int = 0, deletions: int = 0) -> None:
    ins_xml = "".join(f'<w:ins w:id="{idx}"><w:r><w:t>x</w:t></w:r></w:ins>' for idx in range(insertions))
    del_xml = "".join(f'<w:del w:id="{idx}"><w:r><w:t>x</w:t></w:r></w:del>' for idx in range(deletions))
    document_xml = (
        f'<w:document xmlns:w="{W_NS}"><w:body><w:p><w:r><w:t>{text}</w:t></w:r>'
        f"{ins_xml}{del_xml}</w:p></w:body></w:document>"
    )
    comments_xml = (
        f'<w:comments xmlns:w="{W_NS}">'
        + "".join(f'<w:comment w:id="{idx}"><w:p><w:r><w:t>comment</w:t></w:r></w:p></w:comment>' for idx in range(comments))
        + "</w:comments>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", document_xml)
        if comments:
            zf.writestr("word/comments.xml", comments_xml)


class QualityGateTests(unittest.TestCase):
    def run_gate(self, *, issue_registry: dict, redline_comments: int, mapping_report: dict | None = None) -> dict:
        with tempfile.TemporaryDirectory() as tempdir:
            working = os.path.join(tempdir, "working")
            deliverables = os.path.join(tempdir, "deliverables")
            os.makedirs(working)
            os.makedirs(deliverables)

            write_json(os.path.join(working, "issue-registry.json"), issue_registry)
            write_json(
                os.path.join(working, "review-scorecard.json"),
                {
                    "overall_average": 9.0,
                    "overall_grade": "A",
                    "release_recommendation": "Pass",
                    "dimensions": {},
                },
            )
            write_json(
                os.path.join(working, "verification-audit.json"),
                {"total_citations": 0, "citations": []},
            )
            write_json(os.path.join(working, "review-manifest.json"), {"matter_id": "M-1", "round": 1})
            if mapping_report is not None:
                write_json(os.path.join(working, "redline-mapping-report.json"), mapping_report)
            write_minimal_docx(os.path.join(deliverables, "matter_redline_v1.docx"), comments=redline_comments)
            write_minimal_docx(os.path.join(deliverables, "matter_clean_v1.docx"))
            write_minimal_docx(os.path.join(deliverables, "review-cover-memo_v1.docx"), text="Pass")

            output_path = os.path.join(working, "quality-gate-report.json")
            subprocess.run([sys.executable, QUALITY_GATE, working, deliverables, output_path], check=True)
            with open(output_path, "r", encoding="utf-8") as handle:
                return json.load(handle)

    def test_missing_critical_major_comments_is_fail(self) -> None:
        report = self.run_gate(
            issue_registry={
                "issues": [
                    {"issue_id": "ISS-1", "dimension": 1, "severity": "Critical"},
                    {"issue_id": "ISS-2", "dimension": 2, "severity": "Major"},
                ]
            },
            redline_comments=1,
        )

        self.assertEqual(report["overall_gate"], "FAIL")
        self.assertEqual(report["blocking_failures"][0]["check"], "Check 1A — Critical/Major Redline Coverage")

    def test_minor_comment_shortfall_is_warn_not_fail(self) -> None:
        report = self.run_gate(
            issue_registry={
                "issues": [
                    {"issue_id": "ISS-1", "dimension": 4, "severity": "Minor"},
                    {"issue_id": "ISS-2", "dimension": 4, "severity": "Suggestion"},
                ]
            },
            redline_comments=1,
        )

        self.assertEqual(report["overall_gate"], "WARN")
        self.assertEqual(report["blocking_failures"], [])

    def test_mapping_report_unmapped_critical_major_is_fail(self) -> None:
        report = self.run_gate(
            issue_registry={
                "issues": [
                    {"issue_id": "ISS-1", "dimension": 1, "severity": "Critical"},
                ]
            },
            redline_comments=1,
            mapping_report={
                "summary": {
                    "total_issues": 1,
                    "critical_major_unmapped": 1,
                },
                "items": [
                    {
                        "issue_id": "ISS-1",
                        "severity": "Critical",
                        "mapping_status": "unmapped",
                    }
                ],
            },
        )

        self.assertEqual(report["overall_gate"], "FAIL")
        self.assertTrue(
            any(item["check"] == "Check 6A — Redline Mapping Report" for item in report["blocking_failures"])
        )

    def test_stale_issue_registry_meta_fails_before_gate_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            working = os.path.join(tempdir, "working")
            deliverables = os.path.join(tempdir, "deliverables")
            os.makedirs(working)
            os.makedirs(deliverables)

            issue_path = os.path.join(working, "issue-registry.json")
            write_json(os.path.join(working, "review-manifest.json"), {"matter_id": "M-1", "round": 1})
            write_json(issue_path, {"issues": []})
            write_artifact_meta(issue_path, artifact_type="issue_registry")
            write_json(
                issue_path,
                {
                    "issues": [
                        {"issue_id": "ISS-1", "dimension": 1, "severity": "Critical"},
                    ]
                },
            )
            write_json(
                os.path.join(working, "review-scorecard.json"),
                {
                    "overall_average": 9.0,
                    "overall_grade": "A",
                    "release_recommendation": "Pass",
                    "dimensions": {},
                },
            )
            write_json(os.path.join(working, "verification-audit.json"), {"total_citations": 0, "citations": []})
            write_minimal_docx(os.path.join(deliverables, "matter_redline_v1.docx"), comments=1)
            write_minimal_docx(os.path.join(deliverables, "matter_clean_v1.docx"))
            write_minimal_docx(os.path.join(deliverables, "review-cover-memo_v1.docx"), text="Pass")

            output_path = os.path.join(working, "quality-gate-report.json")
            with self.assertRaises(subprocess.CalledProcessError) as ctx:
                subprocess.run(
                    [sys.executable, QUALITY_GATE, working, deliverables, output_path],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            output = (ctx.exception.stdout or "") + (ctx.exception.stderr or "")
            self.assertIn("artifact_sha256 mismatch", output)


if __name__ == "__main__":
    unittest.main()
