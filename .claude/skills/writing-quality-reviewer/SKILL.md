# writing-quality-reviewer Skill

Evaluate writing quality (Dimension 4) including register, terminology consistency, style, and language-specific quality.

## Capabilities

1. **Register Validation** (`scripts/register-validator.py`)
   - Detects 번역투 (translationese) patterns in Korean documents
   - Detects 구어체 (colloquial) intrusion in formal documents
   - Detects passive voice overuse
   - Configurable pattern list
   - Usage: `python3 register-validator.py <text_path> <language> <output_path>`

2. **Term Consistency Check** (`scripts/term-consistency-checker.py`)
   - Verifies defined terms are used consistently throughout
   - Detects variant spellings, synonyms, abbreviated forms
   - Cross-references against `defined-terms.json` from document-parser
   - Usage: `python3 term-consistency-checker.py <defined_terms_json> <text_path> <output_path>`

3. **Style Fingerprint Comparison** (`scripts/style-fingerprint-compare.py`)
   - Computes document metrics: avg sentence length, passive voice ratio, formality markers
   - Compares against user's style profile if available
   - Deviations > 1.5 SD flagged as Minor/Suggestion only
   - Usage: `python3 style-fingerprint-compare.py <text_path> <style_profile_json> <output_path>`
   - Exit codes: 0=comparison done, 1=no profile available, 2=insufficient samples

## When to Use

- WF1 Step 4: Multi-Dimension Substantive Review (Dimension 4 only)
- Run after substance-reviewer and in parallel with structure-checker
- Input: `parsed-structure.json`, `defined-terms.json`, `library/style-profiles/` (if available)

## Review Dimensions

### Korean-Specific Checks
- **번역투**: Patterns from `translation-smell-patterns.md`
  - ~에 의해 overuse → restructure as active voice
  - ~함에 있어서 → ~할 때
  - ~의 경우에 있어서 → ~인 경우
  - 불필요한 수동태 → 능동태
- **구어체 intrusion**: Informal endings (해요, 거든요) in formal documents
- **문어체 일관성**: Consistent formal register throughout
- **Legal terminology**: Correct usage of 법률 용어 (e.g., 해제 vs 해지, 취소 vs 무효)
- **띄어쓰기**: Korean spacing rules

### English-Specific Checks
- Register appropriateness for document type
- Plain language balance (avoid archaic legalese unless standard)
- Bluebook/OSCOLA citation form compliance
- Gender-neutral language
- Avoid: "hereinbefore", "witnesseth", "whereas" overuse

### Universal Checks
- Terminological consistency (same concept = same term)
- Ambiguous pronoun references
- Unnecessary verbosity
- Sentence clarity and readability

### Style Fingerprint
- Only activated when ≥5 samples exist in `library/samples/`
- Metrics: avg sentence length, passive voice ratio, formality markers, paragraph length
- Deviations are **always Minor or Suggestion** — never elevated to substance-level
- Purpose: catch AI-generated stylistic tells before external audiences notice

## Output Format

```json
{
  "dimension": 4,
  "severity": "Minor",
  "location": {"paragraph_index": 23, "text_excerpt": "...에 의해 체결된..."},
  "description": "번역투: '~에 의해' 수동태 구문. 능동태로 구조 변경 권고",
  "recommendation": "'계약이 체결되었다' 또는 '양 당사자가 계약을 체결하였다'로 수정",
  "pattern_type": "translationese"
}
```

## References
- `references/translation-smell-patterns.md` — Korean 번역투 patterns
- `references/legal-register-guide.md` — KR/EN register requirements

## Checkpoint

This skill runs as part of Step 4 alongside `substance-reviewer` and `structure-checker`. The main agent updates `checkpoint.json` only after ALL Step 4 skills complete — see `substance-reviewer/SKILL.md` for details.
