"""Two-year, source-aware SE3 historical data preparation.

The representative-day pipeline is deliberately unchanged. This module works with
real historical exports and never manufactures missing observations.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

SWEDEN = ZoneInfo("Europe/Stockholm")
UTC = timezone.utc
FAMILIES = ("load", "pv", "spot", "fcr", "mfrr_capacity", "mfrr_activation")
FIELDS = {
    "load": ("site_load_kw",),
    "pv": ("site_pv_kw",),
    "spot": ("spot_price_eur_mwh",),
    "fcr": ("fcrn_price_eur_mw_h",),
    "mfrr_capacity": ("mfrr_capacity_price_eur_mw_h", "mfrr_capacity_volume_mw"),
    "mfrr_activation": (
        "mfrr_activation_energy_price_eur_mwh",
        "mfrr_activation_volume_mw",
        "mfrr_activation_flag",
    ),
}
SPOT_RESOURCE = "cf392ef3-7345-4e98-970e-83088c185570"
SVK_ENDPOINT = "https://data.svk.se/api/3/action/datastore_search"
MIMER_FCR_ENDPOINT = "https://mimer.svk.se/api/MimerAPI/GetPrimaryRegulationStatistics"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        delimiter = ";" if sample.splitlines()[0].count(";") > sample.splitlines()[0].count(",") else ","
        return [{(key or "").strip(): (value or "").strip() for key, value in row.items()}
                for row in csv.DictReader(handle, delimiter=delimiter)]


def parse_number(value: str | float | int | None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    normalized = str(value).replace("\u00a0", "").replace(" ", "").replace(",", ".")
    return float(normalized)


def parse_date_time(value: str) -> datetime:
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        for fmt in ("%d.%m.%Y/%H:%M", "%d.%m.%Y %H:%M",
                    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
    raise ValueError(f"Unsupported timestamp: {value!r}")


def to_utc(row: dict[str, str]) -> datetime:
    # Prefer source-provided UTC even when local time is also present.
    for field in ("timestamp_utc", "start_time_utc", "Date/Time UTC"):
        if row.get(field):
            parsed = parse_date_time(row[field])
            return (parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed).astimezone(UTC)
    for field in ("timestamp", "Period", "Datum", "time_sweden",
                  "start_time_sweden", "Date/Time CET/CEST"):
        if not row.get(field):
            continue
        parsed = parse_date_time(row[field])
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC)
        if row.get("fold") not in ("", None, "0", "1"):
            raise ValueError("fold must be 0 or 1")
        first = parsed.replace(tzinfo=SWEDEN, fold=0)
        second = parsed.replace(tzinfo=SWEDEN, fold=1)
        if first.utcoffset() != second.utcoffset() and row.get("fold", "") == "":
            raise ValueError(f"Ambiguous Swedish DST timestamp {parsed}; supply timestamp_utc or fold")
        chosen = first if row.get("fold") in ("", None, "0") else second
        if chosen.astimezone(UTC).astimezone(SWEDEN).replace(tzinfo=None) != parsed:
            raise ValueError(f"Nonexistent Swedish DST timestamp: {parsed}")
        return chosen.astimezone(UTC)
    raise ValueError(f"No recognized timestamp column: {list(row)}")


def pick(row: dict[str, str], *names: str) -> float | None:
    for name in names:
        if name in row:
            return parse_number(row[name])
    return None


def transform(family: str, row: dict[str, str]) -> dict[str, float | int | None] | None:
    if family == "load":
        # This must be genuine site observations or independently generated
        # time-aware scenarios, never a repeated June 24 representative day.
        if row.get("data_kind", "measured") not in ("measured", "synthetic_seasonal"):
            raise ValueError("load data_kind must be measured or synthetic_seasonal")
        return {"site_load_kw": pick(row, "site_load_kw")}
    if family == "pv":
        # eSett Solar [MWh] is a country-wide production *shape*, not site PV.
        return {"site_pv_kw": pick(row, "site_pv_kw", "Solar [MWh]")}
    if family == "spot":
        zone = row.get("bidding_zone", "SE3")
        if zone != "SE3":
            return None
        unit = row.get("price_unit", "EUR-MWh").upper().replace("/", "-")
        if unit not in ("EUR-MWH", "EUR-MW-H"):
            raise ValueError(f"Unsupported spot unit: {unit}")
        return {"spot_price_eur_mwh": pick(row, "spot_price_eur_mwh", "price", "SE3")}
    if family == "fcr":
        return {"fcrn_price_eur_mw_h": pick(
            row, "fcrn_price_eur_mw_h", "FCR-N Pris (EUR/MW)", "PriceFCRNEUR"
        )}
    if family == "mfrr_capacity":
        if row.get("Elområde", row.get("mimer_zone", "SN3")) != "SN3":
            return None
        return {
            "mfrr_capacity_price_eur_mw_h": pick(
                row, "mfrr_capacity_price_eur_mw_h", "mFRR Upp Pris (EUR/MW)"
            ),
            "mfrr_capacity_volume_mw": pick(
                row, "mfrr_capacity_volume_mw", "mFRR Upp Volym (MW)"
            ),
        }
    if family == "mfrr_activation":
        if row.get("Elområde", row.get("mimer_zone", "SN3")) != "SN3":
            return None
        price = pick(row, "mfrr_activation_energy_price_eur_mwh", "mFRR Upp Pris")
        volume = pick(row, "mfrr_activation_volume_mw")
        if volume is None:
            sa = pick(row, "mFRR Upp Volym SA (MW)")
            da = pick(row, "mFRR Upp Volym DA (MW)")
            volume = None if sa is None and da is None else (sa or 0) + (da or 0)
        flag = pick(row, "mfrr_activation_flag")
        return {
            "mfrr_activation_energy_price_eur_mwh": price,
            "mfrr_activation_volume_mw": volume,
            "mfrr_activation_flag": int(flag) if flag is not None else (
                int(volume > 0) if volume is not None else None
            ),
        }
    raise ValueError(f"Unknown family: {family}")


def load_raw(root: Path, start: date, end: date) -> tuple[dict, dict]:
    data: dict[str, dict[datetime, dict]] = {family: {} for family in FAMILIES}
    provenance: dict[str, list[str]] = {family: [] for family in FAMILIES}
    for family in FAMILIES:
        folder = root / family
        for path in sorted(folder.glob("**/*.csv")):
            provenance[family].append(str(path))
            for line, row in enumerate(read_csv(path), 2):
                try:
                    timestamp = to_utc(row)
                    if not (start <= timestamp.date() < end):
                        continue
                    values = transform(family, row)
                    if values is None:
                        continue
                    if all(value is None for value in values.values()):
                        raise ValueError("All data fields are null")
                    if timestamp in data[family]:
                        if data[family][timestamp] != values:
                            raise ValueError(f"Conflicting duplicate at {timestamp.isoformat()}")
                        continue
                    data[family][timestamp] = values
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"{path}:{line}: {exc}") from exc
    return data, provenance


def quarter_hour_index(start: date, end: date):
    instant = datetime.combine(start, datetime.min.time(), tzinfo=UTC)
    stop = datetime.combine(end, datetime.min.time(), tzinfo=UTC)
    while instant < stop:
        yield instant
        instant += timedelta(minutes=15)


def expand_to_quarters(family: str, observations: dict[datetime, dict]) -> dict[datetime, dict]:
    # Reserve capacity quotes are hourly. Day-ahead spot switched from
    # hourly to 15-minute MTU; only pre-Oct-2025 hourly prices are repeated.
    expanded = dict(observations)
    for timestamp, values in observations.items():
        hourly = family in ("fcr", "mfrr_capacity") or (
            family == "spot" and timestamp.date() < date(2025, 10, 1)
        )
        if not hourly or timestamp.minute != 0:
            continue
        for minutes in (15, 30, 45):
            child = timestamp + timedelta(minutes=minutes)
            if child not in expanded:
                expanded[child] = values
    return expanded


def write_history(raw_root: Path, output_root: Path, start: date, end: date,
                  *, require_complete: bool = False) -> dict:
    if end <= start:
        raise ValueError("end-exclusive must be after start")
    observations, provenance = load_raw(raw_root, start, end)
    for family in FAMILIES:
        observations[family] = expand_to_quarters(family, observations[family])
    # A single global maximum keeps the seasonal variation in the eSett
    # shape. Zero means zero; missing observations remain missing.
    pv_observations = observations["pv"]
    unscaled = [entry["site_pv_kw"] for entry in pv_observations.values()
                if entry["site_pv_kw"] is not None]
    using_esett = any(
        "esett" in path.lower() for path in provenance["pv"]
    )
    if using_esett:
        if any("site_pv_kw" in row for path in provenance["pv"]
               for row in read_csv(Path(path))[:1]):
            raise ValueError("Do not mix pre-scaled site PV and eSett proxy in one import")
        maximum = max(unscaled) if unscaled else 0
        if maximum <= 0:
            raise ValueError("eSett solar proxy has no positive generation")
        for entry in pv_observations.values():
            if entry["site_pv_kw"] is not None:
                entry["site_pv_kw"] = round(800 * entry["site_pv_kw"] / maximum, 6)

    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / f"historical_15min_se3_{start:%Y%m%d}_{end:%Y%m%d}_exclusive.csv"
    columns = ["timestamp_utc", *[field for family in FAMILIES for field in FIELDS[family]]]
    quality: dict = {
        "start_inclusive_utc": start.isoformat(),
        "end_exclusive_utc": end.isoformat(),
        "market_zone": "SE3",
        "mfrr_zone_approximation": "SN3",
        "timezone": "UTC",
        "pv_semantics": "800 kW scaled eSett Sweden-wide solar proxy" if using_esett else "input site PV",
        "load_semantics": "input measured or separately generated seasonal load; never replicated representative day",
        "families": {},
    }
    totals = defaultdict(int)
    count = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for timestamp in quarter_hour_index(start, end):
            row = {"timestamp_utc": timestamp.isoformat().replace("+00:00", "Z")}
            for family, fields in FIELDS.items():
                data = observations[family].get(timestamp, {})
                # Require complete family observation; partial market rows are missing.
                valid = all(data.get(field) is not None for field in fields)
                if valid:
                    totals[family] += 1
                row.update({field: data.get(field) for field in fields})
            writer.writerow(row)
            count += 1
    for family in FAMILIES:
        quality["families"][family] = {
            "files": provenance[family],
            "non_null_complete_intervals": totals[family],
            "expected_intervals": count,
            "missing_intervals": count - totals[family],
            "completeness_pct": round(100 * totals[family] / count, 3),
        }
    quality["expected_intervals"] = count
    quality["data_file"] = str(path)
    report_path = output_root / "historical_coverage.json"
    report_path.write_text(json.dumps(quality, indent=2) + "\n", encoding="utf-8")
    if require_complete and any(totals[family] != count for family in FAMILIES):
        raise ValueError(f"Incomplete two-year coverage; see {report_path}")
    return quality


def request_json(url: str, params: dict) -> object:
    url = url + "?" + urlencode(params)
    for attempt in range(4):
        try:
            with urlopen(Request(url, headers={"User-Agent": "bess-market-optimizer-history/1.0"}),
                         timeout=45) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise
        except (TimeoutError, URLError):
            if attempt == 3:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError("Request failed")


def month_windows(start: date, end: date):
    current = start
    while current < end:
        following_month = (current.replace(day=1) + timedelta(days=32)).replace(day=1)
        stop = min(end, following_month)
        yield current, stop
        current = stop


def save_rows(destination: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"No observations returned for {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    headers = sorted({key for row in rows for key in row})
    temporary = destination.with_suffix(".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(destination)


def fetch_svk_spot(raw_root: Path, start: date, end: date) -> None:
    """Fetch archived free SVK SE3 spot prices; source has stopped updating."""
    for first, last in month_windows(start, end):
        rows = []
        offset = 0
        while True:
            result = request_json(SVK_ENDPOINT, {
                "resource_id": SPOT_RESOURCE,
                "filters": json.dumps({
                    "bidding_zone": "SE3",
                    "start_time_utc": {
                        "gte": f"{first.isoformat()}T00:00:00",
                        "lt": f"{last.isoformat()}T00:00:00",
                    },
                }),
                "sort": "start_time_utc",
                "limit": 1000,
                "offset": offset,
            })
            if not isinstance(result, dict) or not result.get("success"):
                raise ValueError(f"Invalid SVK CKAN response for {first}")
            batch = result["result"]["records"]
            rows.extend(batch)
            if len(batch) < 1000:
                break
            offset += len(batch)
        if rows:
            save_rows(raw_root / "spot" / f"svk_se3_{first:%Y%m%d}_{last:%Y%m%d}.csv", rows)
        else:
            print(f"No SVK spot rows: {first} to {last} (source may have stopped)", file=sys.stderr)


def fetch_mimer_fcr(raw_root: Path, start: date, end: date) -> None:
    """Fetch Swedish aggregate FCR-N prices; do not mislabel as zone-specific."""
    for first, last in month_windows(start, end):
        result = request_json(MIMER_FCR_ENDPOINT, {
            "periodFrom": first.isoformat(), "periodTo": (last - timedelta(days=1)).isoformat(),
        })
        if not isinstance(result, list):
            raise ValueError(f"Unexpected Mimer response structure: {first}")
        # Preserve source values; importer applies timezone and DST checks.
        if result:
            save_rows(raw_root / "fcr" / f"mimer_fcr_{first:%Y%m%d}_{last:%Y%m%d}.csv", result)
        else:
            print(f"No Mimer FCR rows: {first} to {last}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare two years of real historical SE3/SN3 BESS inputs.")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2024, 7, 1))
    parser.add_argument("--end-exclusive", type=date.fromisoformat, default=date(2026, 7, 1))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/history/raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/history/processed"))
    parser.add_argument("--fetch-svk-spot", action="store_true")
    parser.add_argument("--fetch-mimer-fcr", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args(argv)
    if args.end_exclusive <= args.start:
        parser.error("--end-exclusive must be after --start")
    if args.fetch_svk_spot:
        fetch_svk_spot(args.raw_dir, args.start, args.end_exclusive)
    if args.fetch_mimer_fcr:
        fetch_mimer_fcr(args.raw_dir, args.start, args.end_exclusive)
    result = write_history(args.raw_dir, args.output_dir, args.start, args.end_exclusive,
                           require_complete=args.require_complete)
    print(json.dumps({name: info["completeness_pct"]
                      for name, info in result["families"].items()}, indent=2))
    print(f"Coverage report: {args.output_dir / 'historical_coverage.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
