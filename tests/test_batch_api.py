"""Batch eval API: retrieval endpoint + batch lifecycle with simulated agents."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from skill_eval.api.app import create_app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture()
def app(tmp_path):
    return create_app(runs_dir=str(tmp_path / "runs"))


@pytest.fixture()
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _batch_request(**overrides):
    body = {
        "query": "logging improvement payment api banking",
        "top_k": 2,
        "real_agents": False,
        "max_concurrent": 2,
    }
    body.update(overrides)
    return body


@pytest.mark.anyio
async def test_retrieve_returns_runnable_fixtures(client, monkeypatch):
    # Force the keyword fallback so the test never touches chromadb.
    import skill_eval.retriever as retriever

    monkeypatch.setattr(
        "skill_eval.eval_vector_db.query_cases",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("no db")),
    )
    r = await client.get("/api/retrieve", params={"query": "payment api banking PCI", "k": 3})
    assert r.status_code == 200
    hits = r.json()
    assert 1 <= len(hits) <= 3
    assert all(h["fixture"] == f"testcase:{h['case_id']}" for h in hits)
    assert hits[0]["case_id"] == "01-payment-api"  # keyword overlap ranks payment first
    assert retriever.retrieve_cases("payment", top_k=1)[0]["distance"] is None


@pytest.mark.anyio
async def test_retrieve_rejects_blank_query(client):
    r = await client.get("/api/retrieve", params={"query": "   "})
    assert r.status_code == 422


@pytest.mark.anyio
async def test_create_batch_validates_query(client):
    r = await client.post("/api/batches", json=_batch_request(query="   "))
    assert r.status_code == 422


@pytest.mark.anyio
async def test_batch_lifecycle_simulated(client, monkeypatch):
    """Full batch: retrieve 2 cases, run simulated evals, aggregate stats."""
    monkeypatch.setattr(
        "skill_eval.eval_vector_db.query_cases",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("no db")),
    )
    r = await client.post("/api/batches", json=_batch_request())
    assert r.status_code == 201
    batch_id = r.json()["batch_id"]

    detail = None
    for _ in range(120):  # simulated children finish in a few seconds
        await asyncio.sleep(0.25)
        d = await client.get(f"/api/batches/{batch_id}")
        assert d.status_code == 200
        detail = d.json()
        if detail["summary"]["status"] == "completed":
            break
    assert detail is not None and detail["summary"]["status"] == "completed"

    assert detail["summary"]["total"] == 2
    assert detail["summary"]["completed"] == 2
    assert detail["summary"]["failed"] == 0

    for case in detail["cases"]:
        assert case["status"] == "completed"
        assert case["run_id"]
        assert case["verdict"]
        assert case["baseline_total"] is not None
        assert case["challenger_total"] is not None

    stats = detail["stats"]
    assert stats is not None
    assert sum(stats["win_summary"].values()) == 2
    assert len(stats["per_criterion_avg"]) == 6
    assert len(stats["per_case_totals"]) == 2
    assert len(stats["tokens_per_case"]) == 2
    assert len(stats["score_distribution"]) == 2 * 12  # 2 reports x 12 judge rows

    # batch shows up in the listing
    listing = await client.get("/api/batches")
    assert any(b["batch_id"] == batch_id for b in listing.json())

    # child runs are normal runs, visible in run history
    runs = await client.get("/api/runs")
    child_ids = {c["run_id"] for c in detail["cases"]}
    assert child_ids <= {r["run_id"] for r in runs.json()}


@pytest.mark.anyio
async def test_batch_detail_unknown_id(client):
    r = await client.get("/api/batches/doesnotexist")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_retrieve_rejects_out_of_range_k(client):
    """k bounds must match CreateBatchRequest.top_k: 422, not silent clamping."""
    r = await client.get("/api/retrieve", params={"query": "logging", "k": 99})
    assert r.status_code == 422
    r = await client.get("/api/retrieve", params={"query": "logging", "k": 0})
    assert r.status_code == 422


@pytest.mark.anyio
async def test_batch_forwards_config_to_children(tmp_path, monkeypatch):
    """real_agents/budgets/judge config must reach every child CreateRunRequest."""
    from skill_eval.api.batch_manager import BatchManager
    from skill_eval.api.schemas import CreateBatchRequest, RunSummary

    monkeypatch.setattr(
        "skill_eval.eval_vector_db.query_cases",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("no db")),
    )

    captured = []

    class FakeRunManager:
        _runs: dict = {}

        def start(self, req):
            captured.append(req)
            return f"run-{len(captured)}"

        def summary(self, run_id):
            return RunSummary(run_id=run_id, status="completed", created_at=0.0)

        def report(self, run_id):
            return None

    bm = BatchManager(FakeRunManager(), str(tmp_path / "runs"))
    req = CreateBatchRequest(
        query="logging",
        top_k=2,
        real_agents=True,
        max_turns=7,
        thinking_budget=512,
        judge_model="claude-sonnet-4-6",
        judges_per_criterion=2,
        max_concurrent=1,
    )
    batch_id = await bm.start(req)
    await bm._batches[batch_id].task

    assert len(captured) == 2
    for child in captured:
        assert child.real_agents is True
        assert child.max_turns == 7
        assert child.thinking_budget == 512
        assert child.judge_model == "claude-sonnet-4-6"
        assert child.judges_per_criterion == 2
        assert child.fixture.startswith("testcase:")
        assert child.baseline.name == "logging-naive"
        assert child.challenger.name == "logging-best-practices"


@pytest.mark.anyio
async def test_batch_archive_survives_restart(client, tmp_path, monkeypatch):
    """A completed batch must load from disk in a fresh process (new managers)."""
    monkeypatch.setattr(
        "skill_eval.eval_vector_db.query_cases",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("no db")),
    )
    r = await client.post("/api/batches", json=_batch_request(top_k=1))
    batch_id = r.json()["batch_id"]
    for _ in range(120):
        await asyncio.sleep(0.25)
        d = (await client.get(f"/api/batches/{batch_id}")).json()
        if d["summary"]["status"] == "completed":
            break
    assert d["summary"]["status"] == "completed"

    # "restart": a brand-new app over the same runs_dir
    fresh = create_app(runs_dir=str(tmp_path / "runs"))
    async with AsyncClient(
        transport=ASGITransport(app=fresh), base_url="http://test"
    ) as fresh_client:
        detail = await fresh_client.get(f"/api/batches/{batch_id}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["summary"]["status"] == "completed"
        assert body["stats"] is not None
        listing = await fresh_client.get("/api/batches")
        assert any(b["batch_id"] == batch_id for b in listing.json())


@pytest.mark.anyio
async def test_batch_child_failure_propagates(client, monkeypatch):
    """One broken case -> failed=1, batch still completes, stats from the rest."""
    import skill_eval.testcase_fixture as tf

    monkeypatch.setattr(
        "skill_eval.eval_vector_db.query_cases",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("no db")),
    )
    real_build = tf.build_testcase
    first_case_id = tf.list_testcase_ids()[0]

    def flaky_build(case_id, base_dir):
        if case_id == first_case_id:
            raise RuntimeError("boom: simulated broken fixture")
        return real_build(case_id, base_dir)

    monkeypatch.setattr(tf, "build_testcase", flaky_build)

    r = await client.post(
        "/api/batches", json=_batch_request(query=first_case_id.replace("-", " "), top_k=2)
    )
    batch_id = r.json()["batch_id"]
    detail = None
    for _ in range(120):
        await asyncio.sleep(0.25)
        detail = (await client.get(f"/api/batches/{batch_id}")).json()
        if detail["summary"]["status"] != "running":
            break
    assert detail["summary"]["status"] == "completed"
    assert detail["summary"]["failed"] == 1
    assert detail["summary"]["completed"] == 1
    statuses = {c["case_id"]: c["status"] for c in detail["cases"]}
    assert statuses[first_case_id] == "failed"
    assert detail["stats"] is not None  # aggregates over the surviving case


@pytest.mark.anyio
async def test_batch_respects_max_concurrent(app, client, monkeypatch):
    """With max_concurrent=1 a child may only start after all prior ones ended."""
    monkeypatch.setattr(
        "skill_eval.eval_vector_db.query_cases",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("no db")),
    )
    manager = app.state.manager
    orig_start = manager.start
    snapshots = []

    def spy(req):
        snapshots.append([s.status for s in manager._runs.values()])
        return orig_start(req)

    monkeypatch.setattr(manager, "start", spy)

    r = await client.post(
        "/api/batches", json=_batch_request(top_k=3, max_concurrent=1)
    )
    batch_id = r.json()["batch_id"]
    for _ in range(180):
        await asyncio.sleep(0.25)
        d = (await client.get(f"/api/batches/{batch_id}")).json()
        if d["summary"]["status"] != "running":
            break
    assert d["summary"]["completed"] == 3
    assert len(snapshots) == 3
    for snapshot in snapshots[1:]:  # every later start sees only finished runs
        assert all(s in ("completed", "failed") for s in snapshot)
