"""Asynchronous client for the Facilioo API."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Mapping
from typing import Any

import aiohttp

from .const import (
    API_VERSION,
    BASE_URL,
    EXTENDED_READINGS_ENDPOINT,
    LOGIN_ENDPOINT,
    METERS_ENDPOINT,
    READINGS_ENDPOINT,
    REQUEST_TIMEOUT,
)
from .models import ConsumptionMeter, ConsumptionReading, FaciliooDataError

_LOGGER = logging.getLogger(__name__)


class FaciliooError(Exception):
    """Base error for safe, non-sensitive Facilioo failures."""


class FaciliooAuthenticationError(FaciliooError):
    """Credentials were rejected or authorization expired."""


class FaciliooMfaRequiredError(FaciliooAuthenticationError):
    """Multi-factor authentication is required and cannot be bypassed."""


class FaciliooConnectionError(FaciliooError):
    """The API could not be reached."""


class FaciliooRateLimitError(FaciliooError):
    """The API rate limit was reached."""

    def __init__(self, retry_after: int | None = None) -> None:
        super().__init__("Facilioo rate limit reached")
        self.retry_after = retry_after


class FaciliooResponseError(FaciliooError):
    """The API returned an unexpected response."""


class FaciliooApiClient:
    """Small API client using Home Assistant's shared aiohttp session."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._token: str | None = None

    async def async_login(self) -> None:
        """Authenticate and retain the access token in memory only."""
        data = await self._request(
            "POST",
            LOGIN_ENDPOINT,
            authenticated=False,
            json_body={
                "email": self._email,
                "password": self._password,
                "skipMultiFactorAuthentication": False,
            },
        )
        if not isinstance(data, Mapping):
            raise FaciliooResponseError("Unexpected login response")
        token = data.get("accessToken")
        if not isinstance(token, str) or not token:
            serialized = json.dumps(data).casefold()
            if "multifactor" in serialized or "multi-factor" in serialized or "mfa" in serialized:
                raise FaciliooMfaRequiredError("Multi-factor authentication is required")
            raise FaciliooResponseError("Login response did not contain an access token")
        self._token = token

    async def async_get_meters(self) -> tuple[ConsumptionMeter, ...]:
        raw = await self._paginate(METERS_ENDPOINT, page_size=100)
        return self._parse_items(raw, ConsumptionMeter.from_api, "meter")

    async def async_get_readings(self) -> tuple[ConsumptionReading, ...]:
        raw = await self._paginate(READINGS_ENDPOINT, page_size=1000)
        return self._parse_items(raw, ConsumptionReading.from_api, "reading")

    async def async_get_extended_readings(self) -> tuple[ConsumptionReading, ...]:
        raw = await self._paginate(EXTENDED_READINGS_ENDPOINT, page_size=1000)
        return self._parse_items(raw, ConsumptionReading.from_api, "reading")

    async def async_fetch_all(
        self,
    ) -> tuple[tuple[ConsumptionMeter, ...], tuple[ConsumptionReading, ...]]:
        """Login and fetch all consumptions in one deliberately infrequent cycle."""
        await self.async_login()
        meters = await self.async_get_meters()
        readings = await self.async_get_extended_readings()
        return meters, readings

    def clear_token(self) -> None:
        """Discard the in-memory token."""
        self._token = None

    async def _paginate(self, endpoint: str, page_size: int) -> list[Mapping[str, Any]]:
        items: list[Mapping[str, Any]] = []
        page = 1
        while page <= 1000:
            payload = await self._request(
                "GET", endpoint, params={"PageSize": page_size, "PageNumber": page}
            )
            page_items, has_next = self._page(payload, page, page_size)
            items.extend(item for item in page_items if isinstance(item, Mapping))
            if not has_next:
                return items
            page += 1
        raise FaciliooResponseError("Pagination exceeded the safety limit")

    @staticmethod
    def _page(payload: Any, page: int, page_size: int) -> tuple[list[Any], bool]:
        if isinstance(payload, list):
            return payload, len(payload) == page_size
        if not isinstance(payload, Mapping):
            raise FaciliooResponseError("Unexpected paginated response")
        page_items = next(
            (
                payload[key]
                for key in ("items", "data", "results", "entities")
                if isinstance(payload.get(key), list)
            ),
            None,
        )
        if page_items is None:
            raise FaciliooResponseError("Paginated response did not contain items")
        if isinstance(payload.get("hasNextPage"), bool):
            return page_items, bool(payload["hasNextPage"])
        total_pages = payload.get("totalPages") or payload.get("pageCount")
        if isinstance(total_pages, int):
            return page_items, page < total_pages
        total = payload.get("totalCount") or payload.get("count")
        if isinstance(total, int):
            return page_items, page * page_size < total
        return page_items, len(page_items) == page_size

    @staticmethod
    def _parse_items(raw: list[Mapping[str, Any]], parser: Any, label: str) -> tuple[Any, ...]:
        parsed = []
        for item in raw:
            try:
                parsed.append(parser(item))
            except FaciliooDataError as err:
                _LOGGER.warning("Skipping malformed Facilioo %s: %s", label, err)
        return tuple(parsed)

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        authenticated: bool = True,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> Any:
        headers = {"api-version": API_VERSION, "Accept": "application/json"}
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        if authenticated:
            if not self._token:
                raise FaciliooAuthenticationError("Not authenticated")
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                response = await self._session.request(
                    method,
                    f"{BASE_URL}{endpoint}",
                    headers=headers,
                    params=params,
                    json=json_body,
                )
                async with response:
                    if response.status in (401, 403):
                        self._token = None
                        raise FaciliooAuthenticationError("Authentication failed")
                    if response.status == 429:
                        retry = response.headers.get("Retry-After")
                        retry_seconds = int(retry) if retry and retry.isdigit() else None
                        raise FaciliooRateLimitError(retry_seconds)
                    if response.status >= 500:
                        raise FaciliooConnectionError("Facilioo service error")
                    if response.status >= 400:
                        if not authenticated and response.status in (400, 409):
                            body = (await response.text()).casefold()
                            if "multifactor" in body or "multi-factor" in body or "mfa" in body:
                                raise FaciliooMfaRequiredError(
                                    "Multi-factor authentication is required"
                                )
                            raise FaciliooAuthenticationError("Authentication failed")
                        raise FaciliooResponseError(f"Facilioo API returned HTTP {response.status}")
                    try:
                        return await response.json(content_type=None)
                    except (aiohttp.ContentTypeError, json.JSONDecodeError, ValueError) as err:
                        raise FaciliooResponseError("Facilioo returned invalid JSON") from err
        except FaciliooError:
            raise
        except (TimeoutError, aiohttp.ClientError) as err:
            raise FaciliooConnectionError("Could not connect to Facilioo") from err
