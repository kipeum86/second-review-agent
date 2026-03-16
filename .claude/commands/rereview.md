Re-review a revised document after a prior review round.

Execute WF3 — Re-review Pipeline (4 steps):

1. Identify the revised document and the prior review round:
   - $ARGUMENTS should specify matter_id or prior round reference
   - If not specified, check `output/` for the most recent review of the same document
2. Execute Steps RR-1 through RR-4:
   - RR-1: Load Prior Review State (read issue-registry.json and verification-audit.json from prior round)
   - RR-2: Delta Identification:
     1. Parse both original and revised documents using document-parser skill
     2. For each prior finding in the previous round's issue-registry.json:
        a. Extract text excerpt from the finding's location in the original document
        b. Search for that text in the revised document (fuzzy match, ≥80% similarity threshold)
        c. If found → map finding to new paragraph index (status: `mapped`)
        d. If not found → the relevant text was changed (status: `changed` — mark as potentially addressed)
     3. Identify new/substantially changed paragraphs in revised document not mapped from original → flag for fresh review
     4. Output: `working/rereview-diff.json` with `{prior_finding_id, original_para, revised_para, mapping_status: "mapped"|"changed"|"removed"}`
   - RR-3: Focused Re-review:
     - Check each prior Critical/Major finding: ✓ Resolved / ◐ Partially / ✗ Unresolved
     - Verify new content introduced by revisions (new citations, new arguments)
     - Do NOT re-review unchanged sections (unless cascading effects detected)
   - RR-4: Delta Report Generation:
     - Status per prior finding
     - New findings from revised content
     - Updated scorecard
3. Save to `output/{matter_id}/round_{N+1}/`
4. Present delta summary showing what was fixed and what remains
