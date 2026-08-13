"""Tests for sensor metadata and values."""

from datetime import UTC, date, datetime
from decimal import Decimal

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

from custom_components.facilioo.models import ConsumptionData, MeterKind, MonthlyConsumption
from custom_components.facilioo.sensor import BASE_DESCRIPTIONS


def _description(key):
    return next(item for item in BASE_DESCRIPTIONS if item.key == key)


def test_total_sensor_metadata_and_cumulative_value():
    water = _description("warm_water_total")
    assert water.device_class is SensorDeviceClass.WATER
    assert water.state_class is SensorStateClass.TOTAL
    data = ConsumptionData(
        (),
        (),
        {
            MeterKind.WARM_WATER: (
                MonthlyConsumption(date(2025, 11, 1), Decimal("0.172"), None, False),
                MonthlyConsumption(date(2025, 12, 1), Decimal("0.766"), None, True),
            )
        },
        datetime.now(UTC),
    )
    assert water.value_fn(data) == Decimal("0.938")


def test_last_month_attributes_show_estimate():
    latest = _description("warm_water_last_month")
    data = ConsumptionData(
        (),
        (),
        {
            MeterKind.WARM_WATER: (
                MonthlyConsumption(date(2025, 12, 1), Decimal("0.7"), Decimal("4.2"), True),
            )
        },
        datetime.now(UTC),
    )
    assert latest.value_fn(data) == Decimal("0.7")
    assert latest.attrs_fn(data) == {"billing_month": "2025-12", "is_estimated": True}
