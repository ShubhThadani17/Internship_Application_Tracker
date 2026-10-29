from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.config import settings
from app.services.gemini_service import (
    GeminiConfigurationError,
    GeminiInvalidResponseError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    extract_email_details,
)


def _request():
    return httpx.Request(
        "POST",
        "https://generativelanguage.googleapis.com/test",
    )


def _valid_response():
    return httpx.Response(
        200,
        request=_request(),
        json={
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    '{"company_name":"Adobe",'
                                    '"role_title":"Backend Intern",'
                                    '"stage":"interview",'
                                    '"deadline":"2026-11-15"}'
                                )
                            }
                        ]
                    },
                }
            ]
        },
    )


def _mock_client(response=None, post_error=None):
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False

    if post_error is not None:
        client.post.side_effect = post_error
    else:
        client.post.return_value = response

    return client


@pytest.mark.asyncio
async def test_extract_email_details_parses_structured_response():
    client = _mock_client(response=_valid_response())

    with patch(
        "app.services.gemini_service.httpx.AsyncClient",
        return_value=client,
    ):
        result = await extract_email_details(
            "You have been invited to an interview at Adobe."
        )

    assert result == {
        "company_name": "Adobe",
        "role_title": "Backend Intern",
        "stage": "interview",
        "deadline": "2026-11-15",
    }

    client.post.assert_awaited_once()

    url = client.post.call_args.args[0]
    headers = client.post.call_args.kwargs["headers"]
    payload = client.post.call_args.kwargs["json"]

    assert f"/models/{settings.gemini_model}:generateContent" in url
    assert headers["x-goog-api-key"] == settings.gemini_api_key

    response_format = payload["generationConfig"]["responseFormat"]
    assert response_format["text"]["mimeType"] == "APPLICATION_JSON"

    required_fields = response_format["text"]["schema"]["required"]
    assert set(required_fields) == {
        "company_name",
        "role_title",
        "stage",
        "deadline",
    }


@pytest.mark.asyncio
async def test_extract_email_details_handles_timeout():
    client = _mock_client(
        post_error=httpx.ReadTimeout("Simulated timeout")
    )

    with patch(
        "app.services.gemini_service.httpx.AsyncClient",
        return_value=client,
    ):
        with pytest.raises(GeminiTimeoutError):
            await extract_email_details("Sample email")


@pytest.mark.asyncio
async def test_extract_email_details_handles_provider_rate_limit():
    response = httpx.Response(
        429,
        request=_request(),
        json={"error": {"message": "Quota exceeded"}},
    )

    client = _mock_client(response=response)

    with patch(
        "app.services.gemini_service.httpx.AsyncClient",
        return_value=client,
    ):
        with pytest.raises(GeminiRateLimitError):
            await extract_email_details("Sample email")


@pytest.mark.asyncio
async def test_extract_email_details_handles_invalid_api_key():
    response = httpx.Response(
        403,
        request=_request(),
        json={"error": {"message": "API key denied"}},
    )

    client = _mock_client(response=response)

    with patch(
        "app.services.gemini_service.httpx.AsyncClient",
        return_value=client,
    ):
        with pytest.raises(GeminiConfigurationError):
            await extract_email_details("Sample email")


@pytest.mark.asyncio
async def test_extract_email_details_rejects_missing_candidates():
    response = httpx.Response(
        200,
        request=_request(),
        json={"candidates": []},
    )

    client = _mock_client(response=response)

    with patch(
        "app.services.gemini_service.httpx.AsyncClient",
        return_value=client,
    ):
        with pytest.raises(GeminiInvalidResponseError):
            await extract_email_details("Sample email")


@pytest.mark.asyncio
async def test_extract_email_details_rejects_invalid_json():
    response = httpx.Response(
        200,
        request=_request(),
        json={
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [{"text": "this is not JSON"}]
                    },
                }
            ]
        },
    )

    client = _mock_client(response=response)

    with patch(
        "app.services.gemini_service.httpx.AsyncClient",
        return_value=client,
    ):
        with pytest.raises(GeminiInvalidResponseError):
            await extract_email_details("Sample email")


@pytest.mark.asyncio
async def test_extract_email_details_rejects_invalid_deadline():
    response = httpx.Response(
        200,
        request=_request(),
        json={
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    '{"company_name":"Adobe",'
                                    '"role_title":"Intern",'
                                    '"stage":"interview",'
                                    '"deadline":"next Monday"}'
                                )
                            }
                        ]
                    },
                }
            ]
        },
    )

    client = _mock_client(response=response)

    with patch(
        "app.services.gemini_service.httpx.AsyncClient",
        return_value=client,
    ):
        with pytest.raises(GeminiInvalidResponseError):
            await extract_email_details("Sample email")