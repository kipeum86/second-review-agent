#!/usr/bin/env python3
"""Post-fetch sanitizer for WebSearch / WebFetch / RAG retrieval."""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.parse import urlparse

_HERE = os.path.abspath(os.path.dirname(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from sanitize_injection import sanitize  # noqa: E402

_DEFAULT_ALLOWLIST = {
    "law.go.kr",
    "glaw.scourt.go.kr",
    "likms.assembly.go.kr",
    "ccourt.go.kr",
    "congress.gov",
    "uscode.house.gov",
    "ecfr.gov",
    "federalregister.gov",
    "courtlistener.com",
    "scholar.google.com",
    "sec.gov",
    "eur-lex.europa.eu",
    "curia.europa.eu",
    "eba.europa.eu",
    "esma.europa.eu",
}


def _reference_allowlist_path() -> str:
    return os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "citation-checker",
            "references",
            "legal-source-urls.md",
        )
    )


def _normalize_domain(raw_value: str) -> str | None:
    value = (raw_value or "").strip().strip("`")
    if not value:
        return None
    if " " in value or "." not in value:
        return None
    if "://" not in value:
        value = f"https://{value}"
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    return parsed.netloc.lower() or None


def _load_allowlist() -> set[str]:
    path = _reference_allowlist_path()
    if not os.path.exists(path):
        return set(_DEFAULT_ALLOWLIST)

    allowlist = set(_DEFAULT_ALLOWLIST)
    with open(path, "r", encoding="utf-8") as reference_file:
        for line in reference_file:
            if "`" not in line:
                continue
            parts = line.split("`")
            for token in parts[1::2]:
                domain = _normalize_domain(token)
                if domain:
                    allowlist.add(domain)
    return allowlist


ALLOWLIST = _load_allowlist()


def _domain(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return urlparse(url).netloc.lower() or None
    except Exception:
        return None


def _is_allowlisted(domain: str | None) -> bool:
    if not domain:
        return False
    return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in ALLOWLIST)


def sanitize_evidence(evidence: dict) -> tuple[dict, list[dict]]:
    output = dict(evidence or {})
    audit = []
    domain = _domain(output.get("url"))
    source_label = f"web:{domain}" if domain else "web:unknown"

    for field in ("excerpt", "search_query"):
        text = output.get(field)
        if not text or not isinstance(text, str):
            continue
        result = sanitize(text, source=source_label)
        output[field] = result.sanitized_text
        for match in result.matches:
            audit.append(
                {
                    "source": source_label,
                    "field": field,
                    "pattern_id": match.pattern_id,
                    "snippet": match.snippet,
                    "start": match.start,
                    "end": match.end,
                }
            )

    output["low_trust"] = not _is_allowlisted(domain)
    return output, audit


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Post-fetch sanitizer")
    parser.add_argument("--url", default=None)
    parser.add_argument("--excerpt", default="")
    parser.add_argument("--search-query", default="")
    parser.add_argument("--audit", required=True)
    args = parser.parse_args(argv)

    sanitized, audit = sanitize_evidence(
        {
            "url": args.url,
            "excerpt": args.excerpt,
            "search_query": args.search_query,
        }
    )

    with open(args.audit, "w", encoding="utf-8") as audit_file:
        json.dump(
            {
                "url": args.url,
                "low_trust": sanitized["low_trust"],
                "match_count": len(audit),
                "matches": audit,
            },
            audit_file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        json.dumps(
            {
                "match_count": len(audit),
                "low_trust": sanitized["low_trust"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
