# Executive Summary

## What Was Tested

This project evaluates whether a single behind-the-meter C&I battery should continue using remaining flexibility for FCR-N only, or whether it should also stack mFRR capacity on top of local customer savings and FCR-N.

The model uses a 1 MW / 2 MWh battery, a representative Swedish light-factory load profile with co-located PV, SE3 spot prices, FCR-N capacity prices, and SN3 mFRR capacity and activation signals for one representative day: 2026-06-24.

The B3 sensitivity also tests aggregate battery count as a simple size sweep: 1, 2, and 3 identical 1 MW / 2 MWh units at the same site. This changes available MW and SOC headroom, but not the customer load profile.

## Commercial Finding

mFRR is conditionally attractive, not automatically attractive.

The FCR-N-only case is the most stable benchmark. It preserves the customer-side savings case and adds reserve capacity revenue from unused battery flexibility. Adding mFRR improves total value only in the low-activation case. Under base and high activation assumptions, expected mFRR activation consumes battery SOC, leaving less energy available for later peak shaving and high-price discharge.

## Current Result

| Scenario | Total value EUR | Local savings % | Delta vs FCR-N only EUR |
|---|---:|---:|---:|
| No battery | 0.00 | 0.0% | -512.46 |
| Local-only battery | 319.15 | 15.5% | -193.31 |
| FCR-N only | 512.46 | 15.5% | 0.00 |
| Stacked: low mFRR activation | 528.83 | 15.5% | 16.38 |
| Stacked: base mFRR activation | 483.29 | 13.5% | -29.16 |
| Stacked: high mFRR activation | 463.43 | 12.1% | -49.03 |

All active scenarios clear the 5% minimum local savings floor and the constraint audit reports zero violations.

## B3 Break-Even and Payback

B3 separates operational break-even from investment payback.

Operationally, mFRR is worthwhile when:

```text
stacked_total_value_eur - fcr_only_total_value_eur > 0
```

The sensitivity grid varies mFRR activation probability, mFRR capacity price, and battery count. It contains 336 cells. Only 22 cells beat the FCR-N-only benchmark, and all positive cells occur at 0% activation except one 1-battery case at 5% activation with a 2.00x mFRR capacity price multiplier.

| Battery count | Aggregate size | Positive cells | Best delta vs FCR-N only EUR/day |
|---:|---:|---:|---:|
| 1 | 1 MW / 2 MWh | 8 of 112 | 34.77 |
| 2 | 2 MW / 4 MWh | 7 of 112 | 5.91 |
| 3 | 3 MW / 6 MWh | 7 of 112 | 4.88 |

The larger battery cases do not automatically improve the mFRR decision because the FCR-N-only benchmark also becomes more valuable. In this representative day, extra battery capacity helps local/FCR value more than it helps stacked mFRR under activation risk.

The commercial payback overlay is intentionally narrower than full battery CAPEX recovery. It asks how long incremental mFRR value would take to recover mFRR enablement and operating cost. With the default assumptions, the best grid cell has an 18.6-year payback because the annual operating cost plus risk buffer consumes most of the annualized incremental value.

## What This Means?

The operating policy should not be "always stack mFRR when available." A better commercial rule is:

> Accept mFRR only when expected capacity and activation value clearly exceed the value of the local flexibility it consumes.

This matters because the customer relationship is anchored on local savings and peak protection. Ancillary-service revenue is the larger opportunity, but it should not weaken the customer's bill-savings promise.

## Main Risks

- mFRR activation uncertainty is the key risk driver.
- A representative day cannot prove multi-season profitability.
- Synthetic C&I load is useful for assessment clarity, but measured customer profiles would be needed before production use.
- The current model is hourly; 15-minute settlement and activation dynamics would need a finer production model.
- Residual peak exposure is reported rather than hidden. The model prevents ancillary-service commitments from creating additional peak exposure when battery capacity remains available, but a 1 MW / 2 MWh battery cannot physically eliminate every baseline peak under all SOC and reserve constraints.

## Recommended Next Step

Before production deployment, extend the model to a multi-day 15-minute backtest with measured load, richer mFRR activation probability estimates, and seasonally validated battery-size sensitivity. The representative-day B3 surface is useful for decision framing, but it should not be treated as a long-run merchant revenue forecast.
