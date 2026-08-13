"""Tests for exact idempotent historical series construction."""

from datetime import date
from decimal import Decimal

from custom_components.facilioo.models import MeterKind, MonthlyConsumption
from custom_components.facilioo.statistics import build_statistics, statistic_id


def month(value: str, when: date, estimated: bool = False) -> MonthlyConsumption:
    return MonthlyConsumption(when, Decimal(value), None, estimated)


def cost_month(value: str, costs: str | None, when: date) -> MonthlyConsumption:
    return MonthlyConsumption(
        when,
        Decimal(value),
        Decimal(costs) if costs is not None else None,
        False,
    )


def test_historical_backfill_has_baseline_and_cumulative_boundaries():
    stats, stored = build_statistics(
        (
            month("0.172", date(2025, 11, 1)),
            month("0.766", date(2025, 12, 1)),
            month("0.500", date(2026, 1, 1)),
        ),
        {},
        "Europe/Berlin",
    )
    assert [point["sum"] for point in stats] == [0.0, 0.172, 0.938, 1.438]
    assert stats[0]["start"].minute == 0
    assert stored["2025-11-01"] == "0.172"


def test_repeat_is_identical_and_correction_shifts_following_points():
    original = {
        "2025-11-01": "0.172",
        "2025-12-01": "0.766",
        "2026-01-01": "0.500",
    }
    current = (
        month("0.180", date(2025, 11, 1)),
        month("0.766", date(2025, 12, 1)),
        month("0.500", date(2026, 1, 1)),
    )
    corrected, saved = build_statistics(current, original, "Europe/Berlin")
    repeated, repeated_saved = build_statistics(current, saved, "Europe/Berlin")
    assert [point["sum"] for point in corrected] == [0.0, 0.18, 0.946, 1.446]
    assert corrected == repeated
    assert saved == repeated_saved


def test_deleted_month_becomes_zero_increment_not_stale_data():
    old = {"2025-11-01": "0.2", "2025-12-01": "0.7"}
    stats, saved = build_statistics(
        (month("0.7", date(2025, 12, 1)),),
        old,
        "Europe/Berlin",
        {date(2025, 11, 1), date(2025, 12, 1)},
    )
    assert [point["sum"] for point in stats] == [0.0, 0.0, 0.7]
    assert saved["2025-11-01"] == "0"


def test_temporarily_omitted_month_retains_last_known_value():
    old = {"2025-11-01": "0.2", "2025-12-01": "0.7"}
    stats, saved = build_statistics(
        (month("0.7", date(2025, 12, 1)),),
        old,
        "Europe/Berlin",
        {date(2025, 12, 1)},
    )
    assert [point["sum"] for point in stats] == [0.0, 0.2, 0.9]
    assert saved["2025-11-01"] == "0.2"


def test_monthly_costs_have_independent_cumulative_series():
    stats, saved = build_statistics(
        (
            cost_month("0.172", "3.40", date(2025, 11, 1)),
            cost_month("0.766", "15.94", date(2025, 12, 1)),
        ),
        {},
        "Europe/Berlin",
        costs=True,
    )

    assert [point["sum"] for point in stats] == [0.0, 3.4, 19.34]
    assert saved == {"2025-11-01": "3.40", "2025-12-01": "15.94"}


def test_missing_latest_cost_does_not_erase_stored_month():
    stats, saved = build_statistics(
        (cost_month("0.172", None, date(2025, 11, 1)),),
        {"2025-11-01": "3.40"},
        "Europe/Berlin",
        set(),
        costs=True,
    )

    assert [point["sum"] for point in stats] == [0.0, 3.4]
    assert saved == {"2025-11-01": "3.40"}


def test_deleted_cost_month_becomes_zero_increment():
    stats, saved = build_statistics(
        (),
        {"2025-11-01": "3.40", "2025-12-01": "15.94"},
        "Europe/Berlin",
        {date(2025, 11, 1)},
        costs=True,
    )

    assert [point["sum"] for point in stats] == [0.0, 0.0, 15.94]
    assert saved["2025-11-01"] == "0"


def test_statistic_id_is_external_and_account_specific():
    assert statistic_id("abc123", MeterKind.WARM_WATER) == (
        "facilioo:abc123_warm_water_consumption"
    )


def test_statistic_id_normalizes_uppercase_config_entry_ulid():
    assert statistic_id("01K2N-ABC__DEF", MeterKind.HEATING) == (
        "facilioo:01k2n_abc_def_heating_energy_consumption"
    )


def test_cost_statistic_id_is_normalized_and_account_specific():
    assert statistic_id("01K2N-ABC", MeterKind.WARM_WATER, costs=True) == (
        "facilioo:01k2n_abc_warm_water_costs"
    )
