# Verifier Skills

Third-party verifier skills extend citation-auditor without changing the Python package.

## Layout

Use the Claude Code docs-compliant layout:

- `skills/<your-skill-name>/SKILL.md`

## Required Frontmatter

Each verifier skill must declare:

```yaml
---
name: your-verifier-name
description: Short summary of what the verifier checks.
patterns:
  - "case-insensitive regex"
authority: 0.0
disable-model-invocation: true
---
```

Rules:

- `name` must be unique. The primary skill uses it for explicit routing.
- `patterns` must be regex strings. Routing tests claim text against every pattern case-insensitively.
- `authority` must be between `0.0` and `1.0`.
- Higher authority wins during aggregation. Equal-authority conflicts resolve to `unknown`.

## Input Contract

Verifier skills should accept either:

- a bare `Claim` JSON object, or
- an object shaped like:

```json
{
  "claim": {
    "text": "string",
    "sentence_span": { "start": 0, "end": 10 },
    "claim_type": "factual",
    "suggested_verifier": "your-verifier-name"
  },
  "local_only": false
}
```

`sentence_span` values are chunk-relative when they come from the primary skill. Verifier skills should treat them as opaque metadata and should not rewrite them.

## Output Contract

Return only JSON in this exact shape:

```json
{
  "label": "verified|contradicted|unknown",
  "rationale": "string",
  "supporting_urls": ["https://example.com"],
  "authority": 0.0,
  "reason_code": "optional",
  "source_scope": "optional",
  "enforceable": false
}
```

Notes:

- `authority` in the output should match the frontmatter authority.
- `supporting_urls` may be empty if the verifier cannot reach a conclusion.
- `supporting_urls` may contain either clickable URLs or plain-language source references when no stable URL exists.
- `reason_code`, `source_scope`, and `enforceable` are optional for standalone `/audit`, but strongly preferred when the verifier is used by WF1 native citation-auditor integration. Without a reason code, the adapter will treat `contradicted` conservatively and may map it to `Unverifiable_No_Evidence`.
- Final-user rationales should read like professional review notes, not internal release or task-tracking jargon.
- Do not emit markdown fences or explanatory prose around the JSON.

## WF1 Native Integration Notes

WF1 native integration does not consume verifier JSON directly. The result must pass through `citation-checker/scripts/adapt-citation-auditor.py`, then `merge-verification-audits.py`, and finally appear as canonical `working/verification-audit.json`.

Recommended `reason_code` values:

- `primary_supports_claim`
- `secondary_only`
- `nonexistent_authority`
- `wrong_pinpoint`
- `unsupported_proposition`
- `wrong_jurisdiction`
- `stale_or_superseded`
- `translation_mismatch`
- `no_access`
- `no_evidence`

## Routing Behavior

The primary `citation-auditor` skill routes claims in this order:

1. `suggested_verifier` exact match by skill `name`
2. regex `patterns` match against claim text
3. fallback to `general-web`

If multiple skills match by pattern, all of them may run and Python will aggregate the returned verdicts by authority.

## Reference Implementations

The bundled verifiers are concrete examples of the contract above. When designing your own verifier, the closest pattern depends on your data source:

- **Authoritative MCP server**: see [`korean-law`](verifiers/korean-law/SKILL.md) — illustrates how to chain MCP tool calls (statute lookup, precedent search) and turn them into verdict JSON.
- **Free public REST API + canonical-page WebFetch**: see [`us-law`](verifiers/us-law/SKILL.md), [`uk-law`](verifiers/uk-law/SKILL.md), [`eu-law`](verifiers/eu-law/SKILL.md) — illustrates deterministic URL construction, WebFetch as primary path, and **WebSearch fallback** for environments where WebFetch is permission-denied, blocked by anti-bot interstitials, or returns empty bodies on JS-rendered pages.
- **Pure REST metadata APIs (no-auth)**: see [`scholarly`](verifiers/scholarly/SKILL.md) — illustrates how to combine multiple APIs (CrossRef, arXiv, PubMed) under one verifier umbrella.
- **Lightweight summary API + targeted full-article fallback**: see [`wikipedia`](verifiers/wikipedia/SKILL.md) — illustrates a two-tier lookup strategy that minimizes WebFetch volume.
- **Generic WebSearch + WebFetch fallback**: see [`general-web`](verifiers/general-web/SKILL.md) — the catch-all pattern when no domain-specific source exists.
