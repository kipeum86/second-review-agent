# scoring-engine Skill

Compute per-dimension review scores, overall grade, and independent release recommendation.

## Capabilities

1. **Per-Dimension Scoring** (LLM judgment)
   - Score each dimension 1–10 based on findings
   - Scale: 10=no issues, 7–9=minor only, 4–6=major present, 1–3=critical found
   - Reference `scoring-rubric.md` for detailed criteria

2. **Overall Grade Computation**
   - Average of all applicable dimension scores
   - A (avg ≥ 8.5), B (avg ≥ 7.0), C (avg ≥ 5.0), D (avg < 5.0)
   - **Skipped Dimension Handling**: If a dimension is skipped (e.g., Dim 3 when no client context), set `score: null, skipped: true, skip_reason: "..."` in scorecard. Exclude from average: `overall_average = sum(non-null scores) / count(non-null scores)`. Skipped dimensions are NOT treated as 0.
   - **Grade Constraint**: Grade MUST be exactly one of **A**, **B**, **C**, **D**. No plus/minus modifiers (no "C+", "B-", etc.)

3. **Release Recommendation** (independent safety gate)
   - **Release Not Recommended**: Any Dim 1–3 Critical finding; OR any `Nonexistent` citation on dispositive conclusion
   - **Manual Review Required**: Any `Unverifiable` citation on key conclusion; OR Dim 2 has ≥2 Major findings
   - **Pass with Warnings**: No Dim 1–3 Criticals, but Majors exist in any dimension; OR grade < B
   - **Pass**: No Critical or Major findings; grade ≥ B
   - **Constraint**: `release_recommendation` MUST be exactly one of these four string values. Do NOT use free-form text. Use `release_rationale` for the explanation.
   - **Evaluation order**: top-to-bottom, first match wins:
     ```
     if any Critical in Dim 1–3 OR any Nonexistent on dispositive conclusion → "Release Not Recommended"
     elif any Unverifiable on key conclusion OR Dim 2 Major count >= 2 → "Manual Review Required"
     elif no Dim 1–3 Criticals AND (any Major OR grade < B) → "Pass with Warnings"
     else → "Pass"
     ```

4. **Issue Consolidation**
   - Merge all findings from Steps 3–5 into `issue-registry.json`
   - Deduplicate (same location + same description = merge)
   - Priority sort: (1) severity descending, (2) dimension order, (3) document order
   - Tag known-issue matches via `known-issues-manager` skill

## When to Use

- WF1 Step 6: Issue Consolidation & Scoring
- Input: All findings from Steps 3–5, verification-audit.json, review-manifest.json
- Output: `issue-registry.json`, `review-scorecard.json`
- Script: `scripts/assemble-review-output.py`
- Usage: `python3 assemble-review-output.py <working_dir> [--legacy-issue-registry <path>] [--legacy-scorecard <path>]`

## Grade vs. Release Interaction

Grade measures overall quality. Release recommendation is a safety gate. They are independent:
- Grade A + "Manual Review Required" = excellent analysis but one key citation unverified → human must verify
- Grade C + "Pass with Warnings" = many minor issues but no substance problems → may release with awareness

**The release recommendation is the binding safety decision. The grade is informational.**

## Output Schemas

### issue-registry.json
```json
{
  "issues": [
    {
      "issue_id": "ISS-001",
      "dimension": 1,
      "severity": "Critical",
      "location": {"section": "III.2", "paragraph_index": 45},
      "description": "...",
      "recommendation": "...",
      "evidence": {"citation_id": "CIT-003"},
      "recurring_pattern": null
    }
  ]
}
```

### review-scorecard.json
```json
{
  "dimensions": {
    "1_citation": {"score": 6, "skipped": false, "findings_count": {"Critical": 1, "Major": 0, "Minor": 2}},
    "2_substance": {"score": 8, "skipped": false, "findings_count": {}},
    "3_alignment": {"score": null, "skipped": true, "skip_reason": "No client context provided", "findings_count": {}},
    "4_writing": {"score": 7, "skipped": false, "findings_count": {}},
    "5_structure": {"score": 9, "skipped": false, "findings_count": {}},
    "6_formatting": {"score": 8, "skipped": false, "findings_count": {}}
  },
  "overall_grade": "B",
  "overall_average": 7.6,
  "release_recommendation": "Manual Review Required",
  "release_rationale": "Dim 1에 Critical finding 1건 (CIT-003: Nonexistent citation)"
}
```

## Checkpoint

After issue consolidation, scoring, and known-issues matching complete, the main agent updates `checkpoint.json`:
- `step_6.status` → `"completed"`
- `step_6.output` → `"working/issue-registry.json,working/review-scorecard.json"`
- `last_completed_step` → `6`
