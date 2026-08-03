from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def admin_headers() -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"login": "admin", "password": "Passw0rd!"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_health_check() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_login_happy_path() -> None:
    response = client.post(
        "/auth/login",
        json={"login": "admin", "password": "Passw0rd!"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["username"] == "admin"


def test_login_rejects_invalid_password() -> None:
    response = client.post(
        "/auth/login",
        json={"login": "admin", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_access_token_authorizes_protected_endpoint() -> None:
    login_response = client.post(
        "/auth/login",
        json={"login": "admin", "password": "Passw0rd!"},
    )
    access_token = login_response.json()["access_token"]

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "admin"


def test_roles_list_is_summary_and_role_detail_has_permissions() -> None:
    login_response = client.post(
        "/auth/login",
        json={"login": "admin", "password": "Passw0rd!"},
    )
    headers = {
        "Authorization": f"Bearer {login_response.json()['access_token']}"
    }

    list_response = client.get("/roles", headers=headers)
    assert list_response.status_code == 200
    roles = list_response.json()
    assert roles
    assert "permissions" not in roles[0]

    admin_role = next(role for role in roles if role["name"] == "admin")
    detail_response = client.get(f"/roles/{admin_role['id']}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["permissions"]

    permissions_response = client.get("/roles/permissions/all", headers=headers)
    assert permissions_response.status_code == 200
    permissions = permissions_response.json()
    assert permissions
    assert {"id", "code", "description"} <= permissions[0].keys()


def test_audit_logs_serialize_ip_addresses() -> None:
    login_response = client.post(
        "/auth/login",
        json={"login": "admin", "password": "Passw0rd!"},
    )
    headers = {
        "Authorization": f"Bearer {login_response.json()['access_token']}"
    }

    response = client.get("/audit-logs?page=1&size=20", headers=headers)

    assert response.status_code == 200
    assert response.json()
    ip_address = response.json()[0]["ip_address"]
    assert ip_address is None or isinstance(ip_address, str)


def test_users_list_supports_search_and_pagination() -> None:
    response = client.get(
        "/users?page=1&size=5&search=admin", headers=admin_headers()
    )
    assert response.status_code == 200
    body = response.json()
    assert {"items", "page", "size", "total"} <= body.keys()
    assert body["page"] == 1
    assert body["size"] == 5
    assert body["total"] >= 1
    assert all("admin" in item["username"] for item in body["items"])


def test_admin_cannot_deactivate_own_account() -> None:
    me = client.get("/auth/me", headers=admin_headers()).json()
    response = client.post(
        f"/users/{me['id']}/deactivate", headers=admin_headers()
    )
    assert response.status_code == 422
    assert "own account" in response.json()["detail"]


def test_role_lifecycle_and_admin_safeguards() -> None:
    headers = admin_headers()
    name = f"test_role_{uuid4().hex[:8]}"
    created = client.post(
        "/roles",
        headers=headers,
        json={"name": name, "description": "Initial"},
    )
    assert created.status_code == 201
    role_id = created.json()["id"]

    updated = client.put(
        f"/roles/{role_id}",
        headers=headers,
        json={"name": name, "description": "Updated"},
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Updated"

    permission = client.get("/roles/permissions/all", headers=headers).json()[0]
    assigned = client.put(
        f"/roles/{role_id}/permissions",
        headers=headers,
        json={"permission_ids": [permission["id"]]},
    )
    assert assigned.status_code == 200
    assert assigned.json()["permissions"][0]["id"] == permission["id"]

    deactivated = client.delete(f"/roles/{role_id}", headers=headers)
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    admin_role = next(
        role for role in client.get("/roles", headers=headers).json()
        if role["name"] == "admin"
    )
    assert client.delete(f"/roles/{admin_role['id']}", headers=headers).status_code == 422
    assert client.put(
        f"/roles/{admin_role['id']}/permissions",
        headers=headers,
        json={"permission_ids": []},
    ).status_code == 422


def test_user_without_permission_cannot_access_users() -> None:
    suffix = uuid4().hex[:8]
    created = client.post(
        "/users",
        headers=admin_headers(),
        json={
            "username": f"basic_{suffix}",
            "first_name": "Basic",
            "last_name": "User",
            "email": f"basic_{suffix}@example.com",
            "password": "Passw0rd!",
            "role_ids": [],
        },
    )
    assert created.status_code == 201
    login = client.post(
        "/auth/login",
        json={"login": f"basic_{suffix}", "password": "Passw0rd!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/users", headers=headers).status_code == 403
