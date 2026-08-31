import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_application(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/applications",
        json={"company_name": "Google", "role_title": "SWE Intern"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["company_name"] == "Google"
    assert body["role_title"] == "SWE Intern"
    assert body["current_status"] == "APPLIED"


@pytest.mark.asyncio
async def test_create_application_requires_auth(client: AsyncClient):
    response = await client.post(
        "/applications",
        json={"company_name": "Google", "role_title": "SWE Intern"},
    )

    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_applications_only_returns_own(
    client: AsyncClient, auth_headers: dict
):
    await client.post(
        "/applications",
        json={"company_name": "Amazon", "role_title": "Backend Intern"},
        headers=auth_headers,
    )

    other_email = f"other-{uuid.uuid4()}@example.com"
    other_password = "anotherpassword123"
    await client.post(
        "/auth/register", json={"email": other_email, "password": other_password}
    )
    other_login = await client.post(
        "/auth/login", json={"email": other_email, "password": other_password}
    )
    other_headers = {
        "Authorization": f"Bearer {other_login.json()['access_token']}"
    }

    await client.post(
        "/applications",
        json={"company_name": "Meta", "role_title": "Infra Intern"},
        headers=other_headers,
    )

    response = await client.get("/applications", headers=auth_headers)

    assert response.status_code == 200
    companies = [app["company_name"] for app in response.json()]
    assert "Amazon" in companies
    assert "Meta" not in companies


@pytest.mark.asyncio
async def test_get_application_not_owned_returns_404(client: AsyncClient):
    email_a = f"a-{uuid.uuid4()}@example.com"
    email_b = f"b-{uuid.uuid4()}@example.com"
    password = "password123"

    await client.post("/auth/register", json={"email": email_a, "password": password})
    login_a = await client.post("/auth/login", json={"email": email_a, "password": password})
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    create_response = await client.post(
        "/applications",
        json={"company_name": "Netflix", "role_title": "Intern"},
        headers=headers_a,
    )
    application_id = create_response.json()["id"]

    await client.post("/auth/register", json={"email": email_b, "password": password})
    login_b = await client.post("/auth/login", json={"email": email_b, "password": password})
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    response = await client.get(f"/applications/{application_id}", headers=headers_b)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_partial_update_only_changes_provided_field(
    client: AsyncClient, auth_headers: dict
):
    create_response = await client.post(
        "/applications",
        json={"company_name": "Stripe", "role_title": "Backend Intern"},
        headers=auth_headers,
    )
    application_id = create_response.json()["id"]

    update_response = await client.patch(
        f"/applications/{application_id}",
        json={"role_title": "Senior Backend Intern"},
        headers=auth_headers,
    )

    assert update_response.status_code == 200
    body = update_response.json()
    assert body["role_title"] == "Senior Backend Intern"
    assert body["company_name"] == "Stripe"


@pytest.mark.asyncio
async def test_valid_status_transition(client: AsyncClient, auth_headers: dict):
    create_response = await client.post(
        "/applications",
        json={"company_name": "Adobe", "role_title": "Intern"},
        headers=auth_headers,
    )
    application_id = create_response.json()["id"]

    response = await client.patch(
        f"/applications/{application_id}/status",
        json={"target_status": "OA1"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["current_status"] == "OA1"


@pytest.mark.asyncio
async def test_invalid_status_transition_returns_400(
    client: AsyncClient, auth_headers: dict
):
    create_response = await client.post(
        "/applications",
        json={"company_name": "Adobe", "role_title": "Intern"},
        headers=auth_headers,
    )
    application_id = create_response.json()["id"]

    response = await client.patch(
        f"/applications/{application_id}/status",
        json={"target_status": "OFFER"},
        headers=auth_headers,
    )

    assert response.status_code == 400

@pytest.mark.asyncio
async def test_status_transition_with_deadline_via_api(
    client: AsyncClient, auth_headers: dict
):
    create_response = await client.post(
        "/applications",
        json={"company_name": "Adobe", "role_title": "Intern"},
        headers=auth_headers,
    )
    application_id = create_response.json()["id"]
    deadline_value = "2026-09-15T10:00:00+00:00"

    response = await client.patch(
        f"/applications/{application_id}/status",
        json={"target_status": "OA1", "deadline": deadline_value},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["current_status"] == "OA1"
    assert body["deadline"] is not None