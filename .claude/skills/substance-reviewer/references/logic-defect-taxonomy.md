# Logic Defect Taxonomy for Legal Writing

Common logical defects in legal documents, with definitions, examples, and typical severity.

---

## 1. Unsupported Conclusion (비약적 결론)

**Definition**: A conclusion is stated without sufficient analytical support. The reasoning jumps from premises to conclusion without showing the logical steps.

**Example**: "제3조를 위반하였으므로 계약을 해제할 수 있다" — without analyzing whether the violation constitutes a material breach sufficient for termination under applicable law.

**Typical severity**: Major (Critical if the unsupported conclusion is dispositive)

---

## 2. Circular Reasoning (순환논법)

**Definition**: The conclusion is used as a premise, or the argument restates its conclusion in different words without independent support.

**Example**: "This clause is unenforceable because it cannot be enforced by a court" — the conclusion (unenforceable) is merely restated, not demonstrated.

**Typical severity**: Major

---

## 3. Appeal to Authority Without Analysis (분석 없는 권위 호소)

**Definition**: Citing a statute or case as conclusive without analyzing whether it applies to the specific facts. The citation substitutes for reasoning.

**Example**: "대법원 2020다12345 판결에 의하면 이 경우에도 동일하게 적용된다" — without comparing the cited case's facts to the current situation.

**Typical severity**: Major

---

## 4. False Dichotomy (거짓 이분법)

**Definition**: Presenting only two options when more exist. Common in risk analysis that ignores middle-ground outcomes.

**Example**: "Either the contract is fully enforceable or it is entirely void" — ignoring partial enforceability, severability, or reformation.

**Typical severity**: Minor (Major if it affects the dispositive analysis)

---

## 5. Straw Man of Counterargument (허수아비 반론)

**Definition**: Acknowledging a counterargument but misrepresenting it, making it easier to dismiss. The actual counterargument is stronger than presented.

**Example**: Describing the counterparty's position as "merely arguing inconvenience" when they are actually arguing impossibility of performance.

**Typical severity**: Major

---

## 6. Scope Creep / Irrelevant Tangent (범위 이탈)

**Definition**: Analysis that extends beyond the stated scope or addresses issues not relevant to the client's question.

**Example**: A memo on data privacy compliance that spends 3 pages on general corporate governance principles.

**Typical severity**: Minor (Suggestion if brief; Major if it crowds out relevant analysis)

---

## 7. Missing Premises (전제 누락)

**Definition**: Key assumptions or conditions required for the conclusion are not stated or analyzed.

**Example**: "The limitation of liability clause caps damages at $1M" — without noting that the cap may not apply to willful misconduct, gross negligence, or indemnification obligations.

**Typical severity**: Major (Critical if the missing premise materially changes the conclusion)

---

## 8. Overgeneralization (과잉 일반화)

**Definition**: Drawing a broad conclusion from specific or limited authority. Treating a narrow ruling as establishing a general principle.

**Example**: Citing a case decided under specific factual circumstances as establishing a universal rule applicable to all similar situations.

**Typical severity**: Minor (Major if relied upon for a dispositive conclusion)

---

## 9. Ignoring Exceptions/Limitations (예외 무시)

**Definition**: Stating a legal rule without addressing its exceptions, limitations, or conditions that may apply to the specific situation.

**Example**: "개인정보보호법에 따라 개인정보의 제3자 제공은 금지된다" — without discussing the statutory exceptions (동의, 법률 근거 등).

**Typical severity**: Major (Critical if the exception is likely to apply)

---

## 10. Post Hoc Reasoning (사후 인과 오류)

**Definition**: Assuming that because event B followed event A, A caused B. Common in damages and causation analysis.

**Example**: "The stock price dropped after the announcement, proving the announcement caused the decline" — without ruling out other market factors.

**Typical severity**: Major

---

## 11. Equivocation (의미 혼동)

**Definition**: Using the same term with different meanings in different parts of the analysis without flagging the shift.

**Example**: Using "damages" to mean both contractual damages (손해배상) and penalty amounts (위약금) interchangeably.

**Typical severity**: Minor (Major if it affects the conclusion)

---

## 12. Incomplete Issue Coverage (쟁점 누락)

**Definition**: Failing to address an issue that is within the stated scope and relevant to the client's question.

**Example**: A regulatory compliance memo that omits analysis of a clearly applicable regulation.

**Typical severity**: Major (Critical if the omitted issue is dispositive)

---

## 13. Secondary Source Reliance (2차 소스 의존)

**Definition**: Drawing a legal conclusion or supporting a key argument by citing a non-primary source (news article, blog post, law firm newsletter, commentary, textbook summary) as though it carries the same authority as primary law (statute, regulation, court decision, official gazette).

**Example (KR)**: "법률신문 기사에 따르면 해당 조항은 무효로 해석된다" — citing a legal newspaper article as the basis for a conclusion about statutory invalidity, without citing the actual court decision or statute that supports this position.

**Example (US)**: "According to a client alert from [Law Firm], the SEC has taken the position that..." — citing a law firm publication as authority for a regulatory position, without citing the actual SEC release, no-action letter, or rulemaking.

**Why this matters**: Secondary sources summarize, interpret, or editorialize primary law. They may be inaccurate, outdated, or reflect the author's advocacy position. A legal conclusion resting on secondary sources alone is unsupported — the underlying primary authority must be cited and analyzed.

**Detection heuristic**: For each citation supporting a dispositive or key conclusion, check the source authority tier (see citation-checker Source Authority Classification). Flag any Tier 3–4 source used as the sole or primary support for a legal conclusion.

**Typical severity**: Major (Critical if the conclusion is dispositive and no primary source exists anywhere in the document for that proposition)

---

## 14. Source Authority Misrepresentation (소스 권위 위장)

**Definition**: Paraphrasing or restating content from a secondary or tertiary source in a way that makes it appear to be the author's own primary legal analysis, or that obscures the non-authoritative origin of the information. The source is either not cited at all, or cited in a way that disguises its nature.

**Example (KR)**: A paragraph analyzing 개인정보보호법 enforcement trends that closely follows a 법률신문 commentary article, presented as original analysis without attribution — or attributed vaguely as "실무상" or "통설에 의하면" without identifying the actual source.

**Example (US)**: Restating a Westlaw practice note's analysis of a circuit split as though it were the author's independent case law review, without citing the practice note or the underlying cases it summarized.

**Why this matters**: This is a form of source laundering. It conceals the reliability level of the underlying information and prevents the reader (or reviewer) from evaluating source quality. It also creates a false impression of independent analysis where none was performed. In AI-generated documents, this pattern is especially dangerous because the model may synthesize information from training data without any citable source at all.

**Detection heuristic**: Look for assertions of legal fact or analysis that lack any citation but read as summaries of external content (e.g., enforcement statistics, practice trends, multi-jurisdictional comparisons). Cross-reference with verification-audit.json for sections with low citation density relative to the specificity of claims made.

**Typical severity**: Major (Critical if the misrepresented content is factually wrong or if it forms the basis of a key recommendation)

---

## Severity Guide Summary

| Defect | Default Severity | Escalate to Critical if... |
|--------|-----------------|---------------------------|
| Unsupported Conclusion | Major | ...the conclusion is dispositive |
| Circular Reasoning | Major | — |
| Appeal to Authority | Major | — |
| False Dichotomy | Minor | ...affects dispositive analysis |
| Straw Man | Major | — |
| Scope Creep | Minor | ...crowds out relevant analysis |
| Missing Premises | Major | ...premise materially changes conclusion |
| Overgeneralization | Minor | ...relied upon for key conclusion |
| Ignoring Exceptions | Major | ...exception likely applies |
| Post Hoc Reasoning | Major | — |
| Equivocation | Minor | ...affects conclusion |
| Incomplete Coverage | Major | ...omitted issue is dispositive |
| Secondary Source Reliance | Major | ...conclusion is dispositive with no primary source cited |
| Source Authority Misrepresentation | Major | ...misrepresented content is factually wrong or supports key recommendation |
