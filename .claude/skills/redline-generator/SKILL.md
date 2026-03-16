# redline-generator Skill

Apply margin comments and tracked changes to DOCX for review output generation. Phase 1 (current): comment-only redline using `scripts/add-docx-comments.py`. Phase 2 (future): tracked changes with `<w:del>`/`<w:ins>`.

## Capabilities

0. **Comment-Only Redline** (Phase 1 — `scripts/add-docx-comments.py`)
   - Copy original DOCX (**never modify the original**)
   - Insert margin comments for ALL findings from issue-registry.json
   - Each comment: severity prefix + description + recommendation
   - Paragraph mapping: paragraph_index → regex parse → text search fallback → unmapped collection
   - Usage: `python3 add-docx-comments.py <input_docx> <issue_registry_json> <output_docx>`
   - Output: annotated DOCX with comments attached to relevant paragraphs
   - Unmapped issues collected in a final comment at document end
   - Stdlib only (zipfile + xml.etree.ElementTree) — no python-docx dependency

1. **Redline DOCX with Tracked Changes** (Phase 2 — future)
   - Copy original DOCX (**never modify the original**)
   - Unzip copy → parse `word/document.xml`
   - For each finding in issue-registry.json:
     - Locate target paragraph by text matching (fuzzy fallback)
     - Insert tracked changes (`<w:del>` + `<w:ins>`) for Critical/Major textual corrections
     - Add margin comments for ALL findings (severity-coded prefix)
   - Repack as redline DOCX

2. **Clean DOCX Generation**
   - Start from the redline DOCX
   - Accept only Critical/Major textual corrections (Suggestions remain comment-only)
   - Remove all tracked change markup, leaving corrected text
   - Remove all comments
   - Result: clean document with only substantive fixes applied

3. **Comment Formatting**
   - All comments follow the format guide in `references/comment-format-guide.md`
   - Severity prefix: `[CRITICAL]`, `[MAJOR]`, `[MINOR]`, `[SUGGESTION]`
   - Citation comments: use Verification Status prefix (e.g., `[CRITICAL — NONEXISTENT]`)
   - Author: "10년차 파트너 변호사 반성문" (Korean docs) / "10-Year Partner's Reflection" (English docs)

## DOCX Processing Workflow

```
Original DOCX (in input/)
    │
    ├── Copy to working/ (PRESERVE ORIGINAL)
    │
    ├── Phase 1: Comment-Only Redline (CURRENT)
    │   ├── Run add-docx-comments.py <input> <issue-registry> <output>
    │   ├── Maps issues to paragraphs (index → regex → keyword search)
    │   ├── Inserts <w:comment> + range markers for each issue
    │   ├── Creates/updates comments.xml, rels, content types
    │   └── Output: {doc}_redline_v{N}.docx (with margin comments)
    │
    ├── Phase 2: Tracked Changes (FUTURE)
    │   ├── Insert <w:del>/<w:ins> for textual corrections
    │   └── Requires: run splitting, format preservation
    │
    └── Clean DOCX: accept Critical/Major corrections → {doc}_clean_v{N}.docx
```

## OOXML Tracked Changes Format

Reference patterns from `contract-review-agent/.claude/skills/docx-redliner/scripts/`:

### Deletion (`<w:del>`)
```xml
<w:del w:id="1" w:author="10년차 파트너 변호사 반성문" w:date="2026-03-13T00:00:00Z">
  <w:r w:rsidDel="00000001">
    <w:rPr><!-- preserve original formatting --></w:rPr>
    <w:delText>deleted text</w:delText>
  </w:r>
</w:del>
```

### Insertion (`<w:ins>`)
```xml
<w:ins w:id="2" w:author="10년차 파트너 변호사 반성문" w:date="2026-03-13T00:00:00Z">
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
<w:comment w:id="3" w:author="10년차 파트너 변호사 반성문" w:date="2026-03-13T00:00:00Z">
  <w:p>
    <w:r><w:t>[CRITICAL] Description. Recommendation.</w:t></w:r>
  </w:p>
</w:comment>
```

## When to Use

- WF1 Step 7: Redline & Output Generation
- Input: issue-registry.json, original DOCX, verification-audit.json
- Output: redline DOCX, clean DOCX (saved to `deliverables/`)

## Safety Rules

1. **NEVER modify the original DOCX** — always work on a copy
2. **Preserve original formatting** — copy `<w:rPr>` from existing runs
3. If DOCX XML manipulation fails → attempt auto-repair
4. If repair fails → produce **Markdown fallback** + error report
5. Clean DOCX must have **no remaining tracked changes or comments**

## Paragraph Mapping Strategy

For each issue in issue-registry.json, apply these strategies in order:

1. **Primary**: `location.paragraph_index` as integer → count `<w:p>` elements in `<w:body>`
2. **Fallback 1**: Parse paragraph number from location string fields (regex: `para(?:graph)?\s*(\d+)`)
3. **Fallback 2**: Keyword search — extract keywords from issue description, find paragraph with highest keyword overlap in `<w:t>` text content
4. **Fallback 3**: Unmapped — collect all unmapped issues in a single comment attached to the last paragraph

Target: ≥90% mapping success rate. Script outputs JSON summary with mapping statistics.

## Checkpoint

This skill runs as part of Step 7 alongside `cover-memo-writer`. The main agent updates `checkpoint.json` after ALL Step 7 outputs are generated:
- `step_7.status` → `"completed"`
- `step_7.output` → comma-separated paths of redline DOCX, clean DOCX, and cover memo
- `last_completed_step` → `7`
