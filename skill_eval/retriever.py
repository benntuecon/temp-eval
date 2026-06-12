"""Test-case retrieval for batch evals.

Primary path: semantic search over the Chroma vector DB built by
``scripts/index_testcases.py`` (case descriptions are the embedded
documents). Fallback path: keyword-overlap ranking over the raw
``testcases/<id>/case.json`` descriptions, so the API keeps working on a
machine where the vector DB was never built.

Every hit is normalised to a testcase id that the fixture layer
(``testcase:<id>``) can rebuild from source — the retriever decides *which*
cases run, never *where* their repos live.
"""

from __future__ import annotations

import logging
import re

from skill_eval.testcase_fixture import list_testcase_ids, load_case

logger = logging.getLogger(__name__)


def _keyword_fallback(query: str, top_k: int, ids: list[str]) -> list[dict]:
    q_words = set(re.findall(r"[a-z0-9]+", query.lower()))
    scored: list[tuple[int, str, str]] = []
    for cid in ids:
        desc = str(load_case(cid).get("description", ""))
        words = set(re.findall(r"[a-z0-9]+", desc.lower()))
        scored.append((len(q_words & words), cid, desc))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [
        {"case_id": cid, "description": desc, "distance": None}
        for _score, cid, desc in scored[:top_k]
    ]


def retrieve_cases(query: str, top_k: int = 10) -> list[dict]:
    """Return up to *top_k* matches: ``{case_id, description, distance}``.

    ``distance`` is the vector distance (lower = closer) or ``None`` when the
    keyword fallback produced the row.
    """
    ids = list_testcase_ids()
    if not ids:
        return []

    known = set(ids)
    out: list[dict] = []
    seen: set[str] = set()
    try:
        from skill_eval.eval_vector_db import query_cases

        # Over-fetch: the shared collection may also hold non-testcase entries
        # (e.g. sample cases) that the filter below drops.
        matches = query_cases(query, top_k=min(50, top_k + 20))
        for case, distance in matches:
            if case.case_id in known and case.case_id not in seen:
                seen.add(case.case_id)
                out.append(
                    {
                        "case_id": case.case_id,
                        "description": case.description,
                        "distance": distance,
                    }
                )
            if len(out) >= top_k:
                break
    except Exception:  # noqa: BLE001 — a broken vector DB must not break the API…
        # …but it must not be silent either: without this line, a chromadb
        # upgrade/schema break would demote retrieval to keyword-matching forever.
        logger.warning("vector retrieval failed; falling back to keyword ranking", exc_info=True)

    # Top up from keyword ranking so the caller always gets K cases when K exist.
    if len(out) < top_k:
        for row in _keyword_fallback(query, top_k, ids):
            if row["case_id"] not in seen:
                seen.add(row["case_id"])
                out.append(row)
            if len(out) >= top_k:
                break

    return out[:top_k]
