# Comment Format Guide

Format specification for margin comments in redline DOCX output.

---

## General Comment Format

```
[{SEVERITY}] {Description}. {Recommendation}.
```

## Severity Prefixes

| Prefix | When to Use |
|--------|-------------|
| `[CRITICAL]` | Legal liability or professional embarrassment risk |
| `[MAJOR]` | Significant quality issue undermining credibility |
| `[MINOR]` | Polish issue not affecting substance |
| `[SUGGESTION]` | Enhancement opportunity |

## Citation-Specific Prefixes

These override the general severity prefix for citation-related findings:

| Prefix | Status | Meaning |
|--------|--------|---------|
| `[CRITICAL — NONEXISTENT]` | Nonexistent | Positive evidence authority does not exist |
| `[CRITICAL — WRONG PINPOINT]` | Wrong_Pinpoint | Authority exists but article/section number wrong |
| `[CRITICAL — UNSUPPORTED]` | Unsupported_Proposition | Authority exists but doesn't support the claim |
| `[MAJOR — WRONG JURISDICTION]` | Wrong_Jurisdiction | Authority from different jurisdiction |
| `[MAJOR — STALE]` | Stale | Authority amended/repealed since claimed date |
| `[MAJOR — TRANSLATION MISMATCH]` | Translation_Mismatch | Translation materially diverges from source |
| `[MAJOR — UNVERIFIED]` | Unverifiable_No_Access | Source inaccessible |
| `[MAJOR — UNVERIFIED]` | Unverifiable_No_Evidence | Search inconclusive |
| `[MINOR — SECONDARY ONLY]` | Unverifiable_Secondary_Only | Only secondary sources confirm |

## Comment Body Guidelines

### Korean Documents
```
[CRITICAL — NONEXISTENT] 대법원 2024다54321 판결: 대법원 종합법률정보 검색 결과 해당 사건번호가 존재하지 않습니다. 판례 인용을 삭제하거나 정확한 사건번호를 확인해주세요.
```

```
[MAJOR] 제15조에서 제20조로의 교차참조: 제20조가 본 문서에 존재하지 않습니다. 참조 대상 조항 번호를 확인해주세요.
```

```
[MINOR] 번역투: "~에 의해 체결된 계약"은 수동태 직역. "당사자가 체결한 계약" 등 능동태로 수정을 권고합니다.
```

### English Documents
```
[CRITICAL — WRONG PINPOINT] 42 U.S.C. § 1983: The cited section number appears incorrect. Section 1983 addresses civil rights violations, not the copyright claim discussed here. Please verify the correct section reference.
```

```
[SUGGESTION] Consider restructuring the sentence for clarity: "The party that initiated the proceedings" rather than "The party by whom the proceedings were initiated."
```

## Author Attribution

| Document Language | Author Name |
|------------------|-------------|
| Korean | 시니어 리뷰 스페셜리스트 |
| English | Senior Review Specialist |

## Recurring Pattern Tag

When a finding matches a known issue pattern, append to the comment:
```
[Recurring: KI-003] 이 패턴은 legal-writing-agent의 문서에서 반복적으로 관찰됩니다.
```

## Comment Placement Rules

- **Critical/Major with textual correction**: Both tracked change AND comment
- **Critical/Major without clear fix**: Comment only (no tracked change)
- **Minor**: Comment only
- **Suggestion**: Comment only
- Comments attach to the **first paragraph** of the relevant section/finding location
