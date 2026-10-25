"""Notebook-friendly eSett Open Data downloader.

Keeps eSett source observations independent from canonical BESS model inputs.
See https://api.opendata.esett.com/openapi?format=json.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API = "https://api.opendata.esett.com"
STOCKHOLM = ZoneInfo("Europe/Stockholm")
ROUTES = {
    "production": ("/EXP16/MBAOptions", "/EXP16/Volumes"),
    "consumption": ("/EXP15/MBAOptions", "/EXP15/Consumption"),
    "load_profile": ("/EXP18/MBAOptions", "/EXP18/LoadProfile"),
    "imbalance_prices": ("/EXP14/MBAOptions", "/EXP14/Prices"),
}


def new_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"Accept": "application/json", "User-Agent": "btm-bess-esett-research/0.1"})
    return session


def _get(session: requests.Session, path: str, params=None) -> list:
    response = session.get(API + path, params=params, timeout=(10, 60))
    if response.status_code == 204:
        return []
    if not response.ok:
        raise requests.HTTPError(
            f"{response.status_code} for {response.url}: {response.text[:600]}",
            response=response,
        )
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list at {path}, got {type(payload).__name__}: {str(payload)[:300]}")
    return payload


def _mba_groups(payload: list) -> list[dict]:
    """The EXP18 options schema may be a nested array."""
    groups = []
    for item in payload:
        if isinstance(item, list):
            groups.extend(_mba_groups(item))
        elif isinstance(item, dict):
            groups.append(item)
        else:
            raise ValueError(f"Unexpected MBA options value: {item!r}")
    return groups


def mba_options(dataset: str, session: requests.Session | None = None) -> list[dict]:
    """Return country groups with MBA EIC code and display name."""
    if dataset not in ROUTES:
        raise ValueError(f"Expected one of {list(ROUTES)}, got {dataset!r}")
    session = session or new_session()
    return _mba_groups(_get(session, ROUTES[dataset][0]))


def swedish_mba_codes(groups: list[dict]) -> list[str]:
    """Read EIC codes from live metadata; never assume SE3 is a query code."""
    codes = []
    for group in groups:
        country = str(group.get("countryCode") or group.get("country") or "").strip().lower()
        if country not in ("se", "swe", "sweden", "sverige"):
            continue
        for area in group.get("mbas") or []:
            if isinstance(area, dict) and area.get("code"):
                codes.append(area["code"])
    return sorted(set(codes))


def local_day_window(day: date) -> tuple[datetime, datetime]:
    """Swedish local day to UTC, correctly handling 92/96/100 DST slots."""
    start = datetime(day.year, day.month, day.day, tzinfo=STOCKHOLM)
    next_day = day + timedelta(days=1)
    end = datetime(next_day.year, next_day.month, next_day.day, tzinfo=STOCKHOLM)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def fetch_range(
    dataset: str,
    mba: str,
    start_utc: datetime,
    end_utc: datetime,
    session: requests.Session | None = None,
    *,
    mga: str | None = None,
) -> list[dict]:
    """Fetch raw JSON rows for one MBA and an explicit UTC window."""
    if dataset not in ROUTES:
        raise ValueError(f"Unknown dataset: {dataset}")
    if not mba.strip():
        raise ValueError("Supply an MBA EIC code from the relevant MBAOptions endpoint")
    if start_utc.tzinfo is None or end_utc.tzinfo is None or end_utc <= start_utc:
        raise ValueError("Supply timezone-aware datetimes with start before end")
    if mga and dataset != "load_profile":
        raise ValueError("mga filtering applies only to load_profile")
    params = {
        "start": iso_utc(start_utc),
        "end": iso_utc(end_utc),
        "mba": mba,
    }
    if mga:
        params["mga"] = mga
    rows = _get(session or new_session(), ROUTES[dataset][1], params)
    for index, record in enumerate(rows):
        if not isinstance(record, dict):
            raise ValueError(f"Unexpected non-object response row {index}")
    return rows


def fetch_day(
    dataset: str,
    mba: str,
    day: date,
    session: requests.Session | None = None,
    *,
    mga: str | None = None,
) -> list[dict]:
    start, end = local_day_window(day)
    return fetch_range(dataset, mba, start, end, session, mga=mga)


def utc_timestamps(rows: list[dict]) -> list[datetime]:
    """Validate returned timestamps without dropping records or masking gaps."""
    result = []
    for i, record in enumerate(rows):
        value = record.get("timestampUTC")
        if not value:
            raise ValueError(f"Row {i} has no timestampUTC: {str(record)[:200]}")
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError(f"Row {i} has naive UTC timestamp: {value}")
        result.append(parsed.astimezone(timezone.utc))
    return result


def check_day(rows: list[dict], day: date) -> dict:
    """Check a Swedish day; row count can exceed intervals for MGA-based load."""
    begin, end = local_day_window(day)
    timestamps = utc_timestamps(rows)
    out_of_window = sum(not (begin <= t < end) for t in timestamps)
    unique_intervals = len(set(t for t in timestamps if begin <= t < end))
    expected_intervals = int((end - begin).total_seconds() // 900)
    if out_of_window:
        raise ValueError(
            f"{out_of_window} records outside {day} Swedish-local day. "
            "Check the API's end-boundary semantics before using these records."
        )
    if any(t.minute % 15 or t.second or t.microsecond for t in timestamps):
        raise ValueError("Received timestamps not aligned to 15-minute boundaries")
    return {
        "day": day.isoformat(),
        "row_count": len(rows),
        "distinct_quarter_hours": unique_intervals,
        "expected_quarter_hours": expected_intervals,
        "missing_quarter_hours": expected_intervals - unique_intervals,
        "complete_time_axis": unique_intervals == expected_intervals,
    }


def _partition_file(root: Path, dataset: str, mba: str, day: date, mga: str | None) -> Path:
    safe_mba = re.sub(r"[^A-Za-z0-9_-]", "_", mba)
    safe_mga = "" if mga is None else "_" + re.sub(r"[^A-Za-z0-9_-]", "_", mga)
    return root / dataset / f"mba={safe_mba}{safe_mga}" / f"{day.isoformat()}.json"


def backfill(
    datasets: list[str],
    mba_by_dataset: dict[str, list[str]],
    start: date,
    end_exclusive: date,
    root: Path = Path("data/history/source/esett"),
    *,
    mga: str | None = None,
    overwrite: bool = False,
    pause_seconds: float = 0.3,
    session: requests.Session | None = None,
) -> list[dict]:
    """Daily, resumable, source-preserving backfill; end date is exclusive.

    Each partition stores source JSON + request/coverage metadata.
    Failed requests raise without creating a fake completed partition.
    """
    if end_exclusive <= start:
        raise ValueError("end_exclusive must be after start")
    if pause_seconds < 0:
        raise ValueError("pause_seconds must be nonnegative")
    session = session or new_session()
    manifests = []
    for dataset in datasets:
        if dataset not in ROUTES:
            raise ValueError(f"Unknown dataset: {dataset}")
        codes = mba_by_dataset.get(dataset, [])
        if not codes:
            raise ValueError(f"No MBA codes configured for {dataset}")
        day = start
        while day < end_exclusive:
            for mba in codes:
                path = _partition_file(root, dataset, mba, day, mga if dataset == "load_profile" else None)
                if path.exists() and not overwrite:
                    manifests.append({"dataset": dataset, "mba": mba, "day": str(day), "status": "cached",
                                      "path": str(path)})
                    continue
                start_utc, end_utc = local_day_window(day)
                rows = fetch_range(dataset, mba, start_utc, end_utc, session,
                                   mga=mga if dataset == "load_profile" else None)
                audit = check_day(rows, day)
                document = {
                    "source": API + ROUTES[dataset][1],
                    "dataset": dataset,
                    "mba_eic": mba,
                    "mga": mga if dataset == "load_profile" else None,
                    "start_utc": iso_utc(start_utc),
                    "end_utc_exclusive": iso_utc(end_utc),
                    "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                    "audit": audit,
                    "records": rows,
                }
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix(".json.tmp")
                temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
                temporary.replace(path)
                manifest = {"dataset": dataset, "mba": mba, "day": str(day),
                            "status": "downloaded" if rows else "empty", "path": str(path), **audit}
                manifests.append(manifest)
                print(f"{dataset:16} {mba:18} {day} rows={len(rows):5} "
                      f"quarters={audit['distinct_quarter_hours']}/{audit['expected_quarter_hours']}")
                time.sleep(pause_seconds)
            day += timedelta(days=1)
    return manifests


def main() -> None:
    parser = argparse.ArgumentParser(description="Download eSett Open Data history by dataset and MBA")
    parser.add_argument("--dataset", choices=ROUTES.keys(), required=True)
    parser.add_argument("--mba", required=True, help="MBA EIC code from the corresponding MBAOptions endpoint")
    parser.add_argument("--start", type=date.fromisoformat, required=True, help="Swedish local start day")
    parser.add_argument("--end-exclusive", type=date.fromisoformat, required=True, help="Swedish local end day")
    parser.add_argument("--root", type=Path, default=Path("data/history/source/esett"))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--mga", help="Optional MGA EIC code for load_profile")
    args = parser.parse_args()
    results = backfill(
        [args.dataset], {args.dataset: [args.mba]}, args.start, args.end_exclusive,
        root=args.root, mga=args.mga, overwrite=args.overwrite,
    )
    print(json.dumps({"partitions": len(results), "downloaded": sum(
        r["status"] == "downloaded" for r in results)}, indent=2))


if __name__ == "__main__":
    main()
