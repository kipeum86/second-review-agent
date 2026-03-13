# Scoring Rubric — Per-Dimension Criteria

## Scale Definition

| Score | Meaning | Finding Profile |
|-------|---------|-----------------|
| 10 | Excellent — no issues found | Zero findings |
| 9 | Near-perfect — trivial suggestions only | Suggestions only |
| 8 | Very good — minor polish needed | 1–2 Minor findings |
| 7 | Good — noticeable but non-blocking issues | 3+ Minor or 1 Major |
| 6 | Adequate — several quality concerns | 2+ Major findings |
| 5 | Below standard — significant issues | 3+ Major findings |
| 4 | Poor — multiple serious issues | Major findings across sub-dimensions |
| 3 | Very poor — critical issues present | 1 Critical finding |
| 2 | Unacceptable — multiple critical issues | 2+ Critical findings |
| 1 | Fundamentally flawed | Pervasive critical issues |

---

## Dimension 1 — Citation & Fact Verification

| Score Range | Criteria |
|-------------|----------|
| 9–10 | All citations verified; no issues found |
| 7–8 | All citations verified or unverifiable (no Issues); 1–2 secondary-only |
| 5–6 | 1–2 Stale or Wrong_Jurisdiction findings; no Nonexistent/Unsupported |
| 3–4 | 1 Nonexistent or Unsupported citation; OR 3+ Stale citations |
| 1–2 | Multiple Nonexistent or Unsupported citations |

## Dimension 2 — Legal Substance & Logic

| Score Range | Criteria |
|-------------|----------|
| 9–10 | Logical chain complete; all conclusions well-supported |
| 7–8 | Minor logical gaps that don't affect conclusions |
| 5–6 | 1–2 Major logical gaps or unsupported conclusions |
| 3–4 | Critical logical flaw in dispositive analysis |
| 1–2 | Fundamental analytical framework is flawed |

## Dimension 3 — Client Alignment

| Score Range | Criteria |
|-------------|----------|
| 9–10 | Directly answers client question with practical implications |
| 7–8 | Answers question but misses some practical implications |
| 5–6 | Partially answers question; significant tangents |
| 3–4 | Fails to address the core question |
| 1–2 | Analysis is irrelevant to the client's needs |
| N/A | Dimension skipped (no context provided) — excluded from average |

## Dimension 4 — Writing Quality

| Score Range | Criteria |
|-------------|----------|
| 9–10 | Professional register; consistent terminology; clear prose |
| 7–8 | Minor 번역투 or terminology inconsistencies |
| 5–6 | Frequent 번역투 or register violations; terminology drift |
| 3–4 | 구어체 in formal document; pervasive quality issues |
| 1–2 | Unintelligible or fundamentally inappropriate register |

## Dimension 5 — Structural Integrity

| Score Range | Criteria |
|-------------|----------|
| 9–10 | All cross-references valid; numbering correct; terms consistent |
| 7–8 | Minor numbering gaps; all critical cross-references valid |
| 5–6 | Broken cross-references or missing mandatory sections |
| 3–4 | Multiple structural errors causing reader confusion |
| 1–2 | Document structure is fundamentally broken |

## Dimension 6 — Formatting & Presentation

| Score Range | Criteria |
|-------------|----------|
| 9–10 | Professional, consistent formatting throughout |
| 7–8 | Minor formatting inconsistencies (mixed fonts, slight alignment) |
| 5–6 | Noticeable formatting issues affecting readability |
| 3–4 | Significant formatting problems; unprofessional appearance |
| 1–2 | Formatting so poor it impedes comprehension |

## Dimension 7 — Cross-Document Consistency (WF2 only)

| Score Range | Criteria |
|-------------|----------|
| 9–10 | No contradictions; consistent terminology and facts |
| 7–8 | Minor terminology drift; no factual contradictions |
| 5–6 | Factual inconsistency in non-critical details |
| 3–4 | Factual contradiction in material facts |
| 1–2 | Pervasive contradictions across documents |

---

## Release Recommendation Rules

These override the grade. Evaluated after scoring:

| Recommendation | Hard Rule |
|---------------|-----------|
| **Release Not Recommended** | `(any Critical in Dim 1–3) OR (any Nonexistent citation on dispositive conclusion)` |
| **Manual Review Required** | `(any Unverifiable citation on key conclusion) OR (Dim 2 Major count ≥ 2)` |
| **Pass with Warnings** | `(no Dim 1–3 Criticals) AND (Majors exist OR grade < B)` |
| **Pass** | `(no Critical or Major findings) AND (grade ≥ B)` |

Evaluation order: top to bottom, first match wins.
