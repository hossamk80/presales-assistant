"""
utils/document_blocks.py — تحويل نص Markdown المولَّد إلى كتل مستند مجرّدة.

الذكاء الاصطناعي يُرجع Markdown (عناوين، قوائم، جداول). بدون هذه الطبقة كان
المحتوى يُلصق كفقرة واحدة ضخمة في المستند النهائي. تُستخدم هذه الكتل من
بنّاء Word وبنّاء PDF معاً حتى يخرج الملفان بنفس البنية.
"""
import re
from typing import Iterator

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
BULLET_RE = re.compile(r"^\s*[-*•]\s+(.*)$")
NUMBERED_RE = re.compile(r"^\s*(\d+)[.)]\s+(.*)$")
TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def strip_inline_markup(text: str) -> str:
    """إزالة تشكيل Markdown السطري الذي لا نمرّره كأنماط."""
    text = BOLD_RE.sub(r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text.strip()


def _split_row(line: str) -> list:
    return [strip_inline_markup(c) for c in line.strip().strip("|").split("|")]


def parse_blocks(markdown: str) -> Iterator[dict]:
    """
    يحوّل نص Markdown إلى كتل:
      {"type": "heading", "level": 1-6, "text": str}
      {"type": "paragraph", "text": str}
      {"type": "bullets", "items": [str]}
      {"type": "numbered", "items": [str]}
      {"type": "table", "header": [str], "rows": [[str]]}
    """
    lines = (markdown or "").replace("\r\n", "\n").split("\n")
    i = 0
    para: list[str] = []

    def flush_para():
        nonlocal para
        if para:
            text = strip_inline_markup(" ".join(para))
            if text:
                yield_block = {"type": "paragraph", "text": text}
                para = []
                return yield_block
            para = []
        return None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # سطر فارغ ينهي الفقرة
        if not stripped:
            block = flush_para()
            if block:
                yield block
            i += 1
            continue

        # جدول
        if TABLE_ROW_RE.match(line):
            block = flush_para()
            if block:
                yield block
            header = _split_row(line)
            i += 1
            if i < len(lines) and TABLE_SEP_RE.match(lines[i]):
                i += 1
            rows = []
            while i < len(lines) and TABLE_ROW_RE.match(lines[i]):
                if not TABLE_SEP_RE.match(lines[i]):
                    rows.append(_split_row(lines[i]))
                i += 1
            width = max([len(header)] + [len(r) for r in rows]) if rows else len(header)
            header += [""] * (width - len(header))
            rows = [r + [""] * (width - len(r)) for r in rows]
            yield {"type": "table", "header": header, "rows": rows}
            continue

        # عنوان
        m = HEADING_RE.match(stripped)
        if m:
            block = flush_para()
            if block:
                yield block
            text = strip_inline_markup(m.group(2))
            if text:
                yield {"type": "heading", "level": len(m.group(1)), "text": text}
            i += 1
            continue

        # قائمة نقطية
        if BULLET_RE.match(line):
            block = flush_para()
            if block:
                yield block
            items = []
            while i < len(lines) and BULLET_RE.match(lines[i]):
                items.append(strip_inline_markup(BULLET_RE.match(lines[i]).group(1)))
                i += 1
            yield {"type": "bullets", "items": [x for x in items if x]}
            continue

        # قائمة مرقّمة
        if NUMBERED_RE.match(line):
            block = flush_para()
            if block:
                yield block
            items = []
            while i < len(lines) and NUMBERED_RE.match(lines[i]):
                items.append(strip_inline_markup(NUMBERED_RE.match(lines[i]).group(2)))
                i += 1
            yield {"type": "numbered", "items": [x for x in items if x]}
            continue

        para.append(stripped)
        i += 1

    block = flush_para()
    if block:
        yield block
