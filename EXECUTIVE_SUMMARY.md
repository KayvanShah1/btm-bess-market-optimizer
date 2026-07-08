# Executive Summary

## Market Context

Battery assets create value in two layers.

The first layer is local customer value: reducing grid import, shaving peaks, improving PV self-consumption, and lowering the customer's power bill. This is the value stream that protects the customer relationship, so it must come first.

The second layer is grid-service revenue. FCR-N is the stable benchmark service in this model. It uses available battery capacity for frequency containment revenue while still preserving the local savings case. mFRR is the new opportunity, but it is harder to schedule because activation is uncertain. If mFRR is activated, it can consume battery SOC that may be needed later for peak shaving or high-price discharge.

The operating question is not whether mFRR can earn revenue. It is whether that revenue survives the SOC and local-value trade-off:

> When should the battery use remaining flexibility for mFRR,
> and when is FCR-N-only the safer and more valuable choice?

## What Was Modelled

The model evaluates a representative Swedish C&I site with co-located PV and a 1 MW / 2 MWh behind-the-meter battery.

For each hour, the scheduler:

1. serves local customer value first
2. reserves capacity for near-term peak protection
3. allocates remaining feasible capacity between FCR-N and mFRR
4. checks SOC, power, shared-capacity, reserve-readiness, and peak-protection constraints
5. compares stacked FCR-N + mFRR against an FCR-N-only benchmark

The representative day uses SE3 spot prices, FCR-N capacity prices, and SN3 mFRR capacity and activation signals for 2026-06-24.

## Scenarios Tested

| Scenario | What it represents |
|---|---|
| No battery | Customer-cost baseline |
| Local-only battery | Customer savings without reserve-market participation |
| FCR-N only | Current-style reserve benchmark after local savings |
| Stacked: low mFRR activation | mFRR capacity is available with no expected activation drain |
| Stacked: base mFRR activation | mFRR activation is expected and can reduce SOC |
| Stacked: high mFRR activation | Stress case where mFRR activation risk is higher |

## Main Finding

mFRR is conditionally attractive, not a default add-on.

> Use mFRR only when the battery has enough operational margin for activation risk; otherwise, FCR-N-only is the cleaner choice.

| Scenario | Total value EUR | Local savings % | Delta vs FCR-N only EUR |
|---|---:|---:|---:|
| No battery | 0.00 | 0.0% | -512.46 |
| Local-only battery | 319.15 | 15.5% | -193.31 |
| FCR-N only | 512.46 | 15.5% | 0.00 |
| Stacked: low mFRR activation | 528.83 | 15.5% | +16.38 |
| Stacked: base mFRR activation | 483.29 | 13.5% | -29.16 |
| Stacked: high mFRR activation | 463.43 | 12.1% | -49.03 |

The FCR-N-only case is the stable benchmark. It preserves the local savings case and adds reserve capacity revenue from unused battery flexibility.

Stacking mFRR improves value only when activation exposure is low. Under base and high activation assumptions, expected mFRR activation consumes SOC, which reduces later local savings. In those cases, the extra mFRR revenue is not enough to compensate for the flexibility it consumes.

All active scenarios clear the 5% minimum local savings floor, and the constraint audit reports zero violations.

## B3 Sensitivity Result

The B3 extension asks when mFRR remains worthwhile under different activation, price, and battery-size assumptions.

The operational rule is:

> mFRR is worthwhile when the stacked FCR-N + mFRR case creates more total daily value than the FCR-N-only case.

The sensitivity grid varies:

- mFRR activation probability
- mFRR capacity price multiplier
- aggregate battery count

The result is selective rather than broad. Most attractive cases occur when activation is 0%. At higher activation probabilities, mFRR becomes difficult to justify unless capacity compensation is much stronger.

| Battery count | Aggregate size | Best delta vs FCR-N only |
|---:|---:|---:|
| 1 | 1 MW / 2 MWh | +34.77 EUR/day |
| 2 | 2 MW / 4 MWh | +5.91 EUR/day |
| 3 | 3 MW / 6 MWh | +4.88 EUR/day |

A larger battery does not by itself solve the mFRR case. It also strengthens the FCR-N-only benchmark, so mFRR still needs enough compensation to beat the next-best use of the same capacity.

## Commercial Interpretation

The operating policy should not be to stack whenever mFRR is available. Recommended operating rule:

> Accept mFRR only when expected capacity and activation value clearly exceed the value of the local flexibility it consumes.

This is a screening result from one representative day. It should be used to define when mFRR is operationally attractive, not to claim long-run financial performance.

## Main Risks

- mFRR activation uncertainty is the key risk driver.
- A representative day cannot prove multi-season profitability.
- Synthetic C&I load is useful for model clarity, but measured customer profiles are needed before production use.
- The current model is hourly; 15-minute settlement and activation dynamics need finer production modelling.
- Residual peak exposure is reported rather than hidden. The model prevents market commitments from creating additional peak exposure when battery capacity remains available, but a 1 MW / 2 MWh battery cannot physically eliminate every baseline peak under all SOC and reserve constraints.

## Recommended Next Step

The next step is a multi-day 15-minute backtest using measured site load, weather-aware PV, historical FCR-N/mFRR prices, and activation data. That would allow us to estimate activation risk, seasonal value, and operational thresholds before using mFRR as a live bidding strategy.
