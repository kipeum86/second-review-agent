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
    └── Record in audit trail
```

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
