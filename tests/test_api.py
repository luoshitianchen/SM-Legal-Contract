"""SM Legal Contract 领域测试：合同、版本、审批、到期预警与统计。"""

import pytest
from fastapi.testclient import TestClient

from app import base
from app.main import VERSION, app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(base, "internal_api_key", lambda: "TEST")
    base.reset_state()
    from app.main import _init as init_db
    init_db()
    with TestClient(app) as c:
        c.headers["X-Internal-Token"] = "TEST"
        yield c


def _contract(client, title="软件许可合同", end_date="2026-09-15"):
    return client.post("/api/legal/contracts", json={"title": title, "counterparty": "云启科技", "contract_type": "软件许可", "start_date": "2026-01-01", "end_date": end_date, "amount": 500000, "owner": "法务部"}).json()["id"]


def test_health_and_version(client):
    r = client.get("/health", headers={"X-Request-Id": "suite-test"})
    assert r.status_code == 200
    assert r.json()["version"] == VERSION


def test_contract_and_version(client):
    contract_id = _contract(client)
    detail = client.get(f"/api/legal/contracts/{contract_id}").json()
    assert detail["status"] == "draft"
    assert len(detail["versions"]) == 1
    assert client.post(f"/api/legal/contracts/{contract_id}/versions", json={"content": "第二版修订条款内容说明", "changed_by": "法务小王"}).status_code == 201
    detail = client.get(f"/api/legal/contracts/{contract_id}").json()
    assert len(detail["versions"]) == 2
    assert client.get("/api/legal/contracts").json()["total"] == 1


def test_approve_and_terminate(client):
    contract_id = _contract(client)
    client.post(f"/api/legal/contracts/{contract_id}/versions", json={"content": "修订条款内容说明", "changed_by": "法务小王"})
    assert client.post(f"/api/legal/contracts/{contract_id}/approve", json={"approver": "法务总监", "comment": "同意"}).json()["status"] == "approved"
    assert client.get(f"/api/legal/contracts/{contract_id}").json()["status"] == "signed"
    assert client.post(f"/api/legal/contracts/{contract_id}/terminate").json()["status"] == "terminated"


def test_expiring(client):
    _contract(client, title="即将到期合同", end_date="2026-09-10")
    _contract(client, title="长期合同", end_date="2030-01-01")
    client.post(f"/api/legal/contracts/{client.get('/api/legal/contracts').json()['items'][0]['id']}/versions", json={"content": "x" * 10, "changed_by": "a"})
    client.post(f"/api/legal/contracts/{client.get('/api/legal/contracts').json()['items'][0]['id']}/approve", json={"approver": "法务总监"})
    client.post(f"/api/legal/contracts/{client.get('/api/legal/contracts').json()['items'][1]['id']}/versions", json={"content": "y" * 10, "changed_by": "a"})
    client.post(f"/api/legal/contracts/{client.get('/api/legal/contracts').json()['items'][1]['id']}/approve", json={"approver": "法务总监"})
    expiring = client.get("/api/legal/expiring", params={"days": 60}).json()
    assert expiring["expiring_count"] == 1


def test_missing(client):
    assert client.get("/api/legal/contracts/nope").status_code == 404
    assert client.post("/api/legal/contracts/nope/approve", json={"approver": "a"}).status_code == 404


def test_stats(client):
    contract_id = _contract(client)
    client.post(f"/api/legal/contracts/{contract_id}/versions", json={"content": "合同文本内容说明", "changed_by": "法务小王"})
    client.post(f"/api/legal/contracts/{contract_id}/approve", json={"approver": "法务总监"})
    stats = client.get("/api/legal/stats").json()
    assert stats["contracts"] == 1
    assert stats["total_value"] == 500000


def test_manifest_and_crypto(client):
    assert client.get("/api/integration/manifest").json()["version"] == VERSION
    enc = client.post("/api/crypto/encrypt", json={"value": "x"}).json()["ciphertext"]
    assert client.post("/api/crypto/decrypt", json={"value": enc}).json()["plaintext"] == "x"


def test_write_requires_auth(client):
    del client.headers["X-Internal-Token"]
    assert client.post("/api/legal/contracts", json={"title": "t", "counterparty": "c", "contract_type": "ct", "owner": "o"}).status_code == 401
