"""第二批当前已落地能力：组合诊断、人工复核和租户隔离。"""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_portfolio_diagnosis_requires_confirmed_profile_for_personalized_use():
    result = client.post("/api/v1/portfolio/diagnoses", json={"portfolio_id": "portfolio_demo"})
    assert result.status_code == 200
    data = result.json()["data"]
    assert data["status"] == "human_review"
    assert data["total_market_value"] == 232345.0
    assert any("风险画像未确认" in warning for warning in data["warnings"])
    assert data["industry_exposure"]["食品饮料"] > 0


def test_portfolio_diagnosis_with_confirmed_profile_and_review():
    result = client.post(
        "/api/v1/portfolio/diagnoses",
        json={"portfolio_id": "portfolio_demo", "risk_profile": {"risk_level": "medium", "horizon_years": 5, "liquidity_need": "low", "confirmed": True}},
        headers={"X-Dev-Tenant-Id": "review-tenant", "X-Dev-User-Id": "advisor-1"},
    )
    assert result.status_code == 200
    data = result.json()["data"]
    assert data["status"] == "human_review"
    diagnosis_id = data["diagnosis_id"]
    reviewed = client.post(
        f"/api/v1/portfolio/diagnoses/{diagnosis_id}/review",
        json={"decision": "approve", "note": "已核验样例数据"},
        headers={"X-Dev-Tenant-Id": "review-tenant", "X-Dev-User-Id": "reviewer-1"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["data"]["status"] == "approved"
    audit = client.get(f"/api/v1/audit/{diagnosis_id}", headers={"X-Dev-Tenant-Id": "review-tenant", "X-Dev-User-Id": "reviewer-1"})
    assert audit.status_code == 200
    assert audit.json()["data"]["chain_valid"] is True


def test_portfolio_diagnosis_is_tenant_scoped():
    result = client.post("/api/v1/portfolio/diagnoses", json={"portfolio_id": "portfolio_demo"}, headers={"X-Dev-Tenant-Id": "tenant-a", "X-Dev-User-Id": "dev-user"})
    diagnosis_id = result.json()["data"]["diagnosis_id"]
    hidden = client.get(f"/api/v1/portfolio/diagnoses/{diagnosis_id}", headers={"X-Dev-Tenant-Id": "tenant-b", "X-Dev-User-Id": "dev-user"})
    assert hidden.status_code == 404
