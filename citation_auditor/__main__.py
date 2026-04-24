from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import BaseModel, ValidationError

from citation_auditor.aggregation import aggregate_verdicts
from citation_auditor.chunking import ChunkSegment, MarkdownChunk, chunk_markdown
from citation_auditor.korean_law import LAW_ID_LOOKUP, CitationRef, extract_hang, extract_ho, normalize_case_number, parse_citation
from citation_auditor.models import (
    AggregateInput,
    AggregateOutput,
    AggregatedVerdict,
    Claim,
    ChunkOutput,
    ChunkPayload,
    ChunkSegmentPayload,
    SentenceSpan,
    Verdict,
)
from citation_auditor.render import render_markdown
from citation_auditor.settings import AuditSettings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic utilities for citation-auditor.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    chunk_parser = subparsers.add_parser("chunk", help="Split markdown into block-boundary chunks.")
    chunk_parser.add_argument("file", type=Path, help="Markdown file to chunk.")
    chunk_parser.add_argument("--max-tokens", type=int, default=AuditSettings().max_chunk_tokens)
    chunk_parser.set_defaults(func=_run_chunk)

    aggregate_parser = subparsers.add_parser("aggregate", help="Aggregate verifier verdict candidates.")
    aggregate_parser.add_argument("input", help="JSON file path or - for stdin.")
    aggregate_parser.set_defaults(func=_run_aggregate)

    render_parser = subparsers.add_parser("render", help="Render annotated markdown from aggregated verdicts.")
    render_parser.add_argument("input_md", type=Path, help="Source markdown file.")
    render_parser.add_argument("aggregated_json", type=Path, help="Aggregated verdict JSON file.")
    render_parser.add_argument(
        "--mode",
        choices=["inline", "append"],
        default="inline",
        help="inline: per-claim badges in body + per-claim audit report (default, used by /audit). "
             "append: body preserved with only [Unverified]/[Partially Unverified] tags on failing claims, "
             "plus a '부록: 검증 로그 (Citation Audit Log)' table at the end (used by Step 10).",
    )
    render_parser.set_defaults(func=_run_render)

    korean_law_parser = subparsers.add_parser("korean_law", help="Pure helpers for Korean legal citation parsing.")
    korean_law_subparsers = korean_law_parser.add_subparsers(dest="korean_law_command", required=True)

    parse_parser = korean_law_subparsers.add_parser("parse", help="Parse a Korean legal citation from text.")
    parse_parser.add_argument("text", help="Text containing a Korean legal citation.")
    parse_parser.set_defaults(func=_run_korean_law_parse)

    extract_hang_parser = korean_law_subparsers.add_parser("extract-hang", help="Extract a specific 항 from article text.")
    extract_hang_parser.add_argument("input", help="Text file path or - for stdin.")
    extract_hang_parser.add_argument("hang_num", type=int, help="Paragraph number to extract.")
    extract_hang_parser.set_defaults(func=_run_korean_law_extract_hang)

    extract_ho_parser = korean_law_subparsers.add_parser("extract-ho", help="Extract a specific 호 from paragraph text.")
    extract_ho_parser.add_argument("input", help="Text file path or - for stdin.")
    extract_ho_parser.add_argument("ho_num", type=int, help="Item number to extract.")
    extract_ho_parser.set_defaults(func=_run_korean_law_extract_ho)

    normalize_case_parser = korean_law_subparsers.add_parser("normalize-case", help="Normalize a Korean case number.")
    normalize_case_parser.add_argument("text", help="Case number text to normalize.")
    normalize_case_parser.set_defaults(func=_run_korean_law_normalize_case)

    lookup_law_parser = korean_law_subparsers.add_parser("lookup-law", help="Look up a bundled lawId by statute name.")
    lookup_law_parser.add_argument("name", help="Statute name to resolve.")
    lookup_law_parser.set_defaults(func=_run_korean_law_lookup_law)

    return parser


def _run_chunk(args: argparse.Namespace) -> int:
    md_text = args.file.read_text(encoding="utf-8")
    chunks = chunk_markdown(md_text, max_tokens=args.max_tokens)
    payload = ChunkOutput(
        chunks=[
            ChunkPayload(
                index=chunk.index,
                text=chunk.text,
                segments=[
                    ChunkSegmentPayload(
                        chunk_start=segment.chunk_start,
                        chunk_end=segment.chunk_end,
                        document_start=segment.document_start,
                        document_end=segment.document_end,
                    )
                    for segment in chunk.segments
                ],
            )
            for chunk in chunks
        ]
    )
    print(payload.model_dump_json(indent=2))
    return 0


def _run_aggregate(args: argparse.Namespace) -> int:
    raw_payload = _read_json_input(args.input)
    aggregate_input = AggregateInput.model_validate_json(raw_payload)

    grouped: list[tuple[object, list[object]]] = []
    for bundle in aggregate_input.verdicts:
        normalized_claim = bundle.claim.model_copy(update={"sentence_span": _document_span(bundle.chunk, bundle.claim.sentence_span)})
        normalized_candidates = [
            candidate.model_copy(
                update={"claim": candidate.claim.model_copy(update={"sentence_span": _document_span(bundle.chunk, candidate.claim.sentence_span)})}
            )
            for candidate in bundle.candidates
        ]
        duplicate = next(
            (
                existing
                for existing in grouped
                if existing[0].text == normalized_claim.text
                and abs(existing[0].sentence_span.start - normalized_claim.sentence_span.start) <= 20
            ),
            None,
        )
        if duplicate is None:
            grouped.append((normalized_claim, normalized_candidates))
        else:
            duplicate[1].extend(normalized_candidates)

    aggregated = AggregateOutput(
        aggregated=[
            AggregatedVerdict(claim=claim, verdict=aggregate_verdicts(claim, candidates))
            for claim, candidates in sorted(grouped, key=lambda item: (item[0].sentence_span.start, item[0].sentence_span.end, item[0].text))
        ]
    )
    print(aggregated.model_dump_json(indent=2))
    return 0


def _run_render(args: argparse.Namespace) -> int:
    md_text = args.input_md.read_text(encoding="utf-8")
    aggregate_output = AggregateOutput.model_validate_json(args.aggregated_json.read_text(encoding="utf-8"))
    rendered = render_markdown(
        md_text,
        [item.verdict for item in aggregate_output.aggregated],
        mode=args.mode,
    )
    print(rendered)
    return 0


def _run_korean_law_parse(args: argparse.Namespace) -> int:
    _print_json(parse_citation(args.text))
    return 0


def _run_korean_law_extract_hang(args: argparse.Namespace) -> int:
    article_text = _read_text_input(args.input)
    _print_json({"hang": extract_hang(article_text, args.hang_num)})
    return 0


def _run_korean_law_extract_ho(args: argparse.Namespace) -> int:
    hang_text = _read_text_input(args.input)
    _print_json({"ho": extract_ho(hang_text, args.ho_num)})
    return 0


def _run_korean_law_normalize_case(args: argparse.Namespace) -> int:
    _print_json({"normalized": normalize_case_number(args.text)})
    return 0


def _run_korean_law_lookup_law(args: argparse.Namespace) -> int:
    normalized_name = " ".join(args.name.split())
    _print_json({"law_id": LAW_ID_LOOKUP.get(normalized_name) or LAW_ID_LOOKUP.get(normalized_name.replace(" ", ""))})
    return 0


def _read_json_input(value: str) -> str:
    if value == "-":
        return sys.stdin.read()
    return Path(value).read_text(encoding="utf-8")


def _read_text_input(value: str) -> str:
    if value == "-":
        return sys.stdin.read()
    return Path(value).read_text(encoding="utf-8")


def _document_span(chunk: ChunkPayload, sentence_span: SentenceSpan) -> SentenceSpan:
    markdown_chunk = MarkdownChunk(
        index=chunk.index,
        text=chunk.text,
        segments=tuple(
            ChunkSegment(
                chunk_start=segment.chunk_start,
                chunk_end=segment.chunk_end,
                document_start=segment.document_start,
                document_end=segment.document_end,
            )
            for segment in chunk.segments
        ),
    )
    return markdown_chunk.document_span(sentence_span.start, sentence_span.end)


def _print_json(payload: BaseModel | dict[str, object]) -> None:
    if isinstance(payload, BaseModel):
        print(payload.model_dump_json(indent=2))
        return
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValidationError as exc:
        print(exc, file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
