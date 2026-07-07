# Multi-Market Optimisation & Bidding for Behind-the-Meter Battery Assets 

# 1. Background and context

Truxel optimises behind-the-meter and standalone battery energy storage systems (BESS), often colocated with PV, for commercial and industrial (C&I) customers such as factories, farms, logistics and bus depots, and charging sites. Our value proposition is deliberately ordered: savings come first, revenue follows. Local optimisation (peak shaving, spot-price arbitrage, increased PV selfconsumption) is the entry point that customers trust; grid-facing ancillary services then layer on top to maximise total value.

In our current customer base, roughly 70% of the total value we create comes from ancillary services and roughly 30% from local optimisation. This creates a deliberate tension: the smaller (local) value stream is what wins the customer's trust and protects their power bill, while the larger (ancillary) stream is harder to schedule and to forecast. Our optimisation must respect that ordering, while still capturing as much grid revenue as the remaining battery capacity allows.

## 1.1 Why this assignment, and why now?

Our sites participate today in the Nordic frequency markets, primarily the Frequency Containment Reserves FCR-N and FCR-D (up and down). Scheduling for these is currently done largely manually, supported by an internal commercial simulator. That manual approach is workable while the service mix is small.

We are now prequalifying sites for mFRR (manual Frequency Restoration Reserve). Adding mFRR to a stack that already contains local services and FCR makes manual scheduling intractable: the optimiser must decide, hour by hour, how to split a single battery's limited capacity and state of charge across competing services that interact with each other and with the customer's peak-power constraint. Done naively, adding mFRR can reduce total per-site profit relative to an FCR-only baseline. That is the risk we are asking you to help us reason about.

**The operational headache, in one sentence**

> “When mFRR becomes available for a site, we have to decide hour by hour whether to commit capacity to FCR-N, to mFRR, or to hold it for local savings. We must do this without knowing the cleared prices in advance, and without violating the peak-shaving threshold or the battery's stateof-charge limits.”

## 1.2 What we want to learn about you

This is an R&D role. We are less interested in a polished production system and far more interested in how you frame an ambiguous, real problem; how you reason quantitatively under uncertainty; and how you communicate trade-offs to a mixed audience of engineers and commercial stakeholders. A clear, well-argued notebook with honest assumptions will score much higher than an over-engineered black box.


# 2. Market primer

You are not expected to be an expert in the Nordic balancing markets on day one. The table below gives you everything you need to attempt the assignment; deeper detail is publicly available from the Swedish TSO, Svenska Kraftnät, and you are encouraged (not required) to cite it.

| Service         | What it is                                                                                                                          | Timing / commitment                                                                                  | Relevance to this task                                                                     |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Local services  | Peak shaving, spot-price arbitrage, PV self-consumption. Reduces the customer's own grid cost.                                      | Scheduled by us; constrained by the peakpower threshold.                                             | Must take precedence. It sets the floor on battery capacity reserved for savings.          |
| FCR-N           | Frequency Containment Reserve — Normal. Automatic, symmetric response to small frequency deviations.                                | Procured day-ahead (D-1).                                                                            | Currently a staple of our stack; competes with mFRR for the same capacity.                 |
| FCR-D (up/down) | Disturbance reserve for larger deviations. Up and down are separate products; combining them on one asset incurs a derating factor. | Procured D-1 in two auctions.                                                                        | Lowest impact on peak power; can run in parallel with peak shaving.                        |
| mFRR            | Manual Frequency Restoration Reserve. Tertiary reserve activated on demand to restore 50 Hz.                                        | Capacity market D-1; energy bids close ~45 min before the operating period. Activation is uncertain. | The new service we are adding. Its activation uncertainty is the core modelling challenge. |

> ## Key market dynamics worth knowing
>
>- **Saturation drives diversification.** FCR-D became saturated through 2024 as prequalified battery capacity surged, compressing prices. The industry response has been to diversify into mFRR, where prequalified storage capacity grew several-fold during 2025. This is precisely why Truxel is adding mFRR now.
>
>- **Volatility is the opportunity.** Recent mFRR reforms (a move toward shorter, 15-minute settlement and increasingly automatic activation) are expected to increase price volatility. This is unfavourable for end-consumers, but it represents an opportunity for fast, well-scheduled storage.
>
>- **Prices are revealed late.** FCR clearing prices are not known in advance; they are set at gate closure. We currently bid FCR at zero price to guarantee acceptance. Once mFRR competes for the same capacity, we will likely need to set prices, which requires a forecast of opportunity value.

## 2.1 Operating rules and constraints you must respect

These are real rules from our operations. Treat them as hard constraints in any model you build:

- **Savings-first floor.** The combined schedule must deliver at least a minimum guaranteed saving X% versus operating the site without a battery, with `X ≥ 5%`. The actual savings level should itself be found by optimisation to maximise total value, but it can never drop below the floor.

- **Peak-power protection.** The site's peak grid import must never exceed the threshold set by peak shaving. Ancillary services must not create new cost for the customer by pushing peak power up.

- **FCR-D pairing de-rate.** To bid FCR-D up and FCR-D down on the same asset in the same hour, multiply the offered capacity by 0.8 (you cannot offer the full nameplate on both directions simultaneously).

- **mFRR readiness window.** Before an hour in which the asset offers mFRR, the battery needs roughly one hour during which it is available so its state of charge can be driven to a predefined SOC target.

- **Battery physics.** Respect state-of-charge limits, energy capacity, and charge/discharge power limits. Services must not be scheduled to work against each other (e.g. discharging for peak shaving in an hour the arbitrage logic wants to charge).

- **Single battery, shared capacity.** There is one battery per site serving all services. Two compatible services can share an hour (for example, peak shaving that coincides with a high-price discharge), but the capacity split between the local stack and the external stack should be dynamic, recomputed each hour rather than fixed for the year.



# 3. The optimisation principle

Truxel's objective function for asset scheduling must explicitly include both cost savings and revenue generation, with savings taking precedence. Conceptually:

```text
Maximise Value = Savings(X%) + Profit(grid services)

subject to min(X) ≥ 5% and all operating constraints in §2.1
```

Operationally the two stacks can be solved sequentially each hour: first the local cost-savings optimisation with a preset minimum savings %, then the external-services optimisation on the remaining capacity, and finally an iteration over candidate savings levels to find the split that maximises total value. You are free to propose a better formulation; if you do, please justify why.


# 4. The assignment

The assignment has one core task that everyone should attempt, and a set of extension tasks. We do not expect you to complete everything. Choose depth over breadth, and be explicit about what you did and did not do.

## Part A. Core task (required): the FCR-N vs mFRR commitment problem

A single C&I site has one BESS that is already prequalified for FCR-N and is now prequalified for mFRR. For a representative day (24 hourly steps, or 96 quarter-hourly steps if you prefer), decide for each period how to allocate the battery's available capacity between FCR-N, mFRR, and a reserve held for local savings, so as to maximise expected total value while respecting all constraints in §2.1.

The defining difficulty is that mFRR capacity revenue is fairly predictable, but mFRR activation (and therefore energy revenue) is uncertain, and FCR-N and mFRR compete for the same capacity. We want to see how you handle that uncertainty.

### What to deliver for Part A

- **Problem framing.** A clear written formulation of the decision problem: decision variables, objective, and constraints, mapped explicitly to the rules in §2.1.

- **A model.** A working model that produces an hourly (or quarter-hourly) allocation for the representative day. Any reasonable approach is acceptable, including a MILP/LP, a greedy or rulebased heuristic, a simple stochastic or expected-value model, or an RL formulation. Sophistication is not the goal; sound reasoning is.

- **Uncertainty handling.** An explicit treatment of mFRR activation uncertainty: how you represent it (e.g. an activation probability, a small set of scenarios, or a distribution), and how that representation changes the decision versus assuming no activation.

- **Baseline.** A baseline comparison: total value under your schedule versus an FCR-only baseline, demonstrating whether (and under what assumptions) adding mFRR helps or hurts per-site profit.

## Part B. Extension tasks

Choose whichever best showcases your strengths. Even one task done well beats three done superficially.

- **B1. Price / opportunity-value forecasting.** We currently bid FCR at zero price. Once mFRR competes for capacity, we will need to set prices. Prototype a simple forecaster for FCR-N and/or mFRR capacity prices (or for mFRR activation likelihood) from any public or synthetic data, and show how its output would feed the commitment decision in Part A. Discuss the danger of overrelying on a third-party forecast versus building in-house.

- **B2. Dynamic capacity split.** Extend Part A so the split between the local stack and the external stack is recomputed every hour rather than fixed and quantify the value uplift of going dynamic versus a fixed monthly split.

- **B3. Sensitivity / break-even analysis.** Identify the conditions (mFRR activation rate, price spread, battery size, SOC headroom) under which stacking mFRR is worthwhile. Present this as a small set of charts or a break-even surface a commercial colleague could read.

- **B4. Build-versus-buy memo.** Several vendors sell auto-bidding and peak-shaving components. Write a short, evidence-based recommendation on where Truxel should use off-the-shelf components to bridge the gap to market, and where it must keep the optimisation in-house as its core IP.

## 4.1 Inputs and data

No proprietary company data is needed. Use any of the following, and state clearly what you used:

- **Synthetic.** Synthetic data that you generate and justify (a load profile, a PV profile, spot prices, FCR/mFRR prices, and an mFRR activation series). This is perfectly acceptable and often cleaner for a take-home.

- **Public.** Public market data, for example Nord Pool day-ahead spot prices and Svenska Kraftnät's published FCR/mFRR volumes and prices. Please cite your sources.

Assume a single site with a `1 MW / 2 MWh` battery, co-located PV, and a non-trivial C&I consumption profile, unless you choose to vary these in a sensitivity analysis. State every other assumption you make.


# 5. Deliverables, format and logistics

## 5.1 What to submit

1. **Code.** Code in a runnable form, either a Git repository or a zipped project. Python is preferred but not required. Include a short README with setup and run instructions.

2. **Write-up.** A short technical write-up (3 to 5 pages, or an annotated notebook) covering: your problem framing, model, key assumptions, results with at least one or two charts, the baseline comparison, and an honest “what I'd do with more time” section.

3. **Executive summary.** A one-page executive summary aimed at a commercial stakeholder rather than an engineer: what you found, what it means for Truxel's go-to-market, and the main risks. This page matters, because the role sits between R&D and commercial.

4. **AI tools used disclosure.** Include a section in the README listing which AI tools you used (Claude, Cursor, Copilot, ChatGPT, etc.), what tasks you used them for, and what you wrote or reviewed independently. We are not penalising AI use — we are penalising lack of transparency. Honest disclosure is treated the same as no AI use.

## 5.2 Timeline

We suggest spending 8 to 12 hours, spread across up to 7 calendar days from receipt. If your circumstances need a different timeframe, just let us know. Flexibility is fine, and we would rather see your best thinking than a rushed result.

## 5.3 The follow-up conversation

After submission we will schedule a 45-to-60-minute discussion. We will ask you to walk us through your reasoning, defend an assumption or two, and explore how you would extend the work toward production. The conversation is part of the evaluation; the written deliverable is the starting point, not the whole of it.


# 6. How we will evaluate it

We grade on reasoning and communication first. We are explicitly not grading on whether you matched some hidden “correct” number, because there isn't one. The weighting below reflects what the role actually requires.

| Dimension              | Weight | What “good” looks like                                                                                                         |
| ---------------------- | -----: | ------------------------------------------------------------------------------------------------------------------------------ |
| Problem framing        |    25% | Clearly restates an ambiguous problem, maps it to the real constraints, and makes assumptions explicit and reasonable.         |
| Quantitative reasoning |    25% | Sound treatment of uncertainty and trade-offs; results that follow logically from the model; a meaningful baseline comparison. |
| Energy-domain insight  |    15% | Demonstrates understanding of the savings-first principle, the peak-power constraint, and why mFRR can both help and hurt.     |
| Code quality           |    15% | Runs as described, readable, reproducible. Polish is secondary to clarity.                                                     |
| Communication          |    20% | The write-up and especially the one-page executive summary are clear, honest, and audience-appropriate.                        |

> **A note on scope and honesty.** If you make a simplifying assumption because the full problem is too large for a take-home, say so and move on. That is exactly the judgement we want to see. We would much rather read “I assumed FCR-N price is known and constant because forecasting it was out of scope; here is how I'd relax that” than discover a hidden, unexplained shortcut. Thoughtful scoping is a strength, not a weakness.


# 7. Glossary

| Term                 | Meaning                                                                                                        |
| -------------------- | -------------------------------------------------------------------------------------------------------------- |
| BESS                 | Battery Energy Storage System.                                                                                 |
| C&I                  | Commercial & Industrial customers (factories, depots, farms, charging sites).                                  |
| Behind-the-meter     | Assets sited behind a customer's grid connection, where a consumption load exists.                             |
| Peak shaving         | Discharging the battery to keep grid import below a threshold, lowering capacity charges.                      |
| Spot-price arbitrage | Charging when electricity is cheap and discharging when it is expensive.                                       |
| FCR-N / FCR-D        | Frequency Containment Reserves: Normal (small deviations) and Disturbance (large deviations, split up/down).   |
| mFRR                 | Manual Frequency Restoration Reserve: tertiary reserve, manually/automatically activated to restore frequency. |
| Prequalification     | TSO process that tests and approves an asset to deliver a given ancillary service.                             |
| SOC                  | State of Charge, meaning how full the battery is.                                                              |
| Gate closure         | The deadline after which bids for a market period can no longer be submitted or changed.                       |
| TSO                  | Transmission System Operator (Svenska Kraftnät in Sweden).                                                     |

Good luck. We are looking forward to seeing how you think.
