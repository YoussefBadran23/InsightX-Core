"""
Kaggle "E-Commerce Shipping Dataset" / "Brazilian E-Commerce" Adapter
Maps Kaggle columns → InsightX-compatible CSV format.

Usage:
    1. Download dataset from Kaggle and place CSV(s) in ../raw/
    2. python kaggle_ecommerce_adapter.py --input ../raw/E_Commerce_Shipping.csv
    3. Output: ../output/kaggle_ecommerce_adapted.csv

Supported datasets:
    - "E-Commerce Shipping Dataset" (kaggle.com/datasets/prachi13/customer-analytics)
    - "Brazilian E-Commerce" (kaggle.com/datasets/olistbr/brazilian-ecommerce)
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def adapt_shipping_dataset(input_path: str) -> pd.DataFrame:
    """Adapt the E-Commerce Shipping Dataset."""
    df = pd.read_csv(input_path)
    print(f"Loaded {len(df)} rows. Columns: {list(df.columns)}")

    # Common column mappings — adapt based on what's actually in the file
    column_map = {}
    col_lower = {c.lower(): c for c in df.columns}

    # Try to map known patterns
    known_mappings = {
        "id": "order_id",
        "customer_id": "customer_id",
        "order_date": "order_date",
        "ship_date": "ship_date",
        "mode_of_shipment": "payment_method",
        "customer_care_calls": None,
        "customer_rating": None,
        "cost_of_the_product": "unit_price",
        "prior_purchases": None,
        "product_importance": "product_category",
        "gender": "customer_gender",
        "discount_offered": "discount_amount",
        "weight_in_gms": None,
        "reached.on_time_y.n": "delivery_status",
    }

    for src, dst in known_mappings.items():
        if src.lower() in col_lower and dst:
            column_map[col_lower[src.lower()]] = dst

    df = df.rename(columns=column_map)

    # Ensure required columns exist with defaults
    if "order_id" not in df.columns:
        df["order_id"] = [f"KAG-{i+1:06d}" for i in range(len(df))]
    if "customer_id" not in df.columns:
        df["customer_id"] = [f"KCUS-{i+1:05d}" for i in range(len(df))]
    if "order_date" not in df.columns:
        # Generate random dates if not present
        import numpy as np
        rng = np.random.default_rng(42)
        dates = pd.date_range("2023-01-01", "2025-12-31", periods=len(df))
        df["order_date"] = rng.choice(dates, size=len(df))
    if "quantity" not in df.columns:
        df["quantity"] = 1
    if "total_amount" not in df.columns and "unit_price" in df.columns:
        df["total_amount"] = df["unit_price"] * df.get("quantity", 1)
    if "product_id" not in df.columns:
        df["product_id"] = [f"KPRD-{i % 200 + 1:04d}" for i in range(len(df))]
    if "status" not in df.columns:
        df["status"] = "completed"
    if "region" not in df.columns:
        df["region"] = "NA"
    if "currency" not in df.columns:
        df["currency"] = "USD"

    # Select and order output columns
    output_cols = [
        "order_id", "customer_id", "order_date", "product_id",
        "quantity", "unit_price", "total_amount", "discount_amount",
        "status", "region", "currency", "payment_method",
    ]
    available = [c for c in output_cols if c in df.columns]

    return df[available]


def main():
    parser = argparse.ArgumentParser(description="Adapt Kaggle e-commerce dataset for InsightX")
    parser.add_argument("--input", required=True, help="Path to raw Kaggle CSV")
    parser.add_argument("--output", default=None, help="Output path (default: ../output/)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        print(f"Download a Kaggle dataset and place it in: {Path(__file__).parent.parent / 'raw'}")
        sys.exit(1)

    df = adapt_shipping_dataset(str(input_path))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output) if args.output else OUTPUT_DIR / "kaggle_ecommerce_adapted.csv"
    df.to_csv(output_path, index=False)
    print(f"\nSaved adapted dataset to: {output_path}")
    print(f"Rows: {len(df)}, Columns: {list(df.columns)}")


if __name__ == "__main__":
    main()
