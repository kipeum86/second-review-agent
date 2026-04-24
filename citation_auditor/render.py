from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Literal

from marko import Markdown
from marko.md_renderer import MarkdownRenderer

from citation_auditor.models import Claim, Verdict, VerdictLabel

RenderMode = Literal["inline", "append"]


def render_markdown(
    md_text: str,
    verdicts: list[Verdict],
    mode: RenderMode = "inline",
) -> str:
    if mode == "append":
        return _render_append(md_text, verdicts)
    return _render_inline(md_text, verdicts)


def _render_inline(md_text: str, verdicts: list[Verdict]) -> str:
    markdown = Markdown(renderer=MarkdownRenderer)
    markdown.parse(md_text)

    insertions: list[tuple[int, str]] = []
    skip_ranges = _skip_ranges(md_text)
    for verdict in verdicts:
        claim = verdict.claim
        if _span_overlaps_skip_range(claim.sentence_span.start, claim.sentence_span.end, skip_ranges):
            continue
        insertions.append((claim.sentence_span.end, f" {_badge_for_verdict(verdict)}"))

    rendered = md_text
    for offset, badge in sorted(insertions, key=lambda item: item[0], reverse=True):
        rendered = rendered[:offset] + badge + rendered[offset:]

    rendered = rendered.rstrip() + "\n\n" + _audit_report(verdicts)
    return markdown.convert(rendered)


def _render_append(md_text: str, verdicts: list[Verdict]) -> str:
    markdown = Markdown(renderer=MarkdownRenderer)
    markdown.parse(md_text)

    insertions: list[tuple[int, str]] = []
    skip_ranges = _skip_ranges(md_text)
    for verdict in verdicts:
        if verdict.label == VerdictLabel.VERIFIED:
            continue
        claim = verdict.claim
        if _span_overlaps_skip_range(claim.sentence_span.start, claim.sentence_span.end, skip_ranges):
            continue
        tag = "[Unverified]" if verdict.label == VerdictLabel.CONTRADICTED else "[Partially Unverified]"
        insertions.append((claim.sentence_span.end, f" {tag}"))

    rendered = md_text
    for offset, tag in sorted(insertions, key=lambda item: item[0], reverse=True):
        rendered = rendered[:offset] + tag + rendered[offset:]

    rendered = rendered.rstrip() + "\n\n" + _audit_log_table(verdicts)
    return markdown.convert(rendered)


def _badge_for_verdict(verdict: Verdict) -> str:
    if verdict.label == VerdictLabel.VERIFIED:
        marker = "✅"
    elif verdict.label == VerdictLabel.CONTRADICTED:
        marker = "⚠️"
    else:
        marker = "❓"
    return f"**[{marker} {verdict.verifier_name}]**"


def _audit_report(verdicts: list[Verdict]) -> str:
    lines = ["## Audit Report", ""]
    for index, verdict in enumerate(verdicts, start=1):
        lines.append(f"### Claim {index}")
        lines.append(f"- Verdict: {verdict.label.value}")
        lines.append(f"- Verifier: {verdict.verifier_name}")
        lines.append(f"- Claim: {verdict.claim.text}")
        lines.append(f"- Rationale: {verdict.rationale}")
        if verdict.evidence:
            evidence_summary = "; ".join(_format_evidence(item.title, item.url) for item in verdict.evidence)
            lines.append(f"- Evidence: {evidence_summary}")
        else:
            lines.append("- Evidence: none")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _audit_log_table(verdicts: list[Verdict]) -> str:
    lines = [
        "---",
        "",
        "## 부록: 검증 로그 (Citation Audit Log)",
        "",
        "본 산출물에 포함된 사실·인용 주장에 대한 자동 인용 감사 결과입니다. "
        "자동 감사는 사람의 검토를 대체하지 않으며, `Contradicted` / `Unknown` 항목은 최종 검토 시 확인이 필요합니다.",
        "",
        "| # | 클레임 (Claim) | 판정 (Verdict) | Verifier | 근거 (Evidence) |",
        "|---|---|---|---|---|",
    ]
    for index, verdict in enumerate(verdicts, start=1):
        icon = _icon_for_label(verdict.label)
        claim_cell = _escape_table_cell(_truncate(verdict.claim.text, 100))
        verdict_cell = f"{icon} {verdict.label.value}"
        verifier_cell = _escape_table_cell(verdict.verifier_name)
        if verdict.evidence:
            evidence_cell = _escape_table_cell(
                "; ".join(_format_evidence(item.title, item.url) for item in verdict.evidence)
            )
        else:
            evidence_cell = "—"
        lines.append(f"| {index} | {claim_cell} | {verdict_cell} | {verifier_cell} | {evidence_cell} |")
    return "\n".join(lines).rstrip() + "\n"


def _icon_for_label(label: VerdictLabel) -> str:
    if label == VerdictLabel.VERIFIED:
        return "✓"
    if label == VerdictLabel.CONTRADICTED:
        return "⚠"
    return "?"


def _truncate(text: str, max_len: int) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_len:
        return collapsed
    return collapsed[: max_len - 1] + "…"


def _escape_table_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _format_evidence(title: str | None, reference: str) -> str:
    if title and title != reference:
        return f"{title} ({reference})"
    return reference


def _skip_ranges(md_text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    fence_start: int | None = None
    fence_token: str | None = None
    cursor = 0
    for line in md_text.splitlines(keepends=True):
        stripped = line.lstrip()
        if fence_start is None:
            match = re.match(r"([`~]{3,})", stripped)
            if match:
                fence_start = cursor
                fence_token = match.group(1)[0] * len(match.group(1))
        else:
            if stripped.startswith(fence_token):
                ranges.append((fence_start, cursor + len(line)))
                fence_start = None
                fence_token = None
        cursor += len(line)
    if fence_start is not None:
        ranges.append((fence_start, len(md_text)))

    in_quote = False
    quote_start = 0
    cursor = 0
    for line in md_text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith(">"):
            if not in_quote:
                quote_start = cursor
                in_quote = True
        elif in_quote:
            ranges.append((quote_start, cursor))
            in_quote = False
        cursor += len(line)
    if in_quote:
        ranges.append((quote_start, len(md_text)))
    return ranges


def _span_overlaps_skip_range(start: int, end: int, skip_ranges: Iterable[tuple[int, int]]) -> bool:
    for skip_start, skip_end in skip_ranges:
        if start < skip_end and end > skip_start:
            return True
    return False
