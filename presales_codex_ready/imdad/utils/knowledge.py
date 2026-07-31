"""
utils/knowledge.py — مستودع معرفة الشركة (استرجاع بالتضمين)

حقول رفع السير الذاتية والشهادات والمشاريع السابقة كانت معطّلة ولا تُغذّي
النموذج بشيء. هنا تُستخرَج نصوصها وتُقسَّم وتُضمَّن وتُخزَّن، ثم يُسترجَع منها
ما يخصّ القسم الجاري كتابته ويُحقن في التعليمات — فيخرج العرض مبنياً على
مشاريع الشركة وخبراتها الحقيقية لا على محتوى عام.
"""
import struct
import streamlit as st
from typing import Optional

from utils import db
from utils.ai_engine import get_client

EMBED_MODEL = "gemini-embedding-001"

# نقتطع المتجه إلى 768 بُعداً (النموذج يدعم الاقتطاع مع إعادة التطبيع)
# لتقليل حجم التخزين دون خسارة تُذكر في جودة الاسترجاع.
EMBED_DIMS = 768

CHUNK_CHARS = 1800
CHUNK_OVERLAP = 200

CATEGORIES = {
    "cv": "السير الذاتية",
    "cert": "الشهادات والاعتمادات",
    "project": "المشاريع السابقة",
    "other": "مستندات أخرى",
}

# أقصى عدد مقاطع تُحقن في تعليمات توليد قسم واحد
DEFAULT_TOP_K = 6
# أدنى تشابه يُعتد به — دون ذلك يُرجَّح أن المقطع غير ذي صلة
MIN_SIMILARITY = 0.35


def _pack(vector: list) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def _unpack(blob: bytes, dims: int) -> list:
    return list(struct.unpack(f"{dims}f", blob))


def _normalize(vector: list) -> list:
    norm = sum(v * v for v in vector) ** 0.5
    return [v / norm for v in vector] if norm else vector


def _dot(a: list, b: list) -> float:
    return sum(x * y for x, y in zip(a, b))


def chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list:
    """تقسيم بتداخل بسيط حتى لا تنقطع المعلومة على حدود المقاطع."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]

    total = len(text)
    chunks, start = [], 0
    while start < total:
        end = min(start + size, total)
        window = text[start:end]

        if end < total:
            # اقطع على حدود فقرة أو سطر إن أمكن
            cut = max(window.rfind("\n\n"), window.rfind("\n"))
            if cut > size * 0.6:
                window = window[:cut]
                end = start + cut

        chunk = window.strip()
        if chunk:
            chunks.append(chunk)

        # التوقف عند نهاية النص. بدونها ينكمش المقطع الأخير دون حجم التداخل
        # فيصير التقدّم سالباً ويزحف المؤشر حرفاً حرفاً منتجاً مئات الشظايا.
        if end >= total:
            break
        start = max(end - overlap, start + 1)

    return chunks


def embed_texts(texts: list, task_type: str) -> Optional[list]:
    """
    يحوّل نصوصاً إلى متجهات مُطبَّعة.
    task_type: RETRIEVAL_DOCUMENT عند الفهرسة · RETRIEVAL_QUERY عند البحث.
    """
    client = get_client()
    if client is None or not texts:
        return None
    try:
        from google.genai import types

        response = client.models.embed_content(
            model=EMBED_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=EMBED_DIMS,
            ),
        )
        # الاقتطاع يُبطل التطبيع، فنعيده حتى يصح الجداء القياسي كتشابه جيبي
        return [_normalize(list(e.values)) for e in response.embeddings]
    except Exception as e:
        st.error(f"❌ تعذّر توليد متجهات التضمين: {e}")
        return None


def ingest_file(file, category: str) -> Optional[int]:
    """
    يستخرج نص ملف ويقسّمه ويضمّنه ويخزّنه.
    يُرجع عدد المقاطع المخزّنة، أو None عند الفشل.
    """
    from utils.file_handler import _extract_single

    text = _extract_single(file).strip()

    if not text:
        st.warning(f"⚠️ لم يُستخرج نص من `{file.name}` — لم يُضَف للمستودع.")
        return None

    chunks = chunk_text(text)
    if not chunks:
        return None

    vectors = embed_texts(chunks, task_type="RETRIEVAL_DOCUMENT")
    if vectors is None:
        return None

    doc_id = db.add_kb_document(file.name, category, len(text))
    db.add_kb_chunks(
        doc_id,
        [(i, chunk, EMBED_DIMS, _pack(vec))
         for i, (chunk, vec) in enumerate(zip(chunks, vectors))],
    )
    return len(chunks)


def search(query: str, top_k: int = DEFAULT_TOP_K,
           categories: Optional[list] = None) -> list:
    """
    يبحث في المستودع عن المقاطع الأقرب للاستعلام.
    يُرجع [{text, doc_name, category, score}] مرتّبة تنازلياً.
    """
    rows = db.all_kb_chunks(categories)
    if not rows:
        return []

    vectors = embed_texts([query], task_type="RETRIEVAL_QUERY")
    if not vectors:
        return []
    q = vectors[0]

    scored = []
    for row in rows:
        if row["dims"] != len(q):
            # مقاطع فُهرست بأبعاد مختلفة — تُتجاهَل بدل إعطاء نتيجة خاطئة
            continue
        score = _dot(q, _unpack(row["embedding"], row["dims"]))
        if score >= MIN_SIMILARITY:
            scored.append({
                "text": row["text"],
                "doc_name": row["doc_name"],
                "category": row["category"],
                "score": score,
            })

    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:top_k]


def build_context(query: str, top_k: int = DEFAULT_TOP_K,
                  categories: Optional[list] = None) -> str:
    """
    يبني مقطع سياق جاهزاً للحقن في التعليمات.
    يُرجع نصاً فارغاً إن لم يوجد ما يخص الاستعلام.
    """
    hits = search(query, top_k=top_k, categories=categories)
    if not hits:
        return ""

    parts = [
        f"[{CATEGORIES.get(h['category'], h['category'])} — {h['doc_name']}]\n{h['text']}"
        for h in hits
    ]
    return (
        "\n\n--- من مستودع معرفة الشركة (معلومات حقيقية موثّقة، استند إليها "
        "ولا تخترع غيرها) ---\n" + "\n\n".join(parts)
    )


def is_populated() -> bool:
    return db.kb_stats().get("chunks", 0) > 0
