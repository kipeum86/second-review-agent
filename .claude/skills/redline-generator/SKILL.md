# redline-generator Skill

Apply margin comments and tracked changes to DOCX for review output generation using `scripts/add-docx-comments.py`.

## Capabilities

0. **Redline DOCX Generation** (`scripts/add-docx-comments.py`)
   - Copy original DOCX (**never modify the original**)
   - Insert margin comments for ALL findings from `issue-registry.json`
   - Insert tracked changes (`<w:del>` + `<w:ins>`) for Critical/Major findings when the recommendation exposes an explicit textual correction (arrow replacement or typo list)
   - Comment prefixes are citation-aware when `verification-audit.json` is provided
   - Paragraph mapping: paragraph_index → regex parse → keyword search → correction-text search → unmapped collection
   - Usage: `python3 add-docx-comments.py <input_docx> <issue_registry_json> <output_redline_docx> [--clean-output <output_clean_docx>] [--verification-audit <verification_audit_json>] [--fallback-markdown <fallback_md_path>] [--mapping-report <redline_mapping_report_json>]`
   - Output: annotated DOCX with comments attached to relevant paragraphs
   - Unmapped issues collected in a final comment at document end
   - Writes `redline-mapping-report.json` next to `issue-registry.json` by default, unless `--mapping-report` is provided
   - Stdlib only (zipfile + xml.etree.ElementTree) — no python-docx dependency

1. **Clean DOCX Generation**
   - Start from a copy of the original DOCX
   - Accept only Critical/Major textual corrections (Suggestions remain comment-only)
   - Apply textual replacements directly so the clean version contains no tracked change or comment markup
   - Result: clean document with only substantive fixes applied

2. **Comment Formatting**
   - All comments follow the format guide in `references/comment-format-guide.md`
   - Severity prefix: `[CRITICAL]`, `[MAJOR]`, `[MINOR]`, `[SUGGESTION]`
   - Citation comments: use Verification Status prefix (e.g., `[CRITICAL — NONEXISTENT]`)
   - Author: "시니어 리뷰 스페셜리스트" (Korean docs) / "Senior Review Specialist" (English docs)

## DOCX Processing Workflow

```
Original DOCX (in `$SECOND_REVIEW_PRIVATE_DIR/input/`)
    │
    ├── Copy to working/ (PRESERVE ORIGINAL)
    │
    ├── Redline Generation (CURRENT)
    │   ├── Run add-docx-comments.py <input> <issue-registry> <redline> --clean-output <clean> --mapping-report <report>
    │   ├── Maps issues to paragraphs (index → regex → keyword search)
    │   ├── Inserts <w:comment> + range markers for each issue
    │   ├── Inserts tracked changes for explicit textual corrections
    │   ├── Creates/updates comments.xml, rels, content types
    │   ├── Writes working/redline-mapping-report.json
    │   └── Output: {doc}_redline_v{N}.docx (with margin comments)
    │
    └── Clean DOCX: accept Critical/Major corrections → {doc}_clean_v{N}.docx
```

## OOXML Tracked Changes Format

Reference patterns from `contract-review-agent/.claude/skills/docx-redliner/scripts/`:

### Deletion (`<w:del>`)
```xml
<w:del w:id="1" w:author="시니어 리뷰 스페셜리스트" w:date="2026-03-13T00:00:00Z">
  <w:r w:rsidDel="00000001">
    <w:rPr><!-- preserve original formatting --></w:rPr>
    <w:delText>deleted text</w:delText>
  </w:r>
</w:del>
```

### Insertion (`<w:ins>`)
```xml
<w:ins w:id="2" w:author="시니어 리뷰 스페셜리스트" w:date="2026-03-13T00:00:00Z">
  <w:r>
    <w:rPr><!-- match surrounding formatting --></w:rPr>
    <w:t>inserted text</w:t>
  </w:r>
</w:ins>
```

### Comment
```xml
<!-- In document.xml: -->
<w:commentRangeStart w:id="3"/>
<w:r><w:t>commented text</w:t></w:r>
<w:commentRangeEnd w:id="3"/>
<w:r>
  <w:rPr><w:rStyle w:val="CommentReference"/></w:rPr>
  <w:commentReference w:id="3"/>
</w:r>

<!-- In comments.xml: -->
<w:comment w:id="3" w:author="시니어 리뷰 스페셜리스트" w:date="2026-03-13T00:00:00Z">
  <w:p>
    <w:r><w:t>[CRITICAL] Description. Recommendation.</w:t></w:r>
  </w:p>
</w:comment>
```

## When to Use

- WF1 Step 7: Redline & Output Generation
- Input: issue-registry.json, original DOCX, verification-audit.json
- Output: redline DOCX, clean DOCX (saved to `$SECOND_REVIEW_PRIVATE_DIR/output/{matter_id}/round_{N}/deliverables/`)

## Safety Rules

1. **NEVER modify the original DOCX** — always work on a copy
2. **Preserve original formatting** — copy `<w:rPr>` from existing runs
3. If DOCX XML manipulation fails → attempt XML sanitization + retry
4. If repair fails → produce **Markdown fallback** + error report
5. Clean DOCX must have **no remaining tracked changes or comments**

## Paragraph Mapping Strategy

For each issue in issue-registry.json, apply these strategies in order:

1. **Primary**: `location.paragraph_index` as integer → count `<w:p>` elements in `<w:body>`
2. **Fallback 1**: Parse paragraph number from location string fields (regex: `para(?:graph)?\s*(\d+)`)
3. **Fallback 2**: Keyword search — extract keywords from issue description, find paragraph with highest keyword overlap in `<w:t>` text content
4. **Fallback 3**: Unmapped — collect all unmapped issues in a single comment attached to the last paragraph

The script writes `redline-mapping-report.json` with per-issue mapping status:

- `exact`: paragraph plus character span, anchor text, or text correction match
- `paragraph`: paragraph index/reference match, but no exact anchor text
- `fallback`: keyword search match
- `unmapped`: no usable location found

Target: ≥90% Critical/Major exact mapping rate for Deep Review. Any unmapped Critical/Major issue should fail the Step 8 quality gate unless the user explicitly approves degraded delivery.

## Checkpoint

This skill runs as part of Step 7 alongside `cover-memo-writer`. The main agent updates `checkpoint.json` after ALL Step 7 outputs are generated:
- `step_7.status` → `"completed"`
- `step_7.output` → comma-separated paths of redline DOCX, clean DOCX, cover memo, and `working/redline-mapping-report.json`
- `last_completed_step` → `7`
