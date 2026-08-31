"""SM Legal Contract —— 合同管理：合同登记、版本管理、审批与到期预警。"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from app import base

SERVICE = "sm-legal-contract"
VERSION = "2.0.0"
NAME = "SM Legal Contract"
DESCRIPTION = "合同管理：合同登记、版本管理、审批与到期预警"
PORT = 8540


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _init() -> None:
    with base.db_ctx() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS contracts (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, counterparty TEXT NOT NULL,
                contract_type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft',
                start_date TEXT, end_date TEXT, amount REAL NOT NULL DEFAULT 0,
                owner TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS versions (
                id TEXT PRIMARY KEY, contract_id TEXT NOT NULL, version INTEGER NOT NULL,
                content TEXT NOT NULL, changed_by TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY, contract_id TEXT NOT NULL, approver TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', comment TEXT, decided_at TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_contracts_expiry ON contracts(end_date, status);
            """
        )


app = base.create_app(
    service=SERVICE, name=NAME, description=DESCRIPTION, version=VERSION, port=PORT,
    dependencies=["sm-iam", "sm-workflow-approval", "sm-audit-log-center"],
    events=["contract.created", "contract.signed", "contract.expiring", "contract.terminated"],
    overview_fn=lambda _r: {
        "summary": {
            "contracts": base.get_db().execute("SELECT COUNT(*) FROM contracts").fetchone()[0],
            "active": base.get_db().execute("SELECT COUNT(*) FROM contracts WHERE status='signed'").fetchone()[0],
        }
    },
)
_init()


class ContractIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    counterparty: str = Field(min_length=2, max_length=120)
    contract_type: str = Field(min_length=2, max_length=60)
    start_date: str = Field(default="", max_length=12)
    end_date: str = Field(default="", max_length=12)
    amount: float = Field(default=0, ge=0)
    owner: str = Field(min_length=1, max_length=80)


class VersionIn(BaseModel):
    content: str = Field(min_length=10, max_length=10000)
    changed_by: str = Field(min_length=1, max_length=80)


class ApprovalIn(BaseModel):
    approver: str = Field(min_length=1, max_length=80)
    comment: str = Field(default="", max_length=300)


@app.post("/api/legal/contracts", status_code=status.HTTP_201_CREATED)
def create_contract(payload: ContractIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    contract_id = str(uuid.uuid4())
    with base.db_ctx() as conn:
        conn.execute("INSERT INTO contracts (id, title, counterparty, contract_type, status, start_date, end_date, amount, owner, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (contract_id, payload.title, payload.counterparty, payload.contract_type, "draft", payload.start_date, payload.end_date, payload.amount, payload.owner, _now()))
        conn.execute("INSERT INTO versions (id, contract_id, version, content, changed_by, created_at) VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), contract_id, 1, f"合同初始创建: {payload.title}", payload.owner, _now()))
        base.record_audit("contract.created", payload.owner, f"contract={contract_id}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": contract_id, "title": payload.title, "status": "draft"}


@app.get("/api/legal/contracts")
def list_contracts(status_: str | None = None) -> dict[str, Any]:
    with base.db_ctx() as conn:
        if status_:
            rows = conn.execute("SELECT * FROM contracts WHERE status=? ORDER BY created_at DESC", (status_,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM contracts ORDER BY created_at DESC LIMIT 200").fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/legal/contracts/{contract_id}")
def get_contract(contract_id: str) -> dict[str, Any]:
    with base.db_ctx() as conn:
        contract = conn.execute("SELECT * FROM contracts WHERE id=?", (contract_id,)).fetchone()
        if not contract:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "合同不存在")
        versions = conn.execute("SELECT * FROM versions WHERE contract_id=? ORDER BY version DESC", (contract_id,)).fetchall()
        approvals = conn.execute("SELECT * FROM approvals WHERE contract_id=? ORDER BY created_at DESC", (contract_id,)).fetchall()
    return {**dict(contract), "versions": [dict(r) for r in versions], "approvals": [dict(r) for r in approvals]}


@app.post("/api/legal/contracts/{contract_id}/versions", status_code=status.HTTP_201_CREATED)
def add_version(contract_id: str, payload: VersionIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    version_id = str(uuid.uuid4())
    with base.db_ctx() as conn:
        contract = conn.execute("SELECT * FROM contracts WHERE id=?", (contract_id,)).fetchone()
        if not contract:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "合同不存在")
        max_version = conn.execute("SELECT COALESCE(MAX(version),0) FROM versions WHERE contract_id=?", (contract_id,)).fetchone()[0]
        conn.execute("INSERT INTO versions (id, contract_id, version, content, changed_by, created_at) VALUES (?,?,?,?,?,?)", (version_id, contract_id, max_version + 1, payload.content, payload.changed_by, _now()))
        conn.execute("UPDATE contracts SET status='in_review' WHERE id=? AND status='draft'", (contract_id,))
    return {"id": version_id, "contract_id": contract_id, "version": max_version + 1}


@app.post("/api/legal/contracts/{contract_id}/approve")
def approve_contract(contract_id: str, payload: ApprovalIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    approval_id = str(uuid.uuid4())
    with base.db_ctx() as conn:
        contract = conn.execute("SELECT * FROM contracts WHERE id=?", (contract_id,)).fetchone()
        if not contract:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "合同不存在")
        conn.execute("INSERT INTO approvals (id, contract_id, approver, status, comment, decided_at, created_at) VALUES (?,?,?,?,?,?,?)", (approval_id, contract_id, payload.approver, "approved", payload.comment, _now(), _now()))
        conn.execute("UPDATE contracts SET status='signed' WHERE id=? AND status IN ('draft','in_review')", (contract_id,))
        base.record_audit("contract.signed", payload.approver, f"contract={contract_id}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": approval_id, "contract_id": contract_id, "status": "approved"}


@app.post("/api/legal/contracts/{contract_id}/terminate")
def terminate_contract(contract_id: str, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    with base.db_ctx() as conn:
        if conn.execute("UPDATE contracts SET status='terminated' WHERE id=? AND status='signed'", (contract_id,)).rowcount == 0:
            raise HTTPException(status.HTTP_409_CONFLICT, "合同不存在或未签署")
        base.record_audit("contract.terminated", "internal", f"contract={contract_id}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": contract_id, "status": "terminated"}


@app.get("/api/legal/expiring")
def expiring_contracts(days: int = 30) -> dict[str, Any]:
    """未来 N 天内到期且仍生效的合同预警。"""
    days = max(1, min(365, days))
    today = date.today()
    horizon_iso = (datetime(today.year, today.month, today.day) + timedelta(days=days)).date().isoformat()
    with base.db_ctx() as conn:
        rows = conn.execute("SELECT * FROM contracts WHERE status='signed' AND end_date IS NOT NULL AND end_date!='' AND end_date>=? AND end_date<=? ORDER BY end_date ASC", (today.isoformat(), horizon_iso)).fetchall()
    return {"horizon_days": days, "expiring_count": len(rows), "items": [dict(r) for r in rows]}


@app.get("/api/legal/stats")
def stats() -> dict[str, Any]:
    with base.db_ctx() as conn:
        def _count(sql: str) -> int:
            return conn.execute(sql).fetchone()[0]
        by_status = [dict(r) for r in conn.execute("SELECT status, COUNT(*) AS count FROM contracts GROUP BY status").fetchall()]
        return {
            "contracts": _count("SELECT COUNT(*) FROM contracts"),
            "signed": _count("SELECT COUNT(*) FROM contracts WHERE status='signed'"),
            "in_review": _count("SELECT COUNT(*) FROM contracts WHERE status='in_review'"),
            "terminated": _count("SELECT COUNT(*) FROM contracts WHERE status='terminated'"),
            "total_value": conn.execute("SELECT COALESCE(SUM(amount),0) FROM contracts WHERE status='signed'").fetchone()[0],
            "by_status": by_status,
        }
