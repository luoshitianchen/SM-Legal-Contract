# SM Legal Contract

合同法务管理：合同起草、审批、电子签章、归档和到期提醒。

```powershell
git clone https://github.com/luoshitianchen/SM-Legal-Contract.git
cd SM-Legal-Contract
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8540
```

接口：`/health`、`/readyz`、`/api/overview`、`/api/items`、`/api/ops/metrics`、`/api/crypto/status`。
