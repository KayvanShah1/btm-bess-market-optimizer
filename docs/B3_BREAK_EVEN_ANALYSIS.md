# B3 Break-Even Analysis

## Scope

B3 is treated as an operational break-even analysis first:

```text
When is stacked FCR-N + mFRR better than FCR-N-only?
```

It is not a full battery investment-payback model. The battery is assumed to already exist and be prequalified, consistent with the assignment framing. A simple commercial payback overlay is included only for incremental mFRR enablement and operating costs.

## Method

The B3 script reuses the Part A dispatch engine and varies two assumptions:

| Variable | Grid |
|---|---:|
| mFRR activation probability | 0.00 to 0.75, in 0.05 steps |
| mFRR capacity price multiplier | 0.50x to 2.00x |

For each grid cell, the model:

1. Runs the FCR-N-only benchmark.
2. Multiplies the mFRR capacity price by the selected multiplier.
3. Runs the stacked FCR-N + mFRR scheduler with the selected activation probability.
4. Calculates the daily value delta versus FCR-N-only.

The operational decision rule is:

```text
mFRR is worthwhile when:

stacked_total_value_eur - fcr_only_total_value_eur > 0
```

The output file is:

```text
data/output/b3_mfrr_break_even_sensitivity_se3_20260624.csv
```

## Results

The first B3 grid contains 112 cells. Eight cells are operationally positive versus the FCR-N-only benchmark.

| Result | Value |
|---|---:|
| FCR-N-only benchmark value | 512.46 EUR/day |
| Best stacked delta | +34.77 EUR/day |
| Worst stacked delta | -121.17 EUR/day |
| Positive operational cells | 8 of 112 |
| Maximum activation probability that clears at 1.00x capacity price | 0% |

Break-even thresholds in the first grid:

| mFRR activation probability | Minimum mFRR capacity price multiplier that beats FCR-N-only |
|---:|---:|
| 0% | 0.50x |
| 5% | 2.00x |
| 10% to 75% | No positive cell in this grid |

The best case is zero activation with a 2.00x mFRR capacity price multiplier, giving a daily incremental value of 34.77 EUR. The only positive nonzero activation case is 5% activation at a 2.00x capacity price multiplier, giving 2.12 EUR/day.

## Interpretation

The result is not "mFRR always wins." It is:

```text
mFRR is attractive only when activation exposure is very low
or when capacity compensation is high enough to cover the flexibility it consumes.
```

At higher activation probabilities, increasing the mFRR capacity price can still produce worse total value if the scheduler commits more mFRR capacity and expected activation drains SOC that would otherwise support local savings. That is why the surface is not perfectly monotonic.

## Commercial Overlay

The CSV also includes a simple payback overlay for incremental mFRR enablement costs:

```text
annual_net_incremental_value =
    annualized_delta_eur
  - annual_mfrr_operating_cost
  - risk_buffer

payback_years =
    upfront_mfrr_enablement_cost
    /
    annual_net_incremental_value
```

Default assumptions used by the script:

| Assumption | Value |
|---|---:|
| Upfront mFRR enablement cost | 25,000 EUR |
| Annual operating cost | 5,000 EUR/year |
| Risk buffer | 2,000 EUR/year |
| Operating days | 300/year |
| Confidence factor | 0.80 |
| Target payback | 5.0 years |

Under these defaults, the strongest cell has a payback of 18.6 years. This is not a formula bug; it is caused by the fixed cost assumptions being large relative to the incremental daily mFRR value in this one-battery representative-day run:

```text
effective operating days = 300 * 0.80 = 240 days
best daily delta = 34.77 EUR/day
annualized gross delta = 34.77 * 240 = 8,345 EUR/year
annual operating cost + risk buffer = 7,000 EUR/year
annual net incremental value = 1,345 EUR/year
payback = 25,000 / 1,345 = 18.6 years
```

The default cost burden from annual operating cost and risk buffer alone is:

```text
7,000 / 240 = 29.17 EUR/day
```

For a 5-year payback under the same assumptions, the required daily delta is:

```text
(25,000 / 5 + 7,000) / 240 = 50.00 EUR/day
```

The best current grid cell is therefore about 15.23 EUR/day short of a 5-year payback. This is a commercial overlay, not the core B3 operational result. The main B3 conclusion should be read from `delta_vs_fcr_only_eur` and `is_mfrr_worthwhile`.

## How to Reproduce

From the repository root:

```powershell
uv run --package bess-optimizer python scripts/run_b3_sensitivity.py
```

Optional cost assumptions can be changed from the CLI:

```powershell
uv run --package bess-optimizer python scripts/run_b3_sensitivity.py `
  --upfront-enable-cost-eur 25000 `
  --annual-operating-cost-eur 5000 `
  --risk-buffer-eur 2000 `
  --operating-days 300 `
  --confidence-factor 0.80 `
  --target-payback-years 5.0
```
