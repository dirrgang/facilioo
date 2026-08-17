"""Asynchronous client for the Facilioo API."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import aiohttp

from .const import (
    ACCOUNT_MYSELF_ENDPOINT,
    API_VERSION,
    BASE_URL,
    EXTENDED_READINGS_ENDPOINT,
    LOGIN_ENDPOINT,
    METERS_ENDPOINT,
    PAGE_SIZE,
    READINGS_ENDPOINT,
    READINGS_SEARCH_ENDPOINT,
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
        self._account_id: int | None = None

    @property
    def account_id(self) -> int | None:
        """Return the authenticated Facilioo account ID, if known."""
        return self._account_id

    async def async_login(self) -> int:
        """Authenticate and return the stable Facilioo account ID."""
        self._account_id = None
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

        account_id = self._extract_account_id(data)
        if account_id is None:
            account = await self._request("GET", ACCOUNT_MYSELF_ENDPOINT)
            account_id = self._extract_account_id(account)
        if account_id is None:
            self._token = None
            raise FaciliooResponseError("Facilioo account response did not contain a valid ID")

        self._account_id = account_id
        return account_id

    async def async_get_meters(self) -> tuple[ConsumptionMeter, ...]:
        raw = await self._paginate(METERS_ENDPOINT, page_size=PAGE_SIZE)
        return self._parse_items(raw, ConsumptionMeter.from_api, "meter")

    async def async_get_readings(self) -> tuple[ConsumptionReading, ...]:
        raw = await self._paginate(READINGS_ENDPOINT, page_size=PAGE_SIZE)
        return self._parse_items(raw, ConsumptionReading.from_api, "reading")

    async def async_get_extended_readings(self) -> tuple[ConsumptionReading, ...]:
        raw = await self._paginate(EXTENDED_READINGS_ENDPOINT, page_size=PAGE_SIZE)
        return self._parse_items(raw, ConsumptionReading.from_api, "reading")

    async def async_search_readings(
        self,
        *,
        changed_since: datetime | None = None,
        dates: Sequence[str] | None = None,
    ) -> tuple[ConsumptionReading, ...]:
        """Search consumption readings using Facilioo's server-side filters."""
        body: dict[str, Any] = {"orderBy": ["readingDate asc"]}
        if changed_since is not None:
            if changed_since.tzinfo is None or changed_since.utcoffset() is None:
                raise ValueError("changed_since must be timezone-aware")
            body["changedSince"] = changed_since.astimezone(UTC).isoformat().replace("+00:00", "Z")
        if dates is not None:
            body["dates"] = list(dates)
        raw = await self._paginate(
            READINGS_SEARCH_ENDPOINT,
            page_size=PAGE_SIZE,
            method="POST",
            json_body=body,
        )
        return self._parse_items(raw, ConsumptionReading.from_api, "reading")

    async def async_fetch_all(
        self,
    ) -> tuple[tuple[ConsumptionMeter, ...], tuple[ConsumptionReading, ...]]:
        """Login and fetch a complete consumption snapshot."""
        await self.async_login()
        meters = await self.async_get_meters()
        readings = await self.async_search_readings()
        return meters, readings

    async def async_fetch_changes(
        self, changed_since: datetime
    ) -> tuple[tuple[ConsumptionMeter, ...], tuple[ConsumptionReading, ...]]:
        """Login and fetch meters plus readings changed since the supplied watermark."""
        await self.async_login()
        meters = await self.async_get_meters()
        readings = await self.async_search_readings(changed_since=changed_since)
        return meters, readings

    def clear_token(self) -> None:
        """Discard authentication state held only in memory."""
        self._token = None
        self._account_id = None

    async def _paginate(
        self,
        endpoint: str,
        page_size: int,
        *,
        method: str = "GET",
        json_body: Mapping[str, Any] | None = None,
    ) -> list[Mapping[str, Any]]:
        items: list[Mapping[str, Any]] = []
        page = 1
        while page <= 1000:
            payload = await self._request(
                method,
                endpoint,
                params={"PageSize": page_size, "PageNumber": page},
                json_body=json_body,
            )
            page_items, has_next = self._page(payload, page, page_size, items_seen=len(items))
            items.extend(item for item in page_items if isinstance(item, Mapping))
            if not has_next:
                return items
            page += 1
        raise FaciliooResponseError("Pagination exceeded the safety limit")

    @staticmethod
    def _page(
        payload: Any, page: int, page_size: int, *, items_seen: int = 0
    ) -> tuple[list[Any], bool]:
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
            return page_items, items_seen + len(page_items) < total
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

    @classmethod
    def _extract_account_id(cls, payload: Any) -> int | None:
        """Extract an account ID from either login or account responses."""
        if not isinstance(payload, Mapping):
            return None
        account_id = payload.get("id")
        if cls._valid_account_id(account_id):
            return account_id
        account = payload.get("account")
        if isinstance(account, Mapping):
            account_id = account.get("id")
            if cls._valid_account_id(account_id):
                return account_id
        return None

    @staticmethod
    def _valid_account_id(value: Any) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value > 0

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
