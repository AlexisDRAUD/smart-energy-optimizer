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
    *,
    interval: timedelta = timedelta(minutes=1),
) -> list[ConsumptionObservation]:
    reasons = reasons_by_index or {}
    return [
        ConsumptionObservation(
            site_id=site_id,
            measured_at=START + interval * index,
            consumption_kwh_raw=value,
            null_reasons=reasons.get(index, ()),
        )
        for index, value in enumerate(values)
    ]


def permissive_config(**overrides: object) -> BacktestConfig:
    values = {
        "minimum_points": 1,
        "minimum_method_improvement": 0.10,
        "maximum_normalized_error": 1.0,
        "maximum_gap_minutes": 1,
    }
    values.update(overrides)
    return BacktestConfig(**values)  # type: ignore[arg-type]


def test_provisional_configuration_uses_distinct_agreed_thresholds() -> None:
    config = BacktestConfig()

    assert config.minimum_points == 100
    assert config.minimum_method_improvement == pytest.approx(0.10)
    assert config.maximum_normalized_error == pytest.approx(0.10)
    assert config.maximum_gap_minutes == 3
    assert config.interval == timedelta(minutes=1)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("minimum_points", 0),
        ("minimum_points", -1),
        ("minimum_points", 1.0),
        ("minimum_points", True),
        ("maximum_gap_minutes", 0),
        ("maximum_gap_minutes", -1),
        ("maximum_gap_minutes", 1.0),
        ("maximum_gap_minutes", True),
    ],
)
def test_point_and_gap_limits_must_be_strictly_positive_integers(
    field: str, invalid_value: object
) -> None:
    with pytest.raises(ValueError, match=rf"{field} must be a strictly positive integer"):
        BacktestConfig(**{field: invalid_value})  # type: ignore[arg-type]


def test_metrics_follow_the_three_percentage_formulas() -> None:
    result = compare_imputation_methods(
        observations("FORMULAS", [0.0, 1.5, 4.0]),
        config=permissive_config(),
    )[0]

    assert result.max_observed_consumption == pytest.approx(4.0)
    assert result.mae_linear == pytest.approx(0.5)
    assert result.mae_report == pytest.approx(1.5)
    assert result.normalized_mae_linear_pct == pytest.approx(0.5 / 4.0 * 100)
    assert result.normalized_mae_report_pct == pytest.approx(1.5 / 4.0 * 100)
    assert result.relative_improvement_pct == pytest.approx((1.5 - 0.5) / 1.5 * 100)


def test_zero_denominators_are_handled_explicitly() -> None:
    result = compare_imputation_methods(
        observations("ZERO", [0.0, 0.0, 0.0]),
        config=permissive_config(),
    )[0]

    assert result.mae_linear == pytest.approx(0)
    assert result.mae_report == pytest.approx(0)
    assert result.normalized_mae_linear_pct is None
    assert result.normalized_mae_report_pct is None
    assert result.relative_improvement_pct is None
    assert result.profile == "unknown"
    assert result.decision_reason == "invalid_normalization_denominator"


def test_unknown_profile_keeps_computable_metrics_when_sample_is_too_small() -> None:
    result = compare_imputation_methods(
        observations("SHORT", [0.0, 1.0, 2.0]),
    )[0]

    assert result.profile == "unknown"
    assert result.decision_reason == "insufficient_test_points"
    assert result.sample_count == 1
    assert result.mae_linear == pytest.approx(0)
    assert result.mae_report == pytest.approx(1)
    assert result.normalized_mae_linear_pct == pytest.approx(0)
    assert result.normalized_mae_report_pct == pytest.approx(50)
    assert result.relative_improvement_pct == pytest.approx(100)


def test_method_improvement_and_normalized_error_thresholds_are_configurable() -> None:
    source = observations("THRESHOLDS", [0.0, 1.5, 4.0])

    variable = compare_imputation_methods(
        source,
        config=permissive_config(
            minimum_method_improvement=0.60,
            maximum_normalized_error=0.20,
        ),
    )[0]
    stable = compare_imputation_methods(
        source,
        config=permissive_config(
            minimum_method_improvement=0.70,
            maximum_normalized_error=0.40,
        ),
    )[0]

    assert variable.profile == "variable"
    assert stable.profile == "stable"


@pytest.mark.parametrize(
    ("maximum_gap_minutes", "expected_sequences", "expected_samples"),
    [(1, 3, 3), (2, 5, 7), (3, 6, 10)],
)
def test_every_valid_window_from_one_to_three_minutes_is_tested(
    maximum_gap_minutes: int,
    expected_sequences: int,
    expected_samples: int,
) -> None:
    result = compare_imputation_methods(
        observations("WINDOWS", [0.0, 1.0, 2.0, 3.0, 4.0]),
        config=permissive_config(maximum_gap_minutes=maximum_gap_minutes),
    )[0]

    assert result.sequence_count == expected_sequences
    assert result.sample_count == expected_samples


def test_three_minute_limit_accepts_one_to_three_missing_values_at_one_minute_cadence() -> None:
    result = compare_imputation_methods(
        observations("ONE_MINUTE", [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]),
        config=permissive_config(maximum_gap_minutes=3),
    )[0]

    assert result.sequence_count == 9
    assert result.sample_count == 16


def test_three_minute_limit_accepts_only_one_missing_value_at_two_minute_cadence() -> None:
    cadence = timedelta(minutes=2)
    result = compare_imputation_methods(
        observations("TWO_MINUTES", [0.0, 1.0, 2.0, 3.0], interval=cadence),
        config=permissive_config(maximum_gap_minutes=3, interval=cadence),
    )[0]

    assert result.sequence_count == 2
    assert result.sample_count == 2


def test_null_value_cuts_the_series() -> None:
    result = compare_imputation_methods(
        observations("NULL", [0.0, 1.0, 2.0, None, 100.0, 101.0, 102.0]),
        config=permissive_config(maximum_gap_minutes=3),
    )[0]

    assert result.sequence_count == 2
    assert result.sample_count == 2
    assert result.mae_linear == pytest.approx(0)


def test_network_loss_cuts_the_series_even_when_it_has_a_numeric_value() -> None:
    result = compare_imputation_methods(
        observations(
            "NETWORK",
            [0.0, 1.0, 2.0, 999.0, 100.0, 101.0, 102.0],
            reasons_by_index={3: ("network_loss",)},
        ),
        config=permissive_config(maximum_gap_minutes=3),
    )[0]

    assert result.sequence_count == 2
    assert result.sample_count == 2
    assert result.max_observed_consumption == pytest.approx(102)


def test_irregular_cadence_cuts_the_series() -> None:
    source = observations("IRREGULAR", [0.0, 1.0, 2.0, 3.0, 100.0, 101.0, 102.0])
    del source[3]

    result = compare_imputation_methods(
        source,
        config=permissive_config(maximum_gap_minutes=3),
    )[0]

    assert result.sequence_count == 2
    assert result.sample_count == 2


def test_method_is_rejected_when_its_normalized_error_exceeds_ten_percent() -> None:
    result = compare_imputation_methods(
        observations("TOO_IMPRECISE", [0.0, 9.0, 10.0]),
        config=BacktestConfig(minimum_points=1, maximum_gap_minutes=1),
    )[0]

    assert result.normalized_mae_linear_pct == pytest.approx(40)
    assert result.relative_improvement_pct > 10
    assert result.profile == "unknown"
    assert result.decision_reason == "candidate_method_error_above_threshold"


def test_results_are_produced_independently_for_each_site() -> None:
    source = [
        *observations("B", [10.0, 10.0, 10.0]),
        *observations("A", [0.0, 1.0, 2.0, 3.0]),
    ]

    results = compare_imputation_methods(
        reversed(source),
        config=permissive_config(maximum_gap_minutes=1),
    )

    assert [result.site_id for result in results] == ["A", "B"]
    assert [result.sample_count for result in results] == [2, 1]
    assert results[0].max_observed_consumption == pytest.approx(3)
    assert results[0].profile == "variable"
    assert results[1].max_observed_consumption == pytest.approx(10)
    assert results[1].profile == "stable"
