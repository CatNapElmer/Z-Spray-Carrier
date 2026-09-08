import pytest
from fastapi.testclient import TestClient
from main import app
from models import ProjectParameters
from drawings import fraction_str
from optimizer import optimize_stock

client = TestClient(app)

def test_fraction_str():
    assert fraction_str(1.0) == "1"
    assert fraction_str(1.5) == "1 1/2"
    assert fraction_str(1.25) == "1 1/4"
    assert fraction_str(0.125) == "1/8"
    assert fraction_str(1.0625) == "1 1/16"
    assert fraction_str(1.1875) == "1 3/16"

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200

def test_geometry():
    params = ProjectParameters(carrier_deck_length=65.0)
    response = client.post("/api/geometry", json=params.model_dump())
    assert response.status_code == 200
    data = response.json()
    assert "bom" in data
    # Check that M1 length is 65.0
    m1 = next((item for item in data["bom"] if item["mark"] == "M1"), None)
    assert m1 is not None
    assert m1["cut_length"] == 65.0

def test_optimizer():
    cut_list = [
        {"mark": "M1", "raw_section": "2x2", "cut_length": 60.0, "quantity": 1},
        {"mark": "M2", "raw_section": "2x2", "cut_length": 60.0, "quantity": 1},
        {"mark": "M3", "raw_section": "2x2", "cut_length": 130.0, "quantity": 1},
    ]
    opt = optimize_stock(cut_list, [240.0], saw_kerf=0.125)
    
    assert len(opt["purchase_list"]) == 1
    assert opt["purchase_list"][0]["quantity"] == 2 # Need two 240" sticks (60+60+130 = 250 > 240)
