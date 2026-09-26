# --- Authentication and RBAC Test Cases ---
from unittest.mock import patch

def test_auth_login_success(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "test123"})
    if response.status_code == 401:
        response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "DevOpsNexus@123"})
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    assert "token" in json_data["data"]
    assert json_data["data"]["username"] == "admin"
    assert json_data["data"]["role"] == "Administrator"
    assert "session_token" in response.cookies

def test_auth_change_password(client):
    # Log in first
    login_res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "test123"})
    if login_res.status_code == 401:
        login_res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "DevOpsNexus@123"})
        curr_pass = "DevOpsNexus@123"
    else:
        curr_pass = "test123"

    token = login_res.json()["data"]["token"]
    
    # Change password
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": curr_pass, "new_password": "NewAdminPass@123"},
        headers=headers
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Re-login with new password
    relogin_res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "NewAdminPass@123"})
    assert relogin_res.status_code == 200
    assert relogin_res.json()["data"]["require_password_change"] is False

    # Restore default password
    new_token = relogin_res.json()["data"]["token"]
    client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "NewAdminPass@123", "new_password": curr_pass},
        headers={"Authorization": f"Bearer {new_token}"}
    )

def test_auth_login_invalid_credentials(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrongpassword"})
    assert response.status_code == 401
    json_data = response.json()
    assert json_data["success"] is False

def test_auth_logout(client):
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    assert response.cookies.get("session_token") is None
