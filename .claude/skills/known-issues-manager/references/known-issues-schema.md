# Known Issues Registry — Schema Reference

## Entry Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `pattern_id` | string | Yes | Unique ID, format: `KI-NNN` |
| `schema_version` | integer | No | Entry schema version. Legacy entries may omit this; new metadata-aware entries should use `2` |
| `agent` | string | Yes | Originating agent name (e.g., "legal-writing-agent") |
| `document_type` | string | No | Document type this pattern applies to (e.g., "advisory", "litigation") |
| `dimension` | integer | Yes | Review dimension (1–7) |
| `defect_type` | string | No | Stable normalized defect category used for exact candidate lookup |
| `pattern` | string | Yes | Human-readable description of the recurring pattern |
| `pattern_normalized` | string | No | Normalized pattern text used for fallback similarity |
| `keywords` | array[string] | No | Pre-normalized matching tokens derived from `pattern` or curated manually |
| `match_signature` | string | No | Compact lookup key: `{agent}|d{dimension}|{document_type}|{defect_type-or-keywords}` |
| `detection_rule` | string | No | How to detect this pattern (script name, threshold, etc.) |
| `recommended_fix` | string | Yes | Recommended correction |
| `frequency` | integer | Yes | Number of distinct matters where this pattern has been observed |
| `first_seen` | string | Yes | ISO date of first observation |
| `last_seen` | string | Yes | ISO date of most recent observation |
| `matter_ids` | array[string] | No | List of distinct matter_ids where this pattern was observed. `frequency` = `len(set(matter_ids))` |
| `examples_max` | integer | No | Maximum retained examples for this entry. Default: `3` |
| `examples` | array[string] | No | Anonymized examples (before → after) |

## Matching Metadata Rules

- Legacy entries may omit all v2 metadata fields.
- New entries should include `schema_version: 2`, `defect_type`, `keywords`, `pattern_normalized`, and `match_signature` when these values are available.
- `match_signature` is a lookup hint, not a final match decision. Exact signature matches should still be checked against dimension and similarity rules before tagging a finding.
- If `document_type` is absent, use `*` in generated signatures.
- If `defect_type` is absent, derive the signature suffix from the first stable normalized keywords.
- Generated metadata may be recomputed from the human-readable fields; the registry entry remains the source of truth.

## File Organization

```
library/known-issues/
├── legal-writing-agent.json
├── legal-writing-agent.index.json
├── contract-review-agent.json
├── contract-review-agent.index.json
└── legal-research-agent.json
```

Each `{agent-name}.json` file contains a JSON array of pattern entries. Each optional `{agent-name}.index.json` file is generated and may be rebuilt from the registry.

## Sidecar Index Schema

```json
{
  "schema_version": 1,
  "agent": "legal-writing-agent",
  "generated_at": "2026-05-27T00:00:00+00:00",
  "source_file": "library/known-issues/legal-writing-agent.json",
  "source_sha256": "sha256:...",
  "patterns_total": 1,
  "patterns_by_signature": {
    "legal-writing-agent|d4|advisory|passive_by_overuse": ["KI-001"]
  },
  "patterns_by_dimension_document_type": {
    "d4|advisory": ["KI-001"]
  },
  "patterns_by_dimension": {
    "4": ["KI-001"]
  }
}
```

Index rules:

- The registry JSON remains the source of truth.
- The index is current only when `source_sha256` matches the registry file hash.
- Missing or stale indexes must not block review; fall back to legacy registry scanning.
- Candidate lookup order is exact `match_signature`, same `dimension + document_type`, same `dimension`.

## Occurrence Ledger Schema

File: `library/known-issues/occurrence-ledger.jsonl`

Each line is one append-only JSON object:

```json
{
  "schema_version": 1,
  "event_id": "sha256:...",
  "agent": "legal-writing-agent",
  "matter_id": "SYN-001",
  "round": "round_1",
  "issue_id": "ISS-001",
  "pattern_id": null,
  "dimension": 4,
  "document_type": "advisory",
  "defect_type": "passive_by_overuse",
  "match_signature": "legal-writing-agent|d4|advisory|passive_by_overuse",
  "description_hash": "sha256:...",
  "occurred_on": "2026-05-27"
}
```

Ledger rules:

- Append only; do not rewrite or truncate the ledger during normal review flow.
- `event_id` is deterministic from agent, matter, round, issue, pattern/signature, and description hash.
- Frequency counting uses distinct `(pattern_id or match_signature, matter_id)` pairs.
- Same matter across multiple re-review rounds counts once.
- If the ledger is missing, use the historical `issue-registry.json` scan as fallback.
- Treat `matter_id` as potentially sensitive; use synthetic IDs in tests and decide production storage location before enabling persistent ledger writes.

## Frequency Cache Schema

File: `library/known-issues/frequency-cache.json`

This file is optional and generated from the occurrence ledger. It stores counts only, not matter IDs:

```json
{
  "schema_version": 1,
  "generated_at": "2026-05-27T00:00:00+00:00",
  "source_file": "library/known-issues/occurrence-ledger.jsonl",
  "source_sha256": "sha256:...",
  "agent": "legal-writing-agent",
  "events_total": 4,
  "frequencies": {
    "signature:legal-writing-agent|d4|advisory|passive_by_overuse": {
      "frequency": 3
    }
  }
}
```

Cache rules:

- The cache is generated and may be deleted.
- Do not store `matter_id` arrays in the cache.
- Rebuild from `occurrence-ledger.jsonl` when ledger counts are needed frequently.
- If the cache is missing or stale, stream the ledger directly.

## Frequency Counting Rules

- Count distinct matters only
- Same matter across multiple re-review rounds = 1 count
- Threshold for new pattern proposal: frequency ≥ 3
- User confirmation required before registry addition

## Pattern ID Assignment

- Sequential within each agent file: KI-001, KI-002, ...
- Never reuse deleted pattern IDs
- When viewing, sort by frequency descending

## Related Plans

- `../../../../docs/plans/known-issues-performance-plan.md` — proposed schema v2 metadata, sidecar indexes, and occurrence-ledger design for performance improvements
