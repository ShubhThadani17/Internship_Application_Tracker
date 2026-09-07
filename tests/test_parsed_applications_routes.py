from unittest.mock import patch

import pytest
from httpx import AsyncClient


FAKE_EXTRACTION_EXISTING_COMPANY = {
    "company_name": "Adobe",
    "role_title": "Intern",
    "stage": "OA",
    "deadline": "September 10th",
}

FAKE_EXTRACTION_NEW_COMPANY = {
    "company_name": "ColdEmailCorp",
    "role_title": "Backend Intern",
    "stage": "interview",
    "deadline": "next Monday",
}


@pytest.mark.asyncio
async def test_parse_email_finds_existing_application(client: AsyncClient, auth_headers: dict):
    create_response = await client.post(
        "/applications",
        json={"company_name": "Adobe", "role_title": "Intern"},
        headers=auth_headers,
    )
    application_id = create_response.json()["id"]

    with patch(
        "app.api.parsed_applications_routes.extract_email_details",
        return_value=FAKE_EXTRACTION_EXISTING_COMPANY,
    ):
        response = await client.post(
            "/parse-email",
            json={"raw_text": "You have been invited to complete an OA."},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["application_id"] == application_id
    assert body["is_new_application"] is False
    assert body["suggested_status"] == "OA1"


@pytest.mark.asyncio
async def test_parse_email_no_match_returns_new_application_suggestion(
    client: AsyncClient, auth_headers: dict
):
    with patch(
        "app.api.parsed_applications_routes.extract_email_details",
        return_value=FAKE_EXTRACTION_NEW_COMPANY,
    ):
        response = await client.post(
            "/parse-email",
            json={"raw_text": "We'd like to schedule an interview."},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["application_id"] is None
    assert body["is_new_application"] is True
    assert body["company_name"] == "ColdEmailCorp"
    assert body["suggested_status"] == "INTERVIEW"


@pytest.mark.asyncio
async def test_parse_email_requires_auth(client: AsyncClient):
    with patch(
        "app.api.parsed_applications_routes.extract_email_details",
        return_value=FAKE_EXTRACTION_NEW_COMPANY,
    ):
        response = await client.post(
            "/parse-email",
            json={"raw_text": "some text"},
        )

    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_confirm_parsed_application_updates_existing(
    client: AsyncClient, auth_headers: dict
):
    create_response = await client.post(
        "/applications",
        json={"company_name": "Stripe", "role_title": "Backend Intern"},
        headers=auth_headers,
    )
    application_id = create_response.json()["id"]

    response = await client.post(
        "/confirm-parsed-application",
        json={
            "application_id": application_id,
            "company_name": "Stripe",
            "role_title": "Backend Intern",
            "suggested_status": "OA1",
            "deadline": "2026-09-15T10:00:00+00:00",
            "is_new_application": False,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["current_status"] == "OA1"
    assert body["deadline"] is not None


@pytest.mark.asyncio
async def test_confirm_parsed_application_creates_new(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/confirm-parsed-application",
        json={
            "application_id": None,
            "company_name": "ColdEmailCorp",
            "role_title": "Backend Intern",
            "suggested_status": "INTERVIEW",
            "deadline": None,
            "is_new_application": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["current_status"] == "INTERVIEW"
    assert body["company_name"] == "ColdEmailCorp"


@pytest.mark.asyncio
async def test_confirm_parsed_application_rejects_other_users_application(
    client: AsyncClient, auth_headers: dict
):
    other_email = "other-parsed@example.com"
    other_password = "anotherpassword123"
    await client.post("/auth/register", json={"email": other_email, "password": other_password})
    other_login = await client.post(
        "/auth/login", json={"email": other_email, "password": other_password}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    create_response = await client.post(
        "/applications",
        json={"company_name": "Netflix", "role_title": "Intern"},
        headers=other_headers,
    )
    application_id = create_response.json()["id"]

    response = await client.post(
        "/confirm-parsed-application",
        json={
            "application_id": application_id,
            "company_name": "Netflix",
            "role_title": "Intern",
            "suggested_status": "OA1",
            "deadline": None,
            "is_new_application": False,
        },
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_confirm_parsed_application_invalid_transition_returns_400(
    client: AsyncClient, auth_headers: dict
):
    create_response = await client.post(
        "/applications",
        json={"company_name": "Adobe", "role_title": "Intern"},
        headers=auth_headers,
    )
    application_id = create_response.json()["id"]

    response = await client.post(
        "/confirm-parsed-application",
        json={
            "application_id": application_id,
            "company_name": "Adobe",
            "role_title": "Intern",
            "suggested_status": "OFFER",
            "deadline": None,
            "is_new_application": False,
        },
        headers=auth_headers,
    )

    assert response.status_code == 400