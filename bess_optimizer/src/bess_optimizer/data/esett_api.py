"""Notebook-friendly eSett Open Data downloader.

Keeps eSett source observations independent from canonical BESS model inputs.
See https://api.opendata.esett.com/openapi?format=json.
"""
from __future__ import annotations

import argparse
import json
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


def metering_grid_areas(mba: str, session: requests.Session | None = None) -> list[dict]:
    """Discover MGA codes for a selected MBA when load-profile requests are too large."""
    if not mba.strip():
        raise ValueError("Supply an MBA EIC code")
    return _get(session or new_session(), "/EXP03/MeteringGridAreas", {"mba": mba})


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
    mba: str | list[str],
    start_utc: datetime,
    end_utc: datetime,
    session: requests.Session | None = None,
    *,
    mga: str | None = None,
) -> list[dict]:
    """Fetch one full UTC window, with one query parameter per requested MBA."""
    if dataset not in ROUTES:
        raise ValueError(f"Unknown dataset: {dataset}")
    mbas = [mba] if isinstance(mba, str) else list(mba)
    if not mbas or any(not isinstance(code, str) or not code.strip() for code in mbas):
        raise ValueError("Supply MBA EIC codes from the matching MBAOptions endpoint")
    if len(set(mbas)) != len(mbas):
        raise ValueError("MBA EIC codes must be unique")
    if start_utc.tzinfo is None or end_utc.tzinfo is None or end_utc <= start_utc:
        raise ValueError("Supply timezone-aware datetimes with start before end")
    if mga and dataset != "load_profile":
        raise ValueError("mga filtering applies only to load_profile")

    base_params = {"start": iso_utc(start_utc), "end": iso_utc(end_utc)}
    if len(mbas) == 1:
        params = {**base_params, "mba": mbas[0]}
    else:
        # The eSett API supports repeated MBA query parameters. Avoid one HTTP
        # call per area when requesting a full quarterly source partition.
        params = list(base_params.items()) + [("mba", code) for code in mbas]
    if mga:
        if isinstance(params, dict):
            params["mga"] = mga
        else:
            params.append(("mga", mga))
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
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = datetime.strptime(str(value), "%d.%m.%Y/%H:%M")
            except ValueError as exc:
                raise ValueError(f"Row {i} has unknown timestampUTC format: {value}") from exc
        # The field is explicitly UTC in the eSett schema, even when no offset is encoded.
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
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


def _next_quarter(day: date) -> date:
    """First day of the quarter immediately following a calendar date."""
    quarter_month = ((day.month - 1) // 3) * 3 + 1
    if quarter_month == 10:
        return date(day.year + 1, 1, 1)
    return date(day.year, quarter_month + 3, 1)


def _require_quarter_boundary(day: date) -> None:
    if day.day != 1 or day.month not in (1, 4, 7, 10):
        raise ValueError(
            f"Expected calendar quarter boundary (Jan/Apr/Jul/Oct 1), got {day}. "
            "Use fetch_day() for a single-day smoke test."
        )


def quarter_windows(start: date, end_exclusive: date):
    """Consecutive [start, end) calendar quarters, without partial files."""
    _require_quarter_boundary(start)
    _require_quarter_boundary(end_exclusive)
    if end_exclusive <= start:
        raise ValueError("end_exclusive must be after start")
    current = start
    while current < end_exclusive:
        stop = _next_quarter(current)
        yield current, stop
        current = stop


def quarter_file(root: Path, dataset: str, first: date) -> Path:
    quarter = (first.month - 1) // 3 + 1
    return root / dataset / f"{first.year}-Q{quarter}.json"


def check_window(
    rows: list[dict], start: date, end_exclusive: date, *, expected_mba_count: int | None = None
) -> dict:
    """Audit 15-minute UTC coverage for a full Swedish calendar quarter.

    Multiple MGAs may share a timestamp; row count is not a coverage count.
    MBA labels in returned rows may differ from requested EIC codes.
    """
    begin, _ = local_day_window(start)
    stop, _ = local_day_window(end_exclusive)
    expected = int((stop - begin).total_seconds() // 900)
    timestamps = utc_timestamps(rows)
    if any(timestamp < begin or timestamp >= stop for timestamp in timestamps):
        raise ValueError("API returned observations outside the requested quarter")
    if any(t.minute % 15 or t.second or t.microsecond for t in timestamps):
        raise ValueError("API returned timestamps not aligned to 15-minute intervals")
    observed = len(set(timestamps))
    by_mba: dict[str, set[datetime]] = {}
    for row, timestamp in zip(rows, timestamps):
        label = str(row.get("mba") or "(missing MBA label)")
        by_mba.setdefault(label, set()).add(timestamp)

    # Some API responses use display names rather than the requested EIC codes.
    # Count the distinct reported MBAs rather than assuming the labels match.
    # A source returning fewer areas than requested must never be marked cached.
    all_areas_present = expected_mba_count is None or len(by_mba) == expected_mba_count
    return {
        "start_local": start.isoformat(),
        "end_exclusive_local": end_exclusive.isoformat(),
        "row_count": len(rows),
        "expected_mba_count": expected_mba_count,
        "response_mba_count": len(by_mba),
        "all_requested_mbas_present_by_count": all_areas_present,
        "expected_quarter_hours": expected,
        "distinct_quarter_hours": observed,
        "missing_quarter_hours": expected - observed,
        "coverage_by_response_mba": {
            mba: {
                "distinct_quarter_hours": len(instants),
                "missing_quarter_hours": expected - len(instants),
            }
            for mba, instants in sorted(by_mba.items())
        },
        "complete_time_axis": bool(rows) and all_areas_present and observed == expected and all(
            len(instants) == expected for instants in by_mba.values()
        ),
    }


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
    """One HTTP request per dataset/quarter, all selected MBAs in one file.

    Exactly four output partitions per full calendar year per dataset.
    A provider error aborts the quarter instead of silently fragmenting into
    more API requests. Cached quarters are reused only if their requested
    area selection matches and coverage is complete.
    """
    windows = list(quarter_windows(start, end_exclusive))
    if pause_seconds < 0:
        raise ValueError("pause_seconds must be nonnegative")
    if mga and datasets != ["load_profile"]:
        raise ValueError("MGA filtering requires only the load_profile dataset")
    session = session or new_session()
    manifests = []
    for dataset in datasets:
        if dataset not in ROUTES:
            raise ValueError(f"Unknown dataset: {dataset}")
        codes = list(mba_by_dataset.get(dataset, []))
        if not codes:
            raise ValueError(f"No MBA codes configured for {dataset}")
        for first, last in windows:
            path = quarter_file(root, dataset, first)
            if path.exists() and not overwrite:
                cached = json.loads(path.read_text(encoding="utf-8"))
                if (cached.get("requested_mba_eic_codes") == codes
                    and cached.get("mga") == (mga if dataset == "load_profile" else None)
                    and cached.get("start_local") == first.isoformat()
                    and cached.get("end_exclusive_local") == last.isoformat()
                    and cached.get("audit", {}).get("complete_time_axis")):
                    manifests.append({
                        "dataset": dataset, "quarter": path.stem,
                        "status": "cached", "path": str(path), **cached["audit"],
                    })
                    continue
            start_utc, _ = local_day_window(first)
            stop_utc, _ = local_day_window(last)
            # A full quarter, all MBAs, in *one* API call. Never fall back to
            # daily/monthly requests without explicit design approval.
            try:
                rows = fetch_range(
                    dataset, codes, start_utc, stop_utc, session,
                    mga=mga if dataset == "load_profile" else None,
                )
            except requests.HTTPError as exc:
                raise RuntimeError(
                    f"eSett rejected {dataset} {path.stem} as one request "
                    f"for {len(codes)} MBA(s): {exc}. No smaller requests were made. "
                    "Check provider query/row limits or reduce the chosen MBA set."
                ) from exc
            if not rows:
                raise ValueError(f"Empty eSett quarter: {dataset} {path.stem}; no file written")
            audit = check_window(rows, first, last, expected_mba_count=len(codes))
            document = {
                "source": API + ROUTES[dataset][1],
                "dataset": dataset,
                "requested_mba_eic_codes": codes,
                "mga": mga if dataset == "load_profile" else None,
                "start_local": first.isoformat(),
                "end_exclusive_local": last.isoformat(),
                "start_utc": iso_utc(start_utc),
                "end_utc_exclusive": iso_utc(stop_utc),
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "audit": audit,
                "records": rows,
            }
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(document, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            temporary.replace(path)
            status = "downloaded" if audit["complete_time_axis"] else "incomplete"
            manifests.append({
                "dataset": dataset, "quarter": path.stem,
                "status": status, "path": str(path), **audit,
            })
            print(
                f"{dataset:16} {path.stem} MBAs={len(codes):2} "
                f"rows={len(rows):6}  quarters="
                f"{audit['distinct_quarter_hours']}/{audit['expected_quarter_hours']} [{status}]"
            )
            time.sleep(pause_seconds)
    return manifests

def main() -> None:
    parser = argparse.ArgumentParser(description="Download eSett Open Data history by dataset and MBA")
    parser.add_argument("--dataset", choices=ROUTES.keys(), required=True)
    parser.add_argument("--mba", action="append", required=True, help="MBA EIC code; repeat --mba to query multiple MBAs together")
    parser.add_argument("--start", type=date.fromisoformat, required=True, help="Swedish local start day")
    parser.add_argument("--end-exclusive", type=date.fromisoformat, required=True, help="Swedish local end day")
    parser.add_argument("--root", type=Path, default=Path("data/history/source/esett"))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--mga", help="Optional MGA EIC code for load_profile")
    args = parser.parse_args()
    results = backfill(
        [args.dataset], {args.dataset: args.mba}, args.start, args.end_exclusive,
        root=args.root, mga=args.mga, overwrite=args.overwrite,
    )
    print(json.dumps({"partitions": len(results), "downloaded": sum(
        r["status"] == "downloaded" for r in results),
        "incomplete": sum(r["status"] == "incomplete" for r in results)}, indent=2))


if __name__ == "__main__":
    main()
