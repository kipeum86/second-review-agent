# Review Dimensions Reference

Seven independent quality axes evaluated during review. Dimensions 1–6 are per-document; Dimension 7 activates only for multi-document reviews (WF2).

---

## Dimension 1 — Citation & Fact Verification

**What it catches**: Hallucinated statutes/cases, wrong article numbers, stale effective dates, non-existent agencies, fabricated penalty amounts.

### Checklist
- [ ] Every cited statute exists and the article/section number is correct
- [ ] Every cited case exists and the case number format is valid
- [ ] Effective dates match current law (not repealed/superseded)
- [ ] Cited content actually supports the proposition claimed
- [ ] Translated citations match the original-language source
- [ ] Agency names and regulatory body designations are correct
- [ ] Penalty amounts and thresholds match the cited source
- [ ] No jurisdiction misattribution (e.g., citing a 시행령 as a 법률)

### Verification Status Taxonomy

| Primary | Sub-Status | Definition |
|---------|-----------|------------|
| **Verified** | Verified | Authority exists, pinpoint correct, content supports proposition |
| **Issue** | Nonexistent | Positive evidence of non-existence (DB searched, no match, format invalid) |
| | Wrong_Pinpoint | Authority exists but article/section number is incorrect |
| | Unsupported_Proposition | Authority exists, pinpoint correct, but content does not support claim |
| | Wrong_Jurisdiction | Authority exists but belongs to different jurisdiction |
| | Stale | Authority amended, superseded, or repealed since claimed date |
| | Translation_Mismatch | Translated text materially diverges from original source |
| **Unverifiable** | No_Access | Primary source exists but inaccessible (paywall, network error) |
| | Secondary_Only | Only secondary sources confirm; primary not accessed |
| | No_Evidence | Neither confirming nor disconfirming evidence found |

**Critical rule**: `Nonexistent` requires positive evidence. Default to `Unverifiable_No_Evidence` when inconclusive.

---

## Dimension 2 — Legal Substance & Logic

**What it catches**: Logical leaps, unsupported conclusions, missing counterarguments, incorrect legal hierarchy application, incomplete issue coverage.

### Checklist
- [ ] Each conclusion follows from its premises
- [ ] No logical leaps — assertions without supporting analysis
- [ ] Counterarguments acknowledged where appropriate
- [ ] Legal hierarchy correctly applied (헌법 → 법률 → 시행령 → 시행규칙 → 행정규칙 / Constitution → Statute → Regulation → Guidance)
- [ ] Exceptions and limitations addressed
- [ ] Analysis complete relative to stated scope
- [ ] No circular reasoning
- [ ] Key assumptions are identified and stated

---

## Dimension 3 — Client Alignment

**What it catches**: Analysis that misses the actual question, missing practical implications, irrelevant tangents.

**Prerequisite**: Requires review context (document purpose, audience, specific concerns). If no context provided → skip with logged reason.

### Checklist
- [ ] Analysis answers the actual question posed
- [ ] Practical implications addressed (not just abstract legal analysis)
- [ ] Level of detail appropriate for the audience
- [ ] Irrelevant tangents absent
- [ ] Actionable recommendations or options provided where expected
- [ ] Business context considered alongside legal analysis

---

## Dimension 4 — Writing Quality

**What it catches**: 번역투, register violations, inconsistent terminology, ambiguous pronoun references, unnecessary verbosity.

### Korean-Specific Checks
- [ ] No 번역투 (영어 구문 직역, 불필요한 수동태, "~에 의해" 남용, "~함에 있어서")
- [ ] No 구어체 intrusion in formal documents
- [ ] 문어체 일관성 maintained
- [ ] Legal terminology precision (정확한 법률 용어 사용)
- [ ] 띄어쓰기 correct

### English-Specific Checks
- [ ] Register appropriate for document type
- [ ] Plain language balance (avoid archaic legalese unless necessary)
- [ ] Bluebook/OSCOLA citation form (if applicable)
- [ ] Gender-neutral language

### Universal Checks
- [ ] Terminological consistency (same concept = same term throughout)
- [ ] No ambiguous pronoun references
- [ ] No unnecessary verbosity
- [ ] Sentence clarity

### Style Fingerprint
- Compared against user's writing samples if available (minimum 5 samples)
- Metrics: avg sentence length, passive voice ratio, formality markers, paragraph length
- Deviations flagged at **Minor or Suggestion severity only**

---

## Dimension 5 — Structural Integrity

**What it catches**: Broken cross-references, numbering gaps, missing sections, defined-term inconsistency.

### Checklist
- [ ] All internal cross-references point to existing sections
- [ ] Numbering continuity (no gaps, no duplicates, correct hierarchy)
- [ ] All defined terms are used; all used terms are defined
- [ ] Mandatory sections present per document type
- [ ] Heading hierarchy consistent (no Heading3 under Heading1 without Heading2)
- [ ] 조/항/호/목 hierarchy correct (Korean documents)

---

## Dimension 6 — Formatting & Presentation

**What it catches**: Font inconsistency, table rendering issues, margin irregularities, unprofessional appearance.

### Checklist
- [ ] Font family/size consistent across body text
- [ ] Heading styles consistent (font, size, bold/italic)
- [ ] Table width/alignment uniform
- [ ] Margin uniformity across sections
- [ ] Page break placement logical (no orphan headings)
- [ ] Header/footer consistent
- [ ] Whitespace balance (no excessive gaps)
- [ ] Overall professional appearance

---

## Dimension 7 — Cross-Document Consistency

**Activates only for WF2 (Cross-Document Review)**.

**What it catches**: Contradictory facts across documents, terminology drift, inconsistent party designations, date conflicts.

### Checklist
- [ ] Factual assertions consistent across documents (same facts, same dates, same amounts)
- [ ] Terminology consistent (same concept uses same term across all documents)
- [ ] Party designations consistent (same names, same roles)
- [ ] Date references internally consistent
- [ ] Legal conclusions compatible across documents
- [ ] No contradictory recommendations
