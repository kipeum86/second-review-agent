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
3. If a single-document review (WF1) is also running for the same matter:
   - **Do NOT run WF2 CD-3 and WF1 Step 6 simultaneously** — both write to issue-registry.json
   - Sequencing: WF2 CD-3 must complete first → WF1 Step 6 then reads and merges Dim 7 findings during consolidation
   - Tag all WF2 findings as Dimension 7 before WF1 Step 6 merges them
4. Save cross-document report to `output/{matter_id}/round_{N}/deliverables/`
