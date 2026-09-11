import pytest
from fastapi.testclient import TestClient
from main import app


client = TestClient(app)


# --------------------------------------------------
# Use Test Database
# --------------------------------------------------

@pytest.fixture(autouse=True)
def use_test_database(monkeypatch):
    monkeypatch.setenv("DB_NAME", "it_operations_test")


# --------------------------------------------------
# Authentication Fixture
# --------------------------------------------------

@pytest.fixture
def auth_headers():

    username = "testuser"
    password = "Test@12345"

    register_response = client.post(
        "/register",
        json={
            "username": username,
            "password": password
        }
    )

    assert register_response.status_code in [201, 409]

    login_response = client.post(
        "/login",
        data={
            "username": username,
            "password": password
        }
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    return {
        "Authorization": f"Bearer {token}"
    }


# --------------------------------------------------
# Home Test
# --------------------------------------------------

def test_home():

    response = client.get("/")

    assert response.status_code == 200

    assert response.json() == {
        "message": "AI IT Operations Platform API is running"
    }


# --------------------------------------------------
# Registration Test
# --------------------------------------------------

def test_register():

    username = "registration_test_user"

    response = client.post(
        "/register",
        json={
            "username": username,
            "password": "Test@12345"
        }
    )

    assert response.status_code in [201, 409]


# --------------------------------------------------
# Login Test
# --------------------------------------------------

def test_login(auth_headers):

    assert "Authorization" in auth_headers

    assert auth_headers["Authorization"].startswith(
        "Bearer "
    )


# --------------------------------------------------
# Unauthorized Access Test
# --------------------------------------------------

def test_unauthorized_ticket_access():

    response = client.get("/tickets")

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Not authenticated"
    }


# --------------------------------------------------
# Get Missing Ticket
# --------------------------------------------------

def test_get_missing_ticket(auth_headers):

    response = client.get(
        "/tickets/999999",
        headers=auth_headers
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Ticket not found"
    }


# --------------------------------------------------
# Create Ticket
# --------------------------------------------------

def test_create_ticket(auth_headers):

    response = client.post(
        "/tickets",
        headers=auth_headers,
        json={
            "title": "Test Ticket",
            "description": "Automated test ticket",
            "priority": "low"
        }
    )

    assert response.status_code == 201

    data = response.json()

    assert data["title"] == "Test Ticket"

    assert data["description"] == "Automated test ticket"

    assert data["priority"] == "low"

    assert data["status"] == "open"

    assert "id" in data


# --------------------------------------------------
# Get Tickets
# --------------------------------------------------

def test_get_tickets(auth_headers):

    response = client.get(
        "/tickets",
        headers=auth_headers
    )

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)


# --------------------------------------------------
# Update Ticket Status
# --------------------------------------------------

def test_update_ticket_status(auth_headers):

    create_response = client.post(
        "/tickets",
        headers=auth_headers,
        json={
            "title": "Status Test",
            "description": "Testing status update",
            "priority": "low"
        }
    )

    assert create_response.status_code == 201

    ticket_id = create_response.json()["id"]

    response = client.put(
        f"/tickets/{ticket_id}/status",
        headers=auth_headers,
        json={
            "status": "resolved"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == ticket_id

    assert data["status"] == "resolved"


# --------------------------------------------------
# Delete Ticket
# --------------------------------------------------

def test_delete_ticket(auth_headers):

    create_response = client.post(
        "/tickets",
        headers=auth_headers,
        json={
            "title": "Delete Test",
            "description": "Testing ticket deletion",
            "priority": "low"
        }
    )

    assert create_response.status_code == 201

    ticket_id = create_response.json()["id"]

    response = client.delete(
        f"/tickets/{ticket_id}",
        headers=auth_headers
    )

    assert response.status_code == 200

    assert response.json() == {
        "message": "Ticket deleted successfully",
        "ticket_id": ticket_id
    }

    get_response = client.get(
        f"/tickets/{ticket_id}",
        headers=auth_headers
    )

    assert get_response.status_code == 404