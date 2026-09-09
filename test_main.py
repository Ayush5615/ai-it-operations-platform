import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def use_test_database(monkeypatch):
    monkeypatch.setenv("DB_NAME", "it_operations_test")


def test_home():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "AI IT Operations Platform is running"}


def test_get_missing_ticket():
    response = client.get("/tickets/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Ticket not found"}


def test_create_ticket():
    response = client.post("/tickets", json={"title": "Test Ticket", "description": "Automated test ticket", "priority": "low"})
    assert response.status_code == 201
    data = response.json()
    assert data["message"] == "Ticket created successfully"
    assert data["ticket"]["title"] == "Test Ticket"
    assert data["ticket"]["priority"] == "low"


def test_get_tickets():
    response = client.get("/tickets")
    assert response.status_code == 200
    data = response.json()
    assert "tickets" in data
    assert isinstance(data["tickets"], list)


def test_update_ticket_status():
    create_response = client.post("/tickets", json={"title": "Status Test", "description": "Testing status update", "priority": "low"})
    assert create_response.status_code == 201
    ticket_id = create_response.json()["ticket"]["id"]

    response = client.put(f"/tickets/{ticket_id}/status", json={"status": "resolved"})
    assert response.status_code == 200
    assert response.json()["ticket"]["status"] == "resolved"


def test_delete_ticket():
    create_response = client.post("/tickets", json={"title": "Delete Test", "description": "Testing ticket deletion", "priority": "low"})
    assert create_response.status_code == 201
    ticket_id = create_response.json()["ticket"]["id"]

    response = client.delete(f"/tickets/{ticket_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Ticket deleted successfully"

    get_response = client.get(f"/tickets/{ticket_id}")
    assert get_response.status_code == 404
