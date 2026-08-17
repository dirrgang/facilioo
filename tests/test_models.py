"""Tests for parsing, classification and month aggregation."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from custom_components.facilioo.models import (
    ConsumptionData,
    ConsumptionMeter,
    ConsumptionReading,
    ConsumptionType,
    FaciliooDataError,
    MeterKind,
    MonthlyConsumption,
    aggregate_monthly,
    billing_month,
    latest_readings_by_meter_month,
    resolve_meter_types,
)


def test_meter_classification(meter_payload):
    meters = tuple(ConsumptionMeter.from_api(item) for item in meter_payload["items"])
    assert [meter.kind for meter in meters] == [
        MeterKind.HEATING,
        MeterKind.WARM_WATER,
        MeterKind.UNKNOWN,
    ]


def test_consumption_type_metadata_classifies_unknown_ids():
    meters = (
        ConsumptionMeter.from_api({"id": 1, "typeId": 700, "unitOfMeasure": "M3"}),
        ConsumptionMeter.from_api({"id": 2, "typeId": 701, "unitOfMeasure": "KWH"}),
    )
    consumption_types = (
        ConsumptionType.from_api(
            {"id": 700, "meterName": "Warmwasserzähler", "utilityName": "Warmwasser"}
        ),
        ConsumptionType.from_api(
            {"id": 701, "meterName": "Wärmemengenzähler", "utilityName": "Heizung"}
        ),
    )

    resolved = resolve_meter_types(meters, consumption_types)

    assert [meter.kind for meter in resolved] == [MeterKind.WARM_WATER, MeterKind.HEATING]
    assert resolved[0].label == "Warmwasserzähler Warmwasser"
    assert resolved[1].label == "Wärmemengenzähler Heizung"


def test_consumption_type_resolution_keeps_unknown_utility_unknown():
    meter = ConsumptionMeter.from_api({"id": 1, "typeId": 700, "unitOfMeasure": "M3"})
    consumption_type = ConsumptionType.from_api(
        {"id": 700, "meterName": "Wasserzähler", "utilityName": "Kaltwasser"}
    )

    resolved = resolve_meter_types((meter,), (consumption_type,))

    assert resolved[0].kind is MeterKind.UNKNOWN
    assert resolved[0].label == "Wasserzähler Kaltwasser"


def test_label_fallback_and_unknown_unit():
    warm = ConsumptionMeter.from_api(
        {"id": 1, "typeId": 500, "unitOfMeasure": "m³", "typeName": "Warmwasserzähler"}
    )
    unknown = ConsumptionMeter.from_api({"id": 2, "typeId": 5, "unitOfMeasure": "L"})
    assert warm.kind is MeterKind.WARM_WATER
    assert unknown.kind is MeterKind.UNKNOWN


def test_billing_month_uses_local_period_end():
    period_end = datetime(2025, 11, 30, 23, tzinfo=UTC)
    assert billing_month(period_end, "Europe/Berlin") == date(2025, 11, 1)
    summer_end = datetime(2025, 6, 30, 22, tzinfo=UTC)
    assert billing_month(summer_end, "Europe/Berlin") == date(2025, 6, 1)


def test_aggregate_values_estimates_and_costs(meter_payload, reading_payload):
    meters = tuple(ConsumptionMeter.from_api(item) for item in meter_payload["items"])
    readings = tuple(ConsumptionReading.from_api(item) for item in reading_payload["items"])
    result = aggregate_monthly(meters, readings, "Europe/Berlin")
    water = result[MeterKind.WARM_WATER]
    assert [item.value for item in water] == [Decimal("0.172"), Decimal("0.766")]
    assert water[-1].is_estimated is True
    assert water[-1].costs == Decimal("15.9429")
    assert water[-1].value_in_different_unit == Decimal("44.5529")


def test_new_revision_replaces_estimate_and_deleted_removes_month():
    meter = ConsumptionMeter.from_api({"id": 1, "typeId": 5, "unitOfMeasure": "M3"})
    base = {
        "consumptionMeterId": 1,
        "readingDate": "2025-11-30T23:00:00Z",
        "costs": 1,
    }
    estimate = ConsumptionReading.from_api(
        base
        | {
            "id": 10,
            "currentValue": 2,
            "isEstimated": True,
            "lastModified": "2025-12-01T00:00:00Z",
        }
    )
    actual = ConsumptionReading.from_api(
        base
        | {
            "id": 11,
            "currentValue": 1.5,
            "isEstimated": False,
            "lastModified": "2025-12-02T00:00:00Z",
        }
    )
    result = aggregate_monthly((meter,), (estimate, actual), "Europe/Berlin")
    assert result[MeterKind.WARM_WATER][0].value == Decimal("1.5")
    deleted = ConsumptionReading.from_api(
        base
        | {
            "id": 12,
            "currentValue": 1.5,
            "deleted": "2025-12-03T00:00:00Z",
            "lastModified": "2025-12-03T00:00:00Z",
        }
    )
    assert MeterKind.WARM_WATER not in aggregate_monthly(
        (meter,), (estimate, actual, deleted), "Europe/Berlin"
    )


def test_nullable_current_value_replaces_previous_month_value():
    meter = ConsumptionMeter.from_api({"id": 1, "typeId": 5, "unitOfMeasure": "M3"})
    base = {
        "consumptionMeterId": 1,
        "readingDate": "2025-11-30T23:00:00Z",
    }
    original = ConsumptionReading.from_api(
        base
        | {
            "id": 10,
            "currentValue": 1.5,
            "lastModified": "2025-12-01T00:00:00Z",
        }
    )
    cleared = ConsumptionReading.from_api(
        base
        | {
            "id": 11,
            "currentValue": None,
            "lastModified": "2025-12-02T00:00:00Z",
        }
    )

    selected = latest_readings_by_meter_month((meter,), (original, cleared), "Europe/Berlin")
    assert tuple(selected.values()) == (cleared,)
    assert cleared.value is None
    assert MeterKind.WARM_WATER not in aggregate_monthly(
        (meter,), (original, cleared), "Europe/Berlin"
    )


def test_latest_revision_without_cost_replaces_stale_cost_revision():
    meter = ConsumptionMeter.from_api({"id": 1, "typeId": 5, "unitOfMeasure": "M3"})
    base = {
        "consumptionMeterId": 1,
        "readingDate": "2025-11-30T23:00:00Z",
        "currentValue": 1.5,
    }
    old = ConsumptionReading.from_api(
        base
        | {
            "id": 10,
            "costs": 4.2,
            "lastModified": "2025-12-01T00:00:00Z",
        }
    )
    latest = ConsumptionReading.from_api(
        base
        | {
            "id": 11,
            "costs": None,
            "lastModified": "2025-12-02T00:00:00Z",
        }
    )

    selected = latest_readings_by_meter_month((meter,), (old, latest), "Europe/Berlin")
    assert tuple(selected.values()) == (latest,)
    assert (
        aggregate_monthly((meter,), (old, latest), "Europe/Berlin")[MeterKind.WARM_WATER][0].costs
        is None
    )


def test_alternative_unit_total_requires_every_month():
    complete = ConsumptionData(
        (),
        (),
        {
            MeterKind.WARM_WATER: (
                MonthlyConsumption(
                    date(2025, 11, 1),
                    Decimal("0.172"),
                    None,
                    False,
                    Decimal("10.0018"),
                ),
                MonthlyConsumption(
                    date(2025, 12, 1),
                    Decimal("0.766"),
                    None,
                    False,
                    Decimal("44.5529"),
                ),
            )
        },
        datetime.now(UTC),
    )
    incomplete = ConsumptionData(
        (),
        (),
        {
            MeterKind.WARM_WATER: complete.values(MeterKind.WARM_WATER)
            + (MonthlyConsumption(date(2026, 1, 1), Decimal("0.5"), None, False),)
        },
        datetime.now(UTC),
    )

    assert complete.total_in_different_unit(MeterKind.WARM_WATER) == Decimal("54.5547")
    assert incomplete.total_in_different_unit(MeterKind.WARM_WATER) is None


@pytest.mark.parametrize("value", ["nan", "inf", "not-a-number"])
def test_invalid_values_are_rejected(value):
    with pytest.raises(FaciliooDataError):
        ConsumptionReading.from_api(
            {
                "id": 1,
                "consumptionMeterId": 2,
                "currentValue": value,
                "readingDate": "2025-11-30T23:00:00Z",
            }
        )


def test_naive_timestamp_is_rejected():
    with pytest.raises(FaciliooDataError, match="timezone"):
        ConsumptionReading.from_api(
            {
                "id": 1,
                "consumptionMeterId": 2,
                "currentValue": 1,
                "readingDate": "2025-11-30T23:00:00",
            }
        )
