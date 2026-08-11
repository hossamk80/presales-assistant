"""اختبارات تحويل Markdown المولَّد إلى كتل مستند."""
import pytest


@pytest.fixture()
def parse():
    from utils.document_blocks import parse_blocks
    return lambda md: list(parse_blocks(md))


def test_heading_levels(parse):
    blocks = parse("## عنوان ثانٍ\n\n### عنوان ثالث")
    assert [(b["type"], b["level"], b["text"]) for b in blocks] == [
        ("heading", 2, "عنوان ثانٍ"),
        ("heading", 3, "عنوان ثالث"),
    ]


def test_paragraph_lines_are_joined(parse):
    blocks = parse("سطر أول\nسطر ثانٍ\n\nفقرة أخرى")
    assert [b["text"] for b in blocks] == ["سطر أول سطر ثانٍ", "فقرة أخرى"]


def test_inline_bold_and_code_stripped(parse):
    blocks = parse("نحن **نفهم** أن `الكود` مهم")
    assert blocks[0]["text"] == "نحن نفهم أن الكود مهم"


def test_bullets_collected(parse):
    blocks = parse("- أول\n- ثانٍ\n* ثالث")
    assert blocks[0]["type"] == "bullets"
    assert blocks[0]["items"] == ["أول", "ثانٍ", "ثالث"]


def test_numbered_list(parse):
    blocks = parse("1. خطوة\n2. خطوة أخرى")
    assert blocks[0]["type"] == "numbered"
    assert blocks[0]["items"] == ["خطوة", "خطوة أخرى"]


def test_table_with_separator_row(parse):
    md = "| المعيار | الوزن |\n|---|---|\n| الخبرة | 40 |\n| السعر | 60 |"
    table = parse(md)[0]
    assert table["type"] == "table"
    assert table["header"] == ["المعيار", "الوزن"]
    assert table["rows"] == [["الخبرة", "40"], ["السعر", "60"]]


def test_ragged_table_rows_are_padded(parse):
    """صف ناقص عمود يجب ألا يكسر البناء."""
    md = "| أ | ب | ج |\n|---|---|---|\n| 1 | 2 |"
    table = parse(md)[0]
    assert len(table["header"]) == 3
    assert all(len(r) == 3 for r in table["rows"])


def test_mixed_document_order_preserved(parse):
    md = (
        "## عنوان\n\nفقرة.\n\n- بند\n\n| ع | و |\n|---|---|\n| 1 | 2 |\n\nخاتمة."
    )
    assert [b["type"] for b in parse(md)] == [
        "heading", "paragraph", "bullets", "table", "paragraph"
    ]


def test_empty_input(parse):
    assert parse("") == []
    assert parse(None) == []
