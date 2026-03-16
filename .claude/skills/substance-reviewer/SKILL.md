# substance-reviewer Skill

Evaluate legal substance (Dimension 2) and client alignment (Dimension 3) of the reviewed document.

## Capabilities

1. **Legal Substance & Logic Review (Dimension 2)**
   - Systematic evaluation of the document's legal reasoning
   - Does each conclusion follow from its premises?
   - Are there logical leaps — assertions without supporting analysis?
   - Are counterarguments acknowledged where appropriate?
   - Is the legal hierarchy correctly applied?
     - Korean: 헌법 → 법률 → 시행령 → 시행규칙 → 행정규칙/고시
     - US: Constitution → Federal Statute → Regulation → Guidance
     - EU: Treaties → Regulations → Directives → Decisions
   - Are exceptions and limitations addressed?
   - Is the analysis complete relative to the stated scope?
   - Reference `logic-defect-taxonomy.md` for common defect patterns

2. **Client Alignment Review (Dimension 3)**
   - **Prerequisite**: Requires review context from `review-manifest.json`
   - If no context → skip Dimension 3 entirely with logged reason
   - Does the analysis answer the actual question posed?
   - Are practical implications addressed (not just abstract legal analysis)?
   - Is the level of detail appropriate for the audience?
   - Are irrelevant tangents present?
   - Are actionable recommendations or options provided where expected?

## When to Use

- WF1 Step 4: Multi-Dimension Substantive Review
- Input: `parsed-structure.json`, `verification-audit.json`, `review-manifest.json`
- This skill handles Dimensions 2 and 3 only. Writing quality (Dim 4) and Structure (Dim 5) are handled by separate skills.

## Output Format

For each finding:
```json
{
  "dimension": 2,
  "severity": "Major",
  "location": {"section": "III.2", "paragraph_index": 45},
  "description": "결론이 전제에서 논리적으로 도출되지 않음 — 제3조 위반이 곧 계약해제 사유라는 주장에 대한 근거가 제시되지 않았음",
  "recommendation": "제3조 위반이 계약해제 사유에 해당하는 법적 근거(민법 제544조 등)를 추가 분석할 것을 권고",
  "defect_type": "unsupported_conclusion"
}
```

## Review Approach

**Per-section systematic review**:
1. Read each section of the document
2. For Dimension 2: evaluate logical chain, identify defects from taxonomy
3. **Source Authority Cross-Check** (Dimension 2, priority sub-step — see below)
4. For Dimension 3: evaluate against stated client needs from manifest
5. Assign severity per the agent's severity classification
6. Provide specific, actionable recommendations

### Source Authority Cross-Check (Step 3 detail)

This sub-step directly consumes `verification-audit.json` — specifically `source_authority_summary.high_risk_citations` and per-citation `authority_tier` fields.

**Prerequisite**: This sub-step requires `authority_tier` fields in `verification-audit.json`. If `source_authority_summary` or per-citation `authority_tier` fields are absent (legacy format or citation-verifier did not produce them), skip the entire Source Authority Cross-Check and log: "Source Authority Cross-Check skipped — authority_tier data not available in verification-audit.json."

**What to check**:

1. **Secondary Source Reliance** (`secondary_source_reliance`): For each conclusion or key assertion in the document, verify that its supporting citations include at least one Tier 1 or Tier 2 source. If a conclusion rests solely on Tier 3–4 citations:
   - Severity: **Major** (escalate to **Critical** if the conclusion is dispositive)
   - Example comment: "이 결론의 근거가 법률신문 기사(Tier 3)뿐입니다. 1차 법원(판례/법령)을 확인하고 인용해야 합니다."

2. **Source Authority Misrepresentation** (`source_authority_misrepresentation`): Look for sections with specific factual claims or analytical conclusions that lack citations entirely but read as summaries of external content. Cross-reference against:
   - Sections with high claim density but low citation density
   - Claims using hedging language that implies external sourcing: "실무상", "통설에 의하면", "일반적으로", "it is generally understood that", "practice suggests"
   - Statistical claims, enforcement trend descriptions, or multi-jurisdictional comparisons without sources
   - Severity: **Major** (escalate to **Critical** if the uncited content is factually wrong or forms the basis of a key recommendation)
   - Example comment: "이 단락에서 '실무상 ~로 해석된다'고 기술하고 있으나, 출처가 전혀 없습니다. 2차 소스를 패러프레이즈한 것으로 의심됩니다. 1차 소스를 확인하여 인용할 것."

3. **Citation-Conclusion Mismatch**: Even when a primary source is cited, verify that the cited source actually supports the specific conclusion drawn. A Tier 1 citation next to an unsupported conclusion is worse than no citation — it creates false confidence.
   - This overlaps with existing defect #3 (Appeal to Authority Without Analysis) but focuses specifically on the authority-tier dimension
   - Severity: **Major**

**Output**: Findings from this sub-step use `defect_type` values: `secondary_source_reliance`, `source_authority_misrepresentation`, or `citation_conclusion_mismatch`.

**Key constraint**: This is review, not research. Flag gaps but do not supply new authorities. "You may want to address X" is permitted. "The answer to X is Y" is not.

## Quality Checks

- Every finding must have: location, severity, description, recommendation
- Findings must be specific (not "the analysis is weak" but "Section III.2 lacks support for the conclusion that...")
- Severity must match the classification rules (Critical = legal liability risk, Major = credibility issue, etc.)
- Dimension 3 findings must connect to specific client needs stated in the manifest

## Checkpoint

This skill runs as part of Step 4 alongside `writing-quality-reviewer` and `structure-checker`. The main agent updates `checkpoint.json` only after ALL Step 4 skills complete:
- `step_4.status` → `"completed"`
- `step_4.output` → comma-separated paths of all dim findings files produced
- `last_completed_step` → `4`
