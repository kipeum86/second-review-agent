# 번역투 (Translationese) Patterns in Korean Legal Writing

Common translation-smell patterns detected in AI-generated or translated Korean legal documents, with corrections.

---

## High-Frequency Patterns (Always Flag)

### 1. ~에 의해 (수동태)
- **Pattern**: `X에 의해 Y가 [동사]되었다`
- **Problem**: English "by X" passive construction directly translated
- **Fix**: Restructure as active voice
- **Example**:
  - ❌ "본 계약은 양 당사자에 의해 체결되었다"
  - ✅ "양 당사자가 본 계약을 체결하였다"
- **Severity**: Minor

### 2. ~함에 있어서
- **Pattern**: `X함에 있어서 Y`
- **Problem**: English "in doing X" or "with respect to doing X"
- **Fix**: ~할 때, ~하는 경우
- **Example**:
  - ❌ "본 조항을 해석함에 있어서 다음 원칙을 적용한다"
  - ✅ "본 조항을 해석할 때 다음 원칙을 적용한다"
- **Severity**: Minor

### 3. ~의 경우에 있어서
- **Pattern**: `X의 경우에 있어서`
- **Problem**: Redundant — "in the case of" over-translated
- **Fix**: ~인 경우, ~할 때
- **Example**:
  - ❌ "계약 위반의 경우에 있어서 손해배상을 청구할 수 있다"
  - ✅ "계약을 위반한 경우 손해배상을 청구할 수 있다"
- **Severity**: Minor

### 4. 이중 수동태 (~되어지다)
- **Pattern**: `X되어진다 / X되어졌다`
- **Problem**: Double passive — Korean already marks passive with 되다
- **Fix**: 단일 수동태 또는 능동태
- **Example**:
  - ❌ "계약이 해제되어질 수 있다"
  - ✅ "계약이 해제될 수 있다" / "당사자가 계약을 해제할 수 있다"
- **Severity**: Minor

---

## Medium-Frequency Patterns (Flag on Repeated Use)

### 5. ~에 관하여(는)
- **Pattern**: `X에 관하여(는)`
- **Problem**: "regarding" / "with respect to" over-translated. Acceptable in some contexts.
- **Fix**: ~에 대해, ~의, or restructure sentence
- **Note**: Flag only when used 3+ times in same section
- **Severity**: Suggestion

### 6. ~을 통해(서)
- **Pattern**: `X을 통해(서) Y`
- **Problem**: "through X" directly translated
- **Fix**: ~으로, ~에 의하여, or restructure
- **Example**:
  - ❌ "서면 통지를 통해서 해지할 수 있다"
  - ✅ "서면 통지로 해지할 수 있다"
- **Severity**: Suggestion

### 7. ~것이 [형용사]
- **Pattern**: `X하는 것이 필요하다/요구된다/예상된다`
- **Problem**: "it is necessary/required/expected" pattern
- **Fix**: 주어 명시 + 능동태
- **Example**:
  - ❌ "당사자가 동의하는 것이 요구된다"
  - ✅ "당사자의 동의가 필요하다" / "당사자가 동의하여야 한다"
- **Severity**: Minor

### 8. ~에 기반하여/기초하여
- **Pattern**: `X에 기반하여/기초하여`
- **Problem**: "based on" directly translated
- **Fix**: ~에 따라, ~을 근거로
- **Example**:
  - ❌ "본 계약에 기반하여 의무를 이행한다"
  - ✅ "본 계약에 따라 의무를 이행한다"
- **Severity**: Suggestion

---

## Low-Frequency Patterns (Flag as Suggestion Only)

### 9. ~에 한정되지 않는
- **Pattern**: `X에 한정되지 않는/아니하는`
- **Problem**: "not limited to" translated awkwardly
- **Fix**: 법률 관용표현 사용
- **Example**:
  - ❌ "다음에 한정되지 않는 사항을 포함한다"
  - ✅ "다음 각 호의 사항을 포함하되, 이에 한하지 아니한다"
- **Severity**: Suggestion

### 10. ~에도 불구하고 (과다 사용)
- **Pattern**: Excessive use of `~에도 불구하고`
- **Problem**: "notwithstanding" — acceptable in legal writing but can be overused
- **Fix**: ~이지만, ~이나, 다만
- **Note**: Acceptable 1-2 times per section; flag if 3+ in same section
- **Severity**: Suggestion

---

## Legal Terminology Precision

| Confused Pair | Distinction |
|--------------|-------------|
| 해제 vs 해지 | 해제 = rescission (소급 효력), 해지 = termination (장래 효력) |
| 취소 vs 무효 | 취소 = voidable (취소권 행사 필요), 무효 = void ab initio |
| 선의 vs 악의 | 선의 = bona fide (사정 모름), 악의 = mala fide (사정 알고 있음) |
| 채권 vs 채무 | 채권 = claim/right, 채무 = obligation/debt |
| 이행 vs 실행 | 이행 = performance of obligation, 실행 = execution/enforcement |
