# structure-checker Skill

Evaluate structural integrity (Dimension 5) of the reviewed document.

## Capabilities

1. **Numbering Validation** (`scripts/numbering-validator.py`)
   - Checks heading/numbering hierarchy for gaps, duplicates, and violations
   - Korean: 조/항/호/목 hierarchy consistency
   - English: Section/subsection numbering continuity
   - Usage: `python3 numbering-validator.py <parsed_structure_json> <output_path>`

2. **Cross-Reference Validation** (`scripts/cross-reference-checker.py`)
   - Verifies all internal references point to existing sections
   - Flags orphaned references (target does not exist)
   - Flags unreferenced sections (informational)
   - Usage: `python3 cross-reference-checker.py <parsed_structure_json> <output_path>`

3. **LLM-Based Structural Review** (no script — LLM judgment)
   - Defined-term audit: all defined terms used, all used terms defined
   - Section completeness per document type (uses checklist from library)
   - Heading hierarchy consistency (no Heading3 under Heading1 without Heading2)
   - Cross-references `defined-terms.json` from document-parser

## When to Use

- WF1 Step 4: Multi-Dimension Substantive Review (Dimension 5 only)
- Run in parallel with substance-reviewer and writing-quality-reviewer
- Input: `parsed-structure.json`, `defined-terms.json`, document-type checklist from `library/checklists/`

## Output Format

```json
{
  "dimension": 5,
  "severity": "Minor",
  "location": {"section": "제5조", "paragraph_index": 30},
  "description": "번호 갭: 제3조에서 제5조로 건너뜀 (제4조 누락)",
  "recommendation": "제4조가 삭제된 것이라면 번호를 재정렬하거나, 의도적 누락이면 주석 추가",
  "check_type": "numbering_gap"
}
```

## Quality Checks

- Numbering issues are typically Minor (cosmetic) unless they cause ambiguity in cross-references (then Major)
- Cross-reference errors are Major if the referenced section contains substantive content
- Defined-term issues: unused terms are Minor; used-but-undefined terms are Major
- Missing mandatory sections per document type are Major

## Checkpoint

This skill runs as part of Step 4 alongside `substance-reviewer` and `writing-quality-reviewer`. The main agent updates `checkpoint.json` only after ALL Step 4 skills complete — see `substance-reviewer/SKILL.md` for details.
