# BESS Optimizer Package

Core Python package for the Part A behind-the-meter BESS optimizer.

Install all workspace packages from the repository root:

```powershell
uv sync --all-packages
```

Run the complete data and modelling pipeline:

```powershell
uv run --package bess-optimizer bess-run-pipeline
```

Individual package commands are also available:

```powershell
uv run --package bess-optimizer bess-build-data
uv run --package bess-optimizer bess-run-model
uv run --package bess-optimizer bess-run-sensitivity
```

The package contains processed-data loading and transformation, the local
dispatch logic, FCR-N baseline, stacked FCR-N/mFRR scheduler, scenario metrics,
constraint audit, B3 sensitivity, and application workflows used by the
dashboard and submission write-up.

For the full modelling explanation, see `../docs/TECHNICAL_WRITEUP.md`.
