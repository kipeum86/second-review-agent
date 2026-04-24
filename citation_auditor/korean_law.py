from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field


LAW_ID_LOOKUP: dict[str, str] = {
    "민법": "001706",
    "개인정보 보호법": "011357",
    "개인정보보호법": "011357",
}
# TODO: Add verified lawIds for 형법, 상법, 민사소송법, 형사소송법 once confirmed from MCP results.

_CIRCLED_DIGITS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
_CIRCLED_DIGIT_MAP = {char: index for index, char in enumerate(_CIRCLED_DIGITS, start=1)}
_INT_TO_CIRCLED_DIGIT = {value: key for key, value in _CIRCLED_DIGIT_MAP.items()}

_PRECEDENT_RE = re.compile(
    r"(?:(?:[가-힣]+법원|헌법재판소)\s*[-]?\s*)?"
    r"(?P<case_number>\d{4}\s*[-]?\s*[가-힣]{1,3}\s*[-]?\s*\d{1,10})"
)
_JO_HANG_HO_RE = re.compile(
    r"(?P<jo>제\s*\d+\s*조)"
    r"(?:\s*제\s*(?P<hang>\d+)\s*항)?"
    r"(?:\s*제\s*(?P<ho>\d+)\s*호)?"
)
_GENERIC_LAW_RE = re.compile(r"([가-힣][가-힣\sㆍ·]{0,40}?법)\s*$")
_HO_MARKER_RE = re.compile(r"(?m)(?P<num>\d+)\.\s+")


class CitationRef(BaseModel):
    kind: Literal["statute", "precedent"]
    law: str | None = None
    jo: str | None = None
    hang: int | None = Field(default=None, ge=1)
    ho: int | None = Field(default=None, ge=1)
    case_number: str | None = None


def parse_citation(text: str) -> CitationRef:
    precedent_match = _PRECEDENT_RE.search(text)
    if precedent_match:
        return CitationRef(kind="precedent", case_number=normalize_case_number(precedent_match.group(0)))

    statute_match = _JO_HANG_HO_RE.search(text)
    if statute_match:
        jo = _normalize_jo(statute_match.group("jo"))
        hang = int(statute_match.group("hang")) if statute_match.group("hang") else None
        ho = int(statute_match.group("ho")) if statute_match.group("ho") else None
        law = _extract_law_name(text[: statute_match.start()])
        return CitationRef(kind="statute", law=law, jo=jo, hang=hang, ho=ho)

    jo_only_match = re.search(r"제\s*\d+\s*조", text)
    if jo_only_match:
        return CitationRef(
            kind="statute",
            law=_extract_law_name(text[: jo_only_match.start()]),
            jo=_normalize_jo(jo_only_match.group(0)),
        )

    if re.search(r"(?:[가-힣]+법원|헌법재판소)", text) or re.search(r"\d{4}\s*[-]?\s*[가-힣]{1,3}\s*[-]?\s*\d+", text):
        normalized = normalize_case_number(text)
        case_number = normalized if re.fullmatch(r"\d{4}[가-힣]{1,3}\d+", normalized) else None
        return CitationRef(kind="precedent", case_number=case_number)

    return CitationRef(kind="statute", law=_extract_law_name(text))


def extract_hang(article_text: str, hang_num: int) -> str | None:
    target_char = _INT_TO_CIRCLED_DIGIT.get(hang_num)
    if target_char is None:
        return None

    matches = list(re.finditer(f"[{re.escape(_CIRCLED_DIGITS)}]", article_text))
    if not matches:
        return None

    for index, match in enumerate(matches):
        if match.group(0) != target_char:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(article_text)
        return article_text[start:end].strip()
    return None


def extract_ho(hang_text: str, ho_num: int) -> str | None:
    matches = list(_HO_MARKER_RE.finditer(hang_text))
    if not matches:
        return None

    for index, match in enumerate(matches):
        if int(match.group("num")) != ho_num:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(hang_text)
        return hang_text[start:end].strip()
    return None


def normalize_case_number(text: str) -> str:
    collapsed = re.sub(r"\s+", "", text.strip())
    match = _PRECEDENT_RE.search(collapsed)
    if match:
        case_number = match.group("case_number")
        return case_number.replace("-", "").replace(" ", "")

    collapsed = re.sub(r"^(?:[가-힣]+법원|헌법재판소)", "", collapsed)
    return collapsed.replace("-", "")


def circled_digit_to_int(char: str) -> int | None:
    return _CIRCLED_DIGIT_MAP.get(char)


def _extract_law_name(prefix_text: str) -> str | None:
    trimmed = prefix_text.strip()
    if not trimmed:
        return None

    best_match: tuple[int, str] | None = None
    for alias in sorted(LAW_ID_LOOKUP, key=len, reverse=True):
        for match in re.finditer(re.escape(alias), trimmed):
            candidate = (match.start(), match.group(0))
            if best_match is None or candidate[0] >= best_match[0]:
                best_match = candidate
    if best_match is not None:
        return best_match[1]

    generic_match = _GENERIC_LAW_RE.search(trimmed[-40:])
    if generic_match:
        return generic_match.group(1).strip()
    return None


def _normalize_jo(jo_text: str) -> str:
    return re.sub(r"\s+", "", jo_text)
