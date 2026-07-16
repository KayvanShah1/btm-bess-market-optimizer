# B3 Break-Even Analysis

## Scope

B3 is treated as an operational break-even analysis first:

> When is stacked FCR-N + mFRR better than FCR-N-only?

It is not a full battery investment-payback model. The battery is assumed to already exist and be prequalified, consistent with the modelling scope.

## Method

The B3 script reuses the core dispatch engine and varies three assumptions:

| Variable | Grid |
|---|---:|
| mFRR activation probability | 0.00 to 0.75, in 0.05 steps |
| mFRR capacity price multiplier | 0.50x to 2.00x |
| Battery count | 1, 2, and 3 identical 1 MW / 2 MWh units |

The battery-count sweep is an aggregate size test at the same site. It scales available battery MW, MWh, initial SOC, and SOC limits proportionally. It does not model separate meters, separate prequalification, or separate customer load profiles.

The consolidated assumptions and formulas are listed in `docs/ASSUMPTIONS_AND_FORMULAS.md`.

For each grid cell, the model:

1. Runs the FCR-N-only benchmark.
2. Scales the battery config for the selected battery count.
3. Multiplies the mFRR capacity price by the selected multiplier.
4. Runs the stacked FCR-N + mFRR scheduler with the selected activation probability.
5. Calculates the daily value delta versus FCR-N-only for the same battery size.

The operational decision rule is:

> mFRR is worthwhile when the stacked FCR-N + mFRR case creates more total daily value than the FCR-N-only case.

The output file is `data/output/b3_mfrr_break_even_sensitivity_se3_20260624.csv`.

## Results

The expanded B3 grid contains 336 cells and compares each stacked case against the same-size FCR-N-only benchmark.

| Result | Value |
|---|---:|
| Grid cells | 336 |
| Best stacked delta | +34.77 EUR/day |
| Worst stacked delta | -373.51 EUR/day |
| Maximum activation probability that clears at 1.00x capacity price | 0% |

Result by battery count:

| Battery count | Aggregate size | Best delta vs FCR-N-only | Best activation probability | Best capacity multiplier | Worst delta |
|---:|---:|---:|---:|---:|---:|
| 1 | 1 MW / 2 MWh | +34.77 EUR/day | 0% | 2.00x | -121.17 EUR/day |
| 2 | 2 MW / 4 MWh | +5.91 EUR/day | 0% | 2.00x | -233.92 EUR/day |
| 3 | 3 MW / 6 MWh | +4.88 EUR/day | 0% | 2.00x | -373.51 EUR/day |

Break-even thresholds in the grid:

| Battery count | mFRR activation probability | Minimum mFRR capacity price multiplier that beats FCR-N-only |
|---:|---:|---:|
| 1 | 0% | 0.50x |
| 1 | 5% | 2.00x |
| 2 | 0% | 0.50x |
| 3 | 0% | 0.50x |
| all tested sizes | 10% to 75% | No positive cell in this grid |

The best case is one 1 MW / 2 MWh battery, zero activation, and a 2.00x mFRR capacity price multiplier, giving a daily incremental value of 34.77 EUR. The only positive nonzero activation case is the 1-battery case at 5% activation and a 2.00x capacity price multiplier, giving 2.12 EUR/day.

## Interpretation

The result is not "mFRR always wins." It is:

> mFRR is attractive only when activation exposure is very low, or when capacity compensation is high enough to cover the flexibility it consumes.

At higher activation probabilities, increasing the mFRR capacity price can still produce worse total value if the scheduler commits more mFRR capacity and expected activation drains SOC that would otherwise support local savings. That is why the surface is not perfectly monotonic.

The battery-count sweep also shows that larger batteries do not automatically make mFRR more attractive. Larger aggregate battery capacity raises both the stacked case and the FCR-N-only benchmark. On this representative day, extra capacity improves the FCR-N-only alternative enough that the incremental mFRR delta is smaller for the 2- and 3-battery cases.

## Commercial Note

This B3 analysis does not estimate full battery payback or hardware investment recovery. The battery is assumed to already exist. The analysis focuses on operational break-even: whether stacked FCR-N + mFRR creates more value than FCR-N-only under different activation, price, and battery-size assumptions.

A production investment case would require multi-season annual value estimates, degradation modelling, actual enablement costs, operating costs, battery life, warranty constraints, and customer-specific tariff data.

## How to Reproduce

From the repository root:

```powershell
uv run --package bess-optimizer bess-run-sensitivity
```

Optional battery-count assumptions can be changed from the CLI:

```powershell
uv run --package bess-optimizer bess-run-sensitivity `
  --battery-counts 1,2,3
```
