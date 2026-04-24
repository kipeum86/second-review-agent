import importlib.util
import os
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
SCRIPT = os.path.join(
    REPO,
    ".claude",
    "skills",
    "cover-memo-writer",
    "scripts",
    "generate-cover-memo.py",
)

spec = importlib.util.spec_from_file_location("generate_cover_memo", SCRIPT)
generate_cover_memo = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(generate_cover_memo)


class GenerateCoverMemoTests(unittest.TestCase):
    def test_clean_korean_memo_does_not_invent_risk_language(self) -> None:
        sections = generate_cover_memo.build_sections(
            {"document": {"language": "ko", "title": "검토서"}},
            {"issues": []},
            {"release_recommendation": "Pass", "overall_grade": "A", "dimensions": {}},
            {"total_citations": 2, "citations": []},
        )

        self.assertIn("등록된 이슈는 없습니다", sections["overall_assessment"])
        self.assertNotIn("외부 공유 기준에는 아직 못 미칩니다", sections["overall_assessment"])
        self.assertNotIn("즉시 수정이 필요한 이슈", sections["overall_assessment"])
        self.assertEqual(sections["next_items"], ["현재 issue registry 기준 추가 수정 권고는 없습니다."])

    def test_critical_korean_memo_uses_hold_language(self) -> None:
        sections = generate_cover_memo.build_sections(
            {"document": {"language": "ko", "title": "검토서"}},
            {
                "issues": [
                    {
                        "severity": "Critical",
                        "description": "존재하지 않는 판례",
                        "recommendation": "판례 인용을 삭제하거나 대체하십시오.",
                    }
                ]
            },
            {"release_recommendation": "Release Not Recommended", "overall_grade": "C", "dimensions": {}},
            {"total_citations": 1, "citations": []},
        )

        self.assertIn("Critical 1건", sections["overall_assessment"])
        self.assertIn("외부 공유를 보류", sections["overall_assessment"])
        self.assertIn("판례 인용을 삭제하거나 대체하십시오.", sections["next_items"])


if __name__ == "__main__":
    unittest.main()
