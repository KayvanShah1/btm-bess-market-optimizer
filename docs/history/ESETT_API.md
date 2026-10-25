# eSett Open Data notebook and downloader

The repo already contains four manually exported eSett datasets for the 2026-06-24 representative Swedish day:

| Existing raw CSV | OpenAPI route | Schema / relevant fields |
|---|---|---|
| `esett_production_profile_20260624.csv` | `GET /EXP16/Volumes` | `timestampUTC`, `mba`, `solar`, `total`, `hydro`, `wind`, etc. (MWh) |
| `esett_consumption_profile_20260624.csv` | `GET /EXP15/Consumption` | `timestampUTC`, `mba`, `metered`, `profiled`, `flex`, `total` (MWh) |
| `esett_load_profile_20260624.csv` | `GET /EXP18/LoadProfile` | `timestampUTC`, `mba`, `mgaCode`, `quantity`, `total` (MWh) |
| `esett_imbalance_prices_20260624.csv` | `GET /EXP14/Prices` | `timestampUTC`, `mba`, `imblPurchasePrice`, `imblSalesPrice`, `upRegPrice`, `downRegPrice` (EUR/MWh) |

Specification: https://api.opendata.esett.com/openapi?format=json

These routes require **MBA EIC codes** rather than the displayed `SE1`–`SE4` labels. Use the matching `/EXPxx/MBAOptions` endpoint first, and inspect the return values before selecting markets. The notebook tests one MBA for a single day **in memory**, without writing daily partitions. Historical requests include repeated `mba` query parameters for all selected Swedish areas in one full-calendar-quarter request per dataset.

The API is public, authorization-free, and subject to provider fair-use restrictions. Queries can be rate-limited; the script retries 429 and transient 5xx statuses with backoff, runs sequentially, and sleeps between noncached requests.

## Jupyter notebook

Open [notebooks/esett_open_data_backfill.ipynb](../../notebooks/esett_open_data_backfill.ipynb) in VS Code or Jupyter. The notebook:

1. Installs `requests` and `pandas`.
2. Reads provider MBA options for each of the four datasets.
3. Tests **one Swedish-local day, one real EIC code per dataset**.
4. Displays returned JSON columns, sample rows, and a time-axis coverage check.
5. Provides a disabled-by-default full-quarter test (2026-Q2), followed by a two-year loop (2024-Q3 through 2026-Q2), with one API call per dataset per quarter.

The API's published OpenAPI response schemas have been inspected, but the live endpoints were not exercised in this branch. The first smoke test must confirm those contracts and possible query size restrictions.

## Script / command line

The same downloader can be used from Python:

```python
from datetime import date
from scripts.esett_open_data import new_session, mba_options, swedish_mba_codes, fetch_day, backfill

session = new_session()
print(mba_options("production", session))
codes = swedish_mba_codes(mba_options("production", session))
print("Check selected EIC code:", codes)
rows = fetch_day("production", codes[0], date(2026, 6, 24), session)
print(len(rows), rows[:2])
```

Or, from the repository root with an MBA EIC code from `MBAOptions`:

```powershell
uv run --with requests --package bess-optimizer python scripts/esett_open_data.py --dataset production --mba <MBA_EIC_CODE> --start 2026-04-01 --end-exclusive 2026-07-01
```

The script uses 15-minute API endpoints rather than `/Aggregate`, since the latter explicitly aggregates to at least hourly resolution. It requests a Swedish-local day expressed as exact UTC boundaries. DST spring/fall days yield **92/100** quarter-hour intervals, not 96. No timezone-naive timestamp is used as a join key.

## Historical quarterly request and partition policy

- **One API request per dataset per calendar quarter**, containing repeated `mba` parameters for the selected Swedish MBA EIC codes. Four quarterly requests per full year per dataset, or 8 across the selected two years. Across the four datasets, that's 32 requests **if every query succeeds**, excluding discovery and the in-memory smoke tests.
- **One consolidated JSON file per dataset per quarter**, containing source observations for all requested MBAs. No files per MBA/day.
- Quarterly records are written atomically after the full-quarter response is received and timestamp boundaries are checked. If the provider rejects the request, times out, or returns an empty response, that quarter is not stored. The downloader does not silently split into shorter requests.
- Source limits are not guaranteed to permit quarterly queries for every endpoint; an API query-limit error is surfaced for investigation. Do not claim a complete two-year history until each quarterly response is validated.
- Missing 15-minute intervals are flagged in the saved `audit`. Incomplete partitions are automatically re-requested next time; fully covered partitions with the same request parameters are cached. Distinct returned MBA labels are included in the report and must be compared with the intended EIC code selection.
- The start and exclusive end dates must fall on Jan 1, Apr 1, Jul 1, or Oct 1. Use `fetch_day()` separately for in-memory one-day validation.

Storage layout:

```text
data/history/source/esett/
    production/2024-Q3.json ... 2026-Q2.json
    consumption/2024-Q3.json ... 2026-Q2.json
    load_profile/2024-Q3.json ... 2026-Q2.json
    imbalance_prices/2024-Q3.json ... 2026-Q2.json
```

Each partition retains original API `records`, endpoint URL, requested EIC codes, retrieval timestamp, quarter's local and UTC range, and coverage audit. The repository ignores these downloads. Existing `data/raw/` samples are unchanged.
## Critical interpretation

- **Production:** the `solar` value is a Swedish market-balancing-area energy series, not a customer PV meter or site PV forecast. Aggregate the relevant MBA series deliberately and check for overlaps, source units, and missing areas before making an 800-kW PV-shape proxy. One arbitrary Swedish MBA is a smoke test, not a national aggregate.
- **Consumption and load:** market-area totals and MGA load profiles are *not* `site_load_kw`. They are useful for regional demand pattern analysis or synthetic-profile calibration, but measured site usage must be sourced separately.
- **Prices:** `/EXP14/Prices` gives imbalance/related regulation prices; it is **not** Nord Pool day-ahead spot prices or Mimer FCR/mFRR capacity data.
- **Partial or missing data:** a successful 200 request, a 204 empty response, or a cached partition does not prove completeness. Inspect the returned interval audit and missing quarter counts. For load profiles, many MGA rows can share the same 15-minute slot; row count cannot be equated to quarter count.
- **Period differences:** the repo's existing `20260624` CSVs are labeled in Swedish local time; the API accepts UTC bounds. The notebook converts the requested local day to UTC and preserves the API's `timestampUTC` values.
- **API limits:** one full quarter for `/EXP18/LoadProfile` across all MGAs may exceed the provider limit. Test the quarter query; the script does not automatically split it. Selecting only one MGA is an explicitly incomplete area subset.

## Next integration gate

Before connecting these observations to `bess_optimizer/data/history.py`, verify the June 24 API responses against the existing four CSVs by matching **local/UTC timestamps, individual MBAs, units, and source categories**. Aggregation methodology must be explicit. Implement a separate transformation from raw source JSON to canonical BESS family CSVs and add tests for duplication, missing coverage, and source totals; do not relabel imbalance prices as spot or regional load as site demand.

Separate publisher ingestion is still needed for Nord Pool day-ahead prices and Svenska kraftnät FCR-N and mFRR market data.
