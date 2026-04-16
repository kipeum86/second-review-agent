# quality-gate Skill

Self-verification checklist for review outputs (WF1 Step 8).

Primary script: `scripts/run-quality-gate.py`
Usage: `python3 run-quality-gate.py <working_dir> <deliverables_dir> <output_path>`

## 7-Item Self-Verification Checklist

Run each check against the generated outputs. All must pass for clean delivery.

### Check 1 — Redline Completeness
**Verify**: Redline DOCX contains tracked changes for ALL Critical and Major findings in issue-registry.json.
- Count tracked changes in redline → count must match Critical + Major findings that have textual corrections
- Missing tracked change for a Critical finding = self-check failure
- If a particular issue has no explicit textual correction, verify it is still represented by a comment in the redline DOCX
- Each comment must have the correct severity prefix per comment-format-guide.md

### Check 2 — Review Comment Integrity
**Verify**: No review comment in the redline DOCX itself contains a hallucination or unsupported assertion.
- Read each comment → verify it is factually supportable from the document content or verification-audit.json
- A comment saying "이 판례는 존재하지 않습니다" must be backed by `Nonexistent` status in audit trail
- A comment making a legal claim must be traceable to the document's own content

### Check 3 — Cover Memo Accuracy
**Verify**: Cover Memo accurately reflects the issue-registry.json.
- Release recommendation in memo matches review-scorecard.json
- Critical findings listed in memo match issue-registry Critical entries
- No finding in the memo that doesn't exist in issue-registry
- No Critical/Major finding in issue-registry that's missing from the memo

### Check 4 — Scorecard Consistency
**Verify**: Review scorecard scores are consistent with actual findings.
- Dimension with 0 findings should score 9–10
- Dimension with Critical finding should score 1–4
- Overall grade computation matches the average
- No mathematical errors in scoring
- Release recommendation is exactly one of: "Pass", "Pass with Warnings", "Manual Review Required", "Release Not Recommended"
- Grade is exactly one of: A, B, C, D (no plus/minus modifiers)
- Skipped dimensions have `score: null, skipped: true` and are excluded from the average

### Check 5 — Audit Trail Completeness
**Verify**: Verification audit trail is complete per review depth setting.
- Quick Scan: all format-validation-escalated citations verified
- Standard: all dispositive-conclusion citations verified
- Deep Review: all citations verified
- No citation in citation-list.json that's missing from verification-audit.json (at applicable depth)

### Check 6 — Clean DOCX Correctness
**Verify**: Clean DOCX incorporates ONLY Critical/Major textual corrections.
- No Suggestion-level changes accepted in clean version
- No tracked changes remaining in clean DOCX
- Original formatting preserved for non-corrected sections

### Check 7 — Release Recommendation Consistency
**Verify**: Release recommendation follows the Release Recommendation Rules exactly.
- If recommendation is "Pass" or "Pass with Warnings" → verify no Critical Dim 1–3 finding exists
- If recommendation is "Release Not Recommended" → verify at least one Critical Dim 1–3 finding or Nonexistent citation exists
- Cross-check against review-scorecard.json

## Remediation Protocol

| Round | Action |
|-------|--------|
| **Round 1** | Fix all failing items. Re-run checks. |
| **Round 2** | Patch only remaining failures. Re-run checks. |
| **After Round 2** | Deliver with `[Self-Check Warning]` flags on unresolved items. Explicitly tell user which checks could not be passed. |

## Delivery Format

On pass:
```
✅ Self-verification complete. All 7 checks passed.
Deliverables saved to: $SECOND_REVIEW_PRIVATE_DIR/output/{matter_id}/round_{N}/deliverables/
```

On partial pass:
```
⚠️ Self-verification complete with warnings.
Passed: 5/7 checks
Failed: Check 2 (comment integrity), Check 6 (clean DOCX)
[Self-Check Warning] details attached.
Deliverables saved to: $SECOND_REVIEW_PRIVATE_DIR/output/{matter_id}/round_{N}/deliverables/
```

## Checkpoint

After self-verification completes (pass or partial pass), the main agent finalizes `checkpoint.json`:
- `step_8.status` → `"completed"`
- `step_8.output` → `"deliverables/quality-gate-report.json"`
- `last_completed_step` → `8`
- This marks the pipeline as fully complete.
