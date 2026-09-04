from datetime import UTC, datetime, timedelta

import pytest
from app.analysis.imputation_backtest import (
    BacktestConfig,
    ConsumptionObservation,
    compare_imputation_methods,
)

START = datetime(2026, 1, 1, tzinfo=UTC)


def observations(
    site_id: str,
    values: list[float | None],
    reasons_by_index: dict[int, tuple[str, ...]] | None = None,
) -> list[ConsumptionObservation]:
    reasons = reasons_by_index or {}
    return [
        ConsumptionObservation(
            site_id=site_id,
            measured_at=START + timedelta(minutes=index),
            consumption_kwh_raw=value,
            null_reasons=reasons.get(index, ()),
        )
        for index, value in enumerate(values)
    ]


def test_provisional_configuration_uses_the_agreed_thresholds() -> None:
    config = BacktestConfig()

    assert config.minimum_points == 100
    assert config.improvement_threshold == pytest.approx(0.10)
    assert config.interval == timedelta(minutes=1)


def test_linear_profile_favors_interpolation_after_enough_backtests() -> None:
    source = observations("VARIABLE", [float(index) for index in range(160)])

    result = compare_imputation_methods(source)[0]

    assert result.profile == "variable"
    assert result.sample_count >= 100
    assert result.mae_report is not None and result.mae_report > 0
    assert result.mae_linear == pytest.approx(0)
    assert result.relative_improvement == pytest.approx(1)


def test_constant_profile_favors_report_after_enough_backtests() -> None:
    source = observations("STABLE", [42.0] * 160)

    result = compare_imputation_methods(source)[0]

    assert result.profile == "stable"
    assert result.sample_count >= 100
    assert result.mae_report == pytest.approx(0)
    assert result.mae_linear == pytest.approx(0)
    assert result.relative_improvement is None


def test_profile_is_unknown_when_fewer_than_one_hundred_points_are_tested() -> None:
    result = compare_imputation_methods(
        observations("SHORT", [float(index) for index in range(100)])
    )[0]

    assert result.profile == "unknown"
    assert 0 < result.sample_count < 100
    assert result.mae_report is not None
    assert result.mae_linear is not None


def test_irregular_null_and_network_loss_observations_are_never_bridged() -> None:
    source = observations(
        "FILTERED",
        [0.0, 1.0, 2.0, 3.0, 400.0, 5.0, 6.0, None, 8.0, 9.0, 10.0, 11.0],
        reasons_by_index={4: ("network_loss",)},
    )
    del source[10]

    result = compare_imputation_methods(
        source,
        config=BacktestConfig(minimum_points=1),
    )[0]

    assert result.sample_count == 1
    assert result.sequence_count == 1
    assert result.mae_report == pytest.approx(1)
    assert result.mae_linear == pytest.approx(0)


def test_results_are_produced_independently_for_each_site() -> None:
    source = [
        *observations("B", [10.0] * 10),
        *observations("A", [float(index) for index in range(10)]),
    ]

    results = compare_imputation_methods(
        source,
        config=BacktestConfig(minimum_points=1),
    )

    assert [result.site_id for result in results] == ["A", "B"]
    assert [result.profile for result in results] == ["variable", "stable"]
    assert all(result.sample_count == 6 for result in results)
    assert all(result.sequence_count == 3 for result in results)
