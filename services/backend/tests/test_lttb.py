from datetime import UTC, datetime, timedelta
from time import perf_counter

import pytest
from app.core.contract import utc_iso
from app.services.lttb import downsample_with_gaps

START = datetime(2026, 9, 8, tzinfo=UTC)


def point(minute: int, value: float | None) -> dict:
    return {"at": utc_iso(START + timedelta(minutes=minute)), "value": value}


def test_lttb_keeps_native_points_bounds_and_shape_extreme():
    points = [point(minute, 1000 if minute == 50 else float(minute % 7)) for minute in range(100)]

    sampled = downsample_with_gaps(
        points, time_key="at", value_key="value", threshold=12, cadence_seconds=60
    )

    assert len(sampled) == 12
    assert sampled[0]["at"] == points[0]["at"]
    assert sampled[-1]["at"] == points[-1]["at"]
    assert points[50]["at"] in {item["at"] for item in sampled}
    assert {(item["at"], item["value"]) for item in sampled} <= {
        (item["at"], item["value"]) for item in points
    }
    assert sampled[0]["segment_start"] is True


def test_nulls_and_both_sides_of_missing_intervals_are_preserved():
    points = [
        *[point(minute, float(minute)) for minute in range(20)],
        point(20, None),
        *[point(minute, float(minute)) for minute in range(21, 40)],
        *[point(minute, float(minute)) for minute in range(45, 65)],
    ]

    sampled = downsample_with_gaps(
        points, time_key="at", value_key="value", threshold=15, cadence_seconds=60
    )

    selected_times = {item["at"] for item in sampled}
    for index in (0, 19, 20, 21, 39, 40, len(points) - 1):
        assert points[index]["at"] in selected_times
    starts = [item["at"] for item in sampled if item["segment_start"]]
    assert starts == [points[index]["at"] for index in (0, 21, 40)]
    assert [item["at"] for item in sampled] == sorted(item["at"] for item in sampled)


def test_mandatory_break_points_can_exceed_target_instead_of_being_dropped():
    points = [point(minute, None if minute % 2 else float(minute)) for minute in range(20)]

    sampled = downsample_with_gaps(
        points, time_key="at", value_key="value", threshold=5, cadence_seconds=60
    )

    assert len(sampled) == len(points)
    assert [item["at"] for item in sampled if item["value"] is None] == [
        item["at"] for item in points if item["value"] is None
    ]


@pytest.mark.parametrize("days", [1, 7, 30])
def test_complete_dashboard_periods_are_reduced_to_display_target(days):
    points = [point(minute, float(minute % 1440)) for minute in range(days * 1440)]

    sampled = downsample_with_gaps(
        points, time_key="at", value_key="value", threshold=600, cadence_seconds=60
    )

    assert len(sampled) == 600
    assert sampled[0]["at"] == points[0]["at"]
    assert sampled[-1]["at"] == points[-1]["at"]


@pytest.mark.parametrize("fragmented", [False, True])
def test_thirty_day_downsampling_performance_and_fragmentation(fragmented):
    points = [
        point(minute, None if fragmented and minute % 2 else float(minute % 1440))
        for minute in range(30 * 1440)
    ]

    started_at = perf_counter()
    sampled = downsample_with_gaps(
        points, time_key="at", value_key="value", threshold=600, cadence_seconds=60
    )
    elapsed = perf_counter() - started_at

    assert elapsed < 2
    assert len(sampled) == (len(points) if fragmented else 600)
    if fragmented:
        assert [item["at"] for item in sampled if item["value"] is None] == [
            item["at"] for item in points if item["value"] is None
        ]
