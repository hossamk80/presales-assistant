"""
utils/knowledge.py — مستودع معرفة الشركة + فهرسة الكراسة (استرجاع بالتضمين)

- مستودع الشركة: تُستخرَج نصوص المستندات وتُقسَّم وتُضمَّن وتُخزَّن، ثم
  يُسترجَع منها ما يخصّ القسم الجاري كتابته ويُحقن في التعليمات.
- موفّر التضمين منفصل عن موفّر النص (11-6): تغيير نموذج التضمين يُبطل
  المتجهات المخزَّنة، فتُحسب المقاطع المعطَّلة صراحةً وتُعاد فهرستها بزر.
- فهرسة الكراسة (11-11): تُقسَّم الكراسة وتُضمَّن في الجلسة، فيُمرَّر للقسم
  ما يخصّه من بنودها بدل النص الكامل.
"""
import hashlib
import struct
import streamlit as st
from typing import Optional

from utils import db, providers
from utils.i18n import t
from utils.providers import BudgetExceeded, ProviderError

# نقتطع المتجه إلى 768 بُعداً (النماذج تدعم الاقتطاع مع إعادة التطبيع)
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

# مقاطع الكراسة المسترجعة لكل قسم — أكثر من المستودع لأنها مصدر المتطلبات
RFP_TOP_K = 8


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
    يحوّل نصوصاً إلى متجهات مُطبَّعة عبر موفّر التضمين النشط.
    task_type: RETRIEVAL_DOCUMENT عند الفهرسة · RETRIEVAL_QUERY عند البحث.
    """
    if not texts:
        return None
    try:
        vectors, _usage, _model = providers.embed(texts, task_type, EMBED_DIMS)
    except BudgetExceeded as e:
        st.error(f"🛑 {e}")
        return None
    except ProviderError as e:
        if str(e) == "missing_key":
            st.error(t("eng.key_missing"))
        else:
            st.error(t("kb.embed_failed", error=e))
        return None
    except Exception as e:
        st.error(t("kb.embed_failed", error=e))
        return None
    # الاقتطاع يُبطل التطبيع، فنعيده حتى يصح الجداء القياسي كتشابه جيبي
    return [_normalize(list(v)) for v in vectors]


def active_embed_model() -> str:
    return providers.active_embed_signature()


def ingest_file(file, category: str) -> Optional[int]:
    """
    يستخرج نص ملف ويقسّمه ويضمّنه ويخزّنه.
    يُرجع عدد المقاطع المخزّنة، أو None عند الفشل.
    """
    from utils.file_handler import _extract_single

    text = _extract_single(file).strip()

    if not text:
        st.warning(t("kb.no_text", name=file.name))
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
        embed_model=active_embed_model(),
    )
    return len(chunks)


def stale_chunk_count() -> int:
    """المقاطع المفهرسة بنموذج تضمين غير النشط — معطَّلة عن البحث (11-6)."""
    return db.kb_stale_chunk_count(active_embed_model())


def reindex_all() -> Optional[int]:
    """
    يعيد تضمين كل مقاطع المستودع بنموذج التضمين النشط.
    يُرجع عدد المقاطع المُحدَّثة أو None عند الفشل.
    """
    rows = db.kb_chunk_texts()
    if not rows:
        return 0

    updated = 0
    batch = 32
    for start in range(0, len(rows), batch):
        part = rows[start:start + batch]
        vectors = embed_texts([r["text"] for r in part],
                              task_type="RETRIEVAL_DOCUMENT")
        if vectors is None:
            return None
        db.update_kb_chunk_embeddings(
            [(r["id"], EMBED_DIMS, _pack(v)) for r, v in zip(part, vectors)],
            embed_model=active_embed_model(),
        )
        updated += len(part)
    return updated


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

    current_model = active_embed_model()
    scored = []
    for row in rows:
        if row["dims"] != len(q):
            # مقاطع فُهرست بأبعاد مختلفة — تُتجاهَل بدل إعطاء نتيجة خاطئة
            continue
        if (row.get("embed_model") or "") not in ("", current_model):
            # فُهرست بنموذج آخر: التشابه بين فضاءين مختلفين بلا معنى
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


# ─── فهرسة الكراسة واسترجاعها (11-11) ────────────────────────────────────────
#
# الفهرس يعيش في الجلسة: الكراسة نصّها موجود أصلاً في session_state، وما
# نضيفه هو متجهات مقاطعها. البصمة تضمن إعادة الفهرسة عند تغيّر النص أو
# نموذج التضمين فقط — لا مع كل استدعاء.


def _rfp_fingerprint(text: str) -> str:
    payload = f"{active_embed_model()}|{len(text)}|{text[:2000]}|{text[-2000:]}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def index_rfp(text: str) -> bool:
    """يفهرس نص الكراسة في الجلسة. يُرجع True عند توفّر فهرس صالح."""
    text = (text or "").strip()
    if not text:
        return False

    fp = _rfp_fingerprint(text)
    index = st.session_state.get("_rfp_index") or {}
    if index.get("fingerprint") == fp and index.get("entries"):
        return True

    chunks = chunk_text(text)
    if not chunks:
        return False
    vectors = embed_texts(chunks, task_type="RETRIEVAL_DOCUMENT")
    if vectors is None:
        return False

    st.session_state["_rfp_index"] = {
        "fingerprint": fp,
        "entries": list(zip(chunks, vectors)),
    }
    return True


def rfp_index_ready(text: str) -> bool:
    index = st.session_state.get("_rfp_index") or {}
    return bool(index.get("entries")) and \
        index.get("fingerprint") == _rfp_fingerprint((text or "").strip())


def rfp_retrieve(query: str, top_k: int = RFP_TOP_K) -> list:
    """المقاطع الأقرب من الكراسة المفهرسة للاستعلام المعطى."""
    index = st.session_state.get("_rfp_index") or {}
    entries = index.get("entries") or []
    if not entries or not query.strip():
        return []

    vectors = embed_texts([query], task_type="RETRIEVAL_QUERY")
    if not vectors:
        return []
    q = vectors[0]

    scored = [(text, _dot(q, vec)) for text, vec in entries]
    scored.sort(key=lambda r: r[1], reverse=True)
    return [text for text, score in scored[:top_k] if score >= MIN_SIMILARITY]


def rfp_context_block(query: str, top_k: int = RFP_TOP_K) -> str:
    """بنود الكراسة ذات الصلة كمقطع سياق جاهز للحقن — بدل النص الكامل."""
    hits = rfp_retrieve(query, top_k=top_k)
    if not hits:
        return ""
    return (
        "\n\n--- بنود كراسة الشروط ذات الصلة بهذا القسم (مسترجعة آلياً) ---\n"
        + "\n\n---\n".join(hits)
    )
