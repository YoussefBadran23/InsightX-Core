"""
Kaggle "Online Retail II" UCI Dataset Adapter
Maps UCI columns → InsightX-compatible CSV format.

Usage:
    1. Download "Online Retail II" from Kaggle/UCI and place in ../raw/
    2. python kaggle_retail_adapter.py --input ../raw/online_retail_II.xlsx
    3. Output: ../output/kaggle_retail_adapted.csv

Source: https://www.kaggle.com/datasets/mashlyn/online-retail-ii-uci
Columns: Invoice, StockCode, Description, Quantity, InvoiceDate, Price, Customer ID, Country
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

# UCI country → region mapping
COUNTRY_REGION = {
    "United Kingdom": "EU", "France": "EU", "Germany": "EU", "Spain": "EU",
    "Italy": "EU", "Belgium": "EU", "Netherlands": "EU", "Portugal": "EU",
    "Sweden": "EU", "Finland": "EU", "Denmark": "EU", "Norway": "EU",
    "Switzerland": "EU", "Austria": "EU", "Ireland": "EU", "Poland": "EU",
    "Greece": "EU", "Czech Republic": "EU", "Iceland": "EU", "Malta": "EU",
    "Cyprus": "EU", "Lithuania": "EU", "Channel Islands": "EU",
    "USA": "NA", "Canada": "NA",
    "Japan": "APAC", "Australia": "APAC", "Singapore": "APAC", "Hong Kong": "APAC",
    "Korea": "APAC", "Thailand": "APAC",
    "Brazil": "LATAM",
    "Saudi Arabia": "MENA", "United Arab Emirates": "MENA", "Bahrain": "MENA",
    "Lebanon": "MENA", "Israel": "MENA",
}


def adapt_retail_dataset(input_path: str) -> pd.DataFrame:
    """Adapt Online Retail II Excel/CSV to InsightX format."""

    ext = Path(input_path).suffix.lower()
    if ext in (".xlsx", ".xls"):
        print("Reading Excel file (this may take a moment for ~1M rows)...")
        sheets = pd.read_excel(input_path, sheet_name=None)
        df = pd.concat(sheets.values(), ignore_index=True)
    else:
        df = pd.read_csv(input_path)

    print(f"Loaded {len(df)} rows. Columns: {list(df.columns)}")

    # Normalize column names
    df.columns = df.columns.str.strip()

    # Filter out cancelled invoices (start with 'C')
    if "Invoice" in df.columns:
        before = len(df)
        df = df[~df["Invoice"].astype(str).str.startswith("C")].copy()
        print(f"Filtered {before - len(df)} cancelled invoices. Remaining: {len(df)}")

    # Drop rows with missing Customer ID
    if "Customer ID" in df.columns:
        df = df.dropna(subset=["Customer ID"]).copy()
        df["Customer ID"] = df["Customer ID"].astype(int).astype(str)

    # Drop negative quantities and prices
    if "Quantity" in df.columns:
        df = df[df["Quantity"] > 0].copy()
    if "Price" in df.columns:
        df = df[df["Price"] > 0].copy()

    # Compute line total
    if "Quantity" in df.columns and "Price" in df.columns:
        df["total_amount"] = (df["Quantity"] * df["Price"]).round(2)

    # Map columns
    rename = {
        "Invoice": "order_id",
        "StockCode": "product_id",
        "Description": "product_name",
        "Quantity": "quantity",
        "InvoiceDate": "order_date",
        "Price": "unit_price",
        "Customer ID": "customer_id",
        "Country": "customer_country",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    # Add region
    if "customer_country" in df.columns:
        df["region"] = df["customer_country"].map(COUNTRY_REGION).fillna("EU")
    else:
        df["region"] = "EU"

    # Defaults
    df["status"] = "completed"
    df["currency"] = "GBP"

    # Generate customer emails
    if "customer_id" in df.columns:
        df["customer_email"] = df["customer_id"].apply(lambda x: f"cust_{x}@retail.imported.local")

    # Select output columns
    output_cols = [
        "order_id", "customer_id", "customer_email", "customer_country",
        "order_date", "product_id", "product_name",
        "quantity", "unit_price", "total_amount",
        "status", "region", "currency",
    ]
    available = [c for c in output_cols if c in df.columns]

    result = df[available].copy()
    print(f"\nFinal dataset: {len(result)} rows")
    print(f"  Unique orders:    {result['order_id'].nunique()}")
    print(f"  Unique customers: {result['customer_id'].nunique()}")
    print(f"  Unique products:  {result['product_id'].nunique()}")
    print(f"  Date range:       {result['order_date'].min()} → {result['order_date'].max()}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Adapt Online Retail II dataset for InsightX")
    parser.add_argument("--input", required=True, help="Path to raw Excel/CSV file")
    parser.add_argument("--output", default=None, help="Output path")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        print(f"Download 'Online Retail II' from Kaggle and place in: {Path(__file__).parent.parent / 'raw'}")
        sys.exit(1)

    df = adapt_retail_dataset(str(input_path))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output) if args.output else OUTPUT_DIR / "kaggle_retail_adapted.csv"
    df.to_csv(output_path, index=False)
    print(f"\nSaved adapted dataset to: {output_path}")


if __name__ == "__main__":
    main()
