# Known Issues Registry — Schema Reference

## Entry Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `pattern_id` | string | Yes | Unique ID, format: `KI-NNN` |
| `agent` | string | Yes | Originating agent name (e.g., "legal-writing-agent") |
| `document_type` | string | No | Document type this pattern applies to (e.g., "advisory", "litigation") |
| `dimension` | integer | Yes | Review dimension (1–7) |
| `pattern` | string | Yes | Human-readable description of the recurring pattern |
| `detection_rule` | string | No | How to detect this pattern (script name, threshold, etc.) |
| `recommended_fix` | string | Yes | Recommended correction |
| `frequency` | integer | Yes | Number of distinct matters where this pattern has been observed |
| `first_seen` | string | Yes | ISO date of first observation |
| `last_seen` | string | Yes | ISO date of most recent observation |
| `examples` | array[string] | No | Anonymized examples (before → after) |

## File Organization

```
library/known-issues/
├── legal-writing-agent.json
├── contract-review-agent.json
├── general-legal-research-agent.json
└── game-legal-research-agent.json
```

Each file contains a JSON array of pattern entries.

## Frequency Counting Rules

- Count distinct matters only
- Same matter across multiple re-review rounds = 1 count
- Threshold for new pattern proposal: frequency ≥ 3
- User confirmation required before registry addition

## Pattern ID Assignment

- Sequential within each agent file: KI-001, KI-002, ...
- Never reuse deleted pattern IDs
- When viewing, sort by frequency descending
