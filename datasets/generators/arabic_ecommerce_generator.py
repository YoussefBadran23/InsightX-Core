"""
InsightX — Arabic/MENA Synthetic E-Commerce Dataset Generator
Generates a realistic 50,000-order dataset with Arabic names, products,
and Middle East seasonal patterns. All text is Arabic UTF-8.

Usage:
    python arabic_ecommerce_generator.py [--orders 50000] [--seed 42]
    Output: ../output/arabic_ecommerce_50k.csv
"""

import argparse
import os
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# ── Configuration ────────────────────────────────────────────────────────────

NUM_CUSTOMERS = 5000
NUM_PRODUCTS = 500
NUM_ORDERS = 50000
SEED = 42
DATE_START = date(2023, 1, 1)
DATE_END = date(2025, 12, 31)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

# ── Arabic Data Pools ────────────────────────────────────────────────────────

MALE_FIRST_NAMES = [
    "أحمد", "محمد", "خالد", "عبدالله", "فيصل", "سلطان", "عمر", "يوسف",
    "إبراهيم", "ناصر", "سعد", "عبدالرحمن", "ماجد", "بدر", "طارق",
    "حسن", "علي", "سالم", "مشعل", "تركي", "سعود", "حمد", "راشد",
    "عبدالعزيز", "نايف", "بندر", "وليد", "هاني", "زياد", "أنس",
    "منصور", "صالح", "ياسر", "عادل", "فهد", "جاسم", "حمود", "مازن",
    "رائد", "شهاب", "كريم", "باسل", "سامي", "رامي", "أمجد",
    "عمار", "أيمن", "هيثم", "مروان", "لؤي",
]

FEMALE_FIRST_NAMES = [
    "فاطمة", "نورة", "سارة", "مريم", "ليلى", "هند", "دانة", "لمى",
    "ريم", "أمل", "رنا", "عائشة", "خلود", "منال", "سمية",
    "جواهر", "نوف", "غادة", "هدى", "سلمى", "ابتسام", "وفاء",
    "شيماء", "نجلاء", "رهف", "لينا", "آلاء", "بسمة", "حنان", "إيمان",
    "نور", "ملاك", "تالا", "سدين", "يارا", "جنى", "شهد", "وجدان",
    "أسماء", "عبير", "مها", "سحر", "رشا", "نادية", "منيرة",
    "لطيفة", "حصة", "موضي", "العنود", "الجوهرة",
]

LAST_NAMES = [
    "الشمري", "العتيبي", "القحطاني", "الدوسري", "المطيري", "الحربي",
    "السبيعي", "الغامدي", "الزهراني", "البلوي", "الشهري", "العنزي",
    "المالكي", "الحارثي", "الرشيدي", "السلمي", "البقمي", "الجهني",
    "العمري", "الأحمدي", "الشريف", "الفيفي", "العسيري", "الخالدي",
    "العلي", "المحمدي", "الناصر", "السالم", "الفهد", "البدر",
    "المنصور", "العبدالله", "الحسيني", "الهاشمي", "المصري", "الأردني",
    "الكويتي", "البحريني", "العماني", "القطري", "الإماراتي", "المغربي",
    "التميمي", "الحنبلي", "الشافعي", "الراجحي", "الدخيل", "النعيمي",
    "الكبيسي", "المهيري", "الكتبي", "الهاملي", "النيادي", "المزروعي",
    "الشحي", "الطنيجي", "الظاهري", "النقبي", "العامري", "المري",
]

# ── Products ─────────────────────────────────────────────────────────────────

PRODUCT_CATEGORIES = {
    "إلكترونيات": [
        ("سماعات بلوتوث", 120, 65), ("شاحن لاسلكي", 85, 35),
        ("ساعة ذكية", 450, 200), ("كابل USB-C", 25, 8),
        ("باور بانك 20000mAh", 150, 60), ("ماوس لاسلكي", 90, 30),
        ("لوحة مفاتيح ميكانيكية", 280, 120), ("كاميرا ويب HD", 200, 80),
        ("سبيكر بلوتوث", 180, 70), ("محول HDMI", 45, 15),
    ],
    "أزياء رجالية": [
        ("ثوب رجالي", 250, 90), ("شماغ", 80, 25),
        ("حذاء رسمي", 350, 150), ("نظارة شمسية", 200, 60),
        ("ساعة يد كلاسيك", 500, 180), ("حقيبة جلدية", 300, 100),
        ("قميص قطني", 120, 40), ("بنطلون رسمي", 180, 65),
        ("جاكيت شتوي", 400, 160), ("حزام جلد طبيعي", 150, 50),
    ],
    "أزياء نسائية": [
        ("عباية مطرزة", 350, 120), ("حقيبة يد", 280, 90),
        ("وشاح حرير", 150, 45), ("حذاء كعب عالي", 300, 110),
        ("فستان سهرة", 500, 180), ("بلوزة شيفون", 120, 40),
        ("تنورة", 160, 55), ("معطف صوف", 450, 170),
        ("إكسسوارات شعر", 60, 15), ("ساعة نسائية", 400, 150),
    ],
    "عطور ومستحضرات تجميل": [
        ("عطر عود", 350, 100), ("بخور فاخر", 120, 35),
        ("كريم مرطب", 90, 25), ("مكياج كامل", 250, 80),
        ("عطر مسك", 200, 60), ("زيت أرغان", 80, 20),
        ("معجون أسنان طبيعي", 30, 8), ("شامبو عشبي", 55, 15),
        ("كريم واقي شمس", 70, 20), ("ماسك للوجه", 45, 12),
    ],
    "أدوات منزلية": [
        ("طقم أواني ستانلس", 400, 150), ("سجادة صلاة فاخرة", 100, 30),
        ("مبخرة خشبية", 150, 40), ("طقم مفارش", 300, 100),
        ("ماكينة قهوة عربية", 500, 200), ("دلة نحاس", 200, 70),
        ("فناجين قهوة", 80, 25), ("صينية تقديم", 120, 35),
        ("مجموعة شموع معطرة", 90, 25), ("إطار صور", 60, 15),
    ],
    "رياضة ولياقة": [
        ("حذاء رياضي", 350, 130), ("دمبل 5 كغ", 100, 35),
        ("حقيبة رياضية", 180, 60), ("سجادة يوغا", 80, 20),
        ("ساعة رياضية", 400, 160), ("حبل قفز", 30, 8),
        ("كرة قدم", 120, 40), ("قميص رياضي", 90, 25),
        ("قارورة مياه", 45, 10), ("نظارة سباحة", 70, 20),
    ],
    "كتب وقرطاسية": [
        ("رواية عربية", 50, 12), ("كتاب تطوير ذات", 60, 15),
        ("مجموعة أقلام", 40, 10), ("دفتر ملاحظات جلدي", 80, 20),
        ("كتاب أطفال", 35, 8), ("تقويم سنوي", 25, 5),
        ("حقيبة لابتوب", 200, 70), ("مخطط يومي", 45, 12),
        ("كتاب طبخ عربي", 55, 14), ("قلم حبر فاخر", 150, 50),
    ],
    "أطعمة ومشروبات": [
        ("تمر عجوة المدينة", 120, 40), ("قهوة عربية فاخرة", 80, 25),
        ("عسل سدر يمني", 200, 70), ("زعفران إيراني", 150, 50),
        ("شاي مغربي", 45, 12), ("حلويات عربية مشكلة", 100, 30),
        ("زيت زيتون فلسطيني", 70, 20), ("هيل هندي", 60, 18),
        ("ماء ورد", 35, 8), ("طحينة لبنانية", 40, 10),
    ],
}

# ── Countries ────────────────────────────────────────────────────────────────

COUNTRIES = [
    {"name": "المملكة العربية السعودية", "code": "SA", "currency": "SAR", "weight": 0.35},
    {"name": "الإمارات العربية المتحدة", "code": "AE", "currency": "AED", "weight": 0.20},
    {"name": "مصر", "code": "EG", "currency": "EGP", "weight": 0.15},
    {"name": "الأردن", "code": "JO", "currency": "JOD", "weight": 0.05},
    {"name": "الكويت", "code": "KW", "currency": "KWD", "weight": 0.06},
    {"name": "قطر", "code": "QA", "currency": "QAR", "weight": 0.05},
    {"name": "البحرين", "code": "BH", "currency": "BHD", "weight": 0.03},
    {"name": "عمان", "code": "OM", "currency": "OMR", "weight": 0.04},
    {"name": "العراق", "code": "IQ", "currency": "IQD", "weight": 0.04},
    {"name": "المغرب", "code": "MA", "currency": "MAD", "weight": 0.03},
]

PAYMENT_METHODS = ["بطاقة ائتمان", "Apple Pay", "تحويل بنكي", "الدفع عند الاستلام", "STC Pay", "مدى"]
ACQUISITION_CHANNELS = ["organic_search", "paid_ads", "referral", "email", "social"]

# ── Arabic Review Comments ───────────────────────────────────────────────────

POSITIVE_COMMENTS = [
    "منتج ممتاز وتوصيل سريع", "جودة عالية وسعر مناسب", "أنصح بالشراء",
    "تجربة شراء ممتازة", "المنتج فاق توقعاتي", "خدمة عملاء رائعة",
    "تغليف أنيق وجودة عالية", "سأشتري مرة أخرى بالتأكيد",
    "أفضل منتج اشتريته هذا العام", "سعر منافس وجودة ممتازة",
    "التوصيل كان أسرع من المتوقع", "منتج أصلي ١٠٠٪",
]

NEGATIVE_COMMENTS = [
    "المنتج لا يطابق الوصف", "تأخر التوصيل كثيراً", "جودة سيئة",
    "لن أشتري من هنا مرة أخرى", "المنتج وصل مكسور",
    "خدمة العملاء لم تساعدني", "السعر مبالغ فيه", "لون مختلف عن الصورة",
    "حجم غير مناسب", "تغليف سيء جداً",
]

NEUTRAL_COMMENTS = [
    "المنتج عادي", "مقبول بالنسبة للسعر", "لا بأس",
    "منتج متوسط الجودة", "يحتاج تحسين", "عادي جداً",
    "ليس سيئاً ولكن ليس ممتازاً", "يستحق التجربة",
]


# ── Seasonal Pattern ─────────────────────────────────────────────────────────

def _seasonal_weight(d: date) -> float:
    """Return a multiplier for order probability based on MENA seasonal patterns."""
    month = d.month
    day = d.day
    w = 1.0

    # Ramadan approximate window (shifts yearly, using fixed proxy for synthetic data)
    if (month == 3 and day >= 10) or (month == 4 and day <= 10):
        w *= 1.4  # +40% during Ramadan

    # Eid al-Fitr (~April 10-15)
    if month == 4 and 10 <= day <= 18:
        w *= 1.6  # +60% Eid spike

    # Eid al-Adha (~June 15-20 proxy)
    if month == 6 and 15 <= day <= 22:
        w *= 1.3

    # Saudi National Day (Sept 23)
    if month == 9 and 20 <= day <= 26:
        w *= 1.25

    # White Friday / Black Friday (late Nov)
    if month == 11 and day >= 20:
        w *= 1.5

    # Summer dip (July-Aug)
    if month in (7, 8):
        w *= 0.8

    return w


# ── Generator Functions ──────────────────────────────────────────────────────

def generate_customers(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Generate n unique Arabic customers."""
    rows = []
    used_emails = set()

    for i in range(n):
        gender = rng.choice(["male", "female"])
        first = rng.choice(MALE_FIRST_NAMES if gender == "male" else FEMALE_FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        full_name = f"{first} {last}"

        # Generate unique email
        base_email = f"{first.replace(' ', '')}_{last.replace(' ', '')}_{i}"
        email = f"{base_email}@insightx-test.com"
        while email in used_emails:
            email = f"{base_email}_{rng.integers(100, 999)}@insightx-test.com"
        used_emails.add(email)

        country = rng.choice(COUNTRIES, p=[c["weight"] for c in COUNTRIES])

        rows.append({
            "customer_id": f"CUS-{i+1:05d}",
            "customer_name": full_name,
            "customer_email": email,
            "customer_country": country["name"],
            "customer_country_code": country["code"],
            "customer_currency": country["currency"],
            "customer_region": "MENA",
            "customer_gender": "ذكر" if gender == "male" else "أنثى",
        })

    return pd.DataFrame(rows)


def generate_products(rng: np.random.Generator) -> pd.DataFrame:
    """Generate products from Arabic category pools."""
    rows = []
    idx = 1
    for category, items in PRODUCT_CATEGORIES.items():
        for name, price, cost in items:
            rows.append({
                "product_id": f"SKU-{idx:04d}",
                "product_name": name,
                "product_category": category,
                "unit_price": round(price * (0.9 + rng.random() * 0.2), 2),  # ±10% variance
                "cost_price": round(cost * (0.9 + rng.random() * 0.2), 2),
            })
            idx += 1
    return pd.DataFrame(rows)


def generate_orders(
    n_orders: int,
    customers: pd.DataFrame,
    products: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Generate n_orders with realistic patterns."""
    # Build date pool with seasonal weighting
    total_days = (DATE_END - DATE_START).days
    all_dates = [DATE_START + timedelta(days=d) for d in range(total_days + 1)]
    weights = np.array([_seasonal_weight(d) for d in all_dates], dtype=float)
    weights /= weights.sum()

    rows = []
    for i in range(n_orders):
        # Pick date with seasonal weighting
        order_date = rng.choice(all_dates, p=weights)

        # Pick customer
        cust = customers.iloc[rng.integers(0, len(customers))]

        # Pick 1-5 items for this order
        n_items = rng.choice([1, 1, 1, 2, 2, 3, 3, 4, 5])  # weighted toward fewer
        order_products = products.sample(n=n_items, random_state=int(rng.integers(0, 1_000_000)))

        for _, prod in order_products.iterrows():
            quantity = int(rng.choice([1, 1, 1, 2, 2, 3, 4, 5]))
            unit_price = prod["unit_price"]
            line_total = round(quantity * unit_price, 2)

            # Discount: 30% chance of discount
            discount = round(line_total * rng.choice([0, 0, 0, 0.05, 0.10, 0.15, 0.20]), 2)

            # Status distribution: 80% completed, 10% pending, 5% refunded, 5% cancelled
            status = rng.choice(
                ["completed", "completed", "completed", "completed",
                 "completed", "completed", "completed", "completed",
                 "pending", "pending", "refunded", "cancelled"]
            )

            # Return flag (only for completed orders, ~8% return rate)
            return_flag = status == "completed" and rng.random() < 0.08

            # Delivery days (3-15 days, skewed toward 5-7)
            delivery_days = int(rng.choice([3, 4, 5, 5, 6, 6, 7, 7, 8, 9, 10, 12, 15]))

            # Comment: 25% chance
            comment = ""
            if rng.random() < 0.25:
                if rng.random() < 0.6:
                    comment = rng.choice(POSITIVE_COMMENTS)
                elif rng.random() < 0.7:
                    comment = rng.choice(NEUTRAL_COMMENTS)
                else:
                    comment = rng.choice(NEGATIVE_COMMENTS)

            rows.append({
                "order_id": f"ORD-{i+1:06d}",
                "customer_id": cust["customer_id"],
                "customer_name": cust["customer_name"],
                "customer_email": cust["customer_email"],
                "customer_country": cust["customer_country"],
                "order_date": order_date.isoformat(),
                "product_id": prod["product_id"],
                "product_name": prod["product_name"],
                "product_category": prod["product_category"],
                "quantity": quantity,
                "unit_price": unit_price,
                "total_amount": line_total,
                "discount_amount": discount,
                "cost_price": prod["cost_price"],
                "status": status,
                "region": "MENA",
                "currency": cust["customer_currency"],
                "payment_method": rng.choice(PAYMENT_METHODS),
                "acquisition_channel": rng.choice(ACQUISITION_CHANNELS),
                "delivery_days": delivery_days,
                "return_flag": return_flag,
                "comment_text": comment,
            })

    return pd.DataFrame(rows)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate Arabic e-commerce dataset")
    parser.add_argument("--orders", type=int, default=NUM_ORDERS, help="Number of orders")
    parser.add_argument("--customers", type=int, default=NUM_CUSTOMERS, help="Number of customers")
    parser.add_argument("--seed", type=int, default=SEED, help="Random seed")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    random.seed(args.seed)

    print(f"Generating {args.customers} customers...")
    customers = generate_customers(args.customers, rng)

    print(f"Generating {len(PRODUCT_CATEGORIES)} categories of products...")
    products = generate_products(rng)
    print(f"  → {len(products)} products created")

    print(f"Generating {args.orders} orders with MENA seasonal patterns...")
    orders = generate_orders(args.orders, customers, products, rng)
    print(f"  → {len(orders)} order line items generated")

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"arabic_ecommerce_{args.orders // 1000}k.csv"

    # UTF-8 with BOM for Excel compatibility with Arabic
    orders.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\nSaved to: {output_path}")
    print(f"File size: {output_path.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"Columns: {list(orders.columns)}")

    # Quick stats
    print(f"\nDataset Stats:")
    print(f"  Unique customers: {orders['customer_id'].nunique()}")
    print(f"  Unique products:  {orders['product_id'].nunique()}")
    print(f"  Unique orders:    {orders['order_id'].nunique()}")
    print(f"  Date range:       {orders['order_date'].min()} → {orders['order_date'].max()}")
    print(f"  Total revenue:    {orders['total_amount'].sum():,.2f}")


if __name__ == "__main__":
    main()
