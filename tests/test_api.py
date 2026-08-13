"""Tests for HTTP behavior and pagination."""

from __future__ import annotations

import json

import aiohttp
import pytest

from custom_components.facilioo.api import (
    FaciliooApiClient,
    FaciliooAuthenticationError,
    FaciliooConnectionError,
    FaciliooRateLimitError,
    FaciliooResponseError,
)


class FakeResponse:
    def __init__(self, payload=None, status=200, headers=None, text=""):
        self.payload = payload
        self.status = status
        self.headers = headers or {}
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def json(self, content_type=None):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload

    async def text(self):
        return self._text


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.mark.asyncio
async def test_successful_login_does_not_put_credentials_in_headers():
    session = FakeSession([FakeResponse({"accessToken": "secret-token"})])
    client = FaciliooApiClient(session, "resident@example.test", "secret-password")
    await client.async_login()
    _, _, kwargs = session.calls[0]
    assert "Authorization" not in kwargs["headers"]
    assert kwargs["json"]["skipMultiFactorAuthentication"] is False


@pytest.mark.asyncio
async def test_wrong_credentials_are_safe():
    client = FaciliooApiClient(
        FakeSession([FakeResponse(status=401)]), "resident@example.test", "secret-password"
    )
    with pytest.raises(FaciliooAuthenticationError) as error:
        await client.async_login()
    assert "secret-password" not in str(error.value)
    assert "resident@example.test" not in str(error.value)


@pytest.mark.asyncio
async def test_server_timeout_rate_limit_and_invalid_json():
    for response, exception in (
        (FakeResponse(status=503), FaciliooConnectionError),
        (TimeoutError(), FaciliooConnectionError),
        (FakeResponse(status=429, headers={"Retry-After": "42"}), FaciliooRateLimitError),
        (
            FakeResponse(json.JSONDecodeError("bad", "x", 0)),
            FaciliooResponseError,
        ),
    ):
        client = FaciliooApiClient(FakeSession([response]), "x", "y")
        with pytest.raises(exception) as error:
            await client.async_login()
        if isinstance(error.value, FaciliooRateLimitError):
            assert error.value.retry_after == 42


@pytest.mark.asyncio
async def test_pagination_requests_every_page(meter_payload):
    first = dict(meter_payload)
    first["items"] = first["items"][:2]
    first["totalCount"] = 3
    second = {"items": meter_payload["items"][2:], "totalCount": 3}
    session = FakeSession(
        [FakeResponse({"accessToken": "token"}), FakeResponse(first), FakeResponse(second)]
    )
    client = FaciliooApiClient(session, "x", "y")
    await client.async_login()
    meters = await client._paginate("/api/consumption-meters", page_size=2)
    assert len(meters) == 3
    assert session.calls[2][2]["params"]["PageNumber"] == 2


@pytest.mark.asyncio
async def test_pagination_uses_received_count_when_server_caps_page_size():
    first = {"items": [{"id": item} for item in range(100)], "totalCount": 150}
    second = {"items": [{"id": item} for item in range(100, 150)], "totalCount": 150}
    session = FakeSession([FakeResponse(first), FakeResponse(second)])
    client = FaciliooApiClient(session, "x", "y")
    client._token = "token"

    items = await client._paginate("/api/consumption-readings", page_size=1000)

    assert len(items) == 150
    assert session.calls[1][2]["params"]["PageNumber"] == 2


@pytest.mark.asyncio
async def test_reading_endpoints_request_supported_page_size():
    session = FakeSession(
        [
            FakeResponse({"items": [], "totalCount": 0}),
            FakeResponse({"items": [], "totalCount": 0}),
        ]
    )
    client = FaciliooApiClient(session, "x", "y")
    client._token = "token"

    await client.async_get_readings()
    await client.async_get_extended_readings()

    assert [call[2]["params"]["PageSize"] for call in session.calls] == [100, 100]


@pytest.mark.asyncio
async def test_aiohttp_error_is_connection_error():
    client = FaciliooApiClient(FakeSession([aiohttp.ClientError()]), "x", "y")
    with pytest.raises(FaciliooConnectionError):
        await client.async_login()
