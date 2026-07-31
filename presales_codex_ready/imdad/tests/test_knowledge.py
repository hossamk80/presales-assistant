"""اختبارات تقسيم النصوص وحساب التشابه في مستودع المعرفة."""
import pytest


@pytest.fixture()
def k():
    from utils import knowledge
    return knowledge


def test_chunk_short_text_stays_whole(k):
    assert k.chunk_text("نص قصير") == ["نص قصير"]


def test_chunk_empty(k):
    assert k.chunk_text("") == []
    assert k.chunk_text("   \n  ") == []


@pytest.mark.parametrize("text,size,overlap", [
    ("\n\n".join(f"فقرة رقم {i} فيها كلام كافٍ." for i in range(120)), 800, 150),
    ("ا" * 7000, 800, 150),
    ("ب" * 800, 800, 150),
    ("ج" * 801, 800, 150),
    ("\n\n".join(["د" * 700, "ه" * 700, "و" * 10]), 800, 150),
])
def test_chunk_bounded_and_terminating(k, text, size, overlap):
    """
    كل مقطع ضمن الحجم، والعدد معقول.

    كان الذيل الأقصر من التداخل يجعل التقدّم سالباً فيزحف المؤشر حرفاً حرفاً
    وينتج مئات الشظايا — هذا الاختبار يحرس ضد عودة تلك الحالة.
    """
    chunks = k.chunk_text(text, size=size, overlap=overlap)
    assert chunks, "لا يجوز أن يعود التقسيم فارغاً لنص غير فارغ"
    assert all(len(c) <= size for c in chunks)
    upper_bound = len(text) // (size - overlap) + 3
    assert len(chunks) <= upper_bound, f"عدد مقاطع مفرط: {len(chunks)} > {upper_bound}"


def test_chunk_covers_all_content(k):
    text = "\n\n".join(f"فقرة رقم {i} فيها كلام." for i in range(300))
    joined = "".join(k.chunk_text(text, size=900, overlap=120))
    assert all(f"فقرة رقم {i} " in joined for i in range(300))


def test_normalize_unit_length(k):
    v = k._normalize([3.0, 4.0, 0.0])
    assert pytest.approx(sum(x * x for x in v) ** 0.5, abs=1e-6) == 1.0
    assert pytest.approx(k._dot(v, v), abs=1e-6) == 1.0


def test_normalize_handles_zero_vector(k):
    assert k._normalize([0.0, 0.0]) == [0.0, 0.0]


def test_orthogonal_vectors_have_zero_similarity(k):
    a = k._normalize([1.0, 0.0, 0.0])
    b = k._normalize([0.0, 0.0, 1.0])
    assert pytest.approx(k._dot(a, b), abs=1e-6) == 0.0


def test_pack_unpack_roundtrip(k):
    v = k._normalize([0.3, -0.7, 0.2, 0.9])
    out = k._unpack(k._pack(v), 4)
    assert all(pytest.approx(a, abs=1e-6) == b for a, b in zip(v, out))


def test_search_returns_empty_without_documents(k, temp_db):
    assert k.search("أي استعلام") == []


def test_build_context_empty_when_nothing_relevant(k, temp_db, monkeypatch):
    monkeypatch.setattr(k, "embed_texts", lambda texts, task_type: None)
    assert k.build_context("استعلام") == ""
