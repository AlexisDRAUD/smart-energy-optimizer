"""LTTB downsampling for display series, with explicit gap preservation."""

from __future__ import annotations

from datetime import datetime
from math import floor
from typing import Any

from app.core.contract import as_utc


def _timestamp(value: str) -> float:
    return as_utc(datetime.fromisoformat(value)).timestamp()


def _lttb(segment: list[tuple[int, float, float]], threshold: int) -> list[int]:
    """Return original indexes selected by Largest-Triangle-Three-Buckets."""
    if threshold >= len(segment):
        return [point[0] for point in segment]
    if threshold <= 2:
        return [segment[0][0], segment[-1][0]][:threshold]

    every = (len(segment) - 2) / (threshold - 2)
    selected = [segment[0][0]]
    selected_position = 0

    for bucket in range(threshold - 2):
        average_start = floor((bucket + 1) * every) + 1
        average_end = min(floor((bucket + 2) * every) + 1, len(segment))
        average_bucket = segment[average_start:average_end] or [segment[-1]]
        average_x = sum(point[1] for point in average_bucket) / len(average_bucket)
        average_y = sum(point[2] for point in average_bucket) / len(average_bucket)

        range_start = floor(bucket * every) + 1
        range_end = min(floor((bucket + 1) * every) + 1, len(segment) - 1)
        previous = segment[selected_position]
        largest_area = -1.0
        next_position = range_start
        for position in range(range_start, range_end):
            candidate = segment[position]
            area = abs(
                (previous[1] - average_x) * (candidate[2] - previous[2])
                - (previous[1] - candidate[1]) * (average_y - previous[2])
            )
            if area > largest_area:
                largest_area = area
                next_position = position
        selected.append(segment[next_position][0])
        selected_position = next_position

    selected.append(segment[-1][0])
    return selected


def _allocate_thresholds(segments: list[list[tuple[int, float, float]]], budget: int) -> list[int]:
    minimums = [min(2, len(segment)) for segment in segments]
    capacities = [
        len(segment) - minimum for segment, minimum in zip(segments, minimums, strict=True)
    ]
    available = max(0, budget - sum(minimums))
    total_capacity = sum(capacities)
    if not available or not total_capacity:
        return minimums

    exact = [available * capacity / total_capacity for capacity in capacities]
    extras = [
        min(capacity, floor(value)) for capacity, value in zip(capacities, exact, strict=True)
    ]
    remaining = min(available, total_capacity) - sum(extras)
    order = sorted(
        range(len(segments)),
        key=lambda index: (exact[index] - extras[index], capacities[index]),
        reverse=True,
    )
    for index in order:
        if remaining == 0:
            break
        if extras[index] < capacities[index]:
            extras[index] += 1
            remaining -= 1
    return [minimum + extra for minimum, extra in zip(minimums, extras, strict=True)]


def downsample_with_gaps(
    points: list[dict[str, Any]],
    *,
    time_key: str,
    value_key: str,
    threshold: int,
    cadence_seconds: int,
) -> list[dict[str, Any]]:
    """Select native points while retaining nulls and every continuous segment boundary."""
    segments: list[list[tuple[int, float, float]]] = []
    current: list[tuple[int, float, float]] = []
    mandatory_indexes: set[int] = set()
    segment_starts: set[int] = set()
    previous_time: float | None = None

    for index, point in enumerate(points):
        point_time = _timestamp(point[time_key])
        value = point[value_key]
        gap = previous_time is not None and point_time - previous_time > cadence_seconds
        if value is None or gap:
            if current:
                segments.append(current)
                current = []
            if value is None:
                mandatory_indexes.add(index)
        if value is not None:
            if not current:
                segment_starts.add(index)
            current.append((index, point_time, float(value)))
        previous_time = point_time
    if current:
        segments.append(current)

    if len(points) <= threshold:
        selected = set(range(len(points)))
    else:
        segment_budget = max(0, threshold - len(mandatory_indexes))
        allocations = _allocate_thresholds(segments, segment_budget)
        selected = set(mandatory_indexes)
        for segment, allocation in zip(segments, allocations, strict=True):
            selected.update(_lttb(segment, allocation))
    return [
        {**points[index], "segment_start": index in segment_starts} for index in sorted(selected)
    ]
