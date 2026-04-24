# citation-auditor vendor stamp

This directory was copied from `game-legal-research` (which vendored it via `scripts/vendor-into.sh` from the upstream citation-auditor repo).

- Upstream version: **v1.3.0**
- Upstream source commit: 6adf638
- Upstream source tag:    v1.2.0
- Copied from:   `/Users/kpsfamily/코딩 프로젝트/game-legal-research`
- Copied at:     2026-04-24
- Target:        `/Users/kpsfamily/코딩 프로젝트/second-review-agent`
- Integration mode: **Standalone `/audit` + optional WF1 Step 3 native backend** (see `CLAUDE.md` §Citation Auditor Integration). The markdown renderer remains standalone-only; WF1 integration must go through `citation-checker/scripts/adapt-citation-auditor.py` and `merge-verification-audits.py`.

To update this vendor copy, re-run `scripts/vendor-into.sh` in the citation-auditor repo against this path, or manually sync from `game-legal-research` when that repo's citation-auditor is updated.

Do not hand-edit files under `.claude/skills/citation-auditor/` or `.claude/skills/verifiers/` — they will be overwritten on the next vendor run. If you need to customize a verifier, copy it to a new folder under `.claude/skills/verifiers/my-<name>/` instead.
