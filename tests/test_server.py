import pytest
from conftest import MACHINE_SESSION, FakeVera
from fastapi.testclient import TestClient

from indy.config import load_config
from indy.jobs import JobStore
from indy.server import create_app


def _client(cfg, vera=None):
    vera = vera or FakeVera()
    return TestClient(create_app(cfg, vera_factory=lambda: vera)), vera


def test_health_matches_the_worker_contract(cfg):
    c, _ = _client(cfg)
    body = c.get("/health").json()
    assert body == {"status": "ok", "agent": "indy", "version": "0.1.0", "busy": False}


def test_health_is_open_even_when_vera_is_down(cfg):
    c, _ = _client(cfg, FakeVera(down=True))
    assert c.get("/health").status_code == 200


def test_page_shell_is_open_and_sets_base_for_the_path_mount(cfg):
    c, _ = _client(cfg)
    r = c.get("/")
    assert r.status_code == 200 and "<base" in r.text and "no-store" in r.headers["cache-control"]
    assert 'href="/' not in r.text and 'src="/' not in r.text  # relative URLs only


def test_everything_but_auth_and_health_needs_a_session(cfg):
    c, _ = _client(cfg)
    for path in ("/v1/jobs", "/v1/jobs/abc", "/ui/api/status"):
        assert c.get(path).status_code == 401, path
    assert c.get("/v1/jobs", headers={"X-Admin-Token": "guess"}).status_code == 401
    assert c.get("/v1/jobs", headers={"Authorization": "Bearer guess"}).status_code == 401


def test_a_vera_session_unlocks_both_apis_by_header_or_bearer(cfg):
    c, _ = _client(cfg)
    assert c.get("/v1/jobs", headers={"X-Admin-Token": MACHINE_SESSION}).json() == []
    assert (
        c.get("/v1/jobs", headers={"Authorization": f"Bearer {MACHINE_SESSION}"}).status_code == 200
    )
    assert c.get("/ui/api/status", headers={"X-Admin-Token": MACHINE_SESSION}).status_code == 200


def test_guarded_routes_fail_closed_with_503_when_vera_is_down(cfg):
    vera = FakeVera()
    c, _ = _client(cfg, vera)
    vera.down = True
    r = c.get("/v1/jobs", headers={"X-Admin-Token": MACHINE_SESSION})
    assert r.status_code == 503 and "refusing" in r.json()["detail"]


def test_guarded_routes_fail_closed_when_vera_is_not_configured(cfg):
    def unconfigured():
        raise RuntimeError("VERA_URL and VERA_AGENT_KEY must be set")

    c = TestClient(create_app(cfg, vera_factory=unconfigured))
    assert c.get("/v1/jobs", headers={"X-Admin-Token": "x"}).status_code == 503
    assert c.get("/health").status_code == 200  # Indy still starts and says why
    assert c.post("/ui/api/auth/verify", json={"pin": "1234"}).status_code == 503


def test_sign_in_is_veras_with_wrong_pin_lockout_and_no_local_pin(cfg):
    vera = FakeVera()
    c, _ = _client(cfg, vera)
    assert c.get("/ui/api/auth/status").json() == {"pin_set": True, "managed_by": "vera"}
    assert c.post("/ui/api/auth/verify", json={"pin": "bad"}).status_code == 401
    ok = c.post("/ui/api/auth/verify", json={"pin": "1234"})
    assert ok.status_code == 200 and ok.json()["token"] in vera.sessions
    vera.locked = True
    assert c.post("/ui/api/auth/verify", json={"pin": "1234"}).status_code == 429
    assert c.post("/ui/api/auth/setup", json={}).status_code == 409


def test_sign_in_says_so_when_the_sso_grant_is_missing(cfg):
    vera = FakeVera()
    vera.sso_grant = False
    c, _ = _client(cfg, vera)
    assert c.post("/ui/api/auth/verify", json={"pin": "1234"}).status_code == 503


def test_logout_ends_the_session_and_still_works_when_vera_is_down(cfg):
    vera = FakeVera()
    c, _ = _client(cfg, vera)
    token = c.post("/ui/api/auth/verify", json={"pin": "1234"}).json()["token"]
    assert c.post("/ui/api/auth/logout", headers={"X-Admin-Token": token}).json() == {"ok": True}
    assert token not in vera.sessions
    vera.down = True
    assert c.post("/ui/api/auth/logout", headers={"X-Admin-Token": "x"}).status_code == 200


def test_unknown_job_is_404(cfg):
    c, _ = _client(cfg)
    r = c.get("/v1/jobs/nope", headers={"X-Admin-Token": MACHINE_SESSION})
    assert r.status_code == 404


def test_jobs_report_busy_and_a_restart_fails_the_interrupted_job(tmp_path):
    store = JobStore(tmp_path)
    job = store.submit(
        "check", {"opportunity_id": "O"}, lambda: (_ for _ in ()).throw(ValueError("boom"))
    )
    for _ in range(200):
        done = store.get(job["job_id"])
        if done["status"] in ("done", "failed"):
            break
    assert done["status"] == "failed" and done["error"] == "boom" and not store.busy()
    # simulate a crash mid-job, then a restart
    stale = dict(done, status="running", error=None)
    store._write(stale)
    again = JobStore(tmp_path)
    assert again.get(stale["job_id"])["status"] == "failed"
    assert "restart" in again.get(stale["job_id"])["error"]


def test_config_rejects_bad_values(tmp_path):
    bad = tmp_path / "c.yaml"
    bad.write_text("llm:\n  ollama_endpoint: localhost:11434\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ollama_endpoint"):
        load_config(bad)
    bad.write_text("llm:\n  pause_seconds: -1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="pause_seconds"):
        load_config(bad)


def test_config_defaults_and_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("INDY_OLLAMA_ENDPOINT", "http://gpu:11434")
    cfg = load_config(tmp_path / "missing.yaml")
    assert cfg["llm"]["ollama_endpoint"] == "http://gpu:11434"
    assert cfg["vera"]["sow_category"] == "sow"
