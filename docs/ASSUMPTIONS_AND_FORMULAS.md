# Assumptions and Formula Glossary

This document consolidates the main modelling assumptions, simplifications, formulas, and variable definitions used across the Part A optimizer and B3 operational break-even analysis.

The goal is to make the model reviewable. The implementation is intentionally scoped for a representative-day take-home assignment, not a production-grade bidding platform.

---

## 1. Core Modelling Assumptions

| Area | Current assumption | Why it is acceptable for this assignment | Real-world production treatment |
|---|---|---|---|
| Asset size | Base asset is one 1 MW / 2 MWh behind-the-meter battery. | This matches the assignment default and keeps the comparison easy to audit. | Use actual asset rating, inverter limits, connection limits, degradation profile, warranty constraints, and prequalification status. |
| SOC limits | SOC operates between 0.2 MWh and 1.8 MWh for the 2 MWh battery. | Keeps headroom for reserve response and avoids using the full theoretical battery range. | Use manufacturer warranty limits, degradation-aware SOC windows, site operating policy, and service-specific reserve requirements. |
| Initial SOC | Initial SOC is 1.0 MWh. | Starts the representative day from the midpoint of the usable range. | Use rolling multi-day optimization with terminal SOC policy and forecasted next-day value. |
| Battery efficiency | Charge and discharge efficiency are both 95%. | Simple but realistic enough for comparing strategies. | Use asset-specific round-trip efficiency, temperature effects, degradation, and part-load efficiency curves. |
| Degradation cost | Degradation proxy is 3 EUR/MWh. | Adds a small cost to activation/discharge without requiring full battery-aging modelling. | Use cycle-depth-dependent degradation, throughput cost, warranty limits, replacement cost, and augmentation planning. |
| Representative day | The model uses one representative day: 2026-06-24. | The assignment asks for a representative day and rewards clear reasoning over production breadth. | Backtest across multiple years, seasons, weekdays/weekends, holidays, and market regimes. |
| Resolution | Part A optimization is hourly. The data pipeline also retains a 15-minute processed dataset. | The assignment allows 24 hourly steps and hourly results are easier to review. | Use 15-minute or finer resolution for settlement, activation, SOC restoration, and reserve-readiness modelling. |
| Site load | C&I load is a synthetic representative light-factory profile. | Avoids proprietary customer data while still creating a non-trivial behind-the-meter case. | Use measured customer meter data, operating calendars, production schedules, and site-specific load forecasts. |
| PV profile | PV is based on a public production shape and scaled to 800 kW. | Gives realistic PV overlap without requiring site-metered PV. | Use measured PV, irradiance, cloud cover, weather forecasts, inverter clipping, and export limits. |
| Market zones | Spot/FCR-N use SE3 and mFRR uses SN3 approximation. | Allows a coherent representative Swedish market case. | Use exact bidding zones, product zones, settlement areas, and TSO-specific mapping rules. |
| FCR-N treatment | FCR-N is modelled as capacity revenue requiring SOC headroom. | FCR-N is the main benchmark and does not require scheduled energy dispatch in this model. | Include actual bid acceptance, price uncertainty, activation energy effects, product rules, and performance penalties. |
| mFRR treatment | mFRR is modelled as up-capacity plus expected activation value and expected SOC impact. | Directly addresses the assignment's core uncertainty: activation can help or hurt. | Simulate physical activation events, restoration windows, bid acceptance, activation duration, imbalance exposure, and TSO settlement rules. |
| mFRR activation uncertainty | Part A uses low, base, and high activation assumptions. B3 sweeps activation probability from 0% to 75%. | Makes activation risk visible without building a full stochastic optimizer. | Estimate calibrated activation probabilities from multi-year activation history and evaluate P10/P50/P90 outcomes. |
| Local-first operation | Local dispatch and local reserve are applied before reserve-market allocation. | Matches the assignment principle that customer savings come first and market revenue follows. | Encode customer contract terms directly, including guaranteed savings, demand charges, tariff windows, and service-level risk limits. |
| Peak shaving | Peak shaving is represented with a configurable peak-import threshold and peak-tariff proxy. | Captures the customer-cost protection mechanism without needing a real tariff sheet. | Use actual customer tariff, contracted demand limit, measured peak charge rules, grid connection limit, and penalty structure. |
| Peak threshold | Threshold is derived from the representative-day net-load quantile. | Creates a consistent threshold for comparing no-battery, local-only, FCR-only, and stacked cases. | Use customer-specific contractual threshold, historical peak baseline, or optimized threshold from tariff economics. |
| Residual peak exposure | Residual exposure is reported when the battery cannot physically eliminate all peak load. | Avoids hiding infeasible peak reduction. | Use multi-day planning, explicit reserve margin, and tariff-specific risk limits. |
| Shared battery capacity | Local use, local reserve, FCR-N, and mFRR share the same MW limit. | Prevents double-counting a single physical battery. | Include all compatible/incompatible product combinations, product de-rates, connection limits, and real-time availability constraints. |
| FCR-D and aFRR | Excluded from the active optimizer and B3 grid. | Part A is explicitly focused on FCR-N versus mFRR. | Add FCR-D up/down, FCR-D pairing de-rate, aFRR, and product-specific rules after the FCR-N/mFRR core is validated. |
| B3 battery-count sweep | B3 scales 1, 2, and 3 identical 1 MW / 2 MWh units at the same site. | Tests whether more MW/MWh changes the mFRR break-even result. | Model each asset separately with site connection limits, separate prequalification, metering, and customer load context. |

---

## 2. Formula Glossary

### 2.1 Customer Cost

```text
customer_cost_eur =
    total_energy_cost_eur
  + peak_cost_eur
```

Where:

| Variable | Meaning |
|---|---|
| `customer_cost_eur` | Total customer-side cost for the scenario |
| `total_energy_cost_eur` | Cost of imported grid energy over the day |
| `peak_cost_eur` | Peak-import cost proxy for the day |

Peak cost is calculated as:

```text
peak_cost_eur =
    peak_import_kw
  * peak_tariff_eur_per_kw_day
```

Where:

| Variable | Meaning |
|---|---|
| `peak_import_kw` | Maximum grid import reached during the scenario |
| `peak_tariff_eur_per_kw_day` | Simplified daily peak-tariff proxy |

---

### 2.2 Local Savings

```text
local_savings_eur =
    no_battery_customer_cost_eur
  - scenario_customer_cost_eur
```

Where:

| Variable | Meaning |
|---|---|
| `local_savings_eur` | Customer bill saving created by the battery |
| `no_battery_customer_cost_eur` | Energy + peak cost without battery |
| `scenario_customer_cost_eur` | Energy + peak cost under the tested strategy |

Savings percentage is:

```text
local_savings_pct =
    local_savings_eur
    /
    no_battery_customer_cost_eur
```

The model checks this against the configured minimum savings floor.

---

### 2.3 Total Market Revenue

```text
total_market_revenue_eur =
    fcr_revenue_eur
  + mfrr_capacity_revenue_eur
  + expected_mfrr_activation_revenue_eur
```

Where:

| Variable | Meaning |
|---|---|
| `fcr_revenue_eur` | Revenue from committed FCR-N capacity |
| `mfrr_capacity_revenue_eur` | Revenue from committed mFRR up-capacity |
| `expected_mfrr_activation_revenue_eur` | Expected value from possible mFRR activation |

---

### 2.4 Total Value

```text
total_value_eur =
    local_savings_eur
  + total_market_revenue_eur
```

Where:

| Variable | Meaning |
|---|---|
| `total_value_eur` | Total economic value created by the battery strategy for the representative day |
| `local_savings_eur` | Customer-side savings versus no-battery operation |
| `total_market_revenue_eur` | FCR-N + mFRR market revenue |

Important: `total_value_eur` is not battery revenue only. It combines customer savings and market revenue.

---

### 2.5 FCR-N Revenue

```text
fcr_revenue_eur =
    fcr_commit_mw
  * fcrn_price_eur_mw_h
  * dt_hours
```

Where:

| Variable | Meaning |
|---|---|
| `fcr_commit_mw` | MW capacity committed to FCR-N |
| `fcrn_price_eur_mw_h` | FCR-N capacity price in EUR/MW/h |
| `dt_hours` | Duration of the model interval in hours |

---

### 2.6 mFRR Capacity Revenue

```text
mfrr_capacity_revenue_eur =
    mfrr_commit_mw
  * mfrr_capacity_price_eur_mw_h
  * dt_hours
```

Where:

| Variable | Meaning |
|---|---|
| `mfrr_commit_mw` | MW capacity committed to mFRR up |
| `mfrr_capacity_price_eur_mw_h` | mFRR capacity price in EUR/MW/h |
| `dt_hours` | Duration of the model interval in hours |

---

### 2.7 Expected mFRR Activation Value

```text
expected_mfrr_activation_revenue_eur =
    mfrr_commit_mw
  * activation_probability
  * activation_duration_hours
  * activation_margin_eur_per_mwh
```

Where:

| Variable | Meaning |
|---|---|
| `mfrr_commit_mw` | MW capacity committed to mFRR up |
| `activation_probability` | Probability or scenario assumption that mFRR is activated |
| `activation_duration_hours` | Assumed duration of activation |
| `activation_margin_eur_per_mwh` | Expected activation margin after replacement cost and degradation proxy |

The current model treats activation conservatively: expected activation can earn value but can also reduce SOC, which may reduce later local savings.

---

### 2.8 Available Market Capacity

```text
available_market_capacity_mw =
    battery_power_mw
  - local_physical_power_mw
  - local_reserve_mw
```

Where:

| Variable | Meaning |
|---|---|
| `available_market_capacity_mw` | Battery MW left for FCR-N and mFRR after local dispatch and reserve |
| `battery_power_mw` | Battery power rating |
| `local_physical_power_mw` | MW already used for local charge or discharge |
| `local_reserve_mw` | MW held back for near-term peak protection |

---

### 2.9 Shared Capacity Constraint

```text
local_physical_power_mw
+ local_reserve_mw
+ fcr_commit_mw
+ mfrr_commit_mw
<= battery_power_mw
```

Where:

| Variable | Meaning |
|---|---|
| `local_physical_power_mw` | Local battery charge/discharge MW |
| `local_reserve_mw` | MW reserved for customer peak protection |
| `fcr_commit_mw` | MW committed to FCR-N |
| `mfrr_commit_mw` | MW committed to mFRR |
| `battery_power_mw` | Total battery MW available |

This ensures the model does not double-count the same battery capacity.

---

### 2.10 B3 Operational Break-Even

```text
delta_vs_fcr_only_eur =
    stacked_total_value_eur
  - fcr_only_total_value_eur
```

Where:

| Variable | Meaning |
|---|---|
| `stacked_total_value_eur` | Total value from local savings + FCR-N + mFRR |
| `fcr_only_total_value_eur` | Total value from local savings + FCR-N only |
| `delta_vs_fcr_only_eur` | Incremental value of adding mFRR |

Decision rule:

```text
mFRR is worthwhile when:
delta_vs_fcr_only_eur > 0
```

Plain meaning:

- positive delta: stacked mFRR beats FCR-N-only
- zero delta: indifferent
- negative delta: FCR-N-only is better

---

## 3. Peak-Shaving Treatment

Peak shaving is handled as a threshold-based local dispatch and protection rule.

The current model:

1. Computes a peak threshold from representative-day net load.
2. Reserves local battery capacity for near-term peak exposure.
3. Discharges the battery when net load exceeds the threshold.
4. Allows low-price grid charging only when it does not create a new peak.
5. Reports residual peak exposure when the battery cannot physically remove the full peak.
6. Flags a peak-import violation only if grid import exceeds the threshold while battery discharge capacity was still available.

This means peak shaving is included, but it is not a full customer-tariff optimization model. A production version should replace the proxy threshold and tariff with customer-specific contract terms, demand-charge rules, grid connection limits, and measured load history.

---

## 4. What This File Does Not Claim

This file does not claim that the representative-day result is a production forecast or a full commercial case.

The current model is designed to answer the assignment question:

> When does adding mFRR improve value over FCR-N only, and when does it reduce value by consuming local flexibility?

A production version would require multi-season backtesting, measured customer data, probabilistic forecasts, and real tariff/settlement rules.
