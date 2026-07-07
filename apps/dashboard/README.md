# BESS Dashboard

Streamlit dashboard for the behind-the-meter BESS market optimizer.

Run from the repository root:

```powershell
uv run --package bess-dashboard bess-dashboard
```

Streamlit deployment:

```text
App file: streamlit_app.py
Dependency file: requirements.txt
Python: 3.12
```

The root `requirements.txt` installs both local packages. Keep `data/processed`
and `data/output` committed so the deployed app can load the representative
input data and Part A dispatch outputs.
