from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from bess_optimizer.data.history import (
    expand_to_quarters,
    parse_number,
    to_utc,
    transform,
    write_history,
)


def test_decimal_comma_and_swedish_summer_time():
    assert parse_number("21,330") == 21.33
    assert to_utc({"Datum": "2026-06-24 00:00"}) == datetime(
        2026, 6, 23, 22, tzinfo=timezone.utc
    )


def test_dst_requires_disambiguation():
    with pytest.raises(ValueError, match="Ambiguous"):
        to_utc({"Period": "2025-10-26 02:15"})
    assert to_utc({"Period": "2025-10-26 02:15", "fold": "1"}) == datetime(
        2025, 10, 26, 1, 15, tzinfo=timezone.utc
    )
    with pytest.raises(ValueError, match="Nonexistent"):
        to_utc({"Period": "2025-03-30 02:15", "fold": "0"})


def test_zone_filtering_and_activation_volume():
    assert transform("spot", {"bidding_zone": "SE2", "price": "30"}) is None
    values = transform("mfrr_activation", {
        "Elområde": "SN3", "mFRR Upp Pris": "100,46",
        "mFRR Upp Volym SA (MW)": "4", "mFRR Upp Volym DA (MW)": "2",
    })
    assert values["mfrr_activation_volume_mw"] == 6
    assert values["mfrr_activation_flag"] == 1


def test_quarter_spot_transition():
    rows = {
        datetime(2025, 9, 30, tzinfo=timezone.utc): {"spot_price_eur_mwh": 50},
        datetime(2025, 10, 1, tzinfo=timezone.utc): {"spot_price_eur_mwh": 60},
    }
    expanded = expand_to_quarters("spot", rows)
    assert datetime(2025, 9, 30, 0, 15, tzinfo=timezone.utc) in expanded
    assert datetime(2025, 10, 1, 0, 15, tzinfo=timezone.utc) not in expanded


def test_empty_run_reports_missing_without_inventing_data(tmp_path: Path):
    result = write_history(tmp_path / "raw", tmp_path / "processed",
                           date(2024, 7, 1), date(2024, 7, 2))
    assert result["expected_intervals"] == 96
    assert all(family["missing_intervals"] == 96 for family in result["families"].values())
    with (tmp_path / "processed" / "historical_15min_se3_20240701_20240702_exclusive.csv").open() as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 96
    assert rows[0]["spot_price_eur_mwh"] == ""
    assert json.loads((tmp_path / "processed" / "historical_coverage.json").read_text())["expected_intervals"] == 96
    with pytest.raises(ValueError, match="Incomplete"):
        write_history(tmp_path / "raw", tmp_path / "processed",
                      date(2024, 7, 1), date(2024, 7, 2), require_complete=True)


def test_conflicting_duplicate_detection(tmp_path: Path):
    raw = tmp_path / "raw" / "spot"
    raw.mkdir(parents=True)
    (raw / "two.csv").write_text(
        "timestamp_utc,SE3\n2024-07-01T00:00:00Z,10\n2024-07-01T00:00:00Z,20\n"
    )
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        write_history(tmp_path / "raw", tmp_path / "processed", date(2024, 7, 1), date(2024, 7, 2))
