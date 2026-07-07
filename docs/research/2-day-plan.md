With **2 days**, cut scope hard.

Do **not** build a full forecasting system, RL model, public-data scraper, or quarter-hourly optimizer. The assignment explicitly says reasoning, assumptions, baseline comparison, uncertainty handling, and communication matter more than a polished production system; it also allows synthetic data. 

## Best 2-day submission scope

### Submit this

**Core Part A only + one light B3 sensitivity extension.**

Use:

* **Synthetic C&I load profile**
* **Synthetic PV generation**
* **Synthetic FCR-N price**
* **Synthetic mFRR capacity price**
* **Synthetic mFRR activation scenarios**
* **1 MW / 2 MWh battery**
* **Hourly 24-step model**
* **FCR-only baseline**
* **mFRR uncertainty via 3 scenarios**
* **Sensitivity chart:** mFRR activation probability × mFRR price premium

This is enough to look thoughtful and complete.

## What public data to use now

Given 2 days: **do not depend on public data downloads.**

Use public sources only as references in the write-up:

| Data need             | What to do                                                                        |
| --------------------- | --------------------------------------------------------------------------------- |
| Site load             | Synthetic C&I profile                                                             |
| PV                    | Synthetic bell-shaped PV curve                                                    |
| Spot price            | Synthetic hourly price curve                                                      |
| FCR-N price           | Synthetic around a stable base                                                    |
| mFRR capacity price   | Synthetic with volatility                                                         |
| mFRR activation       | Scenario-based synthetic activation                                               |
| Public market context | Cite Svenska Kraftnät / Nord Pool in notes, but do not build pipeline around them |

Reason: the assignment accepts synthetic data, and the evaluation is about framing, constraints, uncertainty, baseline, and communication.

## Model to build

Use a **transparent heuristic or small LP**, not a complex MILP.

I would use this logic:

1. Build no-battery baseline.
2. Simulate local battery use for peak shaving / savings.
3. Reserve enough battery capacity to guarantee at least **5% savings**.
4. Allocate remaining capacity each hour between:

   * FCR-N if stable expected value is better
   * mFRR if expected capacity + activation value beats FCR-N
5. Enforce:

   * SOC min/max
   * charge/discharge power limits
   * peak import threshold
   * mFRR readiness hour
6. Compare against:

   * no battery
   * FCR-only battery schedule
   * FCR + mFRR schedule

## 2-day execution plan

### Day 1 — Build the working solution

**Hour 1: Repo setup**

Create:

```text
truxel_assignment/
├── README.md
├── requirements.txt
├── config.yaml
├── notebooks/
│   └── truxel_bess_optimisation.ipynb
├── src/
│   ├── data.py
│   ├── baseline.py
│   ├── scheduler.py
│   └── plots.py
├── figures/
└── outputs/
```

**Hour 2: Synthetic data**

Generate one representative day:

* load profile: morning ramp, afternoon operations, evening decline
* PV profile: bell curve from 7 AM to 6 PM
* spot prices: low midday, high evening
* FCR-N price: stable hourly price
* mFRR price: spiky higher-price hours
* activation probability: low / medium / high scenarios

**Hour 3–4: Baselines**

Create:

1. No-battery cost baseline
2. Local-only battery baseline
3. FCR-only baseline

Output table:

| Scenario | Local savings | FCR revenue | mFRR revenue | Total value | Savings % | Feasible |
| -------- | ------------: | ----------: | -----------: | ----------: | --------: | -------- |

**Hour 5–6: Scheduler**

Build the combined scheduler:

* reserve local savings first
* commit mFRR only when expected mFRR value > FCR value + readiness penalty
* otherwise allocate to FCR-N
* ensure SOC is feasible

Do not over-optimize. Make it explainable.

**Hour 7: First charts**

Create:

1. Hourly allocation chart: local reserve / FCR-N / mFRR
2. SOC over time
3. Value comparison: FCR-only vs FCR + mFRR

**Hour 8: Write assumptions directly in notebook**

Add a clean assumptions table:

| Assumption       |                  Value | Why                                        |
| ---------------- | ---------------------: | ------------------------------------------ |
| Battery power    |                   1 MW | Given in assignment                        |
| Battery energy   |                  2 MWh | Given in assignment                        |
| Time step        |                 1 hour | Simpler within 2-day scope                 |
| Minimum savings  |                     5% | Required floor                             |
| mFRR uncertainty | 3 activation scenarios | Simple, transparent uncertainty handling   |
| Public data      |      Not used in model | Synthetic data allowed; focus on reasoning |

---

### Day 2 — Sensitivity, write-up, packaging

**Hour 1–2: B3 sensitivity**

Run a simple grid:

* mFRR activation probability: 0%, 10%, 20%, 40%, 60%
* mFRR price premium over FCR-N: 0%, 25%, 50%, 100%, 150%

Create one heatmap:

**When does mFRR beat FCR-only?**

This will make the submission much stronger commercially.

**Hour 3: Technical write-up**

Keep it 3–5 pages or make the notebook annotated.

Structure:

1. Problem framing
2. Data and assumptions
3. Model formulation
4. Baselines
5. mFRR uncertainty treatment
6. Results
7. Sensitivity analysis
8. Limitations and next steps

**Hour 4: Executive summary**

One page only.

Use this structure:

```text
What I tested
I modelled a representative C&I site with a 1 MW / 2 MWh BESS and compared an FCR-only schedule against a schedule that can allocate capacity between local savings, FCR-N and mFRR.

What I found
mFRR improves value only when expected activation-adjusted revenue is high enough to compensate for readiness and SOC constraints. In low-activation or low-price-premium cases, FCR-only is safer.

Commercial implication
mFRR should not be added blindly to every site. It needs site-level gating based on load shape, SOC headroom, peak-shaving requirement, and expected mFRR price/activation conditions.

Main risk
Synthetic assumptions are useful for reasoning but should be replaced with historical Svenska Kraftnät/Nord Pool data before production use.
```

**Hour 5: README and AI disclosure**

README must include:

```text
How to run
Files included
Assumptions
Data used
Model summary
Limitations
AI tools used disclosure
```

AI disclosure can be:

```text
AI tools used:
I used ChatGPT for scoping the assignment, structuring the implementation plan, reviewing the write-up, and checking whether the assumptions were clearly explained. I independently reviewed the model logic, constraints, results, and final submission.
```

**Hour 6: Final QA**

Check these before submitting:

* Notebook runs top to bottom.
* No missing imports.
* Figures are saved.
* README has setup instructions.
* Executive summary exists.
* FCR-only baseline exists.
* mFRR uncertainty is explicit.
* Savings floor is shown.
* Peak threshold violations are checked.
* SOC chart is included.
* You clearly say what was simplified.

## What to avoid

Do **not** spend time on:

* downloading and cleaning large public datasets
* mFRR forecasting model
* FCR-D
* quarter-hourly resolution
* RL
* full MILP if solver setup takes time
* beautiful dashboard
* production-style package structure
* multi-day simulation

## Final deliverable checklist

Submit a zip or GitHub repo with:

```text
README.md
requirements.txt
config.yaml
notebooks/truxel_bess_optimisation.ipynb
src/data.py
src/baseline.py
src/scheduler.py
src/plots.py
figures/allocation_schedule.png
figures/soc_profile.png
figures/value_comparison.png
figures/mfrr_sensitivity_heatmap.png
outputs/results_summary.csv
EXECUTIVE_SUMMARY.md
```

> Keep the model simple and auditable because the core question is not whether we can build a complex optimiser, but whether mFRR improves site-level value after preserving guaranteed customer savings and respecting battery feasibility.
