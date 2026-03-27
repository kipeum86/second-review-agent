# Codex Quality Audit & Improvement — second-review-agent

## Your Role

You are a senior systems engineer performing a comprehensive quality audit on a Claude Code agent project called **second-review-agent**. This is a legal document review agent for a Korean law firm (법무법인 진주 / Jinju Law Firm). The agent acts as a 10th-year partner attorney who reviews documents produced by four junior attorney agents before they leave the firm.

**Your job**: Read every file in this project, identify quality issues, inconsistencies, gaps, and bugs — then fix them. Do NOT add new features. Do NOT change the agent's personality, review philosophy, or workflow architecture. Focus exclusively on making what already exists more robust, consistent, and correct.

---

## Audit Progress (Applied Fixes)

The following concrete improvements have already been implemented during this audit and should be treated as completed work, not open TODOs:

### A. Cross-File Consistency Fixes

- `.claude/commands/review.md`
  - Step 1 now scans all supported review input formats, not DOCX only
  - Dependency preflight requirement was added so the command matches the `CLAUDE.md` runtime contract more closely
- `.claude/agents/citation-verifier/AGENT.md`
  - Input path corrected to `working/review-manifest.json`
  - Duplicated step numbering and output/schema wording were cleaned up
- `.claude/skills/citation-checker/SKILL.md`
  - Schema example aligned to canonical `citation_id` / `citation_text` / `citation_type`
  - Audit-trail script description updated to reflect legacy-to-canonical normalization support
- `.claude/skills/ingest/SKILL.md`
  - MarkItDown MCP tool name standardized to `mcp__markitdown-mcp__convert_to_markdown`
- `README.md` / `docs/ko/README.md`
  - Supported input formats, script inventory, `/ingest` flow, and workflow outputs were updated to match the current implementation

### B. Python Script Bug Fixes

- `.claude/skills/library-manager/scripts/validate-checklist.py`
  - Supports `language: any`
  - Falls back to stdlib parsing when PyYAML is unavailable
  - This unblocked validation of `library/checklists/general.yaml`
- `.claude/skills/document-parser/scripts/extract-citations.py`
  - Korean case citation regex widened to cover forms such as `2024다12345`, `2024고단1234`, `2024구합12345`
  - Regex test comments were added per the audit rules
- `.claude/skills/structure-checker/scripts/cross-reference-checker.py`
  - Added unreferenced English section detection
- `.claude/skills/writing-quality-reviewer/scripts/register-validator.py`
  - Preserves `paragraph_index` when fed `parsed-structure.json`
- `.claude/skills/writing-quality-reviewer/scripts/term-consistency-checker.py`
  - Preserves paragraph-aware locations and richer location payloads when fed `parsed-structure.json`

### C. Previously Missing Implementations Now Closed

- `.claude/skills/redline-generator/scripts/add-docx-comments.py`
  - Generates tracked changes for explicit textual corrections
  - Generates optional clean DOCX output
  - Uses verification-aware comment prefixes
  - Attempts XML sanitization/repair before falling back to Markdown
- `.claude/skills/citation-checker/scripts/build-audit-trail.py`
  - Normalizes legacy grouped verification output into the canonical flat `citations` schema
- `.claude/skills/scoring-engine/scripts/assemble-review-output.py`
  - Normalizes or assembles canonical `issue-registry.json` and `review-scorecard.json`
- `.claude/skills/cover-memo-writer/scripts/generate-cover-memo.py`
  - Generates `review-cover-memo_v{N}.docx`
- `.claude/skills/quality-gate/scripts/run-quality-gate.py`
  - Produces `quality-gate-report.json`
- `.claude/skills/document-parser/scripts/build-rereview-diff.py`
  - Produces `working/rereview-diff.json` for RR-2

### D. Sample Round Refreshed

The sample round under `output/global_ai_reg_2026/round_1/` was refreshed so that the runtime artifacts now match the documented contracts:

- `working/parsed-structure.json`, `working/citation-list.json`, `working/defined-terms.json`
- canonicalized `working/verification-audit.json`
- canonicalized `working/issue-registry.json`
- canonicalized `working/review-scorecard.json`
- `deliverables/*_redline_v1.docx`
- `deliverables/*_clean_v1.docx`
- `deliverables/review-cover-memo_v1.docx`
- `deliverables/quality-gate-report.json`
- corrected `checkpoint.json` Step 2 / Step 7 artifact paths

### E. Verification Performed

- `python3 -m py_compile` passed for all Python scripts under `.claude/skills/`
- checklist validation passed after the `validate-checklist.py` fix
- sample WF1 Step 6–8 scripts were re-run end-to-end
- sample `quality-gate-report.json` now records overall `PASS`
- RR-2 diff generation was smoke-tested with `build-rereview-diff.py`

---

## Project Architecture (Read This First)

```
Orchestrator:     CLAUDE.md (main routing + rules)
Workflows:        .claude/commands/{review,cross-review,rereview,library,ingest}.md
Skills (14):      .claude/skills/{skill-name}/SKILL.md + scripts/ + references/
Sub-agent (1):    .claude/agents/citation-verifier/AGENT.md
Library:          library/{checklists,known-issues,samples,style-profiles,grade-a,grade-b,grade-c,inbox}/
Docs:             docs/{review-dimensions-reference.md, ko-legal-opinion-style-guide.md}
Python scripts:   19 scripts across skill directories
```

The agent has 5 workflows (WF1–WF5), 7 review dimensions, 4 severity levels, and produces DOCX deliverables (redline, clean, cover memo) plus JSON artifacts.

---

## Audit Scope & Instructions

### Phase 1: Cross-File Consistency Audit

Check that all files agree with each other. This is the highest-priority phase because inconsistencies between files cause runtime failures.

**1.1 — CLAUDE.md ↔ Command Files**

For each workflow command in `.claude/commands/`:
- Does the command file's step sequence exactly match what CLAUDE.md describes?
- Are step numbers, step names, and artifact file names identical?
- Are skill invocation names consistent (e.g., if CLAUDE.md says `document-parser`, does the command file also say `document-parser`)?
- Are severity levels, dimension numbers, and review depth rules consistent?
- Does the Resume Protocol in the command file match the checkpoint schema in CLAUDE.md?

**1.2 — CLAUDE.md ↔ Skill Files**

For each skill in `.claude/skills/`:
- Does the SKILL.md's stated purpose match what CLAUDE.md says this skill does?
- Are input/output file names consistent between CLAUDE.md's artifact table and the skill's own documentation?
- Are severity classifications consistent?
- Are dimension numbers consistent?

**1.3 — CLAUDE.md ↔ Sub-Agent**

- Does `.claude/agents/citation-verifier/AGENT.md` match CLAUDE.md's sub-agent dispatch table?
- Are dispatch conditions identical?
- Are input/output file names identical?
- Are verification status taxonomies consistent between the agent, the citation-checker skill, and CLAUDE.md?

**1.4 — Skill ↔ Skill Consistency**

- Do producer skills output JSON in the schema that consumer skills expect?
- Example: `document-parser` outputs `citation-list.json` — does `citation-checker` expect the same schema?
- Example: `scoring-engine` consumes `dim{2,3,4,5,6}-findings.json` — do all dimension skills produce findings in the same schema?
- Are severity level names spelled identically across all skills?
- Are dimension numbers used consistently?

**1.5 — Skill ↔ Python Script Consistency**

- Does each SKILL.md accurately describe what its scripts do?
- Are script file names in SKILL.md instructions correct (no typos, no references to non-existent scripts)?
- Are script CLI argument signatures consistent with how skills invoke them?
- Do scripts reference the correct input/output file paths?

**1.6 — Reference Document Consistency**

- Do reference documents (in `references/` subdirectories) align with their parent skill's rules?
- Example: Does `scoring-rubric.md` match the scoring rules described in the `scoring-engine` SKILL.md?
- Example: Does `logic-defect-taxonomy.md` match what `substance-reviewer` actually checks for?
- Example: Does `comment-format-guide.md` match `redline-generator`'s comment format rules?

### Phase 2: Python Script Quality Audit

For each of the 19 Python scripts:

**2.1 — Correctness**
- Does the script actually do what its SKILL.md says it should?
- Are regex patterns correct for their intended matches (especially legal citation patterns for Korean/US/EU)?
- Are there off-by-one errors, incorrect string slicing, or wrong index access?
- Are JSON schemas produced correctly?

**2.2 — Robustness**
- Does the script handle empty input gracefully (empty DOCX, no citations found, no defined terms)?
- Does the script handle malformed input (truncated DOCX XML, invalid UTF-8)?
- Are file paths handled correctly (spaces in paths, Korean characters in paths)?
- Is the script stdlib-only where the SKILL.md claims it is? (The project avoids pip dependencies for core scripts — only `zipfile`, `xml.etree.ElementTree`, `json`, `re`, `os`, `sys`, `argparse` are allowed unless the skill explicitly states otherwise)

**2.3 — Edge Cases**
- Korean-specific: Do scripts handle mixed Korean/English text, Korean numbering (가, 나, 다 / 제1조, 제2조), and Korean date formats?
- DOCX-specific: Do scripts handle nested tables, merged cells, footnotes/endnotes, tracked changes already present in input?
- Citation-specific: Do regex patterns handle edge cases like multi-line citations, citations with parenthetical explanations, consolidated case numbers?

**2.4 — Output Schema Consistency**
- Does every script's JSON output match the schema expected by downstream consumers?
- Are field names consistent (e.g., `severity` vs `level`, `location` vs `position`)?
- Are enum values consistent (e.g., `"Critical"` vs `"critical"` vs `"CRITICAL"`)?

### Phase 3: Skill & Agent Definition Quality

For each SKILL.md and AGENT.md:

**3.1 — Instruction Clarity**
- Are instructions unambiguous? Could an LLM misinterpret any step?
- Are conditional branches clear (if X then Y, else Z)?
- Are edge cases addressed (what happens when input is empty, when a dimension is skipped, when network is unavailable)?

**3.2 — Completeness**
- Does every skill define its inputs, outputs, and error handling?
- Are all referenced file paths correct?
- Are all referenced scripts actually present on disk?
- Are step numbers sequential with no gaps?

**3.3 — Instruction Economy**
- Are there redundant instructions that could confuse the LLM?
- Are there overly verbose sections that could be tightened without losing meaning?
- Are there contradictory instructions within the same file?

### Phase 4: Library & Checklist Quality

**4.1 — YAML Checklists** (`library/checklists/*.yaml`)
- Are all 6 checklist files valid YAML?
- Do they follow a consistent schema?
- Are dimension names consistent with the 7-dimension system?
- Are check items actionable and specific (not vague like "check quality")?
- Are Korean checklists written in natural Korean, not 번역투?

**4.2 — Known-Issues Registry** (`library/known-issues/*.json`)
- Are all 4 JSON files valid (even if empty arrays)?
- Do they follow the schema described in `known-issues-schema.md`?

**4.3 — Reference Documentation**
- Is `docs/review-dimensions-reference.md` complete and consistent with CLAUDE.md?
- Is `docs/ko-legal-opinion-style-guide.md` internally consistent?

### Phase 5: Gap Analysis (Report Only — Do NOT Implement)

Identify but do NOT fix:
- Missing error handling paths described in CLAUDE.md but not implemented in skills/scripts
- Described features that have no corresponding implementation (e.g., "Phase 2: tracked changes" for redline — is any scaffolding in place?)
- Checkpoint schema fields that no skill actually writes or reads
- Dead code or unused files
- Scripts that are referenced but contain only placeholder/stub logic

For this phase, write your findings to a new file: `output/codex-audit-gaps.md`. Do NOT create implementations for gaps.

---

## Rules of Engagement

1. **Read before writing.** Read every file mentioned in this prompt before making any changes. Do not guess file contents.

2. **Fix, don't redesign.** If a script has a bug, fix the bug. Do not refactor the script into a different architecture. If a SKILL.md has an inconsistency, fix the inconsistency. Do not rewrite the skill.

3. **Preserve voice and tone.** CLAUDE.md and SKILL.md files have a specific persona (meticulous, red-pen partner attorney). Do not sanitize the personality. Do not add corporate-speak.

4. **Preserve language.** Korean text stays Korean. English text stays English. Do not translate between languages unless fixing a mistranslation.

5. **No new features.** Do not add capabilities, dimensions, scripts, or workflows. Do not add docstrings, type hints, or comments to code you didn't change. The scope is fixing what's broken, not improving what works.

6. **No dependency additions.** Scripts must remain stdlib-only (unless they already import a third-party package). Do not add `pip install` steps.

7. **Atomic commits.** Each fix should be a separate commit with a clear message describing what was inconsistent and how you fixed it. Group related fixes (e.g., "fix severity enum casing across all skills") into single commits.

8. **Gap report is read-only.** Phase 5 produces a report file only. Do not implement anything from Phase 5.

9. **Test your regex changes.** If you modify a citation regex pattern, include test cases as comments showing what it now matches and what it correctly rejects.

10. **Preserve .gitignore rules.** Do not commit files in gitignored directories (input/, output/ user data, library/samples/, library/grade-*/, library/style-profiles/).

---

## Execution Order

```
Phase 1 (Cross-File Consistency) → Phase 2 (Python Scripts) → Phase 3 (Skill Definitions) → Phase 4 (Library & Checklists) → Phase 5 (Gap Report)
```

Within each phase, process files in dependency order: CLAUDE.md first (it's the source of truth), then commands, then skills, then scripts, then references.

---

## Deliverables

1. **Fixed files** — committed atomically with descriptive messages
2. **`output/codex-audit-gaps.md`** — Phase 5 gap analysis report, structured as:
   ```markdown
   # Quality Audit — Gap Analysis
   ## Date: {today}

   ### Category 1: Unimplemented Error Handling
   - [ ] {description} — {file}:{line}

   ### Category 2: Stub/Placeholder Code
   - [ ] {description} — {file}:{line}

   ### Category 3: Dead Code / Unused Files
   - [ ] {description} — {file}

   ### Category 4: Schema Mismatches (Not Auto-Fixable)
   - [ ] {description} — {producer file} → {consumer file}

   ### Category 5: Missing Implementations
   - [ ] {description} — referenced in {file}:{line}
   ```

---

## Critical Patterns to Watch For

These are known recurring issues in this project type:

| Pattern | Where to Look | What to Fix |
|---------|--------------|-------------|
| Severity enum casing inconsistency | All SKILL.md + scripts | Standardize to Title Case: `Critical`, `Major`, `Minor`, `Suggestion` |
| Dimension number drift | CLAUDE.md, skills, scoring-rubric.md | Ensure Dim 1–7 mapping is identical everywhere |
| JSON field name inconsistency | Python script outputs + SKILL.md input specs | Standardize field names across producer/consumer boundaries |
| Checkpoint artifact path mismatch | CLAUDE.md resume protocol + command files + skills | Ensure `step_artifacts.output` paths match actual script output paths |
| Citation regex false positives/negatives | extract-citations.py, register-validator.py | Test against Korean legal citation edge cases |
| Missing `encoding='utf-8'` in file I/O | All Python scripts | Korean text will break without explicit UTF-8 |
| Hardcoded paths vs. parameterized paths | Python scripts | Scripts should accept paths via CLI args, not hardcode |
| SKILL.md referencing wrong script name | SKILL.md files | Cross-check every script reference against actual filenames on disk |
| Orphaned references (file mentions non-existent file) | All .md files | Find and fix or remove dead references |
| Schema version drift between related skills | Dimension findings JSON schemas | All dim{N}-findings.json should share a common base schema |

---

## Start Here

1. Read `CLAUDE.md` end-to-end — it is the single source of truth
2. Read each `.claude/commands/*.md` and cross-check against CLAUDE.md
3. Read each `.claude/skills/*/SKILL.md` and cross-check against CLAUDE.md and its command file
4. Read `.claude/agents/citation-verifier/AGENT.md` and cross-check
5. Read and test each Python script
6. Read each reference document and cross-check against its skill
7. Read library YAML/JSON files and validate
8. Read docs/ and cross-check
9. Write gap report
10. Commit all fixes
