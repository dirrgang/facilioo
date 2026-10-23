"""Offline request-contract regression tests based on the documented Facilioo API v2."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from custom_components.facilioo.api import FaciliooApiClient
from custom_components.facilioo.const import (
    ACCOUNT_MYSELF_ENDPOINT,
    API_VERSION,
    BASE_URL,
    CONSUMPTION_TYPES_ENDPOINT,
    EXTENDED_READINGS_ENDPOINT,
    LOGIN_ENDPOINT,
    METERS_ENDPOINT,
    PAGE_SIZE,
    READINGS_ENDPOINT,
    READINGS_SEARCH_ENDPOINT,
)


def _contract() -> dict[str, Any]:
    """Read the reviewed public endpoint-contract fixture without network access."""
    path = Path(__file__).parent / "fixtures" / "facilioo_api_v2_contract.json"
    return json.loads(path.read_text(encoding="utf-8"))


class _Response:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.status = 200
        self.headers: dict[str, str] = {}

    async def __aenter__(self) -> _Response:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def json(self, *, content_type: str | None = None) -> Any:
        return self.payload


class _Session:
    def __init__(self, payloads: list[Any]) -> None:
        self.responses = [_Response(payload) for payload in payloads]
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def request(self, method: str, url: str, **kwargs: Any) -> _Response:
        self.calls.append((method, url, kwargs))
        if not self.responses:
            raise AssertionError("Unexpected request in mocked API contract test")
        return self.responses.pop(0)


def _empty_page() -> dict[str, Any]:
    return {
        "items": [],
        "pageNumber": 1,
        "totalPages": 1,
        "totalCount": 0,
        "hasPreviousPage": False,
        "hasNextPage": False,
    }


def test_documented_endpoint_constants_match_reviewed_contract() -> None:
    contract = _contract()
    endpoints = contract["endpoints"]
    expected = {
        "login": LOGIN_ENDPOINT,
        "myself": ACCOUNT_MYSELF_ENDPOINT,
        "meters": METERS_ENDPOINT,
        "consumption_types": CONSUMPTION_TYPES_ENDPOINT,
        "readings": READINGS_ENDPOINT,
        "extended_readings": EXTENDED_READINGS_ENDPOINT,
        "search_readings": READINGS_SEARCH_ENDPOINT,
    }
    assert API_VERSION == contract["api_version"] == "2.0"
    assert BASE_URL == contract["base_url"]
    assert set(endpoints) == set(expected)
    for name, path in expected.items():
        assert endpoints[name]["path"] == path
        assert endpoints[name]["reference"].startswith("https://developers.facilioo.de/reference/")


@pytest.mark.asyncio
async def test_login_matches_documented_request_contract_and_never_skips_mfa() -> None:
    contract = _contract()
    session = _Session([{"accessToken": "synthetic-token", "account": {"id": 123}}])
    client = FaciliooApiClient(session, "example@example.invalid", "synthetic-password")
    assert await client.async_login() == 123

    method, url, options = session.calls[0]
    assert method == contract["endpoints"]["login"]["method"] == "POST"
    assert url == BASE_URL + contract["endpoints"]["login"]["path"]
    assert set(options["json"]) == set(contract["endpoints"]["login"]["required_body"])
    assert options["json"]["skipMultiFactorAuthentication"] is False
    assert options["headers"]["api-version"] == API_VERSION
    assert options["headers"]["Content-Type"] == "application/json"
    assert "Authorization" not in options["headers"]


@pytest.mark.asyncio
async def test_account_identity_fallback_matches_documented_get_endpoint() -> None:
    contract = _contract()
    session = _Session([{"accessToken": "synthetic-token"}, {"id": 123}])
    client = FaciliooApiClient(session, "example@example.invalid", "synthetic-password")
    assert await client.async_login() == 123

    method, url, options = session.calls[1]
    assert method == contract["endpoints"]["myself"]["method"] == "GET"
    assert url == BASE_URL + contract["endpoints"]["myself"]["path"]
    assert options["headers"]["Authorization"] == "Bearer synthetic-token"
    assert options["headers"]["api-version"] == API_VERSION


@pytest.mark.parametrize(
    ("endpoint_name", "client_method"),
    [
        ("meters", "async_get_meters"),
        ("consumption_types", "async_get_consumption_types"),
        ("readings", "async_get_readings"),
        ("extended_readings", "async_get_extended_readings"),
    ],
)
@pytest.mark.asyncio
async def test_paginated_get_requests_follow_documented_contract(
    endpoint_name: str, client_method: str
) -> None:
    contract = _contract()
    session = _Session([_empty_page()])
    client = FaciliooApiClient(session, "example@example.invalid", "synthetic-password")
    client._token = "synthetic-token"

    assert await getattr(client, client_method)() == ()
    method, url, options = session.calls[0]
    assert method == contract["endpoints"][endpoint_name]["method"] == "GET"
    assert url == BASE_URL + contract["endpoints"][endpoint_name]["path"]
    assert options["params"] == {
        "PageNumber": contract["pagination"]["first_page"],
        "PageSize": contract["pagination"]["max_page_size"],
    }
    assert PAGE_SIZE == 100
    assert options["headers"]["api-version"] == API_VERSION
    assert options["headers"]["Authorization"] == "Bearer synthetic-token"


@pytest.mark.asyncio
async def test_search_request_uses_documented_body_fields_and_utc_timestamp() -> None:
    contract = _contract()
    session = _Session([_empty_page()])
    client = FaciliooApiClient(session, "example@example.invalid", "synthetic-password")
    client._token = "synthetic-token"

    local_time = datetime(2026, 8, 16, 18, tzinfo=timezone(timedelta(hours=2)))
    await client.async_search_readings(changed_since=local_time, dates=["2026-08"])
    method, url, options = session.calls[0]

    assert method == contract["endpoints"]["search_readings"]["method"] == "POST"
    assert url == BASE_URL + contract["endpoints"]["search_readings"]["path"]
    assert set(options["json"]) <= set(
        contract["endpoints"]["search_readings"]["documented_body_fields"]
    )
    assert options["json"] == {
        "orderBy": ["readingDate asc"],
        "changedSince": "2026-08-16T16:00:00Z",
        "dates": ["2026-08"],
    }
    assert options["params"] == {"PageNumber": 1, "PageSize": 100}
    assert options["headers"]["api-version"] == API_VERSION
    assert options["headers"]["Content-Type"] == "application/json"
    assert options["headers"]["Authorization"] == "Bearer synthetic-token"


@pytest.mark.asyncio
async def test_has_next_page_contract_fetches_each_page_once() -> None:
    session = _Session(
        [
            {
                "items": [{"id": 1}],
                "pageNumber": 1,
                "totalPages": 2,
                "totalCount": 2,
                "hasPreviousPage": False,
                "hasNextPage": True,
            },
            {
                "items": [{"id": 2}],
                "pageNumber": 2,
                "totalPages": 2,
                "totalCount": 2,
                "hasPreviousPage": True,
                "hasNextPage": False,
            },
        ]
    )
    client = FaciliooApiClient(session, "example@example.invalid", "synthetic-password")
    client._token = "synthetic-token"

    result = await client._paginate(METERS_ENDPOINT, page_size=100)
    assert [item["id"] for item in result] == [1, 2]
    assert [options["params"]["PageNumber"] for _, _, options in session.calls] == [1, 2]
