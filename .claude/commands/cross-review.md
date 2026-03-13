Cross-document consistency review for related documents.

Execute WF2 — Cross-Document Review Pipeline (4 steps):

1. Identify all documents for cross-review:
   - If $ARGUMENTS specifies file paths → use those
   - If multiple files in `input/` → review all as a set
   - Establish matter context (same client, same transaction)
2. Execute Steps CD-1 through CD-4:
   - CD-1: Document Set Intake (parse all documents)
   - CD-2: Cross-Document Extraction (extract parties, dates, terms, facts, conclusions per doc)
   - CD-3: Consistency Analysis (compare across documents using cross-document-checker skill)
   - CD-4: Cross-Document Report generation
3. If a single-document review (WF1) is also running, tag findings as Dimension 7 and integrate into issue-registry
4. Save cross-document report to `output/{matter_id}/round_{N}/deliverables/`
