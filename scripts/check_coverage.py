#!/usr/bin/env python3
"""
فحص أرضيات التغطية لكل طبقة / per-layer coverage floors.

**رقمٌ عامٌّ واحد لا يكفي.** طبقات هذا النظام تختلف اختلافاً أصيلاً: منطقٌ
خالص في `utils/` يُفحَص بلا واجهة، وشاشات في `views/` يصعب فحصها آلياً.
أرضيةٌ عامةٌ واحدة تجعل ارتفاع `views` يغطّي انخفاض `utils` — فيُرى الرقم
مستقراً والمنطق يتعرّى.

الأرضيات **مقيسة لا مُقدَّرة**: قُرئت من تشغيل فعليّ ثم أُنزلت قليلاً
لتحتمل تذبذباً، فهي تمنع الانحدار ولا تَعِد بما ليس قائماً.

الاستعمال: بعد `pytest --cov-report=json:coverage.json`
    python scripts/check_coverage.py [coverage.json]
"""
import json
import pathlib
import sys

# (اسم الطبقة, الأرضية %, المقيس وقت الضبط) — والتعليق يقول لماذا الرقم هكذا
FLOORS = (
    # المنطق الخالص: هنا تعني التغطية شيئاً، وهنا تُشدّ الأرضية
    ("utils",           85, 89, "منطق بلا واجهة — لا عذر لانخفاضه"),
    ("utils/db",        85, 90, "طبقة التخزين: كل استعلام يمسّ بيانات عطاء"),
    ("app.py",          90, 96, "الإقلاع والتوجيه — صغير ومفحوص بالكامل تقريباً"),
    # طبقتان أدنى بطبيعتهما، والأرضية تعترف بذلك بلا أن تُسقطها
    ("components",      60, 66, "مكوّنات واجهة — تُفحَص بالمخرَج لا بالنقر"),
    ("views",           48, 52, "شاشات Streamlit: الفحص الآلي لها أغلى وأضعف"),
    ("utils/providers", 58, 63, "استدعاء خارجي: المحاكاة تغطّي العقد لا الشبكة"),
)

GLOBAL_FLOOR = 71   # المقيس وقت الضبط: 73.4%

# **الأرضية تُشدّ مع كل ارتفاع.** `utils/providers` ارتفعت من ٥٠٪ إلى ٦٣٪
# بعد فحص موفّر Anthropic (ب-2)، فشُدّت أرضيتها من ٤٥ إلى ٥٨: أرضيةٌ تبقى
# حيث كانت تسمح للمكسوب أن يتسرّب صامتاً.


def layer_of(path: str) -> str:
    if path == "app.py":
        return "app.py"
    if path.startswith("utils/db/"):
        return "utils/db"
    if path.startswith("utils/providers/"):
        return "utils/providers"
    return path.split("/")[0]


def main() -> int:
    report = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "coverage.json")
    if not report.exists():
        print(f"❌ لا تقرير تغطية في {report} — هل شُغّل pytest بـ --cov؟")
        return 1

    data = json.loads(report.read_text(encoding="utf-8"))
    totals = {}
    for path, entry in data["files"].items():
        summary = entry["summary"]
        statements, covered = totals.setdefault(layer_of(path), [0, 0])
        totals[layer_of(path)] = [
            statements + summary["num_statements"],
            covered + summary["covered_lines"],
        ]

    failures = []
    print(f"{'الطبقة':18} {'%':>6} {'الأرضية':>8}")
    print("─" * 36)
    for layer, floor, measured, _why in FLOORS:
        statements, covered = totals.get(layer, [0, 0])
        if not statements:
            failures.append(f"{layer}: لا ملف واحد — هل تغيّر مسار الطبقة؟")
            continue
        percent = 100 * covered / statements
        mark = "✅" if percent >= floor else "❌"
        print(f"{layer:18} {percent:5.1f}% {floor:7}% {mark}")
        if percent < floor:
            failures.append(
                f"{layer}: {percent:.1f}% دون الأرضية {floor}% "
                f"(كانت {measured}% وقت الضبط)"
            )

    overall = data["totals"]["percent_covered"]
    print("─" * 36)
    print(f"{'الإجمالي':18} {overall:5.1f}% {GLOBAL_FLOOR:7}%")
    if overall < GLOBAL_FLOOR:
        failures.append(f"الإجمالي {overall:.1f}% دون {GLOBAL_FLOOR}%")

    # طبقةٌ جديدة لا تذكرها `FLOORS` تمرّ بلا أرضية — وهو ثلمٌ في الفحص
    unknown = sorted(set(totals) - {name for name, *_ in FLOORS})
    if unknown:
        failures.append(
            "طبقات بلا أرضية معلَنة (أضِفها إلى FLOORS): " + ", ".join(unknown)
        )

    if failures:
        print("\n".join(["", "❌ انحدار في التغطية:"] + [f"   · {f}" for f in failures]))
        return 1

    print("\n✅ كل طبقة فوق أرضيتها")
    return 0


if __name__ == "__main__":
    sys.exit(main())
