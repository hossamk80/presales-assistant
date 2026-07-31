{ pkgs }: {
  deps = [
    pkgs.python311
    pkgs.python311Packages.pip

    # ─── حزم نظام لازمة لميزات اختيارية ───────────────────────────────
    # OCR للكراسات الممسوحة ضوئياً (كثير من ملفات اعتماد صور بلا طبقة نص)
    pkgs.tesseract
    pkgs.poppler_utils

    # خط يدعم الحروف العربية — يحتاجه تصدير PDF.
    # بدونه يرفض بنّاء الـ PDF العمل برسالة صريحة بدل إخراج ملف مشوّه.
    pkgs.dejavu_fonts

    # مطلوبة لبناء بعض عجلات Python الثنائية
    pkgs.glibcLocales
    pkgs.libxml2
    pkgs.libxslt
  ];

  env = {
    # tesseract يبحث عن بيانات اللغات هنا (بما فيها العربية)
    TESSDATA_PREFIX = "${pkgs.tesseract}/share/tessdata";
    LANG = "en_US.UTF-8";
    LOCALE_ARCHIVE = "${pkgs.glibcLocales}/lib/locale/locale-archive";
  };
}
