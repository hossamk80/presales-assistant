"""
utils/file_handler.py — File I/O: Extraction & Export
"""
import streamlit as st
import pandas as pd
from io import BytesIO
from typing import List, Optional

# أقل عدد أحرف في الصفحة يُعتبر معه استخراج النص ناجحاً.
# ما دون ذلك يرجّح أن الصفحة صورة ممسوحة ضوئياً.
MIN_CHARS_PER_PAGE = 40


def ocr_available() -> bool:
    """هل أدوات الـ OCR الاختيارية مثبّتة؟"""
    try:
        import pytesseract  # noqa: F401
        from pdf2image import convert_from_bytes  # noqa: F401
    except ImportError:
        return False
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _ocr_pdf(file_bytes: bytes, file_name: str) -> str:
    """
    تشغيل OCR على ملف PDF ممسوح ضوئياً (عربي + إنجليزي).
    يتطلب: pytesseract + pdf2image + tesseract-ocr مع حزمة اللغة العربية.
    """
    import pytesseract
    from pdf2image import convert_from_bytes

    pages = convert_from_bytes(file_bytes, dpi=300)
    out = []
    progress = st.progress(0.0, text=f"OCR — {file_name}")
    for i, page in enumerate(pages, start=1):
        out.append(pytesseract.image_to_string(page, lang="ara+eng"))
        progress.progress(i / len(pages), text=f"OCR — {file_name} ({i}/{len(pages)})")
    progress.empty()
    return "\n".join(out)


def extract_text_from_files(files: list) -> tuple[str, list]:
    """
    Extract text from uploaded files. Returns (combined_text, list_of_filenames).
    Handles: PDF (with OCR fallback), DOCX/DOC, XLSX/XLS/CSV, HTML, TXT
    """
    text_parts = []
    file_names = []

    for file in files:
        file_names.append(file.name)
        ext = file.name.rsplit(".", 1)[-1].lower()
        try:
            if ext == "pdf":
                from pypdf import PdfReader

                raw = file.getvalue()
                reader = PdfReader(BytesIO(raw))
                page_count = len(reader.pages)
                pages_text = []
                for page in reader.pages:
                    t = page.extract_text()
                    if t:
                        pages_text.append(t)
                extracted = "\n".join(pages_text)

                # كشف الملفات الممسوحة ضوئياً: نص ضئيل مقارنة بعدد الصفحات
                is_scanned = page_count > 0 and len(extracted.strip()) < MIN_CHARS_PER_PAGE * page_count

                if is_scanned:
                    if ocr_available():
                        st.info(f"🔍 `{file.name}` يبدو ممسوحاً ضوئياً — جاري تشغيل OCR ({page_count} صفحة)...")
                        try:
                            extracted = _ocr_pdf(raw, file.name)
                            st.success(f"✅ اكتمل OCR لـ `{file.name}` — {len(extracted):,} حرف.")
                        except Exception as ocr_err:
                            st.error(f"❌ فشل OCR لـ `{file.name}`: {ocr_err}")
                    else:
                        st.error(
                            f"🚨 `{file.name}` ملف PDF ممسوح ضوئياً ولم يُستخرَج منه نص يُذكر "
                            f"({len(extracted.strip()):,} حرف من {page_count} صفحة). "
                            "**سيُحلَّل هذا الملف ناقصاً.** لتفعيل OCR ثبّت: "
                            "`pip install pytesseract pdf2image` + حزمة النظام "
                            "`tesseract-ocr tesseract-ocr-ara poppler-utils`."
                        )

                text_parts.append(f"\n\n=== {file.name} ===\n" + extracted)

            elif ext in ("docx", "doc"):
                import docx2txt
                text_parts.append(f"\n\n=== {file.name} ===\n" + docx2txt.process(file))

            elif ext in ("xlsx", "xls"):
                df = pd.read_excel(file)
                text_parts.append(f"\n\n=== {file.name} (Excel) ===\n" + df.to_string(index=False))

            elif ext == "csv":
                df = pd.read_csv(file)
                text_parts.append(f"\n\n=== {file.name} (CSV) ===\n" + df.to_string(index=False))

            elif ext in ("html", "htm"):
                from bs4 import BeautifulSoup
                content = file.getvalue().decode("utf-8", errors="replace")
                soup = BeautifulSoup(content, "html.parser")
                text_parts.append(f"\n\n=== {file.name} (HTML) ===\n" + soup.get_text(separator="\n"))

            elif ext == "txt":
                content = file.getvalue().decode("utf-8", errors="replace")
                text_parts.append(f"\n\n=== {file.name} ===\n" + content)

            elif ext in ("png", "jpg", "jpeg", "gif", "webp"):
                text_parts.append(f"\n\n=== {file.name} ===\n[صورة — لا يمكن استخراج النص منها تلقائياً]")

            else:
                text_parts.append(f"\n\n=== {file.name} ===\n[تنسيق غير مدعوم: .{ext}]")

        except Exception as e:
            st.warning(f"⚠️ فشل قراءة `{file.name}`: {e}")
            text_parts.append(f"\n\n=== {file.name} ===\n[فشل الاستخراج: {e}]")

    return "\n".join(text_parts).strip(), file_names


def build_word_document(
    company_name: str,
    sections: dict,
    template_bytes: Optional[bytes] = None,
    include_flags: Optional[dict] = None,
    cover_template_text: str = "",
    df_compliance: Optional[pd.DataFrame] = None,
    df_boq: Optional[pd.DataFrame] = None,
) -> BytesIO:
    """
    Build a Word document from the provided sections.
    If template_bytes is provided, injects into the existing template.
    Returns a BytesIO buffer.
    """
    from docx import Document
    from docx.shared import Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    import datetime

    if template_bytes:
        doc = Document(BytesIO(template_bytes))
        # Add page break after template content if it has content
        if len(doc.paragraphs) > 0:
            doc.add_page_break()
    else:
        doc = Document()
        # Page margins
        for section in doc.sections:
            section.top_margin = Cm(2.5)
            section.bottom_margin = Cm(2.5)
            section.left_margin = Cm(3)
            section.right_margin = Cm(3)

    flags = include_flags or {}

    # Helper: add styled heading
    def add_heading(text, level=1):
        h = doc.add_heading(text, level=level)
        h.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        for run in h.runs:
            run.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
        return h

    # Helper: add paragraph
    def add_para(text, bold=False):
        if not text or not text.strip():
            return
        p = doc.add_paragraph(text.strip())
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        if bold:
            for run in p.runs:
                run.bold = True

    # ── Title Page ────────────────────────────────────────────────────────────
    title = doc.add_heading(f"العرض الفني", 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if company_name:
        sub = doc.add_paragraph(f"مقدَّم من: {company_name}")
        sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_p = doc.add_paragraph(f"التاريخ: {datetime.date.today().strftime('%Y/%m/%d')}")
    date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_page_break()

    # ── Cover Letter ──────────────────────────────────────────────────────────
    if flags.get("cover"):
        add_heading("خطاب التقديم", 1)
        use_template = sections.get("cover_use_template", True)
        cover_text = cover_template_text if use_template else sections.get("cover", "")
        add_para(cover_text or "[يرجى إضافة نص الخطاب]")
        doc.add_page_break()

    # ── Confidentiality Notice ────────────────────────────────────────────────
    if flags.get("docinfo"):
        add_heading("معلومات المستند وإشعار السرية", 1)
        add_para(
            f"هذا المستند سري للغاية ومُعدّ حصرياً للجهة المُرسَل إليها.\n"
            f"الشركة المُقدِّمة: {company_name}\n"
            f"يُحظر توزيع هذا المستند أو إعادة إنتاجه دون إذن كتابي مسبق.",
        )
        doc.add_page_break()

    # ── Exec Summary ─────────────────────────────────────────────────────────
    if flags.get("exec") and sections.get("exec"):
        add_heading("الملخص التنفيذي", 1)
        add_para(sections["exec"])
        doc.add_page_break()

    # ── Scope ─────────────────────────────────────────────────────────────────
    if flags.get("scope") and sections.get("scope"):
        add_heading("فهم النطاق والمتطلبات", 1)
        add_para(sections["scope"])
        doc.add_page_break()

    # ── Methodology ──────────────────────────────────────────────────────────
    if flags.get("methodology") and sections.get("methodology"):
        add_heading("المنهجية الفنية والحل المقترح", 1)
        add_para(sections["methodology"])
        doc.add_page_break()

    # ── Governance / SLAs ─────────────────────────────────────────────────────
    if flags.get("gov") and sections.get("gov"):
        add_heading("حوكمة المشروع ومستويات الخدمة (SLAs)", 1)
        add_para(sections["gov"])
        doc.add_page_break()

    # ── Project Plan ─────────────────────────────────────────────────────────
    if flags.get("plan") and sections.get("plan"):
        add_heading("خطة المشروع والجدول الزمني", 1)
        add_para(sections["plan"])
        doc.add_page_break()

    # ── Team ─────────────────────────────────────────────────────────────────
    if flags.get("team") and sections.get("team"):
        add_heading("هيكلة الفريق والسير الذاتية", 1)
        add_para(sections["team"])
        doc.add_page_break()

    # ── External Requirements ─────────────────────────────────────────────────
    if flags.get("external") and sections.get("external"):
        add_heading("المتطلبات الخارجية والضمانات", 1)
        add_para(sections["external"])
        doc.add_page_break()

    # ── Compliance Matrix Table ───────────────────────────────────────────────
    if flags.get("compliance_table") and df_compliance is not None and not df_compliance.empty:
        add_heading("جدول الامتثال بالمواصفات", 1)
        cols = list(df_compliance.columns)
        table = doc.add_table(rows=1, cols=len(cols))
        table.style = "Light Shading Accent 1"
        hdr_cells = table.rows[0].cells
        for i, col in enumerate(cols):
            hdr_cells[i].text = col
        for _, row in df_compliance.iterrows():
            row_cells = table.add_row().cells
            for i, val in enumerate(row):
                row_cells[i].text = str(val) if val else ""
        doc.add_paragraph()

    # ── BOQ Table ─────────────────────────────────────────────────────────────
    if flags.get("boq_table") and df_boq is not None and not df_boq.empty:
        add_heading("جدول الكميات (BOQ)", 1)
        cols = list(df_boq.columns)
        table = doc.add_table(rows=1, cols=len(cols))
        table.style = "Light Shading Accent 1"
        hdr_cells = table.rows[0].cells
        for i, col in enumerate(cols):
            hdr_cells[i].text = col
        for _, row in df_boq.iterrows():
            row_cells = table.add_row().cells
            for i, val in enumerate(row):
                row_cells[i].text = str(val) if val else ""

    bio = BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio
