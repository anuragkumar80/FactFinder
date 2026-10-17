import json
from fastapi.testclient import TestClient
from backend import main, service
from backend.ratelimit import RateLimiter

client = TestClient(main.app)
RESULT = {"input": "x", "claims": [], "meta": {"cached": False}}


def parse_sse(body: str):
    events = []
    for block in body.strip().split("\n\n"):
        ev = {"event": "message", "data": ""}
        for line in block.split("\n"):
            if line.startswith("event:"): ev["event"] = line[6:].strip()
            if line.startswith("data:"): ev["data"] += line[5:].strip()
        if ev["data"]:
            events.append((ev["event"], json.loads(ev["data"])))
    return events


def test_health_index_demo_quota():
    assert client.get("/healthz").json() == {"ok": True}
    assert "Fact" in client.get("/").text
    assert len(client.get("/api/demo").json()) >= 3
    assert client.get("/api/quota").json()["fetches"] == 0


def test_empty_and_long_input_rejected():
    assert client.post("/api/check", json={"text": "  "}).status_code == 400
    assert client.post("/api/check", json={"text": "a" * 1600}).status_code == 400


def test_stream_emits_trace_then_result(monkeypatch):
    def fake(text, emit, rate_check=None):
        emit("extract", "Extracting claims"); emit("search", "Searching")
        return RESULT
    monkeypatch.setattr(service, "check", fake)
    r = client.post("/api/check", json={"text": "water is wet"})
    assert r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    assert [e[0] for e in events] == ["trace", "trace", "result"]
    assert events[0][1]["stage"] == "extract"


def test_errors_are_streamed(monkeypatch):
    from backend.errors import RateLimited
    def fake(text, emit, rate_check=None): raise RateLimited("slow down")
    monkeypatch.setattr(service, "check", fake)
    events = parse_sse(client.post("/api/check", json={"text": "claim"}).text)
    assert events[-1] == ("error", {"code": "rate_limited", "message": "slow down"})


def test_unexpected_error_does_not_hang(monkeypatch):
    def fake(text, emit, rate_check=None): raise ValueError("kaboom")
    monkeypatch.setattr(service, "check", fake)
    events = parse_sse(client.post("/api/check", json={"text": "claim"}).text)
    assert events[-1][0] == "error" and events[-1][1]["code"] == "internal"
