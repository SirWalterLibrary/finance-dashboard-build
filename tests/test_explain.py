"""T15 — Optional AI explain: POST /api/explain, HTTP calls monkeypatched."""
import httpx

from conftest import login

GOAL_BODY = {"name": "House", "target_cents": 1000000,
             "target_date": "2027-06-01", "allocated_cents": 100000,
             "scope": "joint"}


def _fake_resp(text="Sentence one. Sentence two."):
    def fake(url, **kw):
        fake.calls.append((url, kw))
        return httpx.Response(
            200, json={"message": {"content": text}},
            request=httpx.Request("POST", url),
        )
    fake.calls = []
    return fake


def _seed(client):
    client.post("/api/accounts", json={
        "name": "Savings", "institution": "Bank", "type": "savings",
        "shared": True, "opening_balance_cents": 500000,
    })
    r = client.post("/api/goals", json=GOAL_BODY)
    assert r.status_code == 201


def _set_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://ollama.test")
    monkeypatch.setenv("EXPLAIN_MODEL", "explain-model")


def test_explain_requires_login(client):
    r = client.post("/api/explain", json={"kind": "goals"})
    assert r.status_code == 401


def test_explain_goals_success(client, user, monkeypatch):
    _set_env(monkeypatch)
    login(client, user)
    _seed(client)
    fake = _fake_resp("Your goal is on track.")
    monkeypatch.setattr(httpx, "post", fake)
    r = client.post("/api/explain", json={"kind": "goals"})
    assert r.status_code == 200
    assert r.json() == {"text": "Your goal is on track.", "llm_available": True}
    url, kw = fake.calls[0]
    assert url == "http://ollama.test/api/chat"
    assert kw["json"]["stream"] is False
    assert kw["json"]["model"] == "explain-model"
    prompt = kw["json"]["messages"][0]["content"]
    assert "Do not change any number or date." in prompt
    assert '"remaining_cents": 900000' in prompt
    assert '"monthly_cents_used"' in prompt


def test_explain_forecast_success(client, user, monkeypatch):
    _set_env(monkeypatch)
    login(client, user)
    _seed(client)
    fake = _fake_resp("Your savings look fine.")
    monkeypatch.setattr(httpx, "post", fake)
    r = client.post("/api/explain", json={"kind": "forecast"})
    assert r.status_code == 200
    assert r.json() == {"text": "Your savings look fine.", "llm_available": True}
    url, kw = fake.calls[0]
    assert url == "http://ollama.test/api/chat"
    prompt = kw["json"]["messages"][0]["content"]
    assert "Do not change any number or date." in prompt
    assert '"baseline_monthly_cents"' in prompt
    assert '"start_balance_cents": 500000' in prompt
    assert '"first_negative_month"' in prompt


def test_explain_llm_failure_returns_empty(client, user, monkeypatch):
    _set_env(monkeypatch)
    login(client, user)

    def fake(url, **kw):
        raise httpx.ConnectError("no server")
    monkeypatch.setattr(httpx, "post", fake)
    r = client.post("/api/explain", json={"kind": "goals"})
    assert r.status_code == 200
    assert r.json() == {"text": "", "llm_available": False}


def test_explain_http_500_returns_empty(client, user, monkeypatch):
    _set_env(monkeypatch)
    login(client, user)
    monkeypatch.setattr(
        httpx, "post",
        lambda url, **kw: httpx.Response(
            500, json={}, request=httpx.Request("POST", url)))
    r = client.post("/api/explain", json={"kind": "forecast"})
    assert r.status_code == 200
    assert r.json() == {"text": "", "llm_available": False}


def test_explain_model_not_configured(client, user, monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://ollama.test")
    monkeypatch.delenv("EXPLAIN_MODEL", raising=False)
    login(client, user)

    def fake(url, **kw):
        raise AssertionError("LLM must not be called")
    monkeypatch.setattr(httpx, "post", fake)
    r = client.post("/api/explain", json={"kind": "goals"})
    assert r.status_code == 200
    assert r.json() == {"text": "", "llm_available": False}


def test_explain_bad_scope_and_kind(client, user):
    login(client, user)
    r = client.post("/api/explain", json={"kind": "goals", "scope": "bogus"})
    assert r.status_code == 400
    assert client.post("/api/explain",
                       json={"kind": "nope"}).status_code == 422
