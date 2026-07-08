# BESS Optimizer Package

Core Python package for the Part A behind-the-meter BESS optimizer.

Install all workspace packages from the repository root:

```powershell
uv sync --all-packages
```

Run the model:

```powershell
uv run --package bess-optimizer python scripts/run_part_a_model.py
```

The package contains the local dispatch logic, FCR-N baseline, stacked FCR-N/mFRR scheduler, scenario metrics, and constraint audit used by the dashboard and submission write-up.

For the full modelling explanation, see `../docs/TECHNICAL_WRITEUP.md`.
