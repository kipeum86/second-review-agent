Language: **English** | [한국어](docs/ko/README.md)

# Second Review Agent

Final quality gate for AI-generated legal documents in Jinju Legal Orchestrator, powered by Claude Code.

> **[Disclaimer](docs/en/disclaimer.md)** | **[면책조항](docs/ko/disclaimer.md)**

## Overview

Second Review Agent is a Claude Code agent scaffold within Jinju Legal Orchestrator that acts as the final review layer before any legal document leaves the workflow. It reviews documents produced by Contract Specialist Ko Duksoo ([contract-review](https://github.com/kipeum86/contract-review-agent)), Legal Drafting Specialist Han Seokbong ([legal-writing](https://github.com/kipeum86/legal-writing-agent)), Legal Research Specialist Kim Jaesik ([general-legal-research](https://github.com/kipeum86/general-legal-research)), and Game Industry Law Specialist Shim Jinju ([game-legal-research](https://github.com/kipeum86/game-legal-research-agent)) — verifying citations, checking legal logic, evaluating writing quality, and producing redlined DOCX deliverables with tracked changes.

The agent persona is **Senior Review Specialist Ban Seong-mun** — a self-described AI Luddite who fundamentally distrusts machine-generated legal documents. This makes him the most relentless verifier in the workflow. His review style: red pen in the margin, one-line comments, zero tolerance for hallucinated citations.

This project does **not** provide legal advice. It assists with quality control of AI-generated legal work product.

Archived design note: [`senior-legal-review-agent-design.md`](senior-legal-review-agent-design.md) records the earlier design draft that preceded the current `CLAUDE.md` / `.claude/` implementation.

## Core Design Principles

- **Anti-hallucination in review**: The reviewer itself must not hallucinate. `Nonexistent` classification requires positive evidence of non-existence; when in doubt, classify as `Unverifiable`
- **Verify, don't draft**: The agent checks and critiques — it never supplies new legal authorities, restructures analysis, or provides legal advice
- **Independent release gate**: The release recommendation (Pass / Pass with Warnings / Manual Review Required / Release Not Recommended) is a safety gate independent of the letter grade
- **Tracked changes only**: All corrections go through DOCX tracked changes with margin comments. No silent edits
- **Jurisdiction-aware citations**: Verification against primary legal databases (law.go.kr, congress.gov, eur-lex.europa.eu, and others)

## Workflows

| Command | Workflow | Description |
|---------|----------|-------------|
| `/review` | WF1 — Single Document Review | 8-step pipeline: parse, verify citations, review substance/writing/structure/formatting, score, generate redline, self-check |
| `/cross-review` | WF2 — Cross-Document Review | Compare multiple related documents for factual/terminological/date consistency |
| `/rereview` | WF3 — Re-review | Review a revised document against previous round findings |
| `/library` | WF4 — Library Management | Manage writing samples, checklists, known-issue patterns, style profiles |
| `/ingest` | WF5 — Source Ingest | Ingest reference sources (PDF, DOCX, etc.) into the graded library |

### WF1: Single Document Review (8 Steps)

| Step | Name | Skills | Output |
|------|------|--------|--------|
| 1 | Intake | — | `review-manifest.json` |
| 2 | Parsing | `document-parser` | `parsed-structure.json`, `citation-list.json`, `defined-terms.json` |
| 3 | Citation Verification | `citation-checker` (via sub-agent) | `verification-audit.json` |
| 4 | Substantive Review | `substance-reviewer`, `writing-quality-reviewer`, `structure-checker` | Dim 2-5 findings |
| 5 | Formatting Review | `formatting-reviewer` | Dim 6 findings |
| 6 | Consolidation & Scoring | `scoring-engine`, `known-issues-manager` | `issue-registry.json`, `review-scorecard.json` |
| 7 | Output Generation | `redline-generator`, `cover-memo-writer` | Redline DOCX, Clean DOCX, Cover Memo |
| 8 | Self-Check | `quality-gate` | 7-item verification report |

Session state is checkpointed after every step in `output/{matter_id}/checkpoint.json`. Interrupted sessions can be resumed.

### Implementation Notes

- WF1 Step 6 canonicalizes or assembles `issue-registry.json` and `review-scorecard.json` via `scoring-engine/scripts/assemble-review-output.py`
- WF1 Step 7 uses `redline-generator/scripts/add-docx-comments.py` for redline/clean DOCX generation and `cover-memo-writer/scripts/generate-cover-memo.py` for the cover memo DOCX
- WF1 Step 8 uses `quality-gate/scripts/run-quality-gate.py` to emit `quality-gate-report.json`
- WF3 RR-2 uses `document-parser/scripts/build-rereview-diff.py` to create `working/rereview-diff.json`
- `citation-checker/scripts/build-audit-trail.py` accepts either canonical flat citation results or legacy grouped verification output and normalizes both into the current `verification-audit.json` schema

## Seven Review Dimensions

| # | Dimension | What It Checks |
|---|-----------|----------------|
| 1 | Citation & Fact Verification | Do cited authorities exist? Correct pinpoint? Support the claimed proposition? |
| 2 | Legal Substance & Logic | Sound reasoning? Logical gaps? Counterarguments addressed? |
| 3 | Client Alignment | Does the document answer the actual question? Practical implications included? |
| 4 | Writing Quality | Register consistency, terminology, translationese, style fingerprint |
| 5 | Structural Integrity | Numbering continuity, cross-reference validity, defined-term consistency |
| 6 | Formatting & Presentation | Font/size consistency, heading hierarchy, margin uniformity, professional appearance |
| 7 | Cross-Document Consistency | (WF2 only) Factual/terminological/date consistency across related documents |

## Citation Verification Taxonomy

The agent classifies every citation into one of three primary statuses:

| Status | Sub-status | Meaning |
|--------|-----------|---------|
| **Verified** | — | Authority exists and supports the claimed proposition |
| **Issue** | Nonexistent | Positive evidence the authority does not exist |
| | Wrong_Pinpoint | Authority exists but article/section number is wrong |
| | Unsupported_Proposition | Authority exists but doesn't support the claim |
| | Wrong_Jurisdiction | Authority from a different jurisdiction |
| | Stale | Authority amended or repealed since the claimed date |
| | Translation_Mismatch | Translation materially diverges from source text |
| **Unverifiable** | No_Access | Primary source database inaccessible |
| | Secondary_Only | Only secondary sources confirm existence |
| | No_Evidence | Search inconclusive — neither confirmed nor denied |

**Critical rule**: `Nonexistent` requires **positive evidence** of non-existence (authoritative database searched, no match found). When uncertain, the agent must classify as `Unverifiable_No_Evidence`.

## Review Depth

| Level | When | Citation Scope |
|-------|------|----------------|
| **Quick Scan** | "quick scan", internal memo, early draft | Format validation only; escalate failures |
| **Standard** (default) | General review | Dual-track for dispositive citations |
| **Deep Review** | "deep review", court filing, external opinion | Dual-track for all citations |

## Scoring & Release

**Per-dimension scores**: 1-10 scale (10 = no issues, 1-3 = critical found)

**Overall grade**: A (avg >= 8.5), B (>= 7.0), C (>= 5.0), D (< 5.0)

**Release recommendation** (independent safety gate):

| Recommendation | Trigger |
|----------------|---------|
| Release Not Recommended | Any Dim 1-3 Critical; OR Nonexistent citation on dispositive conclusion |
| Manual Review Required | Any Unverifiable citation on key conclusion; OR Dim 2 has >= 2 Major findings |
| Pass with Warnings | Majors exist but no Dim 1-3 Criticals; OR grade < B |
| Pass | No Critical or Major; grade >= B |

## Architecture

```text
Main agent (CLAUDE.md orchestrator)
  |-- Skills (14):
  |     document-parser, citation-checker, substance-reviewer,
  |     writing-quality-reviewer, structure-checker, formatting-reviewer,
  |     scoring-engine, known-issues-manager, quality-gate,
  |     redline-generator, cover-memo-writer, cross-document-checker,
  |     library-manager, ingest
  |-- Sub-agent:
  |     citation-verifier (dispatched for Standard/Deep review, and for Quick Scan citations that fail format validation)
  |-- Python scripts (19):
  |     parse-docx-structure.py, parse-markdown-structure.py,
  |     extract-citations.py, extract-defined-terms.py, build-rereview-diff.py,
  |     build-audit-trail.py, docx-format-inspector.py,
  |     ingest-sample.py, build-style-profile.py, validate-checklist.py,
  |     add-docx-comments.py, numbering-validator.py, cross-reference-checker.py,
  |     register-validator.py, style-fingerprint-compare.py, term-consistency-checker.py,
  |     assemble-review-output.py, generate-cover-memo.py, run-quality-gate.py
  `-- Slash commands (5):
        /review, /cross-review, /rereview, /library, /ingest
```

## Deliverables

Each review produces three client-facing deliverables plus runtime audit artifacts:

| Deliverable | Description |
|-------------|-------------|
| **Redline DOCX** | Original document with tracked changes (`<w:del>/<w:ins>`) and severity-coded margin comments. Author: "Senior Review Specialist Ban Seong-mun" |
| **Clean DOCX** | Original with only Critical/Major textual corrections accepted. No tracked changes or comments remain |
| **Cover Memo** | 10-section review report: release recommendation (top), scorecard table, findings by severity, recurring patterns, style analysis, next steps |

Additional runtime artifacts include `checkpoint.json`, `quality-gate-report.json`, and the working JSON files for parsing, verification, and scoring.

## Library System

The agent maintains a review library for pattern accumulation and style consistency:

| Directory | Purpose | Managed by |
|-----------|---------|------------|
| `library/checklists/` | Document-type-specific review checklists (YAML) | `/library add-checklist` |
| `library/known-issues/` | Recurring patterns per junior agent (JSON) | Auto-proposed after >= 3 occurrences |
| `library/samples/` | Writing samples for style fingerprinting | `/library add-sample` |
| `library/style-profiles/` | Aggregated style fingerprint profiles | `/library style-profile regenerate` |

Six default checklists are included: advisory opinion (KR/EN), research report, litigation filing, contract review report, and a general fallback.

### Adding Reference Sources

The agent maintains a graded source library for citation verification. Drop files into `library/inbox/` and run `/ingest`:

1. Drop any file (PDF, DOCX, etc.) into `library/inbox/`
2. Tell the agent: `/ingest` or "파일 넣었어"
3. The agent will automatically:
   - Convert to structured Markdown via MarkItDown
   - Classify source grade (A: primary/B: secondary/C: academic)
   - Generate metadata (YAML frontmatter)
   - Place in the appropriate `library/grade-{a,b,c}/` folder
   - Move originals to `library/inbox/_processed/`

> **Note:** Dropping files alone does not trigger processing.
> You must run `/ingest` or tell the agent (e.g. "inbox에 파일 넣었어")
> to start the parsing pipeline.

## Repository Structure

```text
/project-root
|-- CLAUDE.md                          # main orchestrator
|-- README.md                          # this file
|-- .gitignore
|-- .claude/
|   |-- settings.local.json            # MCP + permission config
|   |-- agents/
|   |   `-- citation-verifier/AGENT.md
|   |-- commands/
|   |   |-- review.md
|   |   |-- cross-review.md
|   |   |-- rereview.md
|   |   |-- library.md
|   |   `-- ingest.md
|   `-- skills/
|       |-- document-parser/           # DOCX parsing + citation/term extraction
|       |-- citation-checker/          # verification workflow + audit trail
|       |-- substance-reviewer/        # legal logic + client alignment (Dim 2-3)
|       |-- writing-quality-reviewer/  # register, terminology, style (Dim 4)
|       |-- structure-checker/         # numbering, cross-refs (Dim 5)
|       |-- formatting-reviewer/       # DOCX format inspection (Dim 6)
|       |-- scoring-engine/            # scoring + release recommendation
|       |-- known-issues-manager/      # pattern matching + registry
|       |-- quality-gate/              # 7-item self-verification
|       |-- redline-generator/         # tracked changes + comments in DOCX
|       |-- cover-memo-writer/         # 10-section review memo
|       |-- cross-document-checker/    # cross-doc consistency (Dim 7)
|       |-- library-manager/           # sample/checklist/profile management
|       `-- ingest/                    # source file ingest into graded library
|-- library/
|   |-- inbox/                         # gitignored; drop source files here for /ingest
|   |   |-- _processed/                # originals moved here after ingest
|   |   `-- _failed/                   # files that failed conversion
|   |-- grade-a/                       # gitignored; primary sources (statutes, guidelines)
|   |-- grade-b/                       # gitignored; secondary sources (precedents, commentary)
|   |-- grade-c/                       # gitignored; academic/reference sources
|   |-- checklists/                    # 6 default YAML checklists
|   |-- known-issues/                  # 4 per-agent JSON registries
|   |-- samples/                       # gitignored; user writing samples
|   `-- style-profiles/                # gitignored; generated profiles
|-- input/                             # gitignored; drop documents here
|-- output/                            # gitignored; review results
`-- docs/
    |-- review-dimensions-reference.md
    |-- en/
    |   `-- disclaimer.md
    `-- ko/
        |-- README.md
        `-- disclaimer.md
```

## How to Use

### Requirements

- [Claude Code](https://claude.ai/code) CLI installed and authenticated
- Python 3 + `python-docx` for DOCX output: `pip install python-docx`
- MCP search providers (brave-search, tavily) for citation verification — optional but recommended

### Running a review

1. Clone this repo and open the directory in Claude Code.
2. Drop a supported review file into `input/` (`.docx`, `.pdf`, `.pptx`, `.xlsx`, `.html`, `.md`, `.txt`).
3. Run `/review` or simply ask: "Review this document."
4. The agent runs the 8-step pipeline and produces deliverables in `output/`.
5. Interrupted sessions resume automatically from the last checkpoint.

**Example prompts:**

```text
Review the advisory opinion in input/. Deep review.
```

```text
Review the advisory opinion in input/. Standard depth. The client is a game publisher
asking about loot box regulations in Korea.
```

```text
/cross-review — There are a research report and an advisory opinion in input/. Run a cross-review.
```

```text
/rereview — I've uploaded the revised version. Check if the previous round's feedback was addressed.
```

### Review depth selection

| Say this | Agent infers |
|----------|-------------|
| "quick scan" | Quick Scan |
| (nothing specific) | Standard (default) |
| "deep review", "court filing" | Deep Review |

## Part of Jinju Legal Orchestrator

This agent is part of the **Jinju Legal Orchestrator** series of specialized legal workflow agents:

| Agent | Specialist | Focus |
|-------|------------|-------|
| [game-legal-research](https://github.com/kipeum86/game-legal-research) | 심진주 (Sim Jinju) | Game industry law |
| [legal-translation-agent](https://github.com/kipeum86/legal-translation-agent) | 변혁기 (Byeon Hyeok-gi) | Legal translation |
| [general-legal-research](https://github.com/kipeum86/general-legal-research) | 김재식 (Kim Jaesik) | Legal research |
| [PIPA-expert](https://github.com/kipeum86/PIPA-expert) | 정보호 (Jeong Bo-ho) | Data privacy law |
| [GDPR-expert](https://github.com/kipeum86/GDPR-expert) | 김덕배 (Kim De Bruyne) | Data protection law (GDPR) |
| [contract-review-agent](https://github.com/kipeum86/contract-review-agent) | 고덕수 (Ko Duksoo) | Contract review |
| [legal-writing-agent](https://github.com/kipeum86/legal-writing-agent) | 한석봉 (Han Seokbong) | Legal writing |
| **[second-review-agent](https://github.com/kipeum86/second-review-agent)** | **반성문 (Ban Seong-mun)** | **Quality review (Senior review specialist)** |

## Disclaimer

This project supports legal document quality control workflows. It does not provide legal advice. For legal decisions, consult qualified counsel in the relevant jurisdiction. See the full [Disclaimer](docs/en/disclaimer.md).

## License

MIT. See `LICENSE`.
