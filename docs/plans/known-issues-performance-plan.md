# Known Issues Performance Improvement Plan

**Created:** 2026-05-27
**Scope:** `known-issues-manager` pattern matching, frequency tracking, and post-delivery recurring-pattern proposal
**Primary files:** `.claude/skills/known-issues-manager/SKILL.md`, `.claude/skills/known-issues-manager/references/known-issues-schema.md`, `library/known-issues/*.json`
**Status:** Planning

## Executive Summary

The current Known Issues registry is simple and appropriate for the empty seed state: each agent owns one JSON array under `library/known-issues/{agent-name}.json`, and matching compares findings against entries by `dimension`, optional `document_type`, and text similarity.

This will become expensive as review history grows. The largest future cost is not the current registry lookup itself, but the post-delivery scan that can traverse all prior `output/*/round_*/working/issue-registry.json` files to propose new recurring patterns.

This plan keeps the existing JSON registry as the source of truth, adds backward-compatible matching metadata, and introduces two performance aids:

1. A per-agent sidecar index for fast candidate lookup.
2. An append-only occurrence ledger for distinct-matter frequency counting without repeatedly scanning all prior review outputs.

## Goals

- Preserve the current human-editable `library/known-issues/{agent-name}.json` registry.
- Reduce pattern matching from "scan every pattern" to "lookup likely candidates, then compare a small set."
- Replace repeated historical review scans with append-only occurrence records.
- Keep `frequency` semantics exact: count distinct `matter_id`s only.
- Keep user confirmation mandatory before adding a new known issue pattern.
- Allow gradual rollout without breaking existing empty or legacy registry files.

## Non-Goals

- Do not introduce a database dependency.
- Do not auto-add patterns without user approval.
- Do not replace the current JSON registry with generated-only artifacts.
- Do not require immediate backfill for all historical output before the system can run.

## Current Behavior

### Pattern Matching

At WF1 Step 6, the skill:

1. Loads `library/known-issues/{agent-name}.json`.
2. Iterates through findings in `issue-registry.json`.
3. Compares each finding to patterns using:
   - matching `dimension`;
   - matching `document_type`, when specified;
   - description keyword overlap above the configured threshold.
4. Tags matched findings with `recurring_pattern`.
5. Updates `frequency` and `last_seen`.

### New Pattern Proposal

After Step 8, the skill:

1. Loads the current review's `issue-registry.json`.
2. Groups findings by `(dimension, defect_type)` or derived description keywords.
3. Scans prior review outputs under `$SECOND_REVIEW_PRIVATE_DIR/output/*/round_*/working/issue-registry.json`.
4. Counts distinct `matter_id`s where similar findings appeared.
5. Proposes a new pattern when the distinct-matter count is at least 3.

## Performance Risks

| Risk | Trigger | Impact |
|------|---------|--------|
| Full pattern scans | Many known issues per agent | Step 6 grows with `findings * patterns` |
| Repeated historical scans | Many completed reviews and rounds | Post-delivery latency grows with total historical output |
| Repeated string normalization | Similarity checks recompute keywords for every comparison | Avoidable CPU and inconsistent matching |
| Large inline `matter_ids` arrays | Long-lived patterns across many matters | Registry files become heavy to read and edit |
| Per-match file writes | Updating registry after each match | Extra disk I/O and partial-write risk |

## Target Architecture

### Source of Truth

Keep the registry file as the canonical user-editable record:

```text
library/known-issues/
├── legal-writing-agent.json
├── legal-writing-agent.index.json       # generated
├── contract-review-agent.json
├── contract-review-agent.index.json     # generated
└── occurrence-ledger.jsonl              # append-only
```

Generated files must be rebuildable from source artifacts. The registry JSON remains authoritative for pattern content and recommended fixes.

### Registry Entry Additions

Add optional, backward-compatible fields:

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `schema_version` | integer | No | Enables future migration logic. Default legacy value is `1`; new entries should use `2`. |
| `defect_type` | string | No | Stable category used for exact candidate lookup. |
| `keywords` | array[string] | No | Pre-normalized matching tokens. |
| `match_signature` | string | No | Compact lookup key derived from agent, dimension, document type, and defect type or keywords. |
| `pattern_normalized` | string | No | Normalized pattern text for fallback similarity. |
| `examples_max` | integer | No | Optional cap for retained examples. Default: `3`. |

Example:

```json
{
  "schema_version": 2,
  "pattern_id": "KI-001",
  "agent": "legal-writing-agent",
  "document_type": "advisory",
  "dimension": 4,
  "defect_type": "passive_by_overuse",
  "pattern": "번역투: '~에 의해' passive construction overuse",
  "pattern_normalized": "번역투 에 의해 passive construction overuse",
  "keywords": ["번역투", "에 의해", "passive", "construction"],
  "match_signature": "legal-writing-agent|d4|advisory|passive_by_overuse",
  "detection_rule": "register-validator.py pattern 'passive_by' count >= 5 in single document",
  "recommended_fix": "Restructure as active voice with subject-verb-object",
  "frequency": 7,
  "first_seen": "2026-03-12",
  "last_seen": "2026-05-27",
  "matter_ids": ["SYN-001", "SYN-002"],
  "examples_max": 3,
  "examples": [
    "본 계약은 양 당사자에 의해 체결되었다 -> 양 당사자가 본 계약을 체결하였다"
  ]
}
```

### Sidecar Index

Create one generated index per agent:

```json
{
  "schema_version": 1,
  "agent": "legal-writing-agent",
  "generated_at": "2026-05-27",
  "source_file": "library/known-issues/legal-writing-agent.json",
  "patterns_by_signature": {
    "legal-writing-agent|d4|advisory|passive_by_overuse": ["KI-001"]
  },
  "patterns_by_dimension": {
    "4": ["KI-001", "KI-002"]
  }
}
```

Lookup order:

1. Exact `match_signature`.
2. Same `dimension + document_type`.
3. Same `dimension`.
4. Legacy full scan fallback when no index exists.

### Occurrence Ledger

Add `library/known-issues/occurrence-ledger.jsonl` as an append-only event log:

```json
{"event_id":"2026-05-27T10:15:00Z:SYN-001:ISS-004","agent":"legal-writing-agent","matter_id":"SYN-001","round":"round_1","issue_id":"ISS-004","dimension":4,"document_type":"advisory","defect_type":"passive_by_overuse","match_signature":"legal-writing-agent|d4|advisory|passive_by_overuse","description_hash":"sha256:...","occurred_on":"2026-05-27"}
```

The ledger supports two flows:

- Matched known issue: append an occurrence for the matched pattern signature.
- Candidate new pattern: append normalized occurrences even when no existing `pattern_id` exists.

Frequency calculation uses distinct `(pattern_id or match_signature, matter_id)` pairs. Re-review rounds for the same matter must not increase frequency.

### Optional Frequency Cache

If the ledger becomes large, add a rebuildable cache:

```text
library/known-issues/frequency-cache.json
```

This cache stores distinct matter counts by `pattern_id` and `match_signature`. It is optional because the ledger alone is enough for the first performance pass.

## Proposed Algorithms

### Step 6 Matching

1. Load registry JSON for the inferred agent.
2. Load sidecar index when present; otherwise use legacy scan.
3. Normalize each finding once:
   - `agent`
   - `dimension`
   - `document_type`
   - `defect_type`, if present
   - normalized keywords
   - `match_signature`
4. Use the index to fetch candidate `pattern_id`s.
5. Compare only candidate patterns:
   - exact `defect_type` match wins;
   - otherwise keyword overlap threshold;
   - otherwise normalized description similarity fallback.
6. Record all matches in memory.
7. Batch update registry metadata once:
   - `frequency`
   - `last_seen`
   - `matter_ids`, if configured
   - capped `examples`, if new example is retained
8. Atomic-write the registry and regenerated index.
9. Append occurrence events to the ledger.

### Post-Delivery New Pattern Proposal

1. Load current `issue-registry.json`.
2. Normalize findings into signatures.
3. Append current finding occurrences to the ledger.
4. For each current signature group, count distinct prior `matter_id`s in the ledger.
5. If count is at least 3 and no known pattern already owns the signature, propose the pattern to the user.
6. On approval:
   - add a new registry entry with `schema_version: 2`;
   - assign the next available `KI-NNN`;
   - set `frequency` from distinct ledger matters;
   - set `first_seen` and `last_seen`;
   - regenerate the sidecar index.

## Complexity Impact

Let:

- `F` = findings in the current review.
- `P` = known issue patterns for the agent.
- `C` = candidate patterns returned by the index.
- `H` = historical `issue-registry.json` files.
- `L` = ledger events.

Current expected behavior:

- Step 6 matching: `O(F * P)`.
- Post-delivery proposal: `O(H)` file opens plus similarity checks across historical findings.

Target behavior:

- Step 6 matching: `O(F * C)`, where `C` should usually be small.
- Post-delivery proposal: `O(L)` streaming ledger scan, with optional cache reducing count lookup to `O(1)`.

The immediate win is fewer filesystem traversals and fewer JSON parses. The larger long-term win is that review history no longer needs to be repeatedly rediscovered from nested output directories.

## Rollout Plan

### Phase 0: Baseline and Fixtures

- Add small fixture registries with legacy entries and v2 entries.
- Add fixture issue registries with repeated `matter_id`s across rounds.
- Measure:
  - number of registry entries loaded;
  - number of candidate comparisons;
  - number of historical files scanned;
  - elapsed time for matching and proposal flows.

Acceptance criteria:

- Baseline command can run locally without external services.
- Re-review rounds for the same `matter_id` count once.

### Phase 1: Schema v2 Metadata

- Update schema documentation.
- Add normalization helper for findings and patterns.
- Populate `defect_type`, `keywords`, `match_signature`, and `pattern_normalized` for new entries.
- Legacy entries without these fields continue to match by the existing algorithm.

Acceptance criteria:

- Existing `library/known-issues/*.json` files remain valid.
- New v2 entries can be matched without full description recomputation.

### Phase 2: Generated Sidecar Index

- Add index build script.
- Rebuild `{agent}.index.json` whenever a registry file changes.
- Use the index during Step 6 matching.
- Fall back to legacy scan if the index is absent or stale.
- Current implementation slice: `known_issue_index.py` builds sidecar indexes, validates `source_sha256`, and exposes candidate lookup with legacy dimension-scan fallback.

Acceptance criteria:

- Exact signature lookup returns the expected pattern IDs.
- Stale or missing index does not block review completion.
- Candidate comparison count is lower than full scan for multi-pattern fixtures.

### Phase 3: Occurrence Ledger

- Append one event per normalized finding after review completion.
- Use the ledger for new-pattern proposal counts.
- Keep historical output scan as fallback only when no ledger exists.
- Current implementation slice: `known_issue_ledger.py` builds deterministic occurrence events, appends JSONL without truncating existing lines, counts distinct matters, and identifies proposal candidates at the configured threshold.

Acceptance criteria:

- Proposal threshold uses distinct matters, not total findings.
- Same matter across multiple rounds counts once.
- Ledger append failure is reported but does not corrupt the registry.

### Phase 4: Cache and Maintenance

- Add optional `frequency-cache.json` only if ledger scans become measurable.
- Add a rebuild command that derives cache and indexes from registry + ledger.
- Cap examples retained in each registry entry.
- Current implementation slice: `known_issue_maintenance.py` rebuilds sidecar indexes, reports missing/stale generated artifacts in check-only mode, and can write a count-only `frequency-cache.json` from the ledger.

Acceptance criteria:

- Cache can be deleted and rebuilt without data loss.
- Registry remains human-readable.

## Migration Strategy

1. Leave all existing registry entries untouched until they are matched or edited.
2. On match, enrich the matched entry with v2 metadata if missing.
3. On new pattern approval, create v2 entries by default.
4. Backfill the ledger opportunistically:
   - first run: start ledger from current review forward;
   - optional maintenance command: scan historical outputs once and append missing occurrences.

This avoids a risky all-at-once migration while still improving future runs.

## Testing Strategy

| Area | Test |
|------|------|
| Normalization | Same finding text produces stable `match_signature` across runs. |
| Legacy compatibility | Legacy entry without v2 fields still matches by current keyword-overlap rules. |
| Index lookup | Exact signature lookup narrows candidates to expected `pattern_id`s. |
| Fallback behavior | Missing or stale index falls back to full scan. |
| Frequency counting | Duplicate rounds for one `matter_id` count once. |
| Ledger append | Ledger writes valid JSONL and does not truncate existing events. |
| Proposal threshold | New pattern is proposed only at `>= 3` distinct matters. |
| Atomic writes | Interrupted write does not leave malformed registry JSON. |

## Operational Rules

- The registry JSON is authoritative; indexes and caches are generated.
- Registry updates should be batched and written once per review.
- Generated files should include `generated_at` and `source_file`.
- Generated files under `library/known-issues/` are ignored by git and should be rebuilt locally.
- Use atomic write semantics for registry and index files.
- Keep `examples` capped to avoid unbounded registry growth.
- Never reuse deleted `pattern_id`s.
- Never auto-add proposed patterns without explicit user confirmation.

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Normalization creates false positives | Medium | Medium | Keep exact signature as candidate lookup, then still apply similarity checks before tagging. |
| Ledger grows large | Medium | Low | Stream JSONL; add optional frequency cache in Phase 4. |
| Index becomes stale | Medium | Low | Store source hash or modified time; fall back to full scan. |
| Registry and ledger disagree | Medium | Medium | Treat registry as source for pattern content; treat ledger as source for occurrence history; add rebuild diagnostics. |
| Human edits break generated metadata | Medium | Low | Recompute metadata during index build instead of trusting stale fields blindly. |
| Migration disrupts current reviews | Low | High | Use opt-in v2 fields and legacy fallback throughout rollout. |

## Open Questions

- Should `matter_ids` remain inline for auditability, or move to a generated frequency cache after a threshold?
- What controlled vocabulary should `defect_type` use for each review dimension?
- Resolved: generated sidecar files should be ignored and rebuilt on demand.
- Should occurrence ledger live under `library/known-issues/` or under `$SECOND_REVIEW_PRIVATE_DIR` if it may contain matter identifiers?
- What retention policy should apply to ledger events that include `matter_id`?

## Recommended First Implementation Slice

The highest-value low-risk slice is:

1. Add v2 schema metadata fields to documentation.
2. Implement normalization helpers.
3. Generate and use per-agent sidecar indexes.
4. Keep historical scans unchanged until the index path is stable.

After that, implement the occurrence ledger to eliminate repeated historical scans. This sequence improves Step 6 first while preserving the current post-delivery behavior as a fallback.
