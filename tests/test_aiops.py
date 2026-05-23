"""
tests/test_aiops.py
===================
Automated tests to verify Pydantic request models validation and API direct endpoints.
"""

import pytest
from pydantic import ValidationError
from src.models.requests import DeviceAnalysisRequest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_pydantic_device_id_validation():
    # Valid device ID format
    req = DeviceAnalysisRequest(device_id="INV-WIFI-1234567890", include_history_days=7)
    assert req.device_id == "INV-WIFI-1234567890"
    
    # Invalid device ID format (should raise ValidationError)
    with pytest.raises(ValidationError):
        DeviceAnalysisRequest(device_id="INVALID-ID-123", include_history_days=7)

    with pytest.raises(ValidationError):
        DeviceAnalysisRequest(device_id="INV-WIFI-abc", include_history_days=7)


def test_agent_card_endpoint():
    # GET / should return valid agent_card.json matching specs
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Invincible WiFi Agent"
    assert "skills" in data
    assert len(data["skills"]) == 3


def test_analyze_device_endpoint():
    # POST /analyze should run diagnosis on a device
    payload = {
        "device_id": "INV-WIFI-1234567801",
        "include_history_days": 5
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "analysis" in data
    assert data["analysis"]["device_id"] == "INV-WIFI-1234567801"
    assert "severity" in data["analysis"]
    assert "root_cause" in data["analysis"]
    assert "requires_truck_roll" in data["analysis"]


def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "2.0.0"
