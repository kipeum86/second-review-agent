from __future__ import annotations

import math
import re
from dataclasses import dataclass

from citation_auditor.models import Claim, SentenceSpan


TOKEN_CHARS = 4


@dataclass(frozen=True, slots=True)
class MarkdownBlock:
    text: str
    start: int
    end: int
    kind: str


@dataclass(frozen=True, slots=True)
class ChunkSegment:
    chunk_start: int
    chunk_end: int
    document_start: int
    document_end: int


@dataclass(frozen=True, slots=True)
class MarkdownChunk:
    index: int
    text: str
    segments: tuple[ChunkSegment, ...]

    def document_offset(self, chunk_offset: int) -> int:
        if chunk_offset <= 0:
            return self.segments[0].document_start
        for segment in self.segments:
            if segment.chunk_start <= chunk_offset < segment.chunk_end:
                return segment.document_start + (chunk_offset - segment.chunk_start)
            if chunk_offset == segment.chunk_end:
                return segment.document_end
        return self.segments[-1].document_end

    def document_span(self, start: int, end: int) -> SentenceSpan:
        doc_start = self.document_offset(start)
        doc_end = self.document_offset(max(start, end))
        return SentenceSpan(start=doc_start, end=max(doc_start, doc_end))


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / TOKEN_CHARS))


def split_markdown_blocks(md_text: str) -> list[MarkdownBlock]:
    if not md_text:
        return []

    blocks: list[MarkdownBlock] = []
    length = len(md_text)
    offset = 0
    fence_marker: str | None = None

    while offset < length:
        blank_match = re.match(r"[ \t]*\n+", md_text[offset:])
        if blank_match:
            offset += blank_match.end()
            continue

        start = offset
        line_end = md_text.find("\n", offset)
        if line_end == -1:
            line_end = length
        first_line = md_text[offset:line_end]
        fence_match = re.match(r"([`~]{3,})", first_line.lstrip())
        if fence_match:
            fence_marker = fence_match.group(1)[0]
            marker_len = len(fence_match.group(1))
            offset = line_end + 1 if line_end < length else length
            while offset < length:
                next_end = md_text.find("\n", offset)
                if next_end == -1:
                    next_end = length
                line = md_text[offset:next_end]
                stripped = line.lstrip()
                if stripped.startswith(fence_marker * marker_len):
                    offset = next_end + 1 if next_end < length else length
                    break
                offset = next_end + 1 if next_end < length else length
            blocks.append(MarkdownBlock(md_text[start:offset].rstrip("\n"), start, offset, "code"))
            continue

        kind = "paragraph"
        stripped = first_line.lstrip()
        if stripped.startswith(">"):
            kind = "quote"
        elif stripped.startswith("#"):
            kind = "heading"
        elif re.match(r"([-*+]|\d+\.)\s", stripped):
            kind = "list"

        while offset < length:
            line_end = md_text.find("\n", offset)
            if line_end == -1:
                line_end = length
            line = md_text[offset:line_end]
            if not line.strip():
                break
            offset = line_end + 1 if line_end < length else length
        blocks.append(MarkdownBlock(md_text[start:offset].rstrip("\n"), start, offset, kind))

    return blocks


def chunk_markdown(md_text: str, max_tokens: int = 3000) -> list[MarkdownChunk]:
    blocks = split_markdown_blocks(md_text)
    if not blocks:
        return []

    chunks: list[MarkdownChunk] = []
    cursor = 0
    chunk_index = 0

    while cursor < len(blocks):
        selected: list[MarkdownBlock] = []
        token_count = 0
        start_cursor = cursor

        while cursor < len(blocks):
            candidate = blocks[cursor]
            separator_tokens = estimate_tokens("\n\n") if selected else 0
            candidate_tokens = estimate_tokens(candidate.text)
            would_be = token_count + separator_tokens + candidate_tokens
            if selected and would_be > max_tokens:
                break
            selected.append(candidate)
            token_count = would_be
            cursor += 1
            if candidate_tokens > max_tokens:
                break

        if not selected:
            selected = [blocks[cursor]]
            cursor += 1

        text_parts: list[str] = []
        segments: list[ChunkSegment] = []
        chunk_offset = 0
        for block in selected:
            if text_parts:
                text_parts.append("\n\n")
                chunk_offset += 2
            start = chunk_offset
            text_parts.append(block.text)
            chunk_offset += len(block.text)
            segments.append(
                ChunkSegment(
                    chunk_start=start,
                    chunk_end=chunk_offset,
                    document_start=block.start,
                    document_end=block.start + len(block.text),
                )
            )

        chunks.append(MarkdownChunk(index=chunk_index, text="".join(text_parts), segments=tuple(segments)))
        chunk_index += 1

        overlap_index: int | None = None
        for idx in range(len(selected) - 1, -1, -1):
            if selected[idx].kind == "paragraph":
                overlap_index = start_cursor + idx
                break

        if cursor < len(blocks) and overlap_index is not None:
            cursor = max(overlap_index, start_cursor + 1)

    return chunks


def dedupe_claims(claims: list[Claim]) -> list[Claim]:
    deduped: list[Claim] = []
    for claim in sorted(claims, key=lambda item: (item.sentence_span.start, item.sentence_span.end, item.text)):
        duplicate = next(
            (
                existing
                for existing in deduped
                if existing.text == claim.text and abs(existing.sentence_span.start - claim.sentence_span.start) <= 20
            ),
            None,
        )
        if duplicate is None:
            deduped.append(claim)
    return deduped

