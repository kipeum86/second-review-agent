# redline-generator Skill

Apply tracked changes and margin comments to DOCX for review output generation.

## Capabilities

1. **Redline DOCX Generation** (LLM + DOCX XML manipulation)
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
   - Author: "주홍철 파트너" (Korean docs) / "Partner H. Ju" (English docs)

## DOCX Processing Workflow

```
Original DOCX (in input/)
    │
    ├── Copy to working/ (PRESERVE ORIGINAL)
    │
    ├── Unzip copy (zipfile)
    │
    ├── Parse document.xml
    │   ├── Map issue locations to <w:p> elements (text matching)
    │   ├── Insert <w:del>/<w:ins> for textual corrections
    │   └── Insert <w:commentRangeStart/End> + comments.xml
    │
    ├── Repack → {doc}_redline_v{N}.docx
    │
    └── Accept Critical/Major changes only → {doc}_clean_v{N}.docx
```

## OOXML Tracked Changes Format

Reference patterns from `contract-review-agent/.claude/skills/docx-redliner/scripts/`:

### Deletion (`<w:del>`)
```xml
<w:del w:id="1" w:author="주홍철 파트너" w:date="2026-03-13T00:00:00Z">
  <w:r w:rsidDel="00000001">
    <w:rPr><!-- preserve original formatting --></w:rPr>
    <w:delText>deleted text</w:delText>
  </w:r>
</w:del>
```

### Insertion (`<w:ins>`)
```xml
<w:ins w:id="2" w:author="주홍철 파트너" w:date="2026-03-13T00:00:00Z">
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
<w:comment w:id="3" w:author="주홍철 파트너" w:date="2026-03-13T00:00:00Z">
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

1. For each issue in issue-registry, get the `paragraph_index` from location
2. Map to `<w:p>` elements by counting paragraphs in document.xml
3. If index mapping fails → use text matching (search for text excerpt in `<w:t>` elements)
4. If text matching fails → log unmapped issue, include in report only (no inline markup)
5. Target: ≥90% mapping coverage

## Checkpoint

This skill runs as part of Step 7 alongside `cover-memo-writer`. The main agent updates `checkpoint.json` after ALL Step 7 outputs are generated:
- `step_7.status` → `"completed"`
- `step_7.output` → comma-separated paths of redline DOCX, clean DOCX, and cover memo
- `last_completed_step` → `7`
