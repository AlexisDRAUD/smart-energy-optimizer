"""Offline comparison of candidate consumption-imputation methods.

This module only scores methods on historical real values. It never reads or
writes the production database and does not select a production imputation rule.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import isfinite
from typing import Literal, cast

NETWORK_LOSS_REASON = "network_loss"

ImputationProfile = Literal["stable", "variable", "unknown"]


@dataclass(frozen=True)
class BacktestConfig:
    """Provisional and configurable decision thresholds."""

    minimum_points: int = 100
    minimum_method_improvement: float = 0.10
    maximum_normalized_error: float = 0.10
    maximum_gap_minutes: int = 3
    interval: timedelta = timedelta(minutes=1)

    def __post_init__(self) -> None:
        if self.minimum_points < 1:
            raise ValueError("minimum_points must be positive")
        if not 0 <= self.minimum_method_improvement <= 1:
            raise ValueError("minimum_method_improvement must be between 0 and 1")
        if not 0 <= self.maximum_normalized_error <= 1:
            raise ValueError("maximum_normalized_error must be between 0 and 1")
        if self.maximum_gap_minutes < 1:
            raise ValueError("maximum_gap_minutes must be positive")
        if self.interval <= timedelta(0):
            raise ValueError("interval must be positive")


@dataclass(frozen=True)
class ConsumptionObservation:
    """Normalized historical value used only by the offline analysis."""

    site_id: str
    measured_at: datetime
    consumption_kwh_raw: float | None
    null_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class SiteImputationBacktest:
    """MAE comparison and experimental decision trace for one site."""

    site_id: str
    sample_count: int
    sequence_count: int
    max_observed_consumption: float | None
    mae_linear: float | None
    mae_report: float | None
    normalized_mae_linear_pct: float | None
    normalized_mae_report_pct: float | None
    relative_improvement_pct: float | None
    profile: ImputationProfile
    decision_reason: str


def _is_real_observation(observation: ConsumptionObservation) -> bool:
    value = observation.consumption_kwh_raw
    return (
        value is not None
        and isfinite(value)
        and NETWORK_LOSS_REASON not in observation.null_reasons
    )


def _contiguous_runs(
    observations: Sequence[ConsumptionObservation], interval: timedelta
) -> Iterator[list[ConsumptionObservation]]:
    """Yield real observations separated by invalid values or cadence breaks."""
    current_run: list[ConsumptionObservation] = []
    for observation in observations:
        is_expected_next = (
            not current_run or observation.measured_at - current_run[-1].measured_at == interval
        )
        if not _is_real_observation(observation) or not is_expected_next:
            if current_run:
                yield current_run
            current_run = []
            if not _is_real_observation(observation):
                continue
        current_run.append(observation)
    if current_run:
        yield current_run


def _masked_sequences(
    run: Sequence[ConsumptionObservation], maximum_gap_minutes: int
) -> Iterator[
    tuple[ConsumptionObservation, Sequence[ConsumptionObservation], ConsumptionObservation]
]:
    """Yield every test window with real anchors around one to N masked points."""
    for sequence_length in range(1, maximum_gap_minutes + 1):
        for start in range(1, len(run) - sequence_length):
            end = start + sequence_length
            yield run[start - 1], run[start:end], run[end]


def _percentage(numerator: float, denominator: float | None) -> float | None:
    """Return a percentage while explicitly rejecting a zero or invalid denominator."""
    if denominator is None or denominator <= 0 or not isfinite(denominator):
        return None
    if not isfinite(numerator):
        return None
    return numerator / denominator * 100


def _classify(
    *,
    sample_count: int,
    normalized_mae_linear_pct: float | None,
    normalized_mae_report_pct: float | None,
    relative_improvement_pct: float | None,
    config: BacktestConfig,
) -> tuple[ImputationProfile, str]:
    if sample_count < config.minimum_points:
        return "unknown", "insufficient_test_points"
    if normalized_mae_linear_pct is None or normalized_mae_report_pct is None:
        return "unknown", "invalid_normalization_denominator"

    maximum_normalized_error_pct = config.maximum_normalized_error * 100
    minimum_method_improvement_pct = config.minimum_method_improvement * 100
    if (
        relative_improvement_pct is not None
        and relative_improvement_pct >= minimum_method_improvement_pct
        and normalized_mae_linear_pct <= maximum_normalized_error_pct
    ):
        return "variable", "linear_improvement_and_error_within_thresholds"
    if normalized_mae_report_pct <= maximum_normalized_error_pct:
        return "stable", "report_error_within_threshold"
    return "unknown", "candidate_method_error_above_threshold"


def compare_imputation_methods(
    observations: Iterable[ConsumptionObservation],
    config: BacktestConfig | None = None,
) -> list[SiteImputationBacktest]:
    """Backtest report and linear interpolation independently for each site."""
    active_config = config or BacktestConfig()
    observations_by_site: dict[str, list[ConsumptionObservation]] = defaultdict(list)
    for observation in observations:
        observations_by_site[observation.site_id].append(observation)

    results: list[SiteImputationBacktest] = []
    for site_id, site_observations in sorted(observations_by_site.items()):
        sorted_observations = sorted(
            site_observations,
            key=lambda observation: observation.measured_at,
        )
        real_values = [
            cast(float, observation.consumption_kwh_raw)
            for observation in sorted_observations
            if _is_real_observation(observation)
        ]
        max_observed_consumption = max(real_values, default=None)
        report_absolute_errors: list[float] = []
        interpolation_absolute_errors: list[float] = []
        sequence_count = 0

        for run in _contiguous_runs(sorted_observations, active_config.interval):
            for previous, masked, following in _masked_sequences(
                run, active_config.maximum_gap_minutes
            ):
                sequence_count += 1
                previous_value = cast(float, previous.consumption_kwh_raw)
                following_value = cast(float, following.consumption_kwh_raw)
                duration = following.measured_at - previous.measured_at

                for observation in masked:
                    actual = cast(float, observation.consumption_kwh_raw)
                    fraction = (observation.measured_at - previous.measured_at) / duration
                    interpolated = previous_value + fraction * (following_value - previous_value)
                    report_absolute_errors.append(abs(actual - previous_value))
                    interpolation_absolute_errors.append(abs(actual - interpolated))

        sample_count = len(report_absolute_errors)
        if sample_count:
            mae_report = sum(report_absolute_errors) / sample_count
            mae_linear = sum(interpolation_absolute_errors) / sample_count
        else:
            mae_report = None
            mae_linear = None

        normalized_mae_linear_pct = (
            _percentage(mae_linear, max_observed_consumption) if mae_linear is not None else None
        )
        normalized_mae_report_pct = (
            _percentage(mae_report, max_observed_consumption) if mae_report is not None else None
        )
        relative_improvement_pct = (
            _percentage(mae_report - mae_linear, mae_report)
            if mae_report is not None and mae_linear is not None
            else None
        )
        profile, decision_reason = _classify(
            sample_count=sample_count,
            normalized_mae_linear_pct=normalized_mae_linear_pct,
            normalized_mae_report_pct=normalized_mae_report_pct,
            relative_improvement_pct=relative_improvement_pct,
            config=active_config,
        )

        results.append(
            SiteImputationBacktest(
                site_id=site_id,
                sample_count=sample_count,
                sequence_count=sequence_count,
                max_observed_consumption=max_observed_consumption,
                mae_linear=mae_linear,
                mae_report=mae_report,
                normalized_mae_linear_pct=normalized_mae_linear_pct,
                normalized_mae_report_pct=normalized_mae_report_pct,
                relative_improvement_pct=relative_improvement_pct,
                profile=profile,
                decision_reason=decision_reason,
            )
        )

    return results
