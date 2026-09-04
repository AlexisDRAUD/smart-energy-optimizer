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
MAX_MASKED_SEQUENCE_LENGTH = 3

ImputationProfile = Literal["stable", "variable", "unknown"]


@dataclass(frozen=True)
class BacktestConfig:
    """Provisional thresholds to validate with the Data team."""

    minimum_points: int = 100
    improvement_threshold: float = 0.10
    interval: timedelta = timedelta(minutes=1)

    def __post_init__(self) -> None:
        if self.minimum_points < 1:
            raise ValueError("minimum_points must be positive")
        if not 0 <= self.improvement_threshold <= 1:
            raise ValueError("improvement_threshold must be between 0 and 1")
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
    """MAE comparison for one site."""

    site_id: str
    sample_count: int
    mae_linear: float | None
    mae_report: float | None
    relative_improvement: float | None
    profile: ImputationProfile
    sequence_count: int


def _contiguous_runs(
    observations: Sequence[ConsumptionObservation], interval: timedelta
) -> Iterator[list[ConsumptionObservation]]:
    current_run: list[ConsumptionObservation] = []
    for observation in observations:
        if current_run and observation.measured_at - current_run[-1].measured_at != interval:
            if current_run:
                yield current_run
            current_run = []
        current_run.append(observation)
    if current_run:
        yield current_run


def _masked_sequences(
    run: Sequence[ConsumptionObservation],
) -> Iterator[
    tuple[ConsumptionObservation, Sequence[ConsumptionObservation], ConsumptionObservation]
]:
    start = 1
    requested_length = 1
    while start < len(run) - 1:
        available_length = len(run) - start - 1
        sequence_length = min(
            requested_length,
            MAX_MASKED_SEQUENCE_LENGTH,
            available_length,
        )
        if sequence_length < 1:
            return
        end = start + sequence_length
        yield run[start - 1], run[start:end], run[end]
        start = end + 1
        requested_length = requested_length % MAX_MASKED_SEQUENCE_LENGTH + 1


def _is_real_observation(observation: ConsumptionObservation) -> bool:
    value = observation.consumption_kwh_raw
    return (
        value is not None
        and isfinite(value)
        and NETWORK_LOSS_REASON not in observation.null_reasons
    )


def _classify(
    mae_report: float,
    mae_linear: float,
    sample_count: int,
    config: BacktestConfig,
) -> tuple[ImputationProfile, float | None]:
    if sample_count < config.minimum_points:
        return "unknown", None
    if mae_report == 0:
        return "stable", None

    improvement = (mae_report - mae_linear) / mae_report
    if improvement >= config.improvement_threshold:
        return "variable", improvement
    return "stable", improvement


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
        real_observations = sorted(
            filter(_is_real_observation, site_observations),
            key=lambda observation: observation.measured_at,
        )
        report_absolute_errors: list[float] = []
        interpolation_absolute_errors: list[float] = []
        sequence_count = 0

        for run in _contiguous_runs(real_observations, active_config.interval):
            for previous, masked, following in _masked_sequences(run):
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
            profile, improvement = _classify(
                mae_report,
                mae_linear,
                sample_count,
                active_config,
            )
        else:
            mae_report = None
            mae_linear = None
            profile = "unknown"
            improvement = None

        results.append(
            SiteImputationBacktest(
                site_id=site_id,
                sample_count=sample_count,
                mae_linear=mae_linear,
                mae_report=mae_report,
                relative_improvement=improvement,
                profile=profile,
                sequence_count=sequence_count,
            )
        )

    return results
