# Behind-the-Meter BESS Market Optimizer

Scenario-based optimizer for deciding how a 1 MW / 2 MWh behind-the-meter battery should allocate hourly capacity between local customer savings, FCR-N, and mFRR.

The project is intentionally scoped to Part A of the Truxel take-home assignment. It focuses on an explainable representative-day model, clear constraint handling, and a dashboard that makes the trade-off between FCR-N-only operation and stacked FCR-N + mFRR participation reviewable.

## Main Finding

The model does not assume that stacked market participation is always better.

- FCR-N-only is the stable benchmark because it adds capacity revenue while preserving local dispatch.
- Stacked FCR-N + mFRR outperforms FCR-N-only in the low-activation case.
- In base and high mFRR activation cases, expected activation consumes SOC and can reduce later local savings, making stacked participation lower value than FCR-N-only.

That is the central Part A conclusion: mFRR should be accepted only when its expected value compensates for the battery flexibility it consumes.

A production version would add a forecasting layer trained on at least two years of site, market, weather, and activation data, but the constrained optimizer would still enforce SOC, local savings, reserve readiness, and shared-capacity limits.

## Setup

From the repository root:

```powershell
uv sync --all-packages
```

## Running the pipeline

Rebuild the processed representative-day dataset:

```powershell
uv run --package bess-optimizer python scripts/build_processed_dataset.py
```

Run the Part A model:

```powershell
uv run --package bess-optimizer python scripts/run_part_a_model.py
```

Run the B3 break-even sensitivity:

```powershell
uv run --package bess-optimizer python scripts/run_b3_sensitivity.py
```

Run the Streamlit dashboard:

```powershell
uv run --package bess-dashboard bess-dashboard
```

The model writes:

- `data/output/part_a_dispatch_hourly_se3_20260624.csv`
- `data/output/part_a_scenario_summary_se3_20260624.csv`
- `data/output/part_a_constraint_audit_se3_20260624.csv`
- `data/output/b3_mfrr_break_even_sensitivity_se3_20260624.csv`

## Submission Documents

- [Executive summary](EXECUTIVE_SUMMARY.md)
- [Technical write-up](docs/TECHNICAL_WRITEUP.md)
- [Assumptions and formulas](docs/ASSUMPTIONS_AND_FORMULAS.md)
- [B3 break-even analysis](docs/B3_BREAK_EVEN_ANALYSIS.md)
- [Data method](docs/DATA_METHOD.md)
- [Implementation notes](docs/IMPLEMENTATION_NOTES.md)
- [Dashboard notes](apps/dashboard/README.md)

## AI Tools Used

I used OpenAI ChatGPT and Codex as support tools during this assignment. They were used for the following purposes:

| Purpose | How AI was used |
|---|---|
| Research and terminology | ChatGPT was used to understand market concepts such as FCR-N, mFRR, activation uncertainty, reserve readiness, behind-the-meter battery operation, and local savings constraints. |
| Problem framing | ChatGPT was used to structure the modelling approach, clarify the local-first operating logic, and compare possible ways to represent mFRR activation uncertainty. |
| Implementation support | Codex was used to help write and refactor parts of the Python implementation, including data processing, dispatch logic, scenario runners, metrics, and dashboard components. |
| Debugging and review | ChatGPT and Codex were used to review whether the model outputs were sensible, identify confusing behaviour in the scenario results, and refine the treatment of FCR-N and mFRR trade-offs. |
| Documentation | ChatGPT was used to help draft and organize the README and documentation sections covering methodology, assumptions, scenario interpretation, limitations, and future extensions. |

All modelling assumptions, scenario choices, code changes, result interpretation, and final submission materials were reviewed, edited, and accepted by me before submission.

No proprietary Truxel data was provided to AI tools. The assignment uses public, synthetic, or representative data only.
