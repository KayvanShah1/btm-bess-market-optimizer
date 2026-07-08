# Technical Write-Up

## 1. Problem Framing

The assignment asks how a single behind-the-meter battery should allocate capacity between local customer value, FCR-N, and mFRR for a representative day.

The difficult part is not simply adding another revenue stream. FCR-N and mFRR compete for the same MW capacity and SOC headroom that local peak shaving and energy-cost savings also need. mFRR activation is uncertain, and if activation consumes battery energy, later customer-side savings can fall.

The model therefore answers:

```text
When does adding mFRR improve value over FCR-N only,
and when does it reduce value by consuming local flexibility?
```

## 2. Model Scope

This is an intentionally scoped Part A implementation:

| Item | Current scope |
|---|---|
| Asset | One 1 MW / 2 MWh behind-the-meter battery |
| Site | Representative Swedish C&I light-factory profile with PV |
| Market area | SE3 spot / FCR-N, SN3 mFRR signal alignment |
| Resolution | Hourly optimization for Part A |
| Horizon | One representative day, 2026-06-24 |
| Main comparison | FCR-N-only vs stacked FCR-N + mFRR |
| Uncertainty | Low, base, and high mFRR activation assumptions |

The model is not claimed to be a production-grade stochastic optimizer. It is a transparent representative-day scheduler designed to expose the local-savings versus reserve-market trade-off.

## 3. Decision Structure

For each hour, the model builds the schedule in two layers:

1. Local site dispatch is calculated first.
2. Remaining feasible capacity is allocated to FCR-N and mFRR using candidate capacity splits.

```mermaid
flowchart TD
    A[Representative hourly input] --> B[PV serves factory load]
    B --> C[Local battery dispatch]
    C --> D[Hold local reserve for near-term peaks]
    D --> E[Calculate remaining market capacity]
    E --> F[Enumerate FCR-N and mFRR candidates]
    F --> G[Apply SOC, power, headroom, readiness checks]
    G --> H[Score feasible candidates]
    H --> I[Select best hourly allocation]
    I --> J[Write dispatch, summary, and audit outputs]
```

The main hourly decision quantities are:

| Symbol | Meaning |
|---|---|
| `soc_h` | Battery state of charge at hour `h` |
| `local_use_h` | Physical charge or discharge used for local value |
| `local_reserve_h` | Capacity held back for near-term local peak exposure |
| `fcr_h` | FCR-N committed capacity |
| `mfrr_h` | mFRR committed up-capacity |

The current scheduler chooses `fcr_h` and `mfrr_h` after local dispatch, rather than solving all variables simultaneously in a MILP. That choice is deliberate: the problem size is small, the candidate grid is easy to audit, and the assignment rewards clear reasoning more than solver complexity.

## 4. Objective

The scenario-level value is:

```text
Total value =
    local savings versus no-battery baseline
  + FCR-N capacity revenue
  + mFRR capacity revenue
  + expected mFRR activation value
```

For candidate reserve allocation in each hour:

```text
candidate value =
    FCR-N MW * FCR-N price * duration
  + mFRR MW * mFRR capacity price * duration
  + expected mFRR activation value
```

Expected mFRR activation value is calculated from activation price, spot-price replacement cost, discharge efficiency, degradation cost, committed mFRR MW, and activation probability.

## 5. Constraints

The model maps the assignment constraints as follows:

| Assignment rule | Implementation |
|---|---|
| Savings-first floor | Scenario-level local savings must exceed the configured 5% minimum |
| Peak-power protection | Ancillary commitments must not create additional peak exposure when battery discharge capacity remains available |
| Battery physics | SOC, energy capacity, power limit, and efficiency are enforced |
| Shared capacity | Local physical use + local reserve + FCR-N + mFRR cannot exceed 1 MW |
| FCR-N headroom | FCR-N capacity requires symmetric SOC buffer |
| mFRR readiness | mFRR up commitment requires enough current and previous-hour SOC to support activation |
| Local priority | Local dispatch and local reserve are computed before market allocation |

The key shared-capacity constraint is:

```text
max(charge_mw, discharge_mw)
+ local_reserve_mw
+ fcr_commit_mw
+ mfrr_commit_mw
<= battery_power_mw
```

Residual peak exposure is reported separately. It is not hidden or treated as a zero target. The model enforces that ancillary-service commitments do not create additional peak exposure where the battery still has available discharge capacity. A 1 MW / 2 MWh battery may still be physically unable to eliminate all baseline peak exposure after SOC, reserve, and power constraints are respected.

## 6. Local Dispatch

Local operation follows a savings-first hierarchy:

```mermaid
flowchart LR
    A[PV generation] --> B{Factory load exists?}
    B -->|Yes| C[Self-consume PV]
    B -->|Surplus| D[Charge battery if SOC headroom exists]
    C --> E{Net load above peak threshold?}
    E -->|Yes| F[Discharge for peak shaving if feasible]
    E -->|No| G{Spot price high?}
    G -->|Yes| H[Discharge to reduce expensive imports]
    G -->|No| I{Spot price low?}
    I -->|Yes| J[Charge safely if no new peak is created]
    I -->|No| K[Hold SOC and reserve]
```

This creates the physical battery path. Market participation is then layered only on remaining feasible capacity.

## 7. FCR-N and mFRR Allocation

After local dispatch, available market capacity is calculated as:

```text
available market capacity =
    battery power
  - local physical use
  - local reserve
```

The scheduler enumerates FCR-N and mFRR capacity splits in 0.25 MW steps. Each candidate is checked before it can be selected.

```mermaid
flowchart TD
    A[Available market MW] --> B[Round down to 0.25 MW step]
    B --> C[Generate FCR-N / mFRR split candidates]
    C --> D{Candidate feasible?}
    D -->|No| E[Reject]
    D -->|Yes| F[Score capacity and expected activation value]
    F --> G{Best value so far?}
    G -->|Yes| H[Store candidate]
    G -->|No| I[Continue]
    H --> I
    I --> J[Select best feasible split]
```

## 8. mFRR Activation Uncertainty

mFRR activation is represented through three scenarios:

| Scenario | Activation assumption | Purpose |
|---|---:|---|
| Stacked low activation | 0.0 | Best-case stacked sensitivity |
| Stacked base activation | Mean activation probability from the processed day | Representative sensitivity |
| Stacked high activation | Twice base activation, capped at 0.75 | Stress sensitivity |

The conservative modelling assumption is that expected mFRR activation has two effects:

1. It can earn expected activation value.
2. It can reduce SOC in base and high activation cases.

That second effect is important. It allows mFRR to reduce later local savings if battery energy is consumed before a peak-shaving or high-price-discharge opportunity.

This is not a full physical replay of every activation event. It is a representative-day sensitivity that makes activation risk visible.

## 9. Scenarios

The model compares six cases:

```mermaid
flowchart TD
    A[No battery baseline] --> B[Local-only battery]
    B --> C[FCR-N only]
    C --> D[Stacked: low mFRR activation]
    C --> E[Stacked: base mFRR activation]
    C --> F[Stacked: high mFRR activation]
```

| Scenario | Role |
|---|---|
| No battery | Reference customer-cost baseline |
| Local-only battery | Local savings benchmark |
| FCR-N only | Main ancillary-service benchmark |
| Stacked low activation | Stacked case with no expected activation drain |
| Stacked base activation | Stacked case with representative activation exposure |
| Stacked high activation | Stacked stress case |

## 10. Results

| Scenario | Total value EUR | Local savings EUR | Local savings % | Delta vs FCR-N only EUR | Minimum SOC MWh | Violations |
|---|---:|---:|---:|---:|---:|---:|
| No battery | 0.00 | 0.00 | 0.0% | -512.46 | 1.00 | 0 |
| Local-only battery | 319.15 | 319.15 | 15.5% | -193.31 | 0.20 | 0 |
| FCR-N only | 512.46 | 319.15 | 15.5% | 0.00 | 0.20 | 0 |
| Stacked: low mFRR activation | 528.83 | 319.15 | 15.5% | 16.38 | 0.20 | 0 |
| Stacked: base mFRR activation | 483.29 | 277.00 | 13.5% | -29.16 | 0.20 | 0 |
| Stacked: high mFRR activation | 463.43 | 249.19 | 12.1% | -49.03 | 0.20 | 0 |

```mermaid
xychart-beta
    title "Delta vs FCR-N only"
    x-axis ["No battery", "Local only", "FCR-N only", "Stack low", "Stack base", "Stack high"]
    y-axis "EUR" -550 --> 50
    bar [-512.46, -193.31, 0.00, 16.38, -29.16, -49.03]
```

## 11. Interpretation

The local-only battery creates customer-side savings of 319.15 EUR, or 15.5% versus the no-battery baseline. This establishes that the battery has a real local value case before ancillary services are added.

The FCR-N-only case keeps the same local savings and adds 193.31 EUR of FCR-N capacity revenue. This makes it the main benchmark.

The stacked low-activation case improves total value by 16.38 EUR versus FCR-N-only because mFRR capacity can be added without expected SOC depletion.

The base and high activation cases underperform FCR-N-only by 29.16 EUR and 49.03 EUR. In these cases, expected mFRR activation consumes SOC, reducing later local savings. The result is economically useful: mFRR participation should be conditional on activation exposure and opportunity cost, not simply enabled whenever prequalification exists.

## 12. Constraint Audit

All six scenarios have 24 feasible rows and zero reported violations.

The maximum total reserved or used capacity is 1.0 MW for active battery scenarios, which confirms that local use, local reserve, FCR-N, and mFRR are not double-counted.

Residual peak exposure remains in the results because the battery is capacity and energy constrained. This is expected and documented. The model's protection rule is that market commitments should not create extra peak exposure when battery discharge capacity remains available.

## 13. Why Not a Full MILP

A MILP would be a natural production extension. It would be especially useful for multi-day, 15-minute, multi-market optimization with terminal SOC constraints and forecast uncertainty.

For this assessment, the candidate scheduler is preferable because it is:

- transparent
- small enough to audit manually
- easy to connect to the dashboard
- sufficient for the representative-day FCR-N versus mFRR comparison
- explicit about assumptions and trade-offs

## 14. What I Would Do With More Time

The next extensions would be:

- run a multi-day 15-minute backtest
- add explicit terminal SOC policy
- use measured C&I load profiles
- estimate mFRR activation probability from a longer history
- add break-even charts for activation probability, price spread, and battery size
- test FCR-D and aFRR only after the FCR-N versus mFRR core is stable
- reformulate the candidate scheduler as a MILP once the modelling assumptions are validated

## 15. Conclusion

The Part A result is not "mFRR always wins." The result is:

```text
FCR-N-only is a stable benchmark.
mFRR helps when activation exposure is low or well compensated.
mFRR hurts when activation consumes SOC needed for local customer value.
```

That is the operating trade-off the model is designed to expose.
