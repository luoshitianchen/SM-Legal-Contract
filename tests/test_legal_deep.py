"""法务合同业务深化测试：起草/审批/归档、模板。"""
from __future__ import annotations

H = {"X-Internal-Token": "test-internal-key-12345"}


async def _make_contract(client, no="HT-001", title="采购框架合同", amount=100000):
    return await client.post("/api/legal/contracts", json={
        "contract_no": no, "title": title, "category": "purchase",
        "party_a": "甲方公司", "party_b": "乙方公司", "amount": amount,
        "effective_date": "2026-10-01", "expiry_date": "2027-09-30",
    }, headers=H)


# ═══════════════════════════════════════════════════════════
# 合同起草
# ═══════════════════════════════════════════════════════════
class TestContractDraft:
    async def test_create_contract(self, client):
        resp = await _make_contract(client, "HT-DRAFT", "服务合同")
        assert resp.status_code == 201
        assert resp.json()["status"] == "draft"

    async def test_create_requires_token(self, client):
        resp = await client.post("/api/legal/contracts", json={
            "contract_no": "HT-NOAUTH", "title": "x", "amount": 1,
        })
        assert resp.status_code in (401, 403)

    async def test_duplicate_contract_no(self, client):
        await _make_contract(client, "HT-DUP")
        resp = await _make_contract(client, "HT-DUP")
        assert resp.status_code == 409

    async def test_date_order_rejected(self, client):
        resp = await client.post("/api/legal/contracts", json={
            "contract_no": "HT-DATE", "title": "日期倒挂", "amount": 1,
            "effective_date": "2027-01-01", "expiry_date": "2026-01-01",
        }, headers=H)
        assert resp.status_code == 400

    async def test_list_and_keyword(self, client):
        await _make_contract(client, "HT-KW", "关键词合同")
        resp = await client.get("/api/legal/contracts?status=draft&keyword=关键词", headers=H)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_get_contract_not_found(self, client):
        resp = await client.get("/api/legal/contracts/nope", headers=H)
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════
# 审批流
# ═══════════════════════════════════════════════════════════
class TestApproval:
    async def _submitted(self, client, no="HT-APV"):
        c = (await _make_contract(client, no)).json()
        await client.post(f"/api/legal/contracts/{c['id']}/submit",
                          json={}, headers=H)
        return c

    async def test_submit_and_approve(self, client):
        c = await self._submitted(client, "HT-APV-1")
        resp = await client.post(f"/api/legal/contracts/{c['id']}/decide", json={
            "approver_id": "lawyer-01", "decision": "approve", "comment": "同意",
        }, headers=H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    async def test_cannot_decide_draft(self, client):
        c = (await _make_contract(client, "HT-DEC-DRAFT")).json()
        resp = await client.post(f"/api/legal/contracts/{c['id']}/decide", json={
            "approver_id": "lawyer-01", "decision": "approve",
        }, headers=H)
        assert resp.status_code == 409

    async def test_cannot_submit_twice(self, client):
        c = await self._submitted(client, "HT-SUB-2")
        resp = await client.post(f"/api/legal/contracts/{c['id']}/submit",
                                 json={}, headers=H)
        assert resp.status_code == 409

    async def test_same_approver_cannot_act_twice(self, client):
        c = await self._submitted(client, "HT-APV-2")
        await client.post(f"/api/legal/contracts/{c['id']}/decide", json={
            "approver_id": "lawyer-02", "decision": "reject",
        }, headers=H)
        # 已驳回后状态为 rejected，再次操作应被状态机拦截
        resp = await client.post(f"/api/legal/contracts/{c['id']}/decide", json={
            "approver_id": "lawyer-03", "decision": "approve",
        }, headers=H)
        assert resp.status_code == 409

    async def test_contract_detail_includes_approvals(self, client):
        c = await self._submitted(client, "HT-DETAIL")
        await client.post(f"/api/legal/contracts/{c['id']}/decide", json={
            "approver_id": "lawyer-04", "decision": "approve", "comment": "通过",
        }, headers=H)
        resp = await client.get(f"/api/legal/contracts/{c['id']}", headers=H)
        assert resp.status_code == 200
        assert len(resp.json()["approvals"]) >= 1


# ═══════════════════════════════════════════════════════════
# 归档
# ═══════════════════════════════════════════════════════════
class TestArchive:
    async def _approved(self, client, no="HT-ARC"):
        c = (await _make_contract(client, no)).json()
        await client.post(f"/api/legal/contracts/{c['id']}/submit", json={}, headers=H)
        await client.post(f"/api/legal/contracts/{c['id']}/decide", json={
            "approver_id": "lawyer-arc", "decision": "approve",
        }, headers=H)
        return c

    async def test_archive_approved_contract(self, client):
        c = await self._approved(client, "HT-ARC-1")
        resp = await client.post(f"/api/legal/contracts/{c['id']}/archive", json={
            "file_ref": "s3://archive/HT-ARC-1.pdf", "location": "档案库A",
        }, headers=H)
        assert resp.status_code == 201
        assert resp.json()["file_ref"] == "s3://archive/HT-ARC-1.pdf"

    async def test_cannot_archive_draft(self, client):
        c = (await _make_contract(client, "HT-ARC-DRAFT")).json()
        resp = await client.post(f"/api/legal/contracts/{c['id']}/archive", json={
            "file_ref": "x.pdf",
        }, headers=H)
        assert resp.status_code == 409

    async def test_cannot_archive_twice(self, client):
        c = await self._approved(client, "HT-ARC-2")
        await client.post(f"/api/legal/contracts/{c['id']}/archive", json={
            "file_ref": "a.pdf",
        }, headers=H)
        resp = await client.post(f"/api/legal/contracts/{c['id']}/archive", json={
            "file_ref": "b.pdf",
        }, headers=H)
        assert resp.status_code == 409


# ═══════════════════════════════════════════════════════════
# 模板
# ═══════════════════════════════════════════════════════════
class TestTemplate:
    async def test_create_template(self, client):
        resp = await client.post("/api/legal/templates", json={
            "code": "TPL-PURCHASE", "name": "采购合同模板", "category": "purchase",
            "content": "甲方与乙方...",
        }, headers=H)
        assert resp.status_code == 201
        assert resp.json()["code"] == "TPL-PURCHASE"

    async def test_duplicate_template_code(self, client):
        await client.post("/api/legal/templates", json={
            "code": "TPL-DUP", "name": "重复",
        }, headers=H)
        resp = await client.post("/api/legal/templates", json={
            "code": "TPL-DUP", "name": "重复2",
        }, headers=H)
        assert resp.status_code == 409

    async def test_list_templates(self, client):
        resp = await client.get("/api/legal/templates?keyword=采购", headers=H)
        assert resp.status_code == 200
        assert "total" in resp.json()
