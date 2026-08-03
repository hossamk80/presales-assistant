"""
utils/retrieval.py — استرجاع لفظي من الكراسة بلا استدعاء ولا تضمين.

كتابة قسم «الالتزام بالمحتوى المحلي» لا تحتاج مئتي صفحة عن مواصفات الكابلات
ومدة الضمان وشروط الدفع. تحتاج البنود التي تتكلّم عن المحتوى المحلي. ومع ذلك
كان النظام يمرّر الكراسة **كاملة** في كل استدعاء: عشرات الاستدعاءات × مئات
الآلاف من التوكن، أكثرها لا صلة له بالقسم الجاري كتابته.

هذه الوحدة تُقطّع الكراسة على حدود بنودها وتُرتّب المقاطع بـ BM25 — خوارزمية
ترجيح لفظي معروفة، حسابية بحتة: **بلا شبكة، بلا مفتاح، بلا كلفة**. مستودع
المعرفة يستعمل التضمين لأنه يبحث في مستندات الشركة عن معنى مشابه؛ هنا نبحث في
وثيقة واحدة عن ألفاظها هي، واللفظ يكفي.

**حدّ الاستعمال**: الاسترجاع للكتابة والمساعدة، **لا للاستخراج الأول**. مصفوفة
الامتثال ومستندات المظروف تُبنى على النص الكامل — متطلب لا يصل إلى النموذج لا
يظهر في المصفوفة، ولا يعوّضه أي توفير.
"""
import math
import re
from collections import Counter
from typing import Optional

# حجم المقطع المستهدف. أصغر من ذلك يقطع البند عن شرطه، وأكبر يُدخل حشواً.
TARGET_CHUNK_CHARS = 1200
MAX_CHUNK_CHARS = 2200

# معاملات BM25 القياسية
_K1 = 1.5
_B = 0.75

# كلمات لا تميّز مقطعاً عن آخر في كراسة شروط — ترد في كل بند تقريباً.
_STOPWORDS = {
    "على", "في", "من", "الى", "إلى", "عن", "مع", "أن", "ان", "التي", "الذي",
    "هذا", "هذه", "ذلك", "كل", "بما", "وفق", "حسب", "يجب", "يكون", "تكون",
    "المورد", "المتعهد", "الشركة", "الجهة", "العقد", "المشروع", "البند",
    "and", "the", "for", "with", "shall", "must", "any", "all", "this", "that",
}

# بداية بند مرقّم: "5-2" أو "5.2.1" أو "المادة الثالثة" أو "أولاً:"
_CLAUSE_START_RE = re.compile(
    r"^\s*(?:"
    r"\d+(?:[.\-/]\d+){0,3}\s*[-:.)]?\s+"
    r"|(?:المادة|البند|الفصل|الملحق)\s+"
    r"|(?:أولاً|ثانياً|ثالثاً|رابعاً|خامساً|سادساً|سابعاً|ثامناً|تاسعاً|عاشراً)\s*[:.\-]"
    r"|#{1,6}\s+"
    r")",
)

_TOKEN_RE = re.compile(r"[\w؀-ۿ]+", re.UNICODE)
_DIACRITICS = re.compile(r"[ً-ْـ]")


def tokenize(text: str) -> list:
    """كلمات دالّة مُوحّدة الإملاء — الهمزات والتاء المربوطة تُكتب بصيغ شتى."""
    normalized = _DIACRITICS.sub("", str(text or "").lower())
    normalized = (normalized.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
                  .replace("ة", "ه").replace("ى", "ي"))
    return [
        w for w in _TOKEN_RE.findall(normalized)
        if len(w) > 2 and w not in _STOPWORDS
    ]


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.؟!؛])\s+")


def _explode_long_lines(lines: list, maximum: int) -> list:
    """
    يفتّت الأسطر الأطول من الحد على حدود الجُمل.

    استخراج الـ PDF كثيراً ما يُخرج الصفحة كلها سطراً واحداً بلا فواصل أسطر.
    والتقطيع على الأسطر وحدها يُنتج حينها مقطعاً بحجم الصفحة، فيتجاوز أي سقف
    سياق ويسقط من الاختيار — أي أن الاسترجاع يتعطّل صامتاً على الملفات التي
    نحتاجه فيها أكثر.
    """
    out = []
    for line in lines:
        if len(line) <= maximum:
            out.append(line)
            continue
        buffer = ""
        for sentence in _SENTENCE_SPLIT_RE.split(line):
            if buffer and len(buffer) + len(sentence) + 1 > maximum:
                out.append(buffer.strip())
                buffer = sentence
            else:
                buffer = f"{buffer} {sentence}".strip() if buffer else sentence
        if buffer.strip():
            out.append(buffer.strip())
    return out


def split_clauses(text: str,
                  target: int = TARGET_CHUNK_CHARS,
                  maximum: int = MAX_CHUNK_CHARS) -> list:
    """
    يقطّع الكراسة على **حدود بنودها** لا على عدد أحرف أعمى.

    القطع الأعمى يفصل الشرط عن رقمه فيضيع مرجع البند، وهو أهم ما يُستشهد به
    في مصفوفة الامتثال.
    """
    lines = str(text or "").replace("\r\n", "\n").split("\n")
    lines = _explode_long_lines(lines, maximum)
    chunks, current = [], []
    size = 0

    def flush():
        nonlocal current, size
        body = "\n".join(current).strip()
        if body:
            chunks.append(body)
        current, size = [], 0

    for line in lines:
        starts_clause = bool(_CLAUSE_START_RE.match(line))
        # نبدأ مقطعاً جديداً عند بند جديد متى بلغ الحالي حجمه المستهدف
        if current and starts_clause and size >= target:
            flush()
        elif size >= maximum:
            flush()
        current.append(line)
        size += len(line) + 1

    flush()
    return chunks


class Index:
    """فهرس BM25 على مقاطع وثيقة واحدة. يُبنى مرة ويُستعلَم مراراً."""

    def __init__(self, chunks: list):
        self.chunks = list(chunks or [])
        self.tokens = [tokenize(c) for c in self.chunks]
        self.lengths = [len(t) for t in self.tokens]
        self.avg_length = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        self.frequencies = [Counter(t) for t in self.tokens]

        document_count = Counter()
        for token_set in (set(t) for t in self.tokens):
            document_count.update(token_set)
        total = max(1, len(self.chunks))
        self.idf = {
            term: math.log(1 + (total - n + 0.5) / (n + 0.5))
            for term, n in document_count.items()
        }

    def __len__(self) -> int:
        return len(self.chunks)

    def score(self, query_tokens: list, index: int) -> float:
        if not self.avg_length:
            return 0.0
        frequencies = self.frequencies[index]
        length = self.lengths[index] or 1
        total = 0.0
        for term in query_tokens:
            frequency = frequencies.get(term, 0)
            if not frequency:
                continue
            idf = self.idf.get(term, 0.0)
            denominator = frequency + _K1 * (1 - _B + _B * length / self.avg_length)
            total += idf * (frequency * (_K1 + 1)) / denominator
        return total

    def search(self, query: str, top_k: int = 8) -> list:
        """يُرجع [{"index", "text", "score"}] مرتّبة تنازلياً، بلا صفريّ الدرجة."""
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        scored = [
            {"index": i, "text": self.chunks[i], "score": self.score(query_tokens, i)}
            for i in range(len(self.chunks))
        ]
        scored = [s for s in scored if s["score"] > 0]
        scored.sort(key=lambda s: s["score"], reverse=True)
        return scored[:top_k]


def focused_context(text: str, query: str, budget_chars: int = 12000,
                    top_k: int = 12) -> tuple[str, dict]:
    """
    مقاطع الكراسة الأوثق صلة بالاستعلام، ضمن سقف أحرف.

    Returns:
        (النص المُركَّز، إحصاءات: الأحرف قبل وبعد والمقاطع المختارة).

    يُرجع النص الأصلي كما هو إن كان أصلاً دون السقف — لا فائدة من الاسترجاع
    حينها، والمخاطرة بإسقاط بند بلا مقابل.
    """
    body = str(text or "")
    stats = {"before": len(body), "after": len(body), "chunks": 0,
             "selected": 0, "applied": False}
    if not body.strip() or len(body) <= budget_chars:
        return body, stats

    chunks = split_clauses(body)
    stats["chunks"] = len(chunks)
    if len(chunks) < 2:
        return body, stats

    hits = Index(chunks).search(query, top_k=top_k)
    if not hits:
        return body, stats

    # نُعيد ترتيب المختار بترتيبه في الوثيقة: البنود تُقرأ متسلسلة، وخلطها
    # يجعل الشرط يسبق سياقه.
    picked, used = [], 0
    for hit in hits:
        if used + len(hit["text"]) > budget_chars:
            continue
        picked.append(hit)
        used += len(hit["text"])
    if not picked:
        return body, stats

    picked.sort(key=lambda h: h["index"])
    focused = "\n\n[…]\n\n".join(h["text"] for h in picked)

    stats.update({"after": len(focused), "selected": len(picked), "applied": True})
    return focused, stats


def build_index(text: str) -> Optional[Index]:
    chunks = split_clauses(text)
    return Index(chunks) if chunks else None
