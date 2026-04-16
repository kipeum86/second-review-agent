Review the document(s) in the matter-private input folder.

Execute WF1 — Single Document Review Pipeline (8 steps):

1. Scan `$SECOND_REVIEW_PRIVATE_DIR/input/` for supported review files to review (`.docx`, `.pdf`, `.pptx`, `.xlsx`, `.html`, `.md`, `.txt`)
2. If $ARGUMENTS provided, use as review context (document purpose, audience, concerns)
3. If no arguments and no prior context, ask ≤3 targeted questions per Context Resolution Protocol
4. Before Step 1, run dependency preflight:
   - Verify `python3` is available
   - Verify stdlib imports required by core scripts: `zipfile`, `xml.etree.ElementTree`, `json`, `re`
   - Verify whether `python-docx` is available; if unavailable, note that cover memo may require Markdown fallback
5. Execute Steps 1–8 of the review pipeline (before each step, validate checkpoint.json artifact existence per the Checkpoint Validation Protocol in CLAUDE.md):
   - Step 1: Document Intake & Context Resolution
   - Step 2: Document Parsing & Structure Analysis (document-parser skill)
   - Step 3: Citation Extraction & Verification (citation-verifier sub-agent)
   - Step 4: Multi-Dimension Substantive Review (substance-reviewer, writing-quality-reviewer, structure-checker)
   - Step 5: Formatting & Presentation Review (formatting-reviewer)
   - Step 6: Issue Consolidation & Scoring (scoring-engine, known-issues-manager)
   - Step 7: Redline & Output Generation (redline-generator, cover-memo-writer)
   - Step 8: Self-Verification & Delivery (quality-gate)
6. Save all artifacts to `$SECOND_REVIEW_PRIVATE_DIR/output/{matter_id}/round_{N}/`
7. Present summary with release recommendation to user
