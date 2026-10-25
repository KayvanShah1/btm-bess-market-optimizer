# Historical BESS dataset: two-year ingestion

## Scope

Historical window (UTC): **2024-07-01 00:00 inclusive to 2026-07-01 00:00 exclusive** (730 days, **70,080** 15-minute slots). Keep the original representative-day model and its results unchanged.

This is an **ingestion and coverage framework**, not a claim that two years of data have already been downloaded. There are no fabricated market prices or re-used daily traces. Each unavailable observation is left blank and counted. Do not deploy dispatch strategies against the output without first checking the coverage report.

| Family | Origin / format | Geographic meaning | Notes |
|---|---|---|---|
| load | Site-meter export with `timestamp_utc,site_load_kw` | Real C&I site | Existing light-factory profile is synthetic for one day and must **not** be copied across 730 days. Separately generated calendar-aware synthetic load must carry `data_kind=synthetic_seasonal`. |
| pv | eSett production export with `Date/Time UTC,Solar [MWh]` | Aggregate Sweden-wide solar proxy | Rescaled using one history-wide peak to 800 kW; **not** an SE3 plant metering or forecast product. Alternative site measurements use `timestamp_utc,site_pv_kw`. |
| spot | Svenska kraftnät export `start_time_utc,bidding_zone,price,price_unit`, or licensed Nord Pool `timestamp_utc,SE3` | SE3 | Unit **EUR/MWh**. Free public SVK dataset is archived and may not cover recent periods. Source differences must be reconciled before using both. |
| fcr | Mimer FCR-N price export `Datum,FCR-N Pris (EUR/MW)` | Swedish aggregate FCR-N price | EUR/MW/h equivalent for an hourly capacity-price interval; not a zone-specific price. |
| mfrr_capacity | Mimer CSV `Period,Elområde,mFRR Upp Pris (EUR/MW),mFRR Upp Volym (MW)` | SN3 approximation | SE3 ≠ SN3. |
| mfrr_activation | Mimer CSV `Period,Elområde,mFRR Upp Pris,mFRR Upp Volym SA (MW),mFRR Upp Volym DA (MW)` | SN3 approximation | Activation is 15-minute and may be published after the operating interval. |

Source families and semantics follow [DATA_METHOD.md](../DATA_METHOD.md). Do not equate spot prices and mFRR activation prices, or use aggregate eSett solar totals as measured site output.

## Run

From repository root, in the uv workspace:

```powershell
uv run --package bess-optimizer python -m bess_optimizer.data.history --start 2024-07-01 --end-exclusive 2026-07-01
```

Put source CSV exports in `data/history/raw/<family>/*.csv`. Each file must contain timestamps: prefer explicitly UTC fields (with offset or `Z`). Source-local Swedish times on DST fallback days are rejected unless a `fold` column specifies 0 or 1. The UTC output contains **70,080** rows even with zero inputs; blanks indicate missing data. `historical_coverage.json` counts complete non-null intervals for each family and records paths. Re-running is deterministic for identical inputs.

An **optional, experimental** fetcher can request the archived SVK open-data spot resource or Mimer FCR-N data:

```powershell
uv run --package bess-optimizer python -m bess_optimizer.data.history --fetch-svk-spot
uv run --package bess-optimizer python -m bess_optimizer.data.history --fetch-mimer-fcr
```

External APIs, response schemas, publication schedules, and historical access can change. Check each received CSV and coverage before relying on it; a successful request does not prove a two-year dataset. If an endpoint fails, obtain the publisher's official CSV export and place it under its family instead. Do not run optional fetches against external endpoints without connectivity.

To fail the build on *any* missing family/interval, add `--require-complete`. For a partial research dataset, leave it off and inspect the report.

## Data quality and next work

The builder detects conflicting duplicates, ambiguous or nonexistent Sweden DST-local times, incompatible price units, missing values, and missing files. The time axis is continuous in UTC; 15-minute slot coverage is tracked family by family. For hourly source markets, the importer carries the hourly value across four quarters. Do **not** automatically carry 15-minute activation or recent quarter-hour spot observations across gaps. Explicitly verify source-specific frequency transitions and settlement-period units.

**Not yet delivered as measured history:** customer load, customer PV, complete Nord Pool SE3 licensed history, complete Mimer FCR/mFRR history, historical weather, holidays/site production calendars, and validated two-year end-to-end backtests. These require acquisition, verified provider schemas, calendar/weather joining, and application-layer model changes. The optimizer remains a one-day scheduler until a separate multi-day optimization and SOC continuity implementation is reviewed.

Public source starting points: [Svenska kraftnät open data](https://data.svk.se/), [Mimer](https://mimer.svk.se/), [eSett open data](https://opendata.esett.com/), [Nord Pool](https://data.nordpoolgroup.com/).
