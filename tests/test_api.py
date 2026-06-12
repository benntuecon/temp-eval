"""Contract tests for the FastAPI service — httpx, no network, no browser.

A full simulated run is driven through POST /api/runs and observed over the
SSE stream; the typed event sequence (incl. thinking deltas and judge
rationales) is asserted end-to-end.
"""

import asyncio
import json

import pytest
from httpx import ASGITransport, AsyncClient

from skill_eval.api.app import create_app
from skill_eval.events import parse_event


def _run_request(**overrides) -> dict:
    body = {
        "fixture": "sample",
        "task_brief": "Fix the add function so the tests pass.",
        "baseline": {"name": "ship-it-fast", "markdown": "# ship it\nJust fix it fast."},
        "challenger": {"name": "disciplined", "markdown": "# disciplined\nAsk, test, then fix."},
        "real_agents": False,
    }
    body.update(overrides)
    return body


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


@pytest.mark.anyio
async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.anyio
async def test_fixtures_lists_testcases_then_builtins(client):
    r = await client.get("/api/fixtures")
    assert r.status_code == 200
    fixtures = r.json()
    ids = [f["id"] for f in fixtures]
    # built-ins always present; demo testcases (if any) listed first
    assert {"flagship", "sample"} <= set(ids)
    testcase_ids = [i for i in ids if i.startswith("testcase:")]
    assert ids[: len(testcase_ids)] == testcase_ids
    for f in fixtures:
        assert f["brief"].strip()
        assert f["default_baseline"]["markdown"].strip()
        assert f["default_challenger"]["markdown"].strip()
    # testcase fixtures default to the logging skill pair
    for f in fixtures:
        if f["id"].startswith("testcase:"):
            assert f["default_baseline"]["name"] == "logging-naive"
            assert f["default_challenger"]["name"] == "logging-best-practices"


@pytest.mark.anyio
async def test_create_run_validates_request(client):
    r = await client.post("/api/runs", json=_run_request(task_brief="   "))
    assert r.status_code == 422

    r = await client.post(
        "/api/runs",
        json=_run_request(baseline={"name": "x", "markdown": "  "}),
    )
    assert r.status_code == 422

    r = await client.post("/api/runs", json=_run_request(fixture="nope"))
    assert r.status_code == 422


@pytest.mark.anyio
async def test_unknown_run_404s(client):
    assert (await client.get("/api/runs/doesnotexist")).status_code == 404
    assert (await client.get("/api/runs/doesnotexist/events")).status_code == 404


@pytest.mark.anyio
async def test_simulated_run_end_to_end_over_the_api(client, app):
    # 1. create
    r = await client.post("/api/runs", json=_run_request())
    assert r.status_code == 201
    summary = r.json()
    run_id = summary["run_id"]
    assert summary["status"] == "running"

    # 2. stream events until RunCompleted (simulated run: a few seconds)
    types: list[str] = []
    nodes: set[str] = set()
    rationales = 0
    thinking = 0
    async with client.stream("GET", f"/api/runs/{run_id}/events") as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        async with asyncio.timeout(60):
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                ev = parse_event(line[len("data: ") :])
                types.append(ev.type)
                nodes.add(ev.node)
                if ev.type == "judge_status" and getattr(ev, "rationale", None):
                    rationales += 1
                if ev.type == "thinking_delta":
                    thinking += 1
                if ev.type in ("run_completed", "run_failed"):
                    break

    assert types[0] == "run_started"
    assert types[-1] == "run_completed"
    assert thinking >= 2  # both arms streamed thinking
    assert rationales >= 12  # every judge carried a rationale
    assert {"test_generator", "sandbox", "taker:baseline", "taker:challenger"} <= nodes

    # 3. detail now has the full typed report
    detail = (await client.get(f"/api/runs/{run_id}")).json()
    assert detail["summary"]["status"] == "completed"
    report = detail["report"]
    assert report is not None
    assert {a["arm"] for a in report["arms"]} == {"baseline", "challenger"}
    assert all(len(a["scores"]) == 6 for a in report["arms"])

    # 4. it's listed, newest first
    listing = (await client.get("/api/runs")).json()
    assert listing[0]["run_id"] == run_id

    # 5. events replay from the archive after the run is gone from memory
    app.state.manager._runs.clear()
    replayed = []
    async with client.stream("GET", f"/api/runs/{run_id}/events") as resp:
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                replayed.append(json.loads(line[6:])["type"])
    assert replayed[0] == "run_started" and replayed[-1] == "run_completed"

    # 6. the archived report still loads
    detail2 = (await client.get(f"/api/runs/{run_id}")).json()
    assert detail2["report"] is not None


@pytest.mark.anyio
async def test_openapi_schema_exposes_contract(client):
    schema = (await client.get("/openapi.json")).json()
    paths = set(schema["paths"])
    assert {"/api/runs", "/api/runs/{run_id}", "/api/runs/{run_id}/events", "/api/fixtures"} <= (
        paths
    )
    assert "CreateRunRequest" in schema["components"]["schemas"]
    assert "ComparisonReport" in schema["components"]["schemas"]
