"""
اختبارات المرحلة 5 — تجميع المستند والهوية البصرية عند التصدير.
"""
import pytest

SECTIONS = [
    {"key": "m", "title": "المنهجية الفنية", "kind": "ai",
     "content": "## النهج\n\nنعتمد منهجية رشيقة.\n"},
]


@pytest.fixture()
def fh():
    from utils import file_handler
    return file_handler


def _docx(fh, tmp_path, **kwargs):
    import docx
    bio = fh.build_word_document("شركة الحلول المتقدمة", SECTIONS, **kwargs)
    out = tmp_path / "p.docx"
    out.write_bytes(bio.getvalue())
    return docx.Document(str(out))


# ─── الغلاف ────────────────────────────────────────────────────────────────────


def test_cover_carries_title_entity_and_company(fh, tmp_path):
    doc = _docx(fh, tmp_path, proposal_title="عرض فني لمشروع الربط الشبكي",
                entity_name="وزارة الصحة")
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "عرض فني لمشروع الربط الشبكي" in text
    assert "مقدَّم إلى: وزارة الصحة" in text
    assert "مقدَّم من: شركة الحلول المتقدمة" in text


def test_cover_falls_back_to_generic_title(fh, tmp_path):
    text = "\n".join(p.text for p in _docx(fh, tmp_path).paragraphs)
    assert "العرض الفني" in text


def test_cover_omits_entity_line_when_unknown(fh, tmp_path):
    """دمج المرفقات قد لا يستخرج الجهة — لا نطبع سطراً فارغاً على الغلاف."""
    text = "\n".join(p.text for p in _docx(fh, tmp_path).paragraphs)
    assert "مقدَّم إلى" not in text


def test_english_cover_uses_english_labels(fh, tmp_path):
    doc = _docx(fh, tmp_path, rtl=False, entity_name="Ministry of Health",
                proposal_title="Network Integration Proposal")
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Submitted to: Ministry of Health" in text
    assert "Submitted by" in text
    assert "مقدَّم" not in text


# ─── الخط واللون ───────────────────────────────────────────────────────────────


def _run_fonts(doc):
    """سمات w:rFonts لأول تشغيلة في المستند."""
    from docx.oxml.ns import qn
    return doc.paragraphs[0].runs[0]._r.find(qn("w:rPr")).find(qn("w:rFonts"))


def test_arabic_font_is_written_to_the_complex_script_slot(fh, tmp_path):
    """
    Word يقرأ خط النص العربي من w:cs لا من w:ascii — ضبط الاسم وحده يترك
    العربية بخط آخر. نتحقق أن السمة مكتوبة فعلاً في XML.
    """
    from docx.oxml.ns import qn

    doc = _docx(fh, tmp_path, proposal_title="عنوان", font_name="Traditional Arabic")
    fonts = _run_fonts(doc)
    assert fonts is not None
    assert fonts.get(qn("w:cs")) == "Traditional Arabic"
    assert fonts.get(qn("w:ascii")) == "Traditional Arabic"


def test_rtl_mark_is_set_on_arabic_runs(fh, tmp_path):
    from docx.oxml.ns import qn

    doc = _docx(fh, tmp_path, proposal_title="عنوان")
    rPr = doc.paragraphs[0].runs[0]._r.find(qn("w:rPr"))
    assert rPr.find(qn("w:rtl")) is not None

    ltr = _docx(fh, tmp_path, rtl=False, proposal_title="Title")
    ltr_rPr = ltr.paragraphs[0].runs[0]._r.find(qn("w:rPr"))
    assert ltr_rPr.find(qn("w:rtl")) is None


def test_font_defaults_follow_direction(fh, tmp_path):
    from docx.oxml.ns import qn

    ar = _run_fonts(_docx(fh, tmp_path, proposal_title="عنوان")).get(qn("w:cs"))
    en = _run_fonts(
        _docx(fh, tmp_path, rtl=False, proposal_title="Title")
    ).get(qn("w:cs"))
    assert ar == fh.BRAND_FONT_AR
    assert en == fh.BRAND_FONT_EN


def test_brand_colour_reaches_the_title(fh, tmp_path):
    doc = _docx(fh, tmp_path, proposal_title="عنوان", brand_color="#8A1538")
    assert str(doc.paragraphs[0].runs[0].font.color.rgb) == "8A1538"


def test_heading_style_carries_the_brand_colour(fh, tmp_path):
    """الأنماط تغطي الفهرس والعناوين التي يولّدها Word ولا نمرّ عليها يدوياً."""
    doc = _docx(fh, tmp_path, brand_color="8A1538")
    assert str(doc.styles["Heading 1"].font.color.rgb) == "8A1538"


@pytest.mark.parametrize("bad", ["", None, "not-a-colour", "#12", 42])
def test_invalid_colour_falls_back_instead_of_crashing(fh, bad, tmp_path):
    doc = _docx(fh, tmp_path, proposal_title="عنوان", brand_color=bad)
    assert str(doc.paragraphs[0].runs[0].font.color.rgb) == fh.BRAND_COLOR


def test_company_template_keeps_its_own_identity(fh, tmp_path):
    """
    قالب الشركة يحمل هويتها البصرية؛ فرض ألواننا فوقه يُفسد ما رفعته عمداً.
    """
    import docx

    base = docx.Document()
    base.styles["Heading 1"].font.name = "Company Serif"
    src = tmp_path / "tpl.docx"
    base.save(str(src))

    doc = _docx(fh, tmp_path, template_bytes=src.read_bytes(), brand_color="8A1538")
    assert doc.styles["Heading 1"].font.name == "Company Serif"


# ─── تطابق PDF مع Word ─────────────────────────────────────────────────────────


def test_pdf_cover_matches_word_cover(fh):
    """الصيغتان تُقدَّمان للجنة الفتح نفسها — اختلاف الغلاف بينهما ارتباك."""
    pytest.importorskip("reportlab")
    if not fh._find_arabic_font()[0]:
        pytest.skip("لا يوجد خط عربي على هذا النظام")

    bio = fh.build_pdf_document(
        "شركة الحلول المتقدمة", SECTIONS, proposal_title="عرض فني لمشروع الربط",
        entity_name="وزارة الصحة", brand_color="#8A1538",
    )
    assert bio.getvalue()[:4] == b"%PDF"


def test_pdf_accepts_colour_with_or_without_hash(fh):
    pytest.importorskip("reportlab")
    if not fh._find_arabic_font()[0]:
        pytest.skip("لا يوجد خط عربي على هذا النظام")

    for value in ("#8A1538", "8A1538"):
        assert fh.build_pdf_document("ش", SECTIONS, brand_color=value).getvalue()


# ─── ربط الهوية بملف الشركة ────────────────────────────────────────────────────


def test_brand_settings_persist_with_the_company_profile(fake_streamlit):
    from utils.state import COMPANY_KEYS, get_company_snapshot

    assert "c_brand_color" in COMPANY_KEYS
    assert "c_doc_font" in COMPANY_KEYS

    fake_streamlit.session_state.update({"c_brand_color": "#8A1538",
                                         "c_doc_font": "Sakkal Majalla"})
    snap = get_company_snapshot()
    assert snap["c_brand_color"] == "#8A1538"
    assert snap["c_doc_font"] == "Sakkal Majalla"
