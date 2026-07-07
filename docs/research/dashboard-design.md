Yes, use public data. Since the data is fairly accessible, it is worth using **some real public market data** instead of going fully synthetic.

But keep the scope controlled: **real market data + synthetic representative site data** is the best 2-day strategy.

## Recommended final data strategy

Use this:

| Input                              | Source                                    | Use in model? |        Priority |
| ---------------------------------- | ----------------------------------------- | ------------: | --------------: |
| **mFRR capacity price**            | Svenska Kraftnät Mimer mFRR CM            |           Yes |       Must-have |
| **mFRR activation / energy price** | Svenska Kraftnät Mimer mFRR EAM           | Yes, if quick | Strong optional |
| **FCR-N price**                    | Svenska Kraftnät Mimer FCR                | Yes, if quick |        Optional |
| **Spot price**                     | Nord Pool day-ahead                       |      Optional |        Optional |
| **C&I consumption profile**        | Synthetic / scaled public proxy           |           Yes |       Must-have |
| **PV profile**                     | Synthetic / normalized public solar shape |           Yes |       Must-have |
| **Battery specs**                  | Assignment: 1 MW / 2 MWh                  |           Yes |       Must-have |

The assignment allows synthetic data and asks for a representative day, but it also names Nord Pool and Svenska Kraftnät as acceptable public sources. 

## What public data is actually easiest

### 1. Svenska Kraftnät mFRR capacity market — use this

This is the most useful real dataset. Mimer’s **mFRR capacity market D-1** page gives marginal capacity prices in **EUR/MW** for mFRR Up and mFRR Down by Swedish bidding area, and it has **CSV / Excel export** options. It also states data is available from **2023-10-18**. ([Mimer][1])

Use one bidding area, probably:

```text id="hu7koh"
SE3
```

Use one representative day:

```text id="5gnhnt"
24 hourly rows
```

Use one column:

```text id="ctq9z1"
mfrr_capacity_price_eur_mw_h
```

This gives your assignment real market grounding without much complexity.

### 2. Svenska Kraftnät mFRR energy activation market — use if quick

Mimer’s **mFRR energy activation market** page gives mFRR Up/Down activation volumes and marginal prices in **EUR/MWh** by bidding area. It also has CSV / Excel export. ([Mimer][2])

This can help you estimate activation uncertainty:

```text id="qk2lw4"
activation_flag = 1 if activation volume > 0 else 0
activation_probability = historical activation_flag.mean()
```

But this data appears at **15-minute granularity**, so use it only if it does not slow you down.

### 3. Nord Pool day-ahead prices — useful but not essential

Nord Pool provides power market data, including day-ahead and intraday data, with API/FTP-style delivery and a data portal. ([Nord Pool][3])

Use it only if you can export quickly. Spot price is helpful for local arbitrage, but the core assignment is **FCR-N vs mFRR commitment**, not spot-trading optimization.

## Should you use eSett?

Maybe, but not first.

eSett can be useful for public Nordic consumption/production-style data, but for this assignment it is less directly valuable because you need a **behind-the-meter C&I customer load**, not national or bidding-area-level consumption.

So I would not make eSett central. Use it only as a **shape proxy**:

```text id="c93hsz"
public_area_consumption_normalized = area_consumption / area_consumption.max()
site_load_kw = public_area_consumption_normalized * chosen_site_peak_kw
```

Then clearly say:

```text id="5i0v2h"
Public system-level consumption was used only as a normalized shape proxy, then scaled to a representative C&I site. It is not claimed to be actual customer-level load.
```

## Streamlit dashboard: yes, but keep it simple

A Streamlit dashboard would work well **if it does not replace the write-up**. The assignment asks for runnable code, a technical write-up, a one-page executive summary, and AI disclosure. 

Use Streamlit as the demo layer:

```text id="89d8po"
streamlit_app.py
```

Not as the only deliverable.

## Best dashboard layout

Create 4 tabs:

### Tab 1 — Data

Show:

```text id="am0xsx"
load_kw
pv_kw
fcrn_price_eur_mw_h
mfrr_capacity_price_eur_mw_h
mfrr_activation_probability
```

Controls:

```text id="t7ho8g"
bidding area: SE1 / SE2 / SE3 / SE4
mFRR direction: Up / Down
representative day
battery size
minimum savings %
```

### Tab 2 — Dispatch Schedule

Charts:

```text id="nyox7w"
hourly allocation: local reserve / FCR-N / mFRR
SOC over time
grid import before vs after battery
```

### Tab 3 — Value Comparison

Show:

```text id="xtejlq"
No battery
Local-only
FCR-only
FCR + mFRR
```

Metrics:

```text id="c2mxk0"
local savings
FCR revenue
mFRR capacity revenue
expected mFRR activation revenue
total value
savings %
constraint violations
```

### Tab 4 — Sensitivity

Show heatmap:

```text id="x769z6"
mFRR activation probability × mFRR price premium
```

Output:

```text id="tpd6na"
Where does mFRR beat FCR-only?
```

This will make the submission look much more practical and commercial.

## What I would build now

Do this version:

```text id="q4ign1"
1. Use real Svenska Kraftnät mFRR CM price data.
2. Use real mFRR EAM activation data only if it is quick.
3. Keep C&I load synthetic.
4. Keep PV synthetic or use a normalized public shape.
5. Keep FCR-N price synthetic if Mimer FCR extraction takes time.
6. Build the optimizer.
7. Wrap results in a simple Streamlit dashboard.
8. Still submit README + write-up + executive summary.
```

## Recommended repo structure

```text id="jwh8wk"
bess-market-optimizer/
├── README.md
├── requirements.txt
├── config.yaml
├── streamlit_app.py
├── data/
│   ├── raw/
│   └── processed/
├── notebooks/
│   └── analysis.ipynb
├── src/
│   ├── data_loader.py
│   ├── synthetic_site.py
│   ├── optimizer.py
│   ├── baselines.py
│   ├── metrics.py
│   └── plots.py
├── outputs/
│   ├── results_summary.csv
│   └── dispatch_schedule.csv
├── figures/
├── EXECUTIVE_SUMMARY.md
└── REPORT.md
```

## Final call

Use public data, but not everywhere.

The best version is:

```text id="h3vrgg"
Real market data from Svenska Kraftnät
+
synthetic representative C&I site
+
simple optimizer
+
Streamlit dashboard
+
clear report
```

[1]: https://mimer.svk.se/Start/NavigateBySortOrder?itemSortOrder=5&parentSortOrder=2 "Mimer | Svenska kraftnät"
[2]: https://mimer.svk.se/Start/NavigateBySortOrder?itemSortOrder=7&parentSortOrder=2 "Mimer | Svenska kraftnät"
[3]: https://www.nordpoolgroup.com/en/services/power-market-data-services/ "Power Data Services | Nord Pool"
