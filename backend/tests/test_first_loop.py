"""第一批闭环：健康检查、产品解释、合规阻断、幂等和租户隔离。"""

from fastapi.testclient import TestClient

from app.api.deps import container
from app.main import app


client = TestClient(app)


def test_health_and_product_explanation():
    assert client.get("/health/live").json()["status"] == "ok"
    result = client.post("/api/v1/consultations", headers={"Idempotency-Key": "one"}, json={"question": "请解释示例基金的主要风险和费用"})
    assert result.status_code == 200
    body = result.json()
    assert body["data"]["status"] == "completed"
    assert "管理费" in body["data"]["answer"]


def test_compliance_block_and_audit_chain():
    result = client.post("/api/v1/consultations", headers={"Idempotency-Key": "two"}, json={"question": "保证我一年赚10%，稳赚不赔"})
    assert result.json()["data"]["status"] == "blocked"
    case_id = result.json()["data"]["case_id"]
    audit = client.get(f"/api/v1/audit/{case_id}")
    assert audit.status_code == 200
    assert audit.json()["data"]["chain_valid"] is True


def test_idempotency_conflict():
    headers = {"Idempotency-Key": "same-key"}
    first = client.post("/api/v1/consultations", headers=headers, json={"question": "请解释产品费用"})
    second = client.post("/api/v1/consultations", headers=headers, json={"question": "请解释产品风险"})
    assert first.status_code == 200
    assert second.status_code == 409


def test_profile_is_persisted_in_workflow_store():
    updated = client.put(
        "/api/v1/users/me/profile",
        headers={"If-Match": "0"},
        json={"risk_level": "medium", "horizon_years": 5, "liquidity_need": "中期", "confirmed": True},
    )
    assert updated.status_code == 200
    profile = client.get("/api/v1/users/me/profile")
    assert profile.status_code == 200
    assert profile.json()["data"]["risk_level"] == "medium"
    assert profile.json()["data"]["version"] == 1


def test_report_is_tenant_scoped_and_persisted():
    consultation = client.post(
        "/api/v1/consultations",
        headers={"Idempotency-Key": "report-consultation"},
        json={"question": "请解释产品费用"},
    )
    case_id = consultation.json()["data"]["case_id"]
    created = client.post("/api/v1/reports", json={"case_id": case_id})
    assert created.status_code == 200
    report_id = created.json()["data"]["report_id"]
    fetched = client.get(f"/api/v1/reports/{report_id}")
    assert fetched.status_code == 200
    assert fetched.json()["data"]["report_id"] == report_id
    hidden = client.get(f"/api/v1/reports/{report_id}", headers={"X-Dev-Tenant-Id": "other-tenant", "X-Dev-User-Id": "dev-user"})
    assert hidden.status_code == 404


    created = client.post("/api/v1/documents", json={"title": "重建索引文档", "content": "流动性和期限风险说明"})
    assert created.status_code == 200
    container.retriever._documents.clear()

    found = client.post("/api/v1/knowledge/search", json={"query": "流动性"})
    assert found.status_code == 200
    assert found.json()["data"]["results"]

    created = client.post("/api/v1/documents", json={"title": "授权研报", "content": "现金流和偿债风险分析"})
    assert created.status_code == 200
    found = client.post("/api/v1/knowledge/search", json={"query": "现金流"})
    assert found.json()["data"]["results"]
    hidden = client.post("/api/v1/knowledge/search", headers={"X-Dev-Tenant-Id": "other-tenant", "X-Dev-User-Id": "dev-user"}, json={"query": "现金流"})
    assert hidden.json()["data"]["results"] == []
