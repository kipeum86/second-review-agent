Review the document(s) in the input folder.

Execute WF1 — Single Document Review Pipeline (8 steps):

1. Scan `input/` folder for DOCX files to review
2. If $ARGUMENTS provided, use as review context (document purpose, audience, concerns)
3. If no arguments and no prior context, ask ≤3 targeted questions per Context Resolution Protocol
4. Execute Steps 1–8 of the review pipeline:
   - Step 1: Document Intake & Context Resolution
   - Step 2: Document Parsing & Structure Analysis (document-parser skill)
   - Step 3: Citation Extraction & Verification (citation-verifier sub-agent)
   - Step 4: Multi-Dimension Substantive Review (substance-reviewer, writing-quality-reviewer, structure-checker)
   - Step 5: Formatting & Presentation Review (formatting-reviewer)
   - Step 6: Issue Consolidation & Scoring (scoring-engine, known-issues-manager)
   - Step 7: Redline & Output Generation (redline-generator, cover-memo-writer)
   - Step 8: Self-Verification & Delivery (quality-gate)
5. Save all artifacts to `output/{matter_id}/round_{N}/`
6. Present summary with release recommendation to user
