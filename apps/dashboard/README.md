# BESS Dashboard

Streamlit dashboard for the behind-the-meter BESS market optimizer.

Install workspace dependencies from the repository root:

```powershell
uv sync --all-packages
```

Run from the repository root:

```powershell
uv run --package bess-dashboard bess-dashboard
```

The dashboard reads the committed files in `data/processed` and `data/output`.
Rebuild them from the repository root before reviewing if model logic or raw
inputs change:

```powershell
uv run --package bess-optimizer python scripts/build_processed_dataset.py
uv run --package bess-optimizer python scripts/run_part_a_model.py
uv run --package bess-optimizer python scripts/run_b3_sensitivity.py
```

The dashboard is a review surface for the Part A model and the B3 break-even
sensitivity. The deeper methodology is documented in
`../../docs/TECHNICAL_WRITEUP.md` and `../../docs/B3_BREAK_EVEN_ANALYSIS.md`.
