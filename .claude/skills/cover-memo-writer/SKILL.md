# cover-memo-writer Skill

Generate the review cover memo in senior partner voice.

## When to Use

- WF1 Step 7: Output Generation
- Input: issue-registry.json, review-scorecard.json, verification-audit.json, review-manifest.json
- Output: `review-cover-memo_v{N}.docx`
- Script: `scripts/generate-cover-memo.py`

## 10 Mandatory Sections

The cover memo MUST contain all 10 sections in this order:

### Section 1 — Document Identification
- Document title
- Author/originating agent
- Date of document
- Matter reference (if available)
- Review date and reviewer

### Section 2 — Release Recommendation (TOP OF MEMO, PROMINENT)
- One of: **Pass** / **Pass with Warnings** / **Manual Review Required** / **Release Not Recommended**
- One-line rationale
- This is the most important section — reader should see it immediately

### Section 3 — Overall Assessment
- One paragraph summary of document quality
- Letter grade (A/B/C/D)
- Key strengths acknowledged

### Section 4 — Scorecard Summary Table
| Dimension | Score | Key Findings |
|-----------|-------|-------------|
| 1. Citation & Fact | X/10 | ... |
| 2. Legal Substance | X/10 | ... |
| ... | ... | ... |
| **Overall** | **Grade** | |

### Section 5 — Critical Findings (Must-Fix)
- Numbered list
- Each: location, description, recommendation
- Empty if no Critical findings: "Critical finding 없음"

### Section 6 — Major Findings (Should-Fix)
- Numbered list
- Each: location, description, recommendation
- Empty if no Major findings

### Section 7 — Minor Findings & Suggestions
- Brief list (not detailed — reader can refer to redline for detail)
- Count + representative examples

### Section 8 — Recurring Pattern Alerts
- List any findings tagged `[Recurring: KI-XXX]`
- Include pattern description and frequency
- Skip if no recurring patterns

### Section 9 — Style Fingerprint Comparison
- If style comparison was performed: summary of deviations
- If not performed (no profile or insufficient samples): note reason
- Skip entirely if style comparison is not applicable

### Section 10 — Recommended Next Steps
- Prioritized action list for the authoring attorney
- Focus on: what to fix first, what can wait, what to verify with human judgment

## Tone & Voice

**빨간펜으로 여백에 적는 코멘트 스타일 — 10년차 파트너 변호사 반성문**:
- 짧고 직설적이되 악의 없음
- 잘된 부분은 "○" 하나로 끝냄 — 칭찬에 인색하지만 인정할 건 함
- 문제 있는 부분은 밑줄 + 물음표 + 한 줄 코멘트
- Hallucination 발견 시 특히 신랄해짐
- AI 산출물에 대한 근본적 불신이 깔려 있으므로, 검증 가능한 사실만 코멘트에 포함

### Example (Korean)
> "○ 쟁점 정리 깔끔함. 다만 Section 5 대법원 판결번호 — 이거 실존합니까? 제가 30분째 찾고 있는데요. 확인 후 수정 바랍니다."

### Example (English)
> "Structure is clean. But 42 U.S.C. § 1983 in Section III — this is a civil rights provision, not copyright. Wrong section. Fix before sending."

## Output Format

- Generate as DOCX using `python-docx` library
- Match document language (Korean or English)
- Page size: A4 (Korean), US Letter (US English), A4 (others)
- Professional formatting: clear headings, consistent fonts
- Release recommendation at top in **bold** with visual emphasis

## DOCX Generation Approach

Use `python-docx` via `scripts/generate-cover-memo.py` to create the memo:
1. Create new Document
2. Add sections with appropriate heading styles
3. Add scorecard as a Table
4. Add findings as numbered lists
5. Save as `review-cover-memo_v{N}.docx`

Usage:
`python3 generate-cover-memo.py <review_manifest_json> <issue_registry_json> <review_scorecard_json> <verification_audit_json> <output_docx>`

If `python-docx` is not available → generate as Markdown fallback next to the requested DOCX path

## Checkpoint

This skill runs as part of Step 7 alongside `redline-generator`. The main agent updates `checkpoint.json` after ALL Step 7 outputs are generated — see `redline-generator/SKILL.md` for details.
