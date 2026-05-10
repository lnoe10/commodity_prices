#!/usr/bin/env python3
"""
World Bank Commodity Price Data Prep Script

Downloads and transforms the Pink Sheet monthly data into a clean JSON format
suitable for dashboard visualization.

Data source: https://www.worldbank.org/en/research/commodity-markets
Monthly prices Excel: CMO-Historical-Data-Monthly.xlsx
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import requests

# URLs for World Bank commodity data
MONTHLY_DATA_URL = "https://thedocs.worldbank.org/en/doc/18675f1d1639c7a34d463f59263ba0a2-0050012025/related/CMO-Historical-Data-Monthly.xlsx"
LOCAL_FILE = "CMO-Historical-Data-Monthly.xlsx"

# Commodity categories based on World Bank classification
CATEGORIES = {
    "Energy": [
        "Coal, Australian", "Coal, South African", "Crude oil, average", 
        "Crude oil, Brent", "Crude oil, Dubai", "Crude oil, WTI",
        "Natural gas, US", "Natural gas, Europe", "Liquefied natural gas, Japan",
        "Natural gas index"
    ],
    "Beverages": [
        "Cocoa", "Coffee, Arabica", "Coffee, Robusta", 
        "Tea, avg 3 auctions", "Tea, Colombo", "Tea, Kolkata", "Tea, Mombasa"
    ],
    "Oils & Meals": [
        "Coconut oil", "Groundnut oil", "Groundnuts", "Fish meal",
        "Palm oil", "Palm kernel oil", "Soybean oil", "Soybeans",
        "Soybean meal", "Rapeseed oil", "Sunflower oil"
    ],
    "Grains": [
        "Barley", "Maize", "Sorghum", 
        "Rice, Thai 5%", "Rice, Thai 25%", "Rice, Thai A.1", "Rice, Viet Namese 5%",
        "Wheat, US HRW", "Wheat, US SRW"
    ],
    "Other Food": [
        "Banana, Europe", "Banana, US", "Orange",
        "Beef", "Chicken", "Lamb", "Shrimps, Mexican",
        "Sugar, EU", "Sugar, US", "Sugar, world"
    ],
    "Raw Materials": [
        "Logs, Cameroon", "Logs, Malaysian", "Sawnwood, Cameroon", "Sawnwood, Malaysian",
        "Plywood", "Cotton, A Index", "Rubber, TSR20", "Rubber, RSS3", 
        "Tobacco, US import u.v."
    ],
    "Fertilizers": [
        "DAP", "Phosphate rock", "Potassium chloride", "TSP", "Urea"
    ],
    "Metals": [
        "Aluminum", "Copper", "Iron ore, cfr spot", "Lead", "Nickel", "Tin", "Zinc"
    ],
    "Precious Metals": [
        "Gold", "Platinum", "Silver"
    ]
}

# Reverse lookup: commodity -> category
def get_category(commodity_name):
    # Clean the commodity name for matching
    clean_name = commodity_name.replace(" **", "").strip()
    
    # First pass: exact matches only
    for cat, commodities in CATEGORIES.items():
        for c in commodities:
            if c.lower() == clean_name.lower():
                return cat
    
    # Second pass: partial matches (but check precious metals first to avoid Platinum->Metals)
    ordered_categories = ["Precious Metals"] + [c for c in CATEGORIES.keys() if c != "Precious Metals"]
    for cat in ordered_categories:
        for c in CATEGORIES[cat]:
            if c.lower() in clean_name.lower() or clean_name.lower() in c.lower():
                return cat
    return "Other"


def download_data(url=MONTHLY_DATA_URL, output_path=LOCAL_FILE):
    """Download the Excel file from World Bank."""
    print(f"Downloading data from {url}...")
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    with open(output_path, 'wb') as f:
        f.write(response.content)
    print(f"Saved to {output_path}")
    return output_path


def load_and_transform(filepath=LOCAL_FILE):
    """
    Load the Pink Sheet Excel and transform to long format.
    
    The Excel file structure:
    - Row 0-3: Title/metadata
    - Row 4: Commodity names
    - Row 5: Units ($/bbl, $/mt, etc.)
    - Row 6+: Data with dates in format "1960M01"
    """
    print(f"Loading {filepath}...")
    
    # Read the Monthly Prices sheet
    df = pd.read_excel(filepath, sheet_name="Monthly Prices", header=None)
    
    # Row 4 has commodity names, Row 5 has units
    HEADER_ROW = 4
    UNITS_ROW = 5
    DATA_START = 6
    
    # Extract commodity names and units
    commodities = df.iloc[HEADER_ROW].tolist()
    units = df.iloc[UNITS_ROW].tolist()
    
    # First column is date
    commodities[0] = "date"
    
    # Clean commodity names (remove ** markers but keep for reference)
    commodities = [str(c).strip() if pd.notna(c) else f"col_{i}" 
                   for i, c in enumerate(commodities)]
    
    # Build units lookup
    units_lookup = {}
    for i, (c, u) in enumerate(zip(commodities, units)):
        if c != "date" and pd.notna(u):
            units_lookup[c] = str(u).strip()
    
    print(f"Found {len([c for c in commodities if c != 'date' and not c.startswith('col_')])} commodities")
    
    # Get data rows
    df_clean = df.iloc[DATA_START:].copy()
    df_clean.columns = commodities
    
    # Parse dates (format: "1960M01")
    df_clean['date'] = pd.to_datetime(
        df_clean['date'].astype(str).str.strip(), 
        format='%YM%m', 
        errors='coerce'
    )
    
    # Drop rows with invalid dates
    df_clean = df_clean.dropna(subset=['date'])
    print(f"Date range: {df_clean['date'].min()} to {df_clean['date'].max()}")
    
    # Convert to long format
    records = []
    commodity_cols = [c for c in commodities if c != 'date' and not c.startswith('col_')]
    
    for _, row in df_clean.iterrows():
        date = row['date']
        for commodity in commodity_cols:
            price = row.get(commodity)
            # Skip missing values and placeholder strings like "…"
            if pd.notna(price) and str(price).strip() not in ['…', '..', '-', '']:
                try:
                    price_float = float(price)
                    records.append({
                        'date': date.strftime('%Y-%m-%d'),
                        'year': date.year,
                        'month': date.month,
                        'commodity': commodity,
                        'category': get_category(commodity),
                        'unit': units_lookup.get(commodity, ''),
                        'price': round(price_float, 4)
                    })
                except (ValueError, TypeError):
                    pass
    
    df_long = pd.DataFrame(records)
    print(f"Transformed to {len(df_long)} records across {df_long['commodity'].nunique()} commodities")
    
    return df_long


def compute_changes(df):
    """
    Compute rolling percentage changes and z-scores for different windows.
    """
    print("Computing price changes and z-scores...")
    
    # Sort by commodity and date
    df = df.sort_values(['commodity', 'date'])
    
    results = []
    
    for commodity in df['commodity'].unique():
        cdf = df[df['commodity'] == commodity].copy()
        cdf = cdf.sort_values('date')
        
        # Compute percentage changes
        cdf['pct_1m'] = cdf['price'].pct_change(1) * 100
        cdf['pct_3m'] = cdf['price'].pct_change(3) * 100
        cdf['pct_12m'] = cdf['price'].pct_change(12) * 100
        cdf['pct_60m'] = cdf['price'].pct_change(60) * 100  # 5 year
        
        # Compute z-score for 1-month returns based on trailing 12-month window
        # z = (current_return - mean_return) / std_return
        cdf['return_mean_12m'] = cdf['pct_1m'].rolling(window=12, min_periods=6).mean()
        cdf['return_std_12m'] = cdf['pct_1m'].rolling(window=12, min_periods=6).std()
        
        # Shift by 1 so we compare current return to *prior* 12 months (not including current)
        cdf['return_mean_12m'] = cdf['return_mean_12m'].shift(1)
        cdf['return_std_12m'] = cdf['return_std_12m'].shift(1)
        
        # Calculate z-score (handle division by zero)
        cdf['zscore_1m'] = (cdf['pct_1m'] - cdf['return_mean_12m']) / cdf['return_std_12m']
        cdf.loc[cdf['return_std_12m'] == 0, 'zscore_1m'] = 0
        
        # Drop intermediate columns
        cdf = cdf.drop(columns=['return_mean_12m', 'return_std_12m'])
        
        results.append(cdf)
    
    df_final = pd.concat(results, ignore_index=True)
    
    # Round values
    for col in ['pct_1m', 'pct_3m', 'pct_12m', 'pct_60m', 'zscore_1m']:
        df_final[col] = df_final[col].round(2)
    
    return df_final


def generate_summary(df):
    """
    Generate a summary of biggest movers for the most recent month.
    """
    # Get most recent date
    latest_date = df['date'].max()
    latest = df[df['date'] == latest_date].copy()
    
    # Filter for valid z-scores
    latest_with_zscore = latest[latest['zscore_1m'].notna()].copy()
    
    summary = {
        'latest_date': latest_date,
        'biggest_gainers_1m': latest.nlargest(10, 'pct_1m')[['commodity', 'category', 'price', 'pct_1m']].to_dict('records'),
        'biggest_losers_1m': latest.nsmallest(10, 'pct_1m')[['commodity', 'category', 'price', 'pct_1m']].to_dict('records'),
        'biggest_gainers_12m': latest.nlargest(10, 'pct_12m')[['commodity', 'category', 'price', 'pct_12m']].to_dict('records'),
        'biggest_losers_12m': latest.nsmallest(10, 'pct_12m')[['commodity', 'category', 'price', 'pct_12m']].to_dict('records'),
        # Z-score based movers - unusual moves relative to recent volatility
        'most_unusual_up': latest_with_zscore.nlargest(10, 'zscore_1m')[['commodity', 'category', 'price', 'pct_1m', 'zscore_1m']].to_dict('records'),
        'most_unusual_down': latest_with_zscore.nsmallest(10, 'zscore_1m')[['commodity', 'category', 'price', 'pct_1m', 'zscore_1m']].to_dict('records'),
    }
    
    return summary


def save_outputs(df, summary, output_dir='.'):
    """Save transformed data to JSON and CSV."""
    output_dir = Path(output_dir)
    
    # Full dataset as JSON (for dashboard)
    json_path = output_dir / 'commodity_prices.json'
    df.to_json(json_path, orient='records', date_format='iso')
    print(f"Saved full data to {json_path}")
    
    # Summary as JSON
    summary_path = output_dir / 'summary.json'
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"Saved summary to {summary_path}")
    
    # Also save as CSV for inspection
    csv_path = output_dir / 'commodity_prices.csv'
    df.to_csv(csv_path, index=False)
    print(f"Saved CSV to {csv_path}")
    
    # Metadata
    meta = {
        'generated_at': datetime.now().isoformat(),
        'source': 'World Bank Commodity Markets - Pink Sheet',
        'source_url': 'https://www.worldbank.org/en/research/commodity-markets',
        'data_url': MONTHLY_DATA_URL,
        'record_count': len(df),
        'commodity_count': df['commodity'].nunique(),
        'date_range': {
            'start': df['date'].min(),
            'end': df['date'].max()
        },
        'categories': list(df['category'].unique()),
        'commodities': sorted(df['commodity'].unique().tolist())
    }
    
    meta_path = output_dir / 'metadata.json'
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2, default=str)
    print(f"Saved metadata to {meta_path}")


def main():
    """Main pipeline."""
    output_dir = Path('data')
    output_dir.mkdir(exist_ok=True)
    
    # Download if not exists
    if not Path(LOCAL_FILE).exists():
        try:
            download_data()
        except Exception as e:
            print(f"Could not download: {e}")
            print(f"Please manually download from {MONTHLY_DATA_URL}")
            print(f"and save as {LOCAL_FILE}")
            return
    
    # Transform
    df = load_and_transform()
    
    # Compute changes
    df = compute_changes(df)
    
    # Generate summary
    summary = generate_summary(df)
    
    # Save outputs
    save_outputs(df, summary, output_dir)
    
    print("\nDone! Output files in ./data/")
    print(f"  - commodity_prices.json ({len(df)} records)")
    print(f"  - summary.json (latest movers)")
    print(f"  - metadata.json (data info)")


if __name__ == '__main__':
    main()
