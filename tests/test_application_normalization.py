import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_application_normalizes_company_and_role(
    client: AsyncClient,
    auth_headers: dict,
):
    response = await client.post(
        "/applications",
        json={
            "company_name": "  Example Technologies  ",
            "role_title": "  BACKEND INTERN  ",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["company_name"] == "EXAMPLE TECHNOLOGIES"
    assert data["role_title"] == "backend intern"


@pytest.mark.asyncio
async def test_confirm_parsed_application_rejects_duplicate(
    client: AsyncClient,
    auth_headers: dict,
):
    # First, manually create the application.
    create_response = await client.post(
        "/applications",
        json={
            "company_name": "Example Technologies",
            "role_title": "Backend Intern",
        },
        headers=auth_headers,
    )

    assert create_response.status_code == 201

    # Now attempt to create the same application through email confirmation,
    # but use different capitalization and whitespace.
    confirm_response = await client.post(
        "/confirm-parsed-application",
        json={
            "application_id": None,
            "company_name": " example technologies ",
            "role_title": "BACKEND INTERN",
            "suggested_status": "INTERVIEW",
            "deadline": None,
            "is_new_application": True,
        },
        headers=auth_headers,
    )

    assert confirm_response.status_code == 409

    assert (
        "already exists"
        in confirm_response.json()["detail"]
    )


@pytest.mark.asyncio
async def test_same_company_different_roles_are_allowed(
    client: AsyncClient,
    auth_headers: dict,
):
    first_response = await client.post(
        "/applications",
        json={
            "company_name": "Google",
            "role_title": "Backend Intern",
        },
        headers=auth_headers,
    )

    second_response = await client.post(
        "/applications",
        json={
            "company_name": "GOOGLE",
            "role_title": "Frontend Intern",
        },
        headers=auth_headers,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    assert first_response.json()["id"] != second_response.json()["id"]

    assert first_response.json()["company_name"] == "GOOGLE"
    assert second_response.json()["company_name"] == "GOOGLE"

    assert first_response.json()["role_title"] == "backend intern"
    assert second_response.json()["role_title"] == "frontend intern"