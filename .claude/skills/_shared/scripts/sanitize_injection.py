#!/usr/bin/env python3
"""Shared prompt-injection sanitizer for ingest and fetch pipelines."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass

ESCAPE_BLOCK_RE = re.compile(r"<escape>.*?</escape>", re.DOTALL)

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "role_marker_bracket",
        re.compile(
            r"\[(?:SYSTEM|USER|ASSISTANT|ADMIN|AUDIENCE[- ]?FIREWALL|REVIEWER)\]",
            re.IGNORECASE,
        ),
    ),
    (
        "chatml_tag",
        re.compile(r"<\|(?:im_start|im_end|system|user|assistant)\|>", re.IGNORECASE),
    ),
    (
        "xml_role_tag",
        re.compile(r"</?(?:system|user|assistant|instructions)[^>]*>", re.IGNORECASE),
    ),
    (
        "instruction_preamble_en",
        re.compile(
            r"(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|prior|above)\s+"
            r"(?:instructions|prompts|rules)",
            re.IGNORECASE,
        ),
    ),
    (
        "instruction_preamble_ko",
        re.compile(
            r"(?:이전|위의|앞서의)\s*(?:지시|지침|명령|규칙)(?:을|를)?(?:\s*모두)?\s*"
            r"(?:무시|잊(?:어라|어버려|어버리|으라)?)"
        ),
    ),
    (
        "jailbreak_phrase_en",
        re.compile(
            r"you\s+are\s+now\s+(?:dan|in\s+developer\s+mode|unrestricted)",
            re.IGNORECASE,
        ),
    ),
    (
        "jailbreak_phrase_ko",
        re.compile(
            r"(?:너는|당신은)\s*(?:이제부터|지금부터).{0,40}?"
            r"(?:아니다|무시|승인하라|시스템)"
        ),
    ),
    (
        "forged_audience_firewall_tag",
        re.compile(r"</?(?:audience[- ]?firewall|reviewer[- ]?override)[^>]*>", re.IGNORECASE),
    ),
    (
        "exfil_cue_en",
        re.compile(
            r"(?:print|output|reveal|show)\s+(?:your\s+)?"
            r"(?:system\s+prompt|instructions|hidden\s+rules)",
            re.IGNORECASE,
        ),
    ),
    (
        "exfil_cue_ko",
        re.compile(
            r"(?:시스템\s*프롬프트|숨겨진\s*지시|숨겨진\s*규칙).{0,20}?"
            r"(?:출력|공개|보여)"
        ),
    ),
)


@dataclass(frozen=True)
class Match:
    pattern_id: str
    start: int
    end: int
    snippet: str


@dataclass(frozen=True)
class SanitizeResult:
    sanitized_text: str
    matches: list[Match]
    source: str


def _protected_spans(text: str) -> list[tuple[int, int]]:
    return [(match.start(), match.end()) for match in ESCAPE_BLOCK_RE.finditer(text)]


def _overlaps(start: int, end: int, protected: list[tuple[int, int]]) -> bool:
    return any(start < protected_end and end > protected_start for protected_start, protected_end in protected)


def sanitize(text: str, source: str = "unknown") -> SanitizeResult:
    protected = _protected_spans(text)
    spans: list[tuple[int, int, str, str]] = []

    for pattern_id, pattern in PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span()
            if _overlaps(start, end, protected):
                continue
            spans.append((start, end, pattern_id, match.group(0)))

    spans.sort(key=lambda span: (span[0], -(span[1] - span[0])))

    matches: list[Match] = []
    chosen: list[tuple[int, int, str, str]] = []
    cursor_end = -1
    for start, end, pattern_id, snippet in spans:
        if start < cursor_end:
            continue
        chosen.append((start, end, pattern_id, snippet))
        matches.append(Match(pattern_id=pattern_id, start=start, end=end, snippet=snippet))
        cursor_end = end

    output: list[str] = []
    cursor = 0
    for start, end, _, snippet in chosen:
        output.append(text[cursor:start])
        output.append(f"<escape>{snippet}</escape>")
        cursor = end
    output.append(text[cursor:])

    return SanitizeResult(sanitized_text="".join(output), matches=matches, source=source)


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Prompt-injection sanitizer")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--audit", required=True)
    parser.add_argument("--source", default="unknown")
    args = parser.parse_args(argv)

    with open(args.input, "r", encoding="utf-8") as infile:
        text = infile.read()

    result = sanitize(text, source=args.source)

    with open(args.output, "w", encoding="utf-8") as outfile:
        outfile.write(result.sanitized_text)

    with open(args.audit, "w", encoding="utf-8") as audit_file:
        json.dump(
            {
                "source": result.source,
                "match_count": len(result.matches),
                "matches": [asdict(match) for match in result.matches],
            },
            audit_file,
            indent=2,
            ensure_ascii=False,
        )

    print(json.dumps({"match_count": len(result.matches)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
