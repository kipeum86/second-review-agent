import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
EXTRACTOR = os.path.join(
    REPO,
    ".claude",
    "skills",
    "document-parser",
    "scripts",
    "extract-citations.py",
)


class ExtractCitationsTests(unittest.TestCase):
    def run_extractor(self, parsed_structure: dict) -> tuple[dict, dict]:
        with tempfile.TemporaryDirectory() as tempdir:
            parsed_path = os.path.join(tempdir, "parsed-structure.json")
            output_path = os.path.join(tempdir, "citation-list.json")
            occurrence_path = os.path.join(tempdir, "citation-occurrences.json")
            with open(parsed_path, "w", encoding="utf-8") as handle:
                json.dump(parsed_structure, handle, ensure_ascii=False)

            subprocess.run(
                [sys.executable, EXTRACTOR, parsed_path, output_path],
                check=True,
            )

            with open(output_path, "r", encoding="utf-8") as handle:
                citation_list = json.load(handle)
            with open(occurrence_path, "r", encoding="utf-8") as handle:
                occurrences = json.load(handle)
            return citation_list, occurrences

    def test_repeated_same_citation_is_preserved_by_occurrence(self) -> None:
        parsed = {
            "source_file": "sample.docx",
            "paragraphs": [
                {
                    "index": 0,
                    "text": "첫째, 「개인정보 보호법」 제15조는 동의 없는 처리를 금지한다고 설명한다.",
                },
                {
                    "index": 1,
                    "text": "둘째, 「개인정보 보호법」 제15조는 위탁 처리의 근거라고도 주장한다.",
                },
            ],
        }

        citation_list, occurrences = self.run_extractor(parsed)
        citations = citation_list["citations"]

        self.assertEqual(citation_list["total_citations"], 2)
        self.assertEqual(occurrences["artifact_type"], "citation_occurrences")
        self.assertEqual(occurrences["total_citations"], 2)
        self.assertEqual(citations[0]["citation_text"], citations[1]["citation_text"])
        self.assertEqual(citations[0]["normalized_citation_key"], citations[1]["normalized_citation_key"])
        self.assertNotEqual(citations[0]["occurrence_id"], citations[1]["occurrence_id"])
        self.assertEqual(citations[0]["location"]["paragraph_index"], 0)
        self.assertEqual(citations[1]["location"]["paragraph_index"], 1)
        self.assertIn("char_start", citations[0]["source_location"])


if __name__ == "__main__":
    unittest.main()
