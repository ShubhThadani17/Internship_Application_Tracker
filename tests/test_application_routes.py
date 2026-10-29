import uuid
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import AnalyticsSnapshot, User

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


@pytest.mark.asyncio
async def test_get_analytics_computes_current_user_data(
    client: AsyncClient,
    auth_headers: dict,
):
    create_response = await client.post(
        "/applications",
        json={
            "company_name": "OnDemandAnalyticsTestCo",
            "role_title": "Backend Intern",
        },
        headers=auth_headers,
    )

    assert create_response.status_code == 201

    response = await client.get(
        "/analytics",
        headers=auth_headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert "data" in body
    assert "computed_at" in body
    assert "funnel_counts" in body["data"]
    assert body["data"]["funnel_counts"]["APPLIED"] >= 1


@pytest.mark.asyncio
async def test_patch_deadline_set_preserve_and_clear(
    client: AsyncClient,
    auth_headers: dict,
):
    # Create an application without a deadline.
    create_response = await client.post(
        "/applications",
        json={
            "company_name": "DeadlineTestCo",
            "role_title": "Backend Intern",
        },
        headers=auth_headers,
    )

    assert create_response.status_code == 201

    application_id = create_response.json()["id"]
    assert create_response.json()["deadline"] is None

    # 1. Set the deadline.
    deadline_value = "2026-11-15T10:00:00+00:00"

    set_response = await client.patch(
        f"/applications/{application_id}",
        json={"deadline": deadline_value},
        headers=auth_headers,
    )

    assert set_response.status_code == 200
    saved_deadline = set_response.json()["deadline"]
    assert saved_deadline is not None

    # 2. Update another field without changing the deadline.
    update_response = await client.patch(
        f"/applications/{application_id}",
        json={"role_title": "Software Engineer Intern"},
        headers=auth_headers,
    )

    assert update_response.status_code == 200
    assert (
        update_response.json()["role_title"]
        == "Software Engineer Intern"
    )
    assert update_response.json()["deadline"] == saved_deadline

    # 3. Explicitly clear the deadline.
    clear_response = await client.patch(
        f"/applications/{application_id}",
        json={"deadline": None},
        headers=auth_headers,
    )

    assert clear_response.status_code == 200
    assert clear_response.json()["deadline"] is None

@pytest.mark.asyncio
async def test_user_cannot_access_another_users_application(
    client: AsyncClient,
    auth_headers: dict,
):
    # User A creates an application.
    create_response = await client.post(
        "/applications",
        json={
            "company_name": "PrivateCompany",
            "role_title": "Backend Intern",
        },
        headers=auth_headers,
    )

    assert create_response.status_code == 201

    application = create_response.json()
    application_id = application["id"]

    # Register User B.
    email = f"another-user-{uuid4()}@example.com"
    password = "StrongPassword123!"

    register_response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    assert register_response.status_code == 201

    # Authenticate as User B.
    login_response = await client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    user_b_headers = {
        "Authorization": (
            f"Bearer {login_response.json()['access_token']}"
        )
    }

    # User B must not be able to retrieve User A's application.
    get_response = await client.get(
        f"/applications/{application_id}",
        headers=user_b_headers,
    )

    assert get_response.status_code == 404

    # User B must not be able to modify User A's application.
    patch_response = await client.patch(
        f"/applications/{application_id}",
        json={"role_title": "Compromised Role"},
        headers=user_b_headers,
    )

    assert patch_response.status_code == 404

    # User B's application list must not contain User A's application.
    list_response = await client.get(
        "/applications",
        headers=user_b_headers,
    )

    assert list_response.status_code == 200

    user_b_application_ids = {
        item["id"] for item in list_response.json()
    }

    assert application_id not in user_b_application_ids

    # Confirm User A's application remains unchanged.
    owner_response = await client.get(
        f"/applications/{application_id}",
        headers=auth_headers,
    )

    assert owner_response.status_code == 200
    assert owner_response.json()["role_title"] == "Backend Intern"