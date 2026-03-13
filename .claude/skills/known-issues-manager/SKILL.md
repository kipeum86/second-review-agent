# known-issues-manager Skill

Match review findings against known recurring patterns and manage the known-issues registry.

## Capabilities

1. **Pattern Matching** (WF1 Step 6)
   - Compare each finding against `library/known-issues/{agent-name}.json`
   - Match by: dimension + document_type + pattern description similarity
   - Tag matches as `[Recurring: {pattern_id}]` in issue registry
   - Include pattern's `recommended_fix` in the review comment

2. **Frequency Tracking** (post-delivery)
   - On pattern match: auto-increment `frequency` and update `last_seen`
   - Count distinct matters only (same matter re-reviews don't increase count)

3. **New Pattern Proposal** (post-delivery)
   - After each review, scan findings for potential new patterns
   - Criteria: similar finding has appeared ≥3 times across distinct matters
   - Present proposed pattern to user for confirmation before adding
   - Never auto-add patterns without user approval

## When to Use

- WF1 Step 6: check findings against existing patterns
- Post-delivery: propose new patterns if criteria met
- WF4 `/library known-issues`: view, add, or edit patterns

## Known Issues Registry Schema

File: `library/known-issues/{agent-name}.json`

```json
[
  {
    "pattern_id": "KI-001",
    "agent": "legal-writing-agent",
    "document_type": "advisory",
    "dimension": 4,
    "pattern": "번역투: '~에 의해' passive construction overuse",
    "detection_rule": "register-validator.py pattern 'passive_by' count ≥ 5 in single document",
    "recommended_fix": "Restructure as active voice with subject-verb-object",
    "frequency": 7,
    "first_seen": "2026-03-12",
    "last_seen": "2026-03-12",
    "examples": [
      "본 계약은 양 당사자에 의해 체결되었다 → 양 당사자가 본 계약을 체결하였다"
    ]
  }
]
```

## Pattern Matching Algorithm

1. Load known-issues for the inferred originating agent
2. For each finding in issue-registry:
   - Compare dimension match
   - Compare document_type match (if specified in pattern)
   - Compare description similarity (keyword overlap > 50%)
3. If match found:
   - Tag finding with `recurring_pattern: {pattern_id}`
   - Add pattern note to review comment
   - Update pattern's `frequency` and `last_seen`

## New Pattern Proposal Format

```
새로운 반복 패턴을 발견했습니다:

패턴: [description]
차원: Dimension [N]
발생 빈도: [N]회 (서로 다른 [N]건에서)
관련 에이전트: [agent-name]

이 패턴을 Known Issues 레지스트리에 추가할까요? (Y/N)
```

## References
- `references/known-issues-schema.md` — full schema documentation

## Checkpoint

This skill runs as part of Step 6 alongside `scoring-engine`. The main agent updates `checkpoint.json` after both skills complete — see `scoring-engine/SKILL.md` for details.
