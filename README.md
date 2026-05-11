# Commodity Prices

A lightweight dashboard for exploring World Bank ["Pink Sheet"](https://www.worldbank.org/en/research/commodity-markets)
commodity price trends, with filtering for biggest movers and z-score anomaly
detection.

Live site: _enable GitHub Pages on this repo (see below) and add the URL here._

## What it does

- Pulls the monthly Pink Sheet Excel file from the World Bank
- Transforms it to a long-format JSON with 1m / 3m / 12m / 5yr percent changes
- Computes a z-score of the current monthly return against the trailing 12-month
  return distribution (shifted by 1 to avoid lookahead) to flag unusual moves
- Renders a zero-build static site with Chart.js

## Running locally

```bash
pip install -r requirements.txt
python prep_data.py        # writes data/*.json
python -m http.server 8000 # then open http://localhost:8000
```

## Deploying to GitHub Pages

The site is plain static files at the repo root, so:

1. **Settings → Pages** → set _Source_ to **Deploy from a branch**
2. Pick branch **`main`** and folder **`/ (root)`**, then save.
3. GitHub will publish to `https://<user>.github.io/<repo>/`. To use a custom
   subdomain, add a `CNAME` file with the hostname and point a `CNAME` DNS
   record at `<user>.github.io`.

No build step or workflow is needed for hosting — the data files committed under
`data/` are what the browser fetches.

## Monthly auto-refresh

`.github/workflows/refresh-data.yml` runs on the 3rd of each month (12:00 UTC)
and on manual dispatch. It:

1. Installs the Python deps
2. Runs `prep_data.py` to download the latest Pink Sheet and rebuild the JSON
3. Commits any changes under `data/` back to `main`

A push to `main` re-publishes the Pages site automatically, so the dashboard
picks up the new data on the next page load.

To trigger a refresh manually: **Actions → Refresh commodity data → Run
workflow**.

## Project layout

```
prep_data.py                       # downloads + transforms the Pink Sheet
requirements.txt                   # pandas, requests, openpyxl
index.html                         # the dashboard (static, Chart.js via CDN)
data/                              # generated outputs the dashboard reads
  ├─ commodity_prices.json         # full long-format dataset
  ├─ commodity_prices.csv          # same data, for inspection
  ├─ summary.json                  # precomputed top movers
  └─ metadata.json                 # date range, commodity list, generated_at
.github/workflows/refresh-data.yml # monthly cron
```

## Data source

[World Bank Commodity Markets — "Pink Sheet"](https://www.worldbank.org/en/research/commodity-markets).
See their [terms of use](https://www.worldbank.org/en/about/legal/terms-of-use-for-datasets).
