# Executive Summary

## What Was Tested

This project evaluates whether a single behind-the-meter C&I battery should continue using remaining flexibility for FCR-N only, or whether it should also stack mFRR capacity on top of local customer savings and FCR-N.

The model uses a 1 MW / 2 MWh battery, a representative Swedish light-factory load profile with co-located PV, SE3 spot prices, FCR-N capacity prices, and SN3 mFRR capacity and activation signals for one representative day: 2026-06-24.

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

## What This Means for Truxel

The operating policy should not be "always stack mFRR when available." A better commercial rule is:

```text
Accept mFRR only when expected capacity and activation value clearly exceed the value of the local flexibility it consumes.
```

This matters because the customer relationship is anchored on local savings and peak protection. Ancillary-service revenue is the larger opportunity, but it should not weaken the customer's bill-savings promise.

## Main Risks

- mFRR activation uncertainty is the key risk driver.
- A representative day cannot prove multi-season profitability.
- Synthetic C&I load is useful for assessment clarity, but measured customer profiles would be needed before production use.
- The current model is hourly; 15-minute settlement and activation dynamics would need a finer production model.
- Residual peak exposure is reported rather than hidden. The model prevents ancillary-service commitments from creating additional peak exposure when battery capacity remains available, but a 1 MW / 2 MWh battery cannot physically eliminate every baseline peak under all SOC and reserve constraints.

## Recommended Next Step

Before production deployment, extend the model to a multi-day 15-minute backtest with measured load, richer mFRR activation probability estimates, and break-even analysis across battery size, activation rate, and price spread.
