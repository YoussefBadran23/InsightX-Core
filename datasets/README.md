# InsightX Datasets

## Directory Structure

```
datasets/
├── raw/
│   ├── kaggle/          # Manually downloaded Kaggle CSVs
│   │   ├── E-Commerce Data.csv
│   │   └── online_retail_II.csv
│   └── generated/       # Output from synthetic generators
│       └── arabic_ecommerce_50k.csv
├── output/              # Adapter-transformed CSVs (ready for upload)
├── adapters/            # Python scripts that normalize Kaggle CSVs
│   ├── kaggle_ecommerce_adapter.py
│   └── kaggle_retail_adapter.py
└── generators/          # Synthetic data generators
    └── arabic_ecommerce_generator.py
```

## Kaggle Datasets (Manual Download)

### 1. E-Commerce Shipping Dataset
- **Source:** https://www.kaggle.com/datasets/prachi13/customer-analytics
- **File:** `raw/kaggle/E-Commerce Data.csv`
- **Adapter:** `adapters/kaggle_ecommerce_adapter.py`

### 2. Online Retail II (UCI)
- **Source:** https://www.kaggle.com/datasets/mashlyn/online-retail-ii-uci
- **File:** `raw/kaggle/online_retail_II.csv`
- **Adapter:** `adapters/kaggle_retail_adapter.py`

## Synthetic Data Generator

### Arabic E-Commerce (MENA)
Generate 50K Arabic e-commerce orders with MENA regional patterns:

```bash
cd datasets/generators
python arabic_ecommerce_generator.py --orders 50000 --customers 2000 --seed 42
```

Output saved to: `raw/generated/arabic_ecommerce_50k.csv`

Features:
- Arabic product names, customer names, and reviews
- 10 MENA countries (SA 35%, UAE 20%, EG 15%, etc.)
- Seasonal patterns: Ramadan +40%, Eid +60%, White Friday +50%
- Payment methods in Arabic
- UTF-8 BOM encoding for Excel compatibility

## Running Adapters

```bash
# Transform Kaggle E-Commerce dataset
python adapters/kaggle_ecommerce_adapter.py

# Transform Online Retail II dataset
python adapters/kaggle_retail_adapter.py
```

Transformed files are saved to `output/` and ready for upload to InsightX.
