from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("requests")
from scripts.esett_open_data import (
    ROUTES,
    backfill,
    check_day,
    check_window,
    quarter_windows,
    fetch_day,
    local_day_window,
    mba_options,
    metering_grid_areas,
    swedish_mba_codes,
    utc_timestamps,
)


class FakeResponse:
    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code
        self.ok = status_code < 400
        self.url = "https://api.opendata.esett.com/test"
        self.text = "mock"

    def json(self):
        return self.data


class FakeSession:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        return FakeResponse(self.data)


def test_expected_four_routes():
    assert set(ROUTES) == {"production", "consumption", "load_profile", "imbalance_prices"}


def test_swedish_mba_codes_from_nested_options():
    options = [
        [{"countryCode": "SE", "mbas": [{"code": "SWEDISH_EIC", "name": "SE3"}]}],
        {"countryCode": "NO", "mbas": [{"code": "NORWEGIAN_EIC"}]},
    ]
    session = FakeSession(options)
    groups = mba_options("load_profile", session)
    assert swedish_mba_codes(groups) == ["SWEDISH_EIC"]


def test_swedish_local_dst_windows():
    assert (local_day_window(date(2025, 3, 30))[1] -
            local_day_window(date(2025, 3, 30))[0]).total_seconds() / 900 == 92
    assert (local_day_window(date(2025, 10, 26))[1] -
            local_day_window(date(2025, 10, 26))[0]).total_seconds() / 900 == 100


def test_query_uses_eic_and_exact_utc_bounds():
    session = FakeSession([{
        "mba": "MY_EIC", "timestampUTC": "2026-06-23T22:00:00Z",
        "solar": 1.2,
    }])
    result = fetch_day("production", "MY_EIC", date(2026, 6, 24), session)
    assert result[0]["solar"] == 1.2
    url, params, _ = session.calls[0]
    assert url.endswith("/EXP16/Volumes")
    assert params == {
        "mba": "MY_EIC",
        "start": "2026-06-23T22:00:00.000Z",
        "end": "2026-06-24T22:00:00.000Z",
    }


def test_utc_parsing_and_coverage_partial():
    records = [{"timestampUTC": "2026-06-23T22:00:00", "mba": "X"}]
    assert utc_timestamps(records)[0] == datetime(2026, 6, 23, 22, tzinfo=timezone.utc)
    audit = check_day(records, date(2026, 6, 24))
    assert audit["expected_quarter_hours"] == 96
    assert audit["missing_quarter_hours"] == 95


def complete_quarter_rows(start: date, end: date, mba: str = "X"):
    utc_start, _ = local_day_window(start)
    utc_end, _ = local_day_window(end)
    count = int((utc_end - utc_start).total_seconds() // 900)
    return [
        {"timestampUTC": (utc_start + timedelta(minutes=15 * n)).isoformat(), "mba": mba, "solar": 3}
        for n in range(count)
    ]


def test_calendar_quarters_are_full_and_four_per_year():
    quarters = list(quarter_windows(date(2024, 1, 1), date(2026, 1, 1)))
    assert len(quarters) == 8
    assert quarters[0] == (date(2024, 1, 1), date(2024, 4, 1))
    assert quarters[-1] == (date(2025, 10, 1), date(2026, 1, 1))
    with pytest.raises(ValueError, match="quarter boundary"):
        list(quarter_windows(date(2026, 6, 24), date(2026, 7, 1)))


def test_quarter_request_all_mbas_once_and_one_partition(tmp_path: Path):
    first, last = date(2026, 4, 1), date(2026, 7, 1)
    rows = complete_quarter_rows(first, last, "X") + complete_quarter_rows(first, last, "Y")
    session = FakeSession(rows)
    result = backfill(
        ["production"], {"production": ["EIC_X", "EIC_Y"]}, first, last,
        root=tmp_path, session=session, pause_seconds=0,
    )
    assert result[0]["status"] == "downloaded"
    assert result[0]["complete_time_axis"] is True
    assert len(session.calls) == 1
    url, params, _ = session.calls[0]
    assert url.endswith("/EXP16/Volumes")
    assert params == [
        ("start", "2026-03-31T22:00:00.000Z"),
        ("end", "2026-06-30T22:00:00.000Z"),
        ("mba", "EIC_X"), ("mba", "EIC_Y"),
    ]
    paths = list((tmp_path / "production").glob("*.json"))
    assert len(paths) == 1
    assert paths[0].name == "2026-Q2.json"
    assert backfill(
        ["production"], {"production": ["EIC_X", "EIC_Y"]}, first, last,
        root=tmp_path, session=session, pause_seconds=0,
    )[0]["status"] == "cached"
    assert len(session.calls) == 1


def test_missing_quarter_is_not_marked_complete_or_cached(tmp_path: Path):
    session = FakeSession([
        {"timestampUTC": "2026-03-31T22:00:00Z", "mba": "X", "solar": 3}
    ])
    first, last = date(2026, 4, 1), date(2026, 7, 1)
    result = backfill(
        ["production"], {"production": ["EIC_X"]}, first, last,
        root=tmp_path, session=session, pause_seconds=0,
    )
    assert result[0]["status"] == "incomplete"
    assert result[0]["missing_quarter_hours"] > 0
    result = backfill(
        ["production"], {"production": ["EIC_X"]}, first, last,
        root=tmp_path, session=session, pause_seconds=0,
    )
    assert result[0]["status"] == "incomplete"
    assert len(session.calls) == 2


def test_no_file_for_empty_quarter(tmp_path: Path):
    session = FakeSession([])
    with pytest.raises(ValueError, match="Empty eSett quarter"):
        backfill(
            ["imbalance_prices"], {"imbalance_prices": ["X"]},
            date(2026, 4, 1), date(2026, 7, 1),
            root=tmp_path, session=session, pause_seconds=0,
        )
    assert not list(tmp_path.rglob("*.json"))


def test_quarter_with_spring_dst_has_one_hour_fewer_slots():
    audit = check_window([], date(2025, 1, 1), date(2025, 4, 1))
    assert audit["expected_quarter_hours"] == 90 * 96 - 4
    assert audit["complete_time_axis"] is False


def test_provider_error_fails_without_daily_fallback(tmp_path: Path):
    class BadSession(FakeSession):
        def get(self, url, params=None, timeout=None):
            self.calls.append((url, params, timeout))
            return FakeResponse([], status_code=400)

    session = BadSession([])
    with pytest.raises(RuntimeError, match="No smaller requests were made"):
        backfill(
            ["production"], {"production": ["EIC_X"]},
            date(2026, 4, 1), date(2026, 7, 1),
            root=tmp_path, session=session, pause_seconds=0,
        )
    assert len(session.calls) == 1
    assert not list(tmp_path.rglob("*.json"))


def test_mga_discovery_for_load_profiles():
    session = FakeSession([{"mgaCode": "GRID-A", "mba": "MY_EIC"}])
    result = metering_grid_areas("MY_EIC", session)
    assert result[0]["mgaCode"] == "GRID-A"
    url, params, _ = session.calls[0]
    assert url.endswith("/EXP03/MeteringGridAreas")
    assert params == {"mba": "MY_EIC"}

def test_missing_requested_mba_cannot_be_cached_as_complete(tmp_path: Path):
    first, last = date(2026, 4, 1), date(2026, 7, 1)
    # All timestamps exist for one of two requested areas. This is incomplete.
    session = FakeSession(complete_quarter_rows(first, last, "X"))
    result = backfill(
        ["production"], {"production": ["EIC_X", "EIC_Y"]}, first, last,
        root=tmp_path, session=session, pause_seconds=0,
    )
    assert result[0]["complete_time_axis"] is False
    assert result[0]["all_requested_mbas_present_by_count"] is False
    assert result[0]["status"] == "incomplete"
    assert check_window(
        complete_quarter_rows(first, last, "X"), first, last,
        expected_mba_count=2,
    )["response_mba_count"] == 1

