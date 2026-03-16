# citation-checker Skill

Citation verification strategy, search execution, and audit trail assembly for the citation-verifier sub-agent.

## Capabilities

1. **Audit Trail Assembly** (`scripts/build-audit-trail.py`)
   - Assembles per-citation verification results into `verification-audit.json`
   - Validates schema compliance for each entry
   - Computes summary statistics (verified/issue/unverifiable counts by sub-status)
   - Usage: `python3 build-audit-trail.py <results_dir> <output_path>`

2. **Search Execution Reference** (`scripts/search-executor.sh`)
   - Documents MCP search invocation patterns by jurisdiction
   - Query construction templates for each legal database
   - Reference only — actual MCP calls are made by the LLM directly

## Verification Workflow per Citation

```
Citation from citation-list.json
    │
    ├── Format Validation (deterministic)
    │   ├── Valid format   → proceed to search
    │   └── Invalid format → flag for deeper investigation
    │
    ├── Track A: Source-List Cross-Check (if source materials available)
    │   └── Match found → record, continue to Track B for confirmation
    │
    ├── Track B: Independent Web Search
    │   ├── WebSearch (primary)
    │   ├── WebFetch direct URL (fallback)
    │   └── All fail → Unverifiable_No_Access
    │
    ├── Classify per Verification Status Taxonomy
    │
    ├── Classify Source Authority Tier (see below)
    │
    └── Record in audit trail (include authority_tier)
```

## Source Authority Classification

Every verified citation must be assigned an **authority tier**. This classification is recorded in `verification-audit.json` alongside the verification status and is consumed by the substance-reviewer (Step 4) to detect secondary-source-reliance defects.

### Authority Tiers

| Tier | Label | Description | Examples |
|------|-------|-------------|----------|
| **1** | Primary Law | Binding legal authority enacted or issued by an authoritative body | Statutes, regulations, court decisions, constitutional provisions, official gazette notices, administrative rulings, treaties |
| **2** | Authoritative Secondary | Official or quasi-official interpretive materials with recognized institutional weight | Government guidance documents, official legislative history, regulatory preambles, authoritative commentaries (주석서), Restatements, official agency reports, approved practice standards |
| **3** | Secondary | Non-binding analytical or scholarly materials | Academic articles, law firm client alerts/newsletters, legal encyclopedias (CJS, AmJur), textbooks, practitioner treatises, Westlaw/LexisNexis practice notes, 법률신문 commentaries |
| **4** | Tertiary / Low-Reliability | Non-legal or non-expert sources with no institutional authority | News articles, blog posts, Wikipedia, general websites, social media, press releases, marketing materials, conference slides |

### Classification Rules

1. **When in doubt, tier down** — if a source straddles two tiers, assign the lower (less authoritative) tier
2. **Government guidance** is Tier 2 only if issued by the relevant regulatory body. A different agency's informal commentary on another's regulation is Tier 3
3. **Law firm publications** are always Tier 3, regardless of the firm's reputation — they represent advocacy or marketing, not authoritative interpretation
4. **AI training data artifacts** — if a citation cannot be traced to any identifiable source and appears to be synthesized from training data, classify as Tier 4 and flag additionally as `Unverifiable_Synthetic_Suspected`
5. **Court decisions from lower courts** remain Tier 1 but may be annotated with jurisdictional weight (e.g., persuasive vs. binding)

### Audit Trail Schema Addition

Each citation entry in `verification-audit.json` must include:

```json
{
  "citation_id": "C-001",
  "text": "...",
  "verification_status": "Verified",
  "authority_tier": 1,
  "authority_label": "Primary Law",
  "authority_note": null,
  "supports_conclusion": true,
  "conclusion_location": {"section": "III.2", "paragraph_index": 45}
}
```

- `authority_tier`: Integer 1–4
- `authority_label`: Human-readable tier name
- `authority_note`: Optional note explaining classification rationale (especially for borderline cases or Tier 4 flags)
- `supports_conclusion`: Boolean — whether this citation is used to support a legal conclusion (vs. background/context)
- `conclusion_location`: If `supports_conclusion` is true, the location of the conclusion it supports

### Flagging Rules for Substance Review Handoff

After completing verification, generate a **source authority summary** appended to `verification-audit.json`:

```json
{
  "source_authority_summary": {
    "tier_distribution": {"tier_1": 12, "tier_2": 3, "tier_3": 5, "tier_4": 1},
    "conclusion_support_by_tier": {"tier_1": 8, "tier_2": 2, "tier_3": 4, "tier_4": 1},
    "high_risk_citations": [
      {
        "citation_id": "C-015",
        "authority_tier": 3,
        "supports_conclusion": true,
        "conclusion_location": {"section": "IV.1", "paragraph_index": 72},
        "risk": "Tier 3 source (법률신문 기사) used as sole support for dispositive conclusion"
      }
    ]
  }
}
```

`high_risk_citations` includes any citation where:
- `authority_tier` ≥ 3 AND `supports_conclusion` = true
- No Tier 1–2 citation supports the same conclusion within the same section

## Search Query Construction by Jurisdiction

### Korean (KR)
- **Statutes**: Search `law.go.kr` with statute name + article number
  - Query: `site:law.go.kr "{statute_name}" 제{N}조`
  - Direct URL: `https://law.go.kr/법령/{statute_name}`
- **Cases**: Search `glaw.scourt.go.kr` with case number
  - Query: `site:glaw.scourt.go.kr {case_number}`
  - Alternative: `대법원 {year}{type}{number} 판결`

### US
- **Statutes**: Search `congress.gov` or `uscode.house.gov`
  - Query: `{title} USC {section}` or `site:congress.gov "{title} U.S.C. {section}"`
  - Direct URL: `https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title{title}-section{section}`
- **Regulations**: Search `ecfr.gov`
  - Query: `site:ecfr.gov {title} CFR {section}`
  - Direct URL: `https://www.ecfr.gov/current/title-{title}/section-{section}`
- **Cases**: Search with reporter citation
  - Query: `{volume} {reporter} {page}` or case name if available

### EU
- **Regulations/Directives**: Search `eur-lex.europa.eu`
  - Query: `site:eur-lex.europa.eu "Regulation (EU) {number}"`
  - Direct URL: `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex_number}`

## Format Validation Rules

| Jurisdiction | Type | Valid Pattern |
|-------------|------|---------------|
| KR | Statute number | 법률 제\d{4,5}호 |
| KR | Case number | \d{4}[가-힣]{1,3}\d{2,6} preceded by court name |
| KR | Article ref | 제\d+조(제\d+항)?(제\d+호)? |
| US | USC | \d{1,2} U.S.C. §? \d+ |
| US | CFR | \d{1,2} C.F.R. §? [\d.]+ |
| US | Reporter | \d{1,3} (U.S.\|F.\d[d]\|S.Ct.) \d+ |
| EU | Regulation | Regulation \(EU\) \d{4}/\d+ |

## When to Use

- Invoked by the citation-verifier sub-agent during WF1 Step 3
- Reference `legal-source-urls.md` for database URL patterns

## Checkpoint

After the citation-verifier sub-agent returns `verification-audit.json`, the main agent updates `checkpoint.json`:
- `step_3.status` → `"completed"`
- `step_3.output` → `"working/verification-audit.json"`
- `last_completed_step` → `3`
