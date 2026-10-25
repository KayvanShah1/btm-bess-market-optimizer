from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

pytest.importorskip("requests")
from scripts.esett_open_data import (
    ROUTES,
    backfill,
    check_day,
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


def test_resumable_source_json(tmp_path: Path):
    session = FakeSession([{"timestampUTC": "2026-06-23T22:00:00Z", "mba": "X", "solar": 3}])
    result = backfill(["production"], {"production": ["X"]},
                      date(2026, 6, 24), date(2026, 6, 25),
                      root=tmp_path, session=session, pause_seconds=0)
    assert result[0]["status"] == "downloaded"
    assert Path(result[0]["path"]).exists()
    assert backfill(["production"], {"production": ["X"]},
                    date(2026, 6, 24), date(2026, 6, 25),
                    root=tmp_path, session=session, pause_seconds=0)[0]["status"] == "cached"
    assert len(session.calls) == 1


def test_no_empty_success_fake_coverage(tmp_path: Path):
    session = FakeSession([])
    result = backfill(["imbalance_prices"], {"imbalance_prices": ["X"]},
                      date(2026, 6, 24), date(2026, 6, 25),
                      root=tmp_path, session=session, pause_seconds=0)
    assert result[0]["status"] == "empty"
    assert result[0]["complete_time_axis"] is False


def test_mga_discovery_for_load_profiles():
    session = FakeSession([{"mgaCode": "GRID-A", "mba": "MY_EIC"}])
    result = metering_grid_areas("MY_EIC", session)
    assert result[0]["mgaCode"] == "GRID-A"
    url, params, _ = session.calls[0]
    assert url.endswith("/EXP03/MeteringGridAreas")
    assert params == {"mba": "MY_EIC"}
