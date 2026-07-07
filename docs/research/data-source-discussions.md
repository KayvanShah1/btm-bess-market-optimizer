# Data Source Discussion

## Purpose

This note defines the data strategy for the behind-the-meter BESS market optimizer. The model needs enough data to schedule a 1 MW / 2 MWh battery across local savings, FCR-N, and mFRR for one representative day, while keeping the work feasible within a short take-home timeline.

The assignment does not require a full historical data platform. A defensible submission can use synthetic site data and one real public market signal, as long as the assumptions are explicit and the scheduler enforces the required constraints.

## Recommendation

Use a hybrid data setup:

| Data group | Recommended source | Model role | Priority |
|---|---|---|---|
| C&I load profile | Synthetic representative site profile | Baseline demand before battery dispatch | Must-have |
| PV generation profile | Synthetic solar curve, or normalized public solar shape if already available | Behind-the-meter generation that reduces grid import | Must-have if PV is included |
| Battery specifications | Assignment assumption: 1 MW / 2 MWh | Power, energy, SOC, and efficiency constraints | Must-have |
| mFRR capacity price | Svenska Kraftnat Mimer mFRR capacity market | Real market signal for mFRR capacity value | Highest-value public data |
| mFRR activation uncertainty | Synthetic low/base/high scenarios; optional Mimer EAM proxy | Activation probability and activation value sensitivity | Must-have |
| FCR-N price | Synthetic stable benchmark; optional Mimer FCR extract | FCR-only baseline and FCR vs mFRR comparison | Must-have, synthetic acceptable |
| Spot price | Synthetic; optional Nord Pool context | Local arbitrage and energy-cost context | Optional |

Best practical version: build the scheduler using synthetic data first, then replace only `mfrr_capacity_price_eur_mw_h` with one day of real Svenska Kraftnat Mimer mFRR capacity-market data.

## Why Not Fully Public Data

The core decision is whether mFRR adds value versus an FCR-only baseline after preserving local savings and battery feasibility. The most relevant real data is therefore ancillary-service market data, not national consumption or generation.

Avoid trying to source every input publicly for the take-home:

```text
Real C&I load
Real PV generation
Real spot price
Real FCR-N price
Real mFRR capacity price
Real mFRR activation
```

That turns the project into data ingestion work and leaves less time for the scheduler, baselines, uncertainty treatment, charts, and write-up.

## Source Evaluation

| Source | Practicality | Relevance | Use now? | Notes |
|---|---:|---:|---:|---|
| Svenska Kraftnat Mimer - mFRR CM | High | Very high | Yes | Best public source for mFRR capacity prices and volumes by bidding area. |
| Svenska Kraftnat Mimer - mFRR EAM | Medium | High | Optional | Useful for activation-volume or activation-price proxies, but likely adds 15-minute cleaning work. |
| Svenska Kraftnat Mimer - FCR | Medium | High | Optional | Useful if FCR-N extraction is quick; otherwise use a synthetic benchmark. |
| Nord Pool day-ahead prices | Medium | Medium | Optional | Helpful for spot-price context, but not central to the FCR-N vs mFRR question. |
| eSett Open Data | Medium | Medium-low | Usually skip | System-level data can be a load-shape proxy, but it is not C&I behind-the-meter load. |
| Brazil ONS or other solar data | High if already cleaned | Medium | Optional | Can provide a normalized PV shape, but synthetic PV is enough. |
| Synthetic data | Very high | High | Yes | Appropriate for site load, PV, FCR-N price, spot price, and activation scenarios. |

## Public Market Data Details

### Svenska Kraftnat Mimer mFRR Capacity Market

This is the single most useful public dataset for the assignment.

Use:

```text
Market: mFRR capacity market
Direction: Up, unless there is a reason to model Down separately
Bidding area: one area only, e.g. SE3 or SE4
Period: one representative day
Resolution: hourly
Model column: mfrr_capacity_price_eur_mw_h
```

The Mimer capacity-market page includes mFRR Up/Down volumes and marginal capacity prices by Swedish bidding area. It also exposes CSV and Excel export options. One representative day is enough to ground the mFRR revenue opportunity without creating a large data-cleaning task.

### Svenska Kraftnat Mimer mFRR Energy Activation Market

Use only after the capacity-market data is already working.

Possible use:

```text
activation_flag = 1 if activation_volume_mw > 0 else 0
activation_probability = mean(activation_flag over selected historical window)
mfrr_activation_energy_price_eur_mwh = marginal_energy_price
```

This can make the activation scenarios more empirical, but it may introduce 15-minute data alignment and additional cleaning. For the two-day version, synthetic low/base/high activation probabilities are acceptable.

### Svenska Kraftnat Mimer FCR

FCR data can improve the FCR-only baseline if it is quick to export and clean. If not, use a stable synthetic FCR-N price series. The comparison remains valid as long as both the FCR-only and FCR+mFRR schedules use the same assumptions.

### Nord Pool Day-Ahead Prices

Spot prices are optional. They help describe local arbitrage or energy-cost savings, but the assignment is primarily about allocating limited battery capacity across local savings, FCR-N, and mFRR.

Use Nord Pool only if the model, baseline, and mFRR uncertainty logic are already complete.

### eSett Open Data

eSett is not a good primary source for C&I site demand. It can provide system or area-level consumption shapes, but the assignment needs a representative behind-the-meter customer profile.

If used, treat it only as a normalized shape proxy:

```text
normalized_load_shape = area_consumption / max(area_consumption)
site_load_kw = normalized_load_shape * chosen_site_peak_kw
```

The write-up should state that the public series is not claimed to be customer-level load.

## Minimum Model Dataset

Build one 24-row hourly dataframe for the representative day:

```text
hour
site_load_kw
pv_generation_kw
spot_price_eur_mwh
fcrn_capacity_price_eur_mw_h
mfrr_capacity_price_eur_mw_h
mfrr_activation_probability
mfrr_activation_energy_price_eur_mwh
```

Battery configuration can stay in a separate config object:

```text
battery_power_mw = 1.0
battery_energy_mwh = 2.0
soc_min = 0.10
soc_max = 0.90
initial_soc = 0.50
round_trip_efficiency = 0.90
peak_import_threshold_kw = 85th percentile of no-battery grid import
minimum_savings_pct = 5
```

## Model Interface

Inputs:

```text
Consumption profile
PV generation profile
Battery specs
Market prices
mFRR activation assumptions
Operating constraints
```

Outputs:

```text
Hourly allocation between local reserve, FCR-N, and mFRR
Hourly SOC
Grid import before and after battery
Local savings
FCR-N revenue
Expected mFRR revenue
Total expected value
Constraint checks
Comparison against FCR-only baseline
```

The scheduler should answer one question:

> Given the site load, PV, battery limits, customer savings floor, FCR-N prices, mFRR prices, and mFRR activation risk, how should each hour's available battery capacity be allocated?

## Scheduling Logic Supported By The Data

1. Calculate site grid import without the battery.
2. Calculate local peak-shaving or savings requirement.
3. Reserve enough battery capacity to keep customer savings above 5%.
4. Use remaining feasible capacity for external services.
5. Compare expected FCR-N value against expected mFRR value.
6. Allocate to mFRR only when expected mFRR value beats FCR-N after readiness and SOC risk.
7. Compare the final schedule against an FCR-only baseline.

## Two-Day Implementation Order

1. Generate the synthetic representative day.
2. Build the no-battery and FCR-only baselines.
3. Build the combined FCR+mFRR scheduler.
4. Add low/base/high mFRR activation scenarios.
5. Add charts and constraint checks.
6. Replace synthetic mFRR capacity price with one day of Mimer mFRR CM data, if the export is quick.
7. Keep all other public data sources optional.

## Report Framing

Use this framing in the README or technical report:

```text
The model uses public Svenska Kraftnat mFRR capacity-market data to ground the mFRR revenue opportunity for a representative Swedish bidding area. Site load, PV generation, FCR-N prices, spot prices, and mFRR activation scenarios are synthetic so the analysis can focus on the scheduling decision, savings-first constraint, SOC feasibility, and comparison against an FCR-only baseline.
```

If all inputs remain synthetic, use:

```text
The assignment allows synthetic data, so the first version uses a fully synthetic representative day. Public Svenska Kraftnat and Nord Pool sources are cited as market context and are natural replacements for the synthetic market-price columns in a production version.
```

## Decision Summary

Use real public data where it matters most: mFRR capacity prices. Keep site-level inputs synthetic unless a clean proxy is already available. The strongest submission is a working, auditable scheduler with explicit uncertainty treatment and baseline comparison, not a broad public-data ingestion project.

## References

- [Mimer portal](https://mimer.svk.se/)
- [Mimer mFRR capacity market](https://mimer.svk.se/Start/NavigateBySortOrder?itemSortOrder=5&parentSortOrder=2)
- [Mimer mFRR energy activation market](https://mimer.svk.se/Start/NavigateBySortOrder?itemSortOrder=7&parentSortOrder=2)
- [Mimer consumption](https://mimer.svk.se/Start/NavigateBySortOrder?itemSortOrder=2&parentSortOrder=2)
- [eSett Open Data](https://opendata.esett.com/)
- [Nord Pool Data Services](https://www.nordpoolgroup.com/en/services/power-market-data-services/)
