"""
utils/db/usage.py — قياس الاستهلاك (11-7 / 11-8) وذاكرة نتائج الاستدعاءات (11-13).
"""

from typing import Any, Optional

from ._core import _now, get_conn, transaction


# ─── قياس الاستهلاك (11-7 / 11-8) ────────────────────────────────────────────


def log_ai_usage(project_id, project_name: str, task: str, provider: str,
                 model: str, input_tokens: int, cached_tokens: int,
                 output_tokens: int, cost: float, elapsed_ms: int,
                 status: str, month: str):
    with transaction() as conn:
        conn.execute(
            "INSERT INTO ai_usage (created_at, month, project_id, project_name, "
            "task, provider, model, input_tokens, cached_tokens, output_tokens, "
            "cost, elapsed_ms, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (_now(), month, project_id, project_name, task, provider, model,
             input_tokens, cached_tokens, output_tokens, cost, elapsed_ms, status),
        )


def usage_month_cost(month: str) -> float:
    row = get_conn().execute(
        "SELECT COALESCE(SUM(cost), 0) AS total FROM ai_usage WHERE month = ?",
        (month,),
    ).fetchone()
    return float(row["total"])


_USAGE_GROUPS = {
    "project": "COALESCE(NULLIF(project_name, ''), 'بلا منافسة / no tender')",
    "task": "task",
    "model": "provider || ' / ' || model",
    "provider": "provider",
}


def usage_summary(group_by: str = "project", month: str = "") -> list:
    """إجماليات الاستهلاك مجمّعة — لشاشة الاستهلاك (11-8)."""
    expr = _USAGE_GROUPS.get(group_by, _USAGE_GROUPS["project"])
    sql = (
        f"SELECT {expr} AS grp, COUNT(*) AS calls, "
        "SUM(input_tokens) AS input_tokens, SUM(cached_tokens) AS cached_tokens, "
        "SUM(output_tokens) AS output_tokens, SUM(cost) AS cost "
        "FROM ai_usage"
    )
    args: list[Any] = []
    if month:
        sql += " WHERE month = ?"
        args.append(month)
    sql += " GROUP BY grp ORDER BY cost DESC"
    return [dict(r) for r in get_conn().execute(sql, args).fetchall()]


def usage_totals(month: str = "") -> dict:
    sql = (
        "SELECT COUNT(*) AS calls, COALESCE(SUM(input_tokens), 0) AS input_tokens, "
        "COALESCE(SUM(cached_tokens), 0) AS cached_tokens, "
        "COALESCE(SUM(output_tokens), 0) AS output_tokens, "
        "COALESCE(SUM(cost), 0) AS cost, "
        "SUM(CASE WHEN status = 'cache' THEN 1 ELSE 0 END) AS cache_hits "
        "FROM ai_usage"
    )
    args: list[Any] = []
    if month:
        sql += " WHERE month = ?"
        args.append(month)
    return dict(get_conn().execute(sql, args).fetchone())


# ─── ذاكرة نتائج الاستدعاءات (11-13) ─────────────────────────────────────────


def ai_cache_get(fingerprint: str) -> Optional[str]:
    row = get_conn().execute(
        "SELECT result FROM ai_cache WHERE fingerprint = ?", (fingerprint,)
    ).fetchone()
    return row["result"] if row else None


def ai_cache_put(fingerprint: str, provider: str, model: str, result: str):
    with transaction() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO ai_cache (fingerprint, created_at, provider, "
            "model, result) VALUES (?, ?, ?, ?, ?)",
            (fingerprint, _now(), provider, model, result),
        )


def ai_cache_clear():
    with transaction() as conn:
        conn.execute("DELETE FROM ai_cache")


# ─── إبطال متجهات المستودع عند تغيير نموذج التضمين (11-6) ────────────────────


def kb_stale_chunk_count(embed_model: str) -> int:
    """عدد المقاطع المفهرسة بنموذج تضمين مختلف عن النشط — مُعطَّلة عن البحث."""
    row = get_conn().execute(
        "SELECT COUNT(*) AS n FROM kb_chunks "
        "WHERE COALESCE(embed_model, '') != ?",
        (embed_model,),
    ).fetchone()
    return int(row["n"])


def kb_chunk_texts() -> list:
    """كل المقاطع (المعرّف والنص) — لإعادة الفهرسة بالنموذج النشط."""
    rows = get_conn().execute("SELECT id, text FROM kb_chunks ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def update_kb_chunk_embeddings(rows: list, embed_model: str):
    """rows: [(chunk_id, dims, embedding_bytes)] — بعد إعادة التضمين."""
    with transaction() as conn:
        conn.executemany(
            "UPDATE kb_chunks SET dims = ?, embedding = ?, embed_model = ? "
            "WHERE id = ?",
            [(d, e, embed_model, cid) for cid, d, e in rows],
        )
