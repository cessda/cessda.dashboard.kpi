# Cessda report dashboard

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Nix](https://nixos.org/download) with flakes enabled
- [devenv](https://devenv.sh/getting-started/)

## Setup

```bash
devenv shell

uv run python -m ipykernel install --user --name=sp-analysis --display-name="sp-analysis"

uv run jupyter notebook
```

Then open `analysis.ipynb` and select the **sp-analysis** kernel via **Kernel → Change Kernel**.


## Updating the dashboard with new data

The dashboard renders from a committed CSV file (`data/sp_data.csv`) so the CI pipeline
does not need internet access. When new data is available in Google Sheets, refresh it locally:

**1. Open the notebook and run the data export cell:**

```python
from sp_analysis import load_data

df = load_data('https://docs.google.com/spreadsheets/d/1sREWbJdEYFjckWHcgAaUTnb6uQIuyM-bs-Un12ZmVaA/gviz/tq?tqx=out:csv&gid=598429315')

df.to_csv('data/sp_data.csv', index=False)
```

**2. Preview the dashboard locally to check everything looks right:**

```bash
uv run quarto preview dashboard.qmd
```

**3. Commit and push:**

```bash
git add data/sp_data.csv
git commit -m "chore: refresh data"
git push origin main
```

The CI pipeline will automatically re-render and publish the updated dashboard to GitLab Pages.

## Project structure

```
sp-analysis/
├── sp_analysis/
│   ├── __init__.py
│   └── charts.py        # shared helpers (data loading, transforms, charts)
├── data/
│   └── sp_data.csv      # committed data snapshot (source of truth for CI)
├── analysis.ipynb       # exploratory notebook
├── dashboard.qmd        # Quarto dashboard source
├── .gitlab-ci.yml       # CI pipeline
├── pyproject.toml       # dependencies managed by uv
└── devenv.nix           # dev environment
```

## Dependencies

To add a new dependency:

```bash
uv add package-name
```
