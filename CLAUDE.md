# Commodity Price Dashboard

## Overview
A lightweight dashboard for exploring World Bank "Pink Sheet" commodity price trends, with filtering for biggest movers and z-score anomaly detection.

## Data Pipeline
- `prep_data.py` downloads and transforms the Pink Sheet Excel into JSON
- Computes 1m/3m/12m/5yr percent changes
- Computes z-scores (current return vs trailing 12-month volatility) to surface unusual moves
- Outputs to `data/` folder

## Key Design Decisions
- Z-score uses 12-month trailing window with 1-month shift (no lookahead)
- Categories manually mapped to match World Bank groupings
- Static HTML + Chart.js for zero-build deployment
- GitHub Action refreshes data monthly on the 3rd

## Running Locally
```bash
python prep_data.py
python -m http.server 8000
```

## Data Source
https://www.worldbank.org/en/research/commodity-markets