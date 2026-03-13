# formatting-reviewer Skill

Evaluate formatting and presentation quality (Dimension 6) via DOCX XML inspection and LLM judgment.

## Capabilities

1. **DOCX Format Inspection** (`scripts/docx-format-inspector.py`)
   - Unzips DOCX, inspects `word/document.xml` and `word/styles.xml`
   - Checks: font family/size consistency, heading style consistency, table width/alignment, margin uniformity, page break logic, numbering format
   - Reports findings with specific XML element locations
   - Usage: `python3 docx-format-inspector.py <docx_path> <output_path>`

2. **LLM-Based Presentation Review** (no script)
   - Professional appearance assessment
   - Layout balance and readability evaluation
   - Visual hierarchy effectiveness
   - White space usage and page flow

## When to Use

- WF1 Step 5: Formatting & Presentation Review
- Input: Original DOCX file (not the parsed text — needs access to XML formatting)
- Run after Step 4 (substantive review) and before Step 6 (consolidation)

## Checks Performed

| Check | Script | LLM |
|-------|--------|-----|
| Font family consistency | ✓ | |
| Font size consistency | ✓ | |
| Heading style consistency | ✓ | |
| Table width/alignment | ✓ | |
| Margin uniformity | ✓ | |
| Page break placement | ✓ | ✓ |
| Numbering format | ✓ | |
| Professional appearance | | ✓ |
| Layout balance | | ✓ |
| Readability | | ✓ |

## Failure Handling

- If DOCX XML is too complex to parse → log limitation, assess from rendered text only
- Script failures are non-blocking for LLM-based assessment
- Formatting findings are typically Minor or Suggestion severity

## Checkpoint

After formatting review completes, the main agent updates `checkpoint.json`:
- `step_5.status` → `"completed"`
- `step_5.output` → `"working/dim6-findings.json"`
- `last_completed_step` → `5`
