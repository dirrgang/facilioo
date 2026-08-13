"""Official Recorder external-statistics backfill for monthly data."""

from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.util.unit_conversion import EnergyConverter, VolumeConverter

from .const import (
    DOMAIN,
    STATISTIC_HEATING,
    STATISTIC_HEATING_COSTS,
    STATISTIC_WARM_WATER,
    STATISTIC_WARM_WATER_COSTS,
    STORE_VERSION,
)
from .models import (
    ConsumptionData,
    MeterKind,
    MonthlyConsumption,
    latest_readings_by_meter_month,
)

_LOGGER = logging.getLogger(__name__)
_INVALID_STATISTIC_KEY = re.compile(r"[^a-z0-9]+")


def statistic_id(entry_id: str, kind: MeterKind, *, costs: bool = False) -> str:
    """Return an account-specific stable external statistic ID."""
    if costs:
        suffix = (
            STATISTIC_WARM_WATER_COSTS if kind is MeterKind.WARM_WATER else STATISTIC_HEATING_COSTS
        )
    else:
        suffix = STATISTIC_WARM_WATER if kind is MeterKind.WARM_WATER else STATISTIC_HEATING
    # Config entry IDs are opaque. Newer Home Assistant versions may use uppercase
    # ULIDs, while Recorder only accepts lowercase statistic ID slugs.
    entry_key = _INVALID_STATISTIC_KEY.sub("_", entry_id.casefold()).strip("_") or "entry"
    return f"{DOMAIN}:{entry_key}_{suffix}"


def _next_month(month: date) -> date:
    return date(month.year + (month.month == 12), month.month % 12 + 1, 1)


def _month_range(first: date, last: date):
    month = first
    while month <= last:
        yield month
        month = _next_month(month)


def _boundary(month: date, time_zone: str) -> datetime:
    """Return local month boundary as an aware, top-of-hour UTC timestamp."""
    return datetime(month.year, month.month, 1, tzinfo=ZoneInfo(time_zone)).astimezone(UTC)


def build_statistics(
    current: tuple[MonthlyConsumption, ...],
    previous: dict[str, str],
    time_zone: str,
    observed_months: set[date] | None = None,
    *,
    costs: bool = False,
) -> tuple[list[StatisticData], dict[str, str]]:
    """Build an exact cumulative series without erasing transiently omitted data."""
    current_values = {
        item.month.isoformat(): item.costs if costs else item.value
        for item in current
        if not costs or item.costs is not None
    }
    if costs and not current_values and not previous:
        return [], {}
    observed = {item.month for item in current} if observed_months is None else observed_months
    values: dict[str, Decimal | str] = dict(previous)
    for month in observed:
        values[month.isoformat()] = current_values.get(month.isoformat(), Decimal(0))
    values.update(current_values)
    months = {date.fromisoformat(key) for key in previous} | {
        date.fromisoformat(key) for key in values
    }
    if not months:
        return [], {}
    first, last = min(months), max(months)
    cumulative = Decimal(0)
    statistics: list[StatisticData] = [
        {"start": _boundary(first, time_zone), "state": 0.0, "sum": 0.0}
    ]
    stored: dict[str, str] = {}
    for month in _month_range(first, last):
        value = Decimal(values.get(month.isoformat(), Decimal(0)))
        cumulative += value
        stored[month.isoformat()] = str(value)
        statistics.append(
            {
                "start": _boundary(_next_month(month), time_zone),
                "state": float(cumulative),
                "sum": float(cumulative),
            }
        )
    return statistics, stored


class FaciliooStatisticsManager:
    """Import and revise historical hourly statistics without direct DB access."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.store: Store[dict[str, Any]] = Store(
            hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}.statistics"
        )

    async def async_sync(self, data: ConsumptionData) -> None:
        saved = await self.store.async_load() or {"months": {}}
        saved_months = saved.get("months", {}) if isinstance(saved, dict) else {}
        next_months: dict[str, dict[str, str]] = {}
        meter_kinds = {meter.id: meter.kind for meter in data.meters}
        observed_by_kind: dict[MeterKind, set[date]] = {}
        observed_costs_by_kind: dict[MeterKind, set[date]] = {}
        latest_readings = latest_readings_by_meter_month(
            data.meters, data.readings, self.hass.config.time_zone
        )
        for (meter_id, month), reading in latest_readings.items():
            kind = meter_kinds[meter_id]
            observed_by_kind.setdefault(kind, set()).add(month)
            if reading.costs is not None or reading.deleted:
                observed_costs_by_kind.setdefault(kind, set()).add(month)
        for kind, unit, unit_class, name, is_costs, store_key in (
            (
                MeterKind.WARM_WATER,
                UnitOfVolume.CUBIC_METERS,
                VolumeConverter.UNIT_CLASS,
                "Facilioo warm water consumption",
                False,
                MeterKind.WARM_WATER.value,
            ),
            (
                MeterKind.HEATING,
                UnitOfEnergy.KILO_WATT_HOUR,
                EnergyConverter.UNIT_CLASS,
                "Facilioo heating energy consumption",
                False,
                MeterKind.HEATING.value,
            ),
            (
                MeterKind.WARM_WATER,
                self.hass.config.currency,
                None,
                "Facilioo warm water costs",
                True,
                f"{MeterKind.WARM_WATER.value}_costs",
            ),
            (
                MeterKind.HEATING,
                self.hass.config.currency,
                None,
                "Facilioo heating costs",
                True,
                f"{MeterKind.HEATING.value}_costs",
            ),
        ):
            previous = saved_months.get(store_key, {})
            if not isinstance(previous, dict):
                previous = {}
            stats, stored = build_statistics(
                data.values(kind),
                previous,
                self.hass.config.time_zone,
                (
                    observed_costs_by_kind.get(kind, set())
                    if is_costs
                    else observed_by_kind.get(kind, set())
                ),
                costs=is_costs,
            )
            if not stats:
                next_months[store_key] = stored
                continue
            metadata: StatisticMetaData = {
                "mean_type": StatisticMeanType.NONE,
                "has_sum": True,
                "name": name,
                "source": DOMAIN,
                "statistic_id": statistic_id(self.entry.entry_id, kind, costs=is_costs),
                "unit_class": unit_class,
                "unit_of_measurement": unit,
            }
            try:
                async_add_external_statistics(self.hass, metadata, stats)
            except HomeAssistantError as err:
                # Historical import is additive functionality. Recorder rejecting a
                # batch must not prevent the regular Facilioo entities from loading.
                _LOGGER.error("Unable to import Facilioo %s history: %s", store_key, err)
                next_months[store_key] = previous
            else:
                next_months[store_key] = stored
        await self.store.async_save({"months": next_months})
        _LOGGER.debug("Facilioo historical statistics synchronized")
