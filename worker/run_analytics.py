"""Standalone analytics runner — execute any registered module against a CSV.

No Docker, no Celery, no Postgres. Just `python` + the seed CSVs.

Usage examples
--------------

    # Run a single module on the English seed and print evaluation
    python run_analytics.py --csv ../datasets/output/english_seed.csv \\
                            --module A01 --evaluate

    # Run on the dirty variants to test resilience
    python run_analytics.py --csv ../datasets/output/dirty_en_03_bad_types.csv \\
                            --module A01 --evaluate

    # Run every registered module
    python run_analytics.py --csv ../datasets/output/english_seed.csv --all --evaluate

    # List what's available
    python run_analytics.py --list

    # Save full JSON output for later inspection
    python run_analytics.py --csv ../datasets/output/english_seed.csv \\
                            --module A01 --save out/A01.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

# Ensure /worker is on sys.path so `from tasks.analytics import ...` works
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tasks.analytics import _base  # noqa: E402  (import after path setup)
import tasks.analytics  # noqa: E402,F401  (triggers @register decorators)

REGISTRY = _base.ANALYTICS_REGISTRY


# ── Module-specific evaluators ─────────────────────────────────────────────
# Each evaluator prints sanity checks and quality metrics for one module.

def _eval_a01(df: pd.DataFrame, result: dict) -> None:
    s = result.get("summary", {})
    by_p = result.get("by_period", {})
    print(f"  Total revenue:     {s.get('total', 0):>14,.2f}")
    print(f"  Order count:       {s.get('order_count', 0):>14,}")
    print(f"  Daily average:     {s.get('avg_daily', 0):>14,.2f}")
    print(f"  Weekly average:    {s.get('avg_weekly', 0):>14,.2f}")
    print(f"  Monthly average:   {s.get('avg_monthly', 0):>14,.2f}")
    dr = s.get("date_range", {})
    print(f"  Date range:        {dr.get('start')} → {dr.get('end')}  ({dr.get('n_days')} days)")
    print(f"  Daily buckets:     {len(by_p.get('daily', []))}")
    print(f"  Weekly buckets:    {len(by_p.get('weekly', []))}")
    print(f"  Monthly buckets:   {len(by_p.get('monthly', []))}")

    by_region = result.get("by_region", [])
    if by_region:
        print(f"\n  Top regions by revenue:")
        for r in by_region[:5]:
            key = r.get("region") or r.get("Region")
            print(f"    {key:20s}  {r.get('revenue', 0):>12,.2f}  ({r.get('pct', 0):>5.1f}%)")

    by_curr = result.get("by_currency", [])
    if by_curr:
        print(f"\n  Currency split:")
        for r in by_curr:
            key = r.get("currency") or r.get("Currency")
            print(f"    {key:6s}  {r.get('revenue', 0):>12,.2f}  ({r.get('pct', 0):>5.1f}%)")

    top = result.get("top_days", [])
    if top:
        print(f"\n  Top 5 revenue days:")
        for r in top[:5]:
            print(f"    {r.get('date')}  {r.get('revenue', 0):>12,.2f}")

    disc = result.get("discount_summary")
    if disc:
        print(f"\n  Discount summary:")
        print(f"    Total discount:     {disc.get('total_discount', 0):>12,.2f}")
        print(f"    Discount %:         {disc.get('discount_pct', 0):>12.2f}")
        print(f"    Orders w/ discount: {disc.get('orders_with_disc', 0):>12,}")

    # ── Sanity / quality flags ───────────────────────────────────────────
    print(f"\n  Quality flags:")
    flags = []
    if s.get("total", 0) <= 0:
        flags.append("✗ headline revenue is non-positive")
    if s.get("order_count", 0) == 0:
        flags.append("✗ zero orders after coercion")
    daily = by_p.get("daily", [])
    if len(daily) >= 3:
        revenues = [d["revenue"] for d in daily]
        avg = sum(revenues) / len(revenues)
        peak = max(revenues)
        if peak > 10 * avg:
            flags.append(f"⚠ one day at {peak:,.0f} is >10× the average ({avg:,.0f}) — investigate")
    n_days = s.get("date_range", {}).get("n_days", 0)
    if n_days > 0 and len(daily) / n_days < 0.10:
        flags.append(f"⚠ only {len(daily)} active days out of {n_days} — sparse data")
    if not flags:
        print(f"    ✓ all checks passed")
    else:
        for f in flags:
            print(f"    {f}")


def _eval_a02(df: pd.DataFrame, result: dict) -> None:
    s = result.get("summary", {})
    segments = result.get("segments", [])
    score_dist = result.get("score_distribution", {})
    top = result.get("top_customers", [])

    if result.get("warning"):
        print(f"  ⚠ {result['warning']}")
        return

    print(f"  Customers analyzed: {s.get('n_customers', 0):>10,}")
    print(f"  Snapshot date:      {s.get('snapshot_date'):>10s}")
    print(f"  Total revenue:      {s.get('total_revenue', 0):>14,.2f}")
    print(f"  Avg recency (days): {s.get('avg_recency', 0):>10.1f}")
    print(f"  Avg frequency:      {s.get('avg_frequency', 0):>10.2f}")
    print(f"  Avg monetary:       {s.get('avg_monetary', 0):>14,.2f}")

    if segments:
        print(f"\n  Segments (by revenue contribution):")
        print(f"    {'SEGMENT':<22s} {'CUST':>6s} {'CUST%':>7s} {'REVENUE':>14s} {'REV%':>7s} {'AVG $':>12s}")
        for seg in segments:
            print(f"    {seg['segment']:<22s} {seg['count']:>6,} {seg['pct']:>6.1f}% "
                  f"{seg['revenue']:>14,.2f} {seg['rev_pct']:>6.1f}% {seg['avg_monetary']:>12,.2f}")

    if score_dist:
        print(f"\n  Score distribution (1=worst, 5=best):")
        for dim in ("R", "F", "M"):
            row = score_dist.get(dim, {})
            cells = " ".join(f"{i}:{row.get(str(i), 0):>5,}" for i in range(1, 6))
            print(f"    {dim}: {cells}")

    if top:
        print(f"\n  Top 5 customers by monetary value:")
        print(f"    {'CUSTOMER':<28s} {'R':>3s} {'F':>5s} {'M':>14s} {'RFM':>5s}  SEGMENT")
        for c in top[:5]:
            cid = c["customer_id"][:26]
            print(f"    {cid:<28s} {c['recency_days']:>3} {c['frequency']:>5} "
                  f"{c['monetary']:>14,.2f} {c['RFM_score']:>5s}  {c['segment']}")

    # ── Sanity / quality flags ───────────────────────────────────────────────
    print(f"\n  Quality flags:")
    flags = []
    if s.get("n_customers", 0) == 0:
        flags.append("✗ zero customers segmented")
    n_segs = len(segments)
    if n_segs <= 2:
        flags.append(f"⚠ only {n_segs} segments emerged — RFM may not differentiate this dataset")
    other = next((seg for seg in segments if seg["segment"] == "Other"), None)
    if other and other["pct"] > 30:
        flags.append(f"⚠ '{other['pct']:.1f}%' of customers fell into 'Other' — segment rules may need tuning")
    champs = next((seg for seg in segments if seg["segment"] == "Champions"), None)
    if champs:
        if champs["rev_pct"] < 5:
            flags.append(f"⚠ Champions only contribute {champs['rev_pct']:.1f}% of revenue — unusually flat")
        if champs["pct"] > 50:
            flags.append(f"⚠ {champs['pct']:.1f}% of customers labeled Champions — quintile cutoff seems off")
    if not flags:
        print(f"    ✓ all checks passed")
    else:
        for f in flags:
            print(f"    {f}")


def _eval_a03(df: pd.DataFrame, result: dict) -> None:
    s = result.get("summary", {})
    top_products = result.get("top_products", [])
    pairs = result.get("top_pairs", [])
    triples = result.get("top_triples", [])

    print(f"  Orders:                {s.get('n_orders', 0):>10,}")
    print(f"  Unique products:       {s.get('n_unique_products', 0):>10,}")
    print(f"  Multi-item baskets:    {s.get('n_multi_item_baskets', 0):>10,}  "
          f"({s.get('multi_item_pct', 0):>5.2f}%)")
    print(f"  Avg basket size:       {s.get('avg_basket_size', 0):>10.3f}")
    print(f"  Max basket size:       {s.get('max_basket_size', 0):>10,}")

    if result.get("warning"):
        print(f"\n  ⚠ {result['warning']}")

    if top_products:
        print(f"\n  Top {len(top_products[:10])} products by basket presence:")
        print(f"    {'PRODUCT':<35s} {'FREQ':>8s} {'SUPPORT':>9s}")
        for p in top_products[:10]:
            name = (p.get("name") or p["product_id"])[:33]
            print(f"    {name:<35s} {p['frequency']:>8,} {p['support']*100:>8.2f}%")

    if pairs:
        print(f"\n  Top {len(pairs[:10])} association rules (by lift):")
        print(f"    {'A → B':<55s} {'CO-OCC':>7s} {'CONF':>7s} {'LIFT':>7s}")
        for r in pairs[:10]:
            ant = (r.get("antecedent_name") or r["antecedent"])[:24]
            con = (r.get("consequent_name") or r["consequent"])[:24]
            rule = f"{ant} → {con}"[:55]
            print(f"    {rule:<55s} {r['co_occurrences']:>7,} "
                  f"{r['confidence']*100:>6.2f}% {r['lift']:>7.2f}")
    elif not result.get("warning"):
        print(f"\n  (no pairs above min support threshold)")

    if triples:
        print(f"\n  Top {len(triples[:5])} item triples:")
        for t in triples[:5]:
            names = [(n or pid)[:18] for n, pid in zip(t.get("names", []), t["items"])]
            print(f"    {' + '.join(names):<60s}  ×{t['co_occurrences']}  ({t['support']*100:.2f}%)")

    # ── Quality flags ───────────────────────────────────────────────────────
    print(f"\n  Quality flags:")
    flags = []
    if s.get("n_orders", 0) == 0:
        flags.append("✗ no orders ingested")
    if s.get("multi_item_pct", 0) < 5:
        flags.append(f"⚠ only {s.get('multi_item_pct', 0):.1f}% multi-item baskets — basket analysis has limited signal")
    if not pairs and not result.get("warning"):
        flags.append("⚠ pair count is empty but multi-item baskets exist — check min support tuning")
    if pairs:
        max_lift = max(r["lift"] for r in pairs)
        if max_lift < 1.5:
            flags.append(f"⚠ best lift is only {max_lift:.2f} — associations are weak")
    if not flags:
        print(f"    ✓ all checks passed")
    else:
        for f in flags:
            print(f"    {f}")


def _eval_a04(df: pd.DataFrame, result: dict) -> None:
    s = result.get("summary", {})
    dist = result.get("margin_distribution", {})

    if result.get("warning"):
        print(f"  ⚠ {result['warning']}")
        return

    print(f"  Total revenue:        {s.get('total_revenue', 0):>14,.2f}")
    print(f"  Total cost:           {s.get('total_cost', 0):>14,.2f}")
    print(f"  Gross margin:         {s.get('gross_margin', 0):>14,.2f}  "
          f"({s.get('gross_margin_pct', 0):>5.2f}%)")
    print(f"  Orders analyzed:      {s.get('n_orders', 0):>14,}")
    print(f"  Loss-making orders:   {s.get('n_loss_making', 0):>14,}  "
          f"({s.get('loss_making_pct', 0):>5.2f}%)")
    print(f"  Avg order margin:     {s.get('avg_order_margin', 0):>14,.2f}  "
          f"({s.get('avg_order_margin_pct', 0):>5.2f}%)")

    if dist:
        total = sum(dist.values()) or 1
        print(f"\n  Margin distribution (per order):")
        for label in ("negative", "0-10%", "10-25%", "25-50%", "50-75%", "75-100%", "above_100%"):
            n = dist.get(label, 0)
            bar = "█" * int(40 * n / total)
            print(f"    {label:<12s} {n:>6,}  {bar}")

    by_cat = result.get("by_category", [])
    if by_cat:
        print(f"\n  Top categories by absolute margin:")
        print(f"    {'CATEGORY':<28s} {'REVENUE':>12s} {'MARGIN':>12s} {'M%':>7s} {'REV%':>7s}")
        for r in by_cat[:8]:
            cat = r["category"][:26]
            print(f"    {cat:<28s} {r['revenue']:>12,.0f} {r['margin']:>12,.0f} "
                  f"{r['margin_pct']:>6.2f}% {r['rev_share_pct']:>6.2f}%")

    by_region = result.get("by_region", [])
    if by_region:
        print(f"\n  Margin by region:")
        for r in by_region[:6]:
            print(f"    {r['region']:<22s} {r['revenue']:>12,.0f}  margin {r['margin']:>10,.0f}  ({r['margin_pct']:>5.2f}%)")

    by_period = (result.get("by_period") or {}).get("monthly", [])
    if by_period:
        print(f"\n  Recent monthly margin:")
        for r in by_period[-6:]:
            print(f"    {r['period']:<10s}  rev {r['revenue']:>10,.0f}  margin {r['margin']:>10,.0f}  ({r['margin_pct']:>5.2f}%)")

    top_prod = result.get("top_margin_products", [])
    if top_prod:
        print(f"\n  Top 5 margin contributors:")
        for r in top_prod[:5]:
            name = (r.get("name") or r["product_id"])[:30]
            print(f"    {name:<32s} margin {r['margin']:>10,.2f}  ({r['margin_pct']:>5.2f}%)  ×{r['orders']}")

    loss = result.get("loss_makers", [])
    if loss:
        print(f"\n  Worst 5 loss-makers:")
        for r in loss[:5]:
            name = (r.get("name") or r["product_id"])[:30]
            print(f"    {name:<32s} margin {r['margin']:>10,.2f}  ({r['margin_pct']:>5.2f}%)  ×{r['orders']}")

    # ── Quality flags ───────────────────────────────────────────────────────
    print(f"\n  Quality flags:")
    flags = []
    gm = s.get("gross_margin_pct", 0)
    if s.get("n_orders", 0) == 0:
        flags.append("✗ no orders survived coercion")
    if gm < 0:
        flags.append(f"✗ overall gross margin is negative ({gm:.2f}%) — costs exceed revenue")
    if 0 <= gm < 5:
        flags.append(f"⚠ thin overall gross margin ({gm:.2f}%) — pricing or cost data may need review")
    if gm > 95:
        flags.append(f"⚠ unusually high gross margin ({gm:.2f}%) — verify cost capture is complete")
    lp = s.get("loss_making_pct", 0)
    if lp > 30:
        flags.append(f"⚠ {lp:.1f}% of orders are loss-making — high concentration")
    above_100 = dist.get("above_100%", 0)
    if above_100 > 0:
        flags.append(f"⚠ {above_100} orders show margin >100% — possible data error (negative cost?)")
    if not flags:
        print(f"    ✓ all checks passed")
    else:
        for f in flags:
            print(f"    {f}")


def _eval_a05(df: pd.DataFrame, result: dict) -> None:
    s = result.get("summary", {})
    matrix = result.get("cohort_matrix", [])
    avg_curve = result.get("avg_retention_curve", [])

    if result.get("warning"):
        print(f"  ⚠ {result['warning']}")
        return

    print(f"  Cohorts:              {s.get('n_cohorts', 0):>10,}")
    print(f"  Customers:            {s.get('n_customers', 0):>10,}")
    print(f"  Cohort range:         {s.get('first_cohort')} → {s.get('last_cohort')}")
    print(f"  Max month offset:     {s.get('max_month_offset', 0):>10,}")
    print(f"  Avg retention M1:     {s.get('avg_retention_m1', 0):>10.2f}%")
    print(f"  Avg retention M3:     {s.get('avg_retention_m3', 0):>10.2f}%")
    print(f"  Avg retention M6:     {s.get('avg_retention_m6', 0):>10.2f}%")
    print(f"  Avg retention M12:    {s.get('avg_retention_m12', 0):>10.2f}%")

    best = result.get("best_cohort_m3")
    worst = result.get("worst_cohort_m3")
    if best:
        print(f"\n  Best  M3 cohort: {best['cohort']}  size={best['size']:,}  rate={best['rate']:.2f}%")
    if worst:
        print(f"  Worst M3 cohort: {worst['cohort']}  size={worst['size']:,}  rate={worst['rate']:.2f}%")

    # Heatmap-ish ASCII rendering: M0..M11 columns for first 12 cohorts.
    if matrix:
        max_cols = min(12, max(len(c["retention"]) for c in matrix))
        header_offsets = [f"M{i:>2}" for i in range(max_cols)]
        print(f"\n  Retention heatmap (first 12 months, first 15 cohorts):")
        print(f"    {'COHORT':<10s} {'SIZE':>6s}  " + " ".join(f"{h:>5s}" for h in header_offsets))
        for c in matrix[:15]:
            cells = []
            for off in range(max_cols):
                if off < len(c["retention"]):
                    rate = c["retention"][off]["rate"]
                    cells.append(f"{rate:>4.1f}%" if rate is not None else "  -- ")
                else:
                    cells.append("  -- ")
            print(f"    {c['cohort']:<10s} {c['size']:>6,}  " + " ".join(cells))

    if avg_curve:
        print(f"\n  Avg retention curve (% of cohort still active by month):")
        for r in avg_curve[:13]:
            bar = "█" * int(r["rate"] / 2)  # 50% → 25 chars
            print(f"    M{r['month_offset']:>2}  ({r['cohorts_observed']:>2} cohorts)  {r['rate']:>5.2f}%  {bar}")

    # ── Quality flags ───────────────────────────────────────────────────────
    print(f"\n  Quality flags:")
    flags = []
    if s.get("n_cohorts", 0) < 3:
        flags.append(f"⚠ only {s.get('n_cohorts', 0)} cohorts — too few for meaningful trend analysis")
    if s.get("max_month_offset", 0) == 0:
        flags.append("⚠ no cross-month repeat purchases — all repeat orders happen within the cohort's acquisition month")
    else:
        m1 = s.get("avg_retention_m1", 0)
        if m1 < 5:
            flags.append(f"⚠ very low M1 retention ({m1:.2f}%) — most customers never return")
        if m1 > 90:
            flags.append(f"⚠ M1 retention is {m1:.2f}% — verify customer_id is granular enough (one ID per real person)")
    if not flags:
        print(f"    ✓ all checks passed")
    else:
        for f in flags:
            print(f"    {f}")


def _eval_a06(df: pd.DataFrame, result: dict) -> None:
    s = result.get("summary", {})
    by_region = result.get("by_region", [])
    by_country = result.get("by_country", [])
    by_city = result.get("by_city", [])
    trend = (result.get("region_trend") or {}).get("monthly", [])
    geo_points = result.get("geo_points", [])

    if result.get("warning"):
        print(f"  ⚠ {result['warning']}")
        return

    print(f"  Total revenue:       {s.get('total_revenue', 0):>14,.2f}")
    print(f"  Regions:             {s.get('n_regions', 0):>10,}")
    print(f"  Countries:           {s.get('n_countries', 0):>10,}")
    print(f"  Cities:              {s.get('n_cities', 0):>10,}")
    tr = s.get("top_region")
    if tr:
        print(f"  Top region:          {tr['name']:<20s}  {tr['revenue']:>12,.2f}  ({tr['pct']:>5.2f}%)")
    tc = s.get("top_country")
    if tc:
        print(f"  Top country:         {tc['name']:<20s}  {tc['revenue']:>12,.2f}  ({tc['pct']:>5.2f}%)")
    print(f"  Top 3 region share:  {s.get('top_3_share_pct', 0):>10.2f}%")
    print(f"  Top 5 region share:  {s.get('top_5_share_pct', 0):>10.2f}%")
    print(f"  Top 10 region share: {s.get('top_10_share_pct', 0):>10.2f}%")
    hhi = s.get("herfindahl_index_region", 0)
    print(f"  HHI (regions):       {hhi:>10.4f}  ({s.get('herfindahl_label', '?')})")

    if by_region:
        print(f"\n  Revenue by region:")
        print(f"    {'#':>2s} {'REGION':<20s} {'REVENUE':>14s} {'ORDERS':>8s} {'CUST':>7s} {'AOV':>9s} {'%':>7s}")
        for r in by_region[:10]:
            print(f"    {r['rank']:>2} {r['region']:<20s} {r['revenue']:>14,.2f} "
                  f"{r['orders']:>8,} {r['customers']:>7,} {r['aov']:>9,.2f} {r['pct']:>6.2f}%")

    if by_country and by_country != by_region:
        print(f"\n  Revenue by country (top 10):")
        print(f"    {'#':>2s} {'COUNTRY':<20s} {'REVENUE':>14s} {'ORDERS':>8s} {'%':>7s}")
        for r in by_country[:10]:
            print(f"    {r['rank']:>2} {r['country'][:18]:<20s} {r['revenue']:>14,.2f} "
                  f"{r['orders']:>8,} {r['pct']:>6.2f}%")

    if by_city:
        print(f"\n  Top 10 cities by revenue:")
        print(f"    {'#':>2s} {'CITY':<24s} {'REVENUE':>14s} {'ORDERS':>8s} {'%':>7s}")
        for r in by_city[:10]:
            city = (r["customer_city"] or "")[:22]
            print(f"    {r['rank']:>2} {city:<24s} {r['revenue']:>14,.2f} "
                  f"{r['orders']:>8,} {r['pct']:>6.2f}%")

    if trend:
        # Recent 6-month region trend (pivot wide for readability)
        recent_periods = sorted({r["period"] for r in trend})[-6:]
        regions_in_trend = sorted({r["region"] for r in trend})[:5]
        print(f"\n  Recent 6-month region revenue:")
        header = f"    {'PERIOD':<10s} " + " ".join(f"{r[:10]:>11s}" for r in regions_in_trend)
        print(header)
        for p in recent_periods:
            row = {r["region"]: r["revenue"] for r in trend if r["period"] == p}
            cells = " ".join(f"{row.get(r, 0):>11,.0f}" for r in regions_in_trend)
            print(f"    {p:<10s} {cells}")

    if geo_points:
        print(f"\n  Geo points: {len(geo_points)} clusters (rounded to 0.01° grid)")

    # ── Quality flags ───────────────────────────────────────────────────────
    print(f"\n  Quality flags:")
    flags = []
    n_regs = s.get("n_regions", 0)
    if n_regs == 0:
        flags.append("✗ no region values found")
    if n_regs == 1:
        flags.append("⚠ only 1 region — geographic analysis falls back to country/city")
    if hhi > 0.5:
        flags.append(f"⚠ extreme regional concentration (HHI={hhi:.4f}) — top region dominates")
    top1 = s.get("top_region", {}).get("pct", 0) if s.get("top_region") else 0
    if top1 > 90:
        flags.append(f"⚠ {top1:.1f}% of revenue from a single region — single-market exposure")
    if not flags:
        print(f"    ✓ all checks passed")
    else:
        for f in flags:
            print(f"    {f}")


def _eval_a07(df: pd.DataFrame, result: dict) -> None:
    s = result.get("summary", {})
    by_tier = result.get("by_tier", [])
    products = result.get("products", [])
    by_cat = result.get("by_category", [])

    if result.get("warning"):
        print(f"  ⚠ {result['warning']}")
        return

    print(f"  Total revenue:     {s.get('total_revenue', 0):>14,.2f}")
    print(f"  Products:          {s.get('n_products', 0):>10,}")
    pareto = s.get("pareto_check", {})
    print(f"  Top 20% revenue:   {pareto.get('top_20pct_revenue_share', 0):>10.2f}%  "
          f"({'✓ follows Pareto' if pareto.get('follows_pareto') else '⚠ deviates from 80/20'})")

    if by_tier:
        print(f"\n  ABC tier breakdown:")
        print(f"    {'TIER':<5s} {'PRODUCTS':>9s} {'PROD%':>7s} {'REVENUE':>14s} {'REV%':>7s} {'AVG/PROD':>11s}")
        for r in by_tier:
            print(f"    {r['tier']:<5s} {r['products']:>9,} {r['products_pct']:>6.2f}% "
                  f"{r['revenue']:>14,.2f} {r['revenue_pct']:>6.2f}% "
                  f"{r['avg_revenue_per_product']:>11,.2f}")

    # Find tier transition rows for the "boundary preview"
    if products:
        a_last = next((p for p in products if p["tier"] == "A" and
                       not any(q["tier"] == "A" and q["rank"] > p["rank"] for q in products)), None)
        b_first = next((p for p in products if p["tier"] == "B"), None)
        b_last = next((p for p in products if p["tier"] == "B" and
                       not any(q["tier"] == "B" and q["rank"] > p["rank"] for q in products)), None)
        c_first = next((p for p in products if p["tier"] == "C"), None)

        print(f"\n  Top 10 products (Tier A heroes):")
        print(f"    {'#':>3s} {'PRODUCT':<35s} {'REVENUE':>12s} {'CUM%':>7s} {'TIER':>5s}")
        for p in products[:10]:
            name = (p.get("name") or p["product_id"])[:33]
            print(f"    {p['rank']:>3} {name:<35s} {p['revenue']:>12,.2f} "
                  f"{p['cumulative_pct']:>6.2f}% {p['tier']:>5s}")

        if a_last and b_first:
            print(f"\n  Tier A → B boundary:")
            for p in (a_last, b_first):
                name = (p.get("name") or p["product_id"])[:33]
                print(f"    #{p['rank']:>4}  {name:<35s} {p['revenue']:>12,.2f}  "
                      f"cum={p['cumulative_pct']:>6.2f}%  tier={p['tier']}")

        if b_last and c_first:
            print(f"\n  Tier B → C boundary:")
            for p in (b_last, c_first):
                name = (p.get("name") or p["product_id"])[:33]
                print(f"    #{p['rank']:>4}  {name:<35s} {p['revenue']:>12,.2f}  "
                      f"cum={p['cumulative_pct']:>6.2f}%  tier={p['tier']}")

    if by_cat:
        print(f"\n  ABC mix per category (top 8):")
        print(f"    {'CATEGORY':<28s} {'A':>5s} {'B':>5s} {'C':>5s} {'TOTAL':>7s}")
        for r in by_cat[:8]:
            cat = r["category"][:26]
            print(f"    {cat:<28s} {r['tier_a']:>5,} {r['tier_b']:>5,} "
                  f"{r['tier_c']:>5,} {r['total_products']:>7,}")

    # ── Quality flags ───────────────────────────────────────────────────────
    print(f"\n  Quality flags:")
    flags = []
    n = s.get("n_products", 0)
    if n == 0:
        flags.append("✗ no products with revenue")
    if n > 0 and n < 10:
        flags.append(f"⚠ only {n} products — ABC classification needs more SKUs to be meaningful")
    a_share = s.get("tier_a", {}).get("products_pct", 0)
    if a_share > 50:
        flags.append(f"⚠ tier A has {a_share:.1f}% of products — revenue is unusually flat (no clear hero set)")
    if a_share < 5 and n > 50:
        flags.append(f"⚠ tier A is only {a_share:.1f}% of products — extreme concentration in a few SKUs")
    top20 = pareto.get("top_20pct_revenue_share", 0)
    if top20 > 95:
        flags.append(f"⚠ top 20% of products = {top20:.1f}% of revenue — extreme long-tail risk")
    if not flags:
        print(f"    ✓ all checks passed")
    else:
        for f in flags:
            print(f"    {f}")


def _eval_a08(df: pd.DataFrame, result: dict) -> None:
    s = result.get("summary", {})
    by_dow = result.get("by_dow", [])
    by_moy = result.get("by_month_of_year", [])
    monthly = (result.get("by_period") or {}).get("monthly", [])
    nvr = result.get("new_vs_returning")
    top_days = result.get("top_aov_days", [])

    if result.get("warning"):
        print(f"  ⚠ {result['warning']}")
        return

    dr = s.get("date_range", {})
    print(f"  Overall AOV:          {s.get('overall_aov', 0):>14,.2f}")
    print(f"  Orders:               {s.get('n_orders', 0):>10,}")
    print(f"  Days observed:        {s.get('n_days', 0):>10,}")
    print(f"  Date range:           {dr.get('start')} → {dr.get('end')}")
    print(f"  Recent 30d AOV:       {s.get('recent_30d_aov', 0):>14,.2f}")
    print(f"  Prior  30d AOV:       {s.get('prior_30d_aov', 0):>14,.2f}")
    print(f"  AOV change:           {s.get('aov_change_pct', 0):>+10.2f}%")
    print(f"  Monthly slope:        {s.get('monthly_slope_pct', 0):>+10.3f}% / month  →  {s.get('trend', '?')}")

    if by_dow:
        max_aov = max(r["aov"] for r in by_dow) or 1
        print(f"\n  AOV by day of week:")
        print(f"    {'DAY':<5s} {'AOV':>10s} {'ORDERS':>8s}")
        for r in sorted(by_dow, key=lambda x: x["day_idx"]):
            bar_len = int(r["aov"] / max_aov * 30)
            bar = "█" * bar_len
            print(f"    {r['day']:<5s} {r['aov']:>10,.2f} {r['orders']:>8,}  {bar}")

    if by_moy and len(by_moy) >= 3:
        max_aov_m = max(r["aov"] for r in by_moy) or 1
        print(f"\n  AOV by month of year (seasonality):")
        for r in sorted(by_moy, key=lambda x: x["month_idx"]):
            bar = "█" * int(r["aov"] / max_aov_m * 30)
            print(f"    {r['month']:<5s} {r['aov']:>10,.2f} {r['orders']:>8,}  {bar}")

    if monthly:
        print(f"\n  Recent 6 months AOV:")
        for r in monthly[-6:]:
            print(f"    {r['period']:<10s}  AOV {r['aov']:>10,.2f}  ({r['orders']:>5,} orders, rev {r['revenue']:>10,.0f})")

    if nvr:
        new_b = nvr["new"]
        ret_b = nvr["returning"]
        print(f"\n  New vs returning customer AOV:")
        print(f"    New:        {new_b['aov']:>10,.2f}  ({new_b['orders']:,} orders)")
        print(f"    Returning:  {ret_b['aov']:>10,.2f}  ({ret_b['orders']:,} orders)")
        print(f"    Lift:       {nvr['lift_pct']:>+10.2f}%   (returning vs new)")

    if top_days:
        print(f"\n  Top 5 AOV days (≥5 orders):")
        for r in top_days[:5]:
            print(f"    {r['date']:<12s} AOV {r['aov']:>10,.2f}  orders={r['orders']:,}  rev={r['revenue']:,.2f}")

    # ── Quality flags ───────────────────────────────────────────────────────
    print(f"\n  Quality flags:")
    flags = []
    if s.get("n_orders", 0) == 0:
        flags.append("✗ no orders to compute AOV")
    if s.get("n_days", 0) < 14:
        flags.append(f"⚠ only {s.get('n_days', 0)} days of data — trend metrics unreliable")
    chg = s.get("aov_change_pct", 0)
    if abs(chg) > 30:
        flags.append(f"⚠ AOV swung {chg:+.2f}% in last 30d — investigate cause")
    if by_dow and len(by_dow) >= 5:
        max_dow_aov = max(r["aov"] for r in by_dow)
        min_dow_aov = min(r["aov"] for r in by_dow if r["aov"] > 0) or 1
        if max_dow_aov / min_dow_aov > 2.0:
            flags.append(f"⚠ day-of-week AOV varies >2× ({min_dow_aov:.2f} to {max_dow_aov:.2f}) — strong DOW effect")
    if not flags:
        print(f"    ✓ all checks passed")
    else:
        for f in flags:
            print(f"    {f}")


def _eval_a09(df: pd.DataFrame, result: dict) -> None:
    s = result.get("summary", {})

    if result.get("warning"):
        print(f"  ⚠ {result['warning']}")
        return

    print(f"  Products:           {s.get('n_products', 0):>10,}")
    print(f"  Total revenue:      {s.get('total_revenue', 0):>14,.2f}")
    print(f"  Total orders:       {s.get('total_orders', 0):>10,}")
    if s.get("total_quantity") is not None:
        print(f"  Total quantity:     {s.get('total_quantity', 0):>10,}")

    def _print_ranking(title: str, rows: list, value_key: str, value_fmt: str = ",.2f"):
        if not rows:
            return
        print(f"\n  {title}")
        print(f"    {'#':>2s} {'PRODUCT':<35s} {'CATEGORY':<22s} {'METRIC':>14s} {'ORDERS':>7s}")
        for i, p in enumerate(rows[:10], 1):
            name = (p.get("name") or p["product_id"])[:33]
            cat = (p.get("category") or "")[:20]
            val = p.get(value_key, 0)
            val_str = f"{val:{value_fmt}}"
            print(f"    {i:>2} {name:<35s} {cat:<22s} {val_str:>14s} {p['orders']:>7,}")

    _print_ranking("Top by REVENUE:", result.get("top_by_revenue", []), "revenue")
    _print_ranking("Top by ORDERS (popularity):", result.get("top_by_orders", []), "orders", ",d")

    if result.get("top_by_quantity"):
        _print_ranking("Top by QUANTITY (volume):", result["top_by_quantity"], "quantity", ",d")

    _print_ranking("Top by AOV (premium):", result.get("top_by_aov", []), "aov")

    if result.get("top_by_margin"):
        _print_ranking("Top by MARGIN ($):", result["top_by_margin"], "margin")

    bottom = result.get("bottom_by_revenue", [])
    if bottom:
        print(f"\n  Bottom 10 by revenue (delisting candidates):")
        print(f"    {'#':>2s} {'PRODUCT':<35s} {'REVENUE':>10s} {'ORDERS':>7s}")
        for i, p in enumerate(bottom[:10], 1):
            name = (p.get("name") or p["product_id"])[:33]
            print(f"    {i:>2} {name:<35s} {p['revenue']:>10,.2f} {p['orders']:>7,}")

    # ── Quality flags ───────────────────────────────────────────────────────
    print(f"\n  Quality flags:")
    flags = []
    if s.get("n_products", 0) == 0:
        flags.append("✗ no products to rank")
    top_rev = result.get("top_by_revenue", [])
    if top_rev:
        # Check if top product is unusually dominant
        top1_rev = top_rev[0]["revenue"]
        total_rev = s.get("total_revenue", 1)
        if top1_rev / total_rev > 0.20:
            flags.append(f"⚠ #1 product = {top1_rev/total_rev*100:.1f}% of revenue — extreme product concentration")
    if not flags:
        print(f"    ✓ all checks passed")
    else:
        for f in flags:
            print(f"    {f}")


def _eval_a10(df: pd.DataFrame, result: dict) -> None:
    s = result.get("summary", {})
    spend_dist = result.get("spend_distribution", [])
    lifespan_dist = result.get("lifespan_distribution") or []
    tiers = result.get("lifespan_tiers")
    top = result.get("top_spenders", [])

    if result.get("warning"):
        print(f"  ⚠ {result['warning']}")
        return

    print(f"  Customers:              {s.get('n_customers', 0):>10,}")
    print(f"  Total revenue:          {s.get('total_revenue', 0):>14,.2f}")
    print(f"  Avg LTV:                {s.get('avg_lifetime_value', 0):>14,.2f}")
    print(f"  Median LTV:             {s.get('median_lifetime_value', 0):>14,.2f}")
    print(f"  P90 LTV:                {s.get('p90_lifetime_value', 0):>14,.2f}")
    print(f"  Avg order count:        {s.get('avg_order_count', 0):>10.2f}")
    if s.get("avg_lifespan_days") is not None:
        print(f"  Avg lifespan (days):    {s.get('avg_lifespan_days', 0):>10.2f}")
    print(f"  One-timer customers:    {s.get('one_timer_pct', 0):>10.2f}%")
    print(f"  Repeat customers:       {s.get('repeat_customer_pct', 0):>10.2f}%")
    if s.get("snapshot_date"):
        print(f"  Snapshot date:          {s.get('snapshot_date')}")

    if spend_dist:
        max_count = max((b["count"] for b in spend_dist), default=1) or 1
        print(f"\n  LTV spend distribution:")
        print(f"    {'BUCKET':<10s} {'COUNT':>7s} {'CUST%':>7s} {'REV%':>7s}")
        for b in spend_dist:
            bar = "█" * int(b["count"] / max_count * 25)
            rev_pct = b.get("revenue_pct", 0)
            print(f"    {b['bucket']:<10s} {b['count']:>7,} {b['pct']:>6.2f}% "
                  f"{rev_pct:>6.2f}%  {bar}")

    if lifespan_dist:
        max_count = max((b["count"] for b in lifespan_dist), default=1) or 1
        print(f"\n  Lifespan distribution (first → last order):")
        for b in lifespan_dist:
            bar = "█" * int(b["count"] / max_count * 25)
            print(f"    {b['bucket']:<14s} {b['count']:>7,} ({b['pct']:>5.2f}%)  {bar}")

    if tiers:
        total_t = sum(t["count"] for t in tiers.values()) or 1
        print(f"\n  Lifespan tiers (current state):")
        for name, info in tiers.items():
            pct = info["count"] / total_t * 100
            print(f"    {name:<10s} {info['count']:>7,} ({pct:>5.2f}%)  — {info['criteria']}")

    if top:
        print(f"\n  Top 10 spenders:")
        print(f"    {'#':>2s} {'CUSTOMER':<28s} {'LTV':>14s} {'ORDERS':>7s} {'AOV':>10s}", end="")
        if "lifespan_days" in top[0]:
            print(f" {'LIFE':>6s} {'RECENCY':>8s}")
        else:
            print()
        for i, c in enumerate(top[:10], 1):
            cid = c["customer_id"][:26]
            line = f"    {i:>2} {cid:<28s} {c['lifetime_value']:>14,.2f} {c['order_count']:>7,} {c['aov']:>10,.2f}"
            if "lifespan_days" in c:
                line += f" {c['lifespan_days']:>6,} {c['recency_days']:>8,}"
            print(line)

    # ── Quality flags ───────────────────────────────────────────────────────
    print(f"\n  Quality flags:")
    flags = []
    n = s.get("n_customers", 0)
    if n == 0:
        flags.append("✗ no customers ingested")
    if n > 0 and s.get("one_timer_pct", 0) > 95:
        flags.append(f"⚠ {s.get('one_timer_pct'):.1f}% one-timers — limited LTV signal in this dataset")
    if s.get("avg_lifetime_value", 0) > 0:
        ratio = s.get("avg_lifetime_value", 0) / max(s.get("median_lifetime_value", 1), 0.01)
        if ratio > 5:
            flags.append(f"⚠ avg LTV is {ratio:.1f}× median — heavy right tail (whale concentration)")
    if tiers:
        dormant_pct = tiers["dormant"]["count"] / max(n, 1) * 100
        if dormant_pct > 50:
            flags.append(f"⚠ {dormant_pct:.1f}% of customers are dormant (no order in 90+ days)")
    if not flags:
        print(f"    ✓ all checks passed")
    else:
        for f in flags:
            print(f"    {f}")


def _eval_a11(df: pd.DataFrame, result: dict) -> None:
    s = result.get("summary", {})
    by_status = result.get("by_status", [])
    by_cat = result.get("by_category", [])
    trend = result.get("monthly_trend") or []

    if result.get("warning"):
        print(f"  ⚠ {result['warning']}")
        return

    print(f"  Orders:                {s.get('n_orders', 0):>10,}")
    print(f"  Unique statuses:       {s.get('n_unique_statuses', 0):>10,}")
    print(f"  Success rate:          {s.get('success_rate_pct', 0):>10.2f}%")
    print(f"  Cancellation rate:     {s.get('cancellation_rate_pct', 0):>10.2f}%")
    print(f"  Refund rate:           {s.get('refund_rate_pct', 0):>10.2f}%")
    print(f"  In progress:           {s.get('in_progress_pct', 0):>10.2f}%")
    print(f"  Unknown bucket:        {s.get('unknown_pct', 0):>10.2f}%")
    if s.get("revenue_at_risk") is not None:
        print(f"  Revenue at risk:       {s.get('revenue_at_risk', 0):>14,.2f}  (non-success orders)")

    if by_status:
        print(f"\n  Status breakdown:")
        print(f"    {'STATUS':<22s} {'COUNT':>8s} {'PCT':>7s} {'CATEGORY':<12s} {'REVENUE':>14s}")
        for r in by_status:
            rev = r.get("revenue")
            rev_str = f"{rev:,.2f}" if rev is not None else "—"
            cat = r["category"]
            cat_marker = {"success": "✓", "in_progress": "⏳", "failure": "✗", "unknown": "?"}.get(cat, "")
            print(f"    {r['status']:<22s} {r['count']:>8,} {r['pct']:>6.2f}% "
                  f"{cat_marker} {cat:<10s} {rev_str:>14s}")

    if by_cat:
        # Render a tiny bar chart per category.
        max_n = max((r["count"] for r in by_cat), default=1) or 1
        print(f"\n  Category rollup:")
        for r in sorted(by_cat, key=lambda x: x["count"], reverse=True):
            bar = "█" * int(r["count"] / max_n * 30)
            rev_str = f"{r.get('revenue', 0):,.2f}" if "revenue" in r else "—"
            print(f"    {r['category']:<12s} {r['count']:>8,} ({r['pct']:>5.2f}%)  rev={rev_str:>14s}  {bar}")

    if trend:
        print(f"\n  Recent 6-month status trend:")
        print(f"    {'PERIOD':<10s} {'SUCCESS':>8s} {'PROG':>6s} {'FAIL':>6s} {'UNK':>5s} {'TOTAL':>7s} {'SUCC%':>7s}")
        for r in trend[-6:]:
            print(f"    {r['period']:<10s} {r['success']:>8,} {r['in_progress']:>6,} "
                  f"{r['failure']:>6,} {r['unknown']:>5,} {r['total']:>7,} {r['success_rate_pct']:>6.2f}%")

    # ── Quality flags ───────────────────────────────────────────────────────
    print(f"\n  Quality flags:")
    flags = []
    n = s.get("n_orders", 0)
    if n == 0:
        flags.append("✗ no orders with status")
    if s.get("unknown_pct", 0) > 10:
        flags.append(f"⚠ {s.get('unknown_pct'):.1f}% of statuses didn't match any keyword bucket — review unknown values")
    succ = s.get("success_rate_pct", 0)
    if 0 < n and succ < 70:
        flags.append(f"⚠ success rate is {succ:.2f}% — low operational health")
    if s.get("cancellation_rate_pct", 0) > 10:
        flags.append(f"⚠ cancellation rate {s.get('cancellation_rate_pct'):.2f}% — investigate root cause")
    if s.get("refund_rate_pct", 0) > 10:
        flags.append(f"⚠ refund rate {s.get('refund_rate_pct'):.2f}% — investigate quality / fulfillment issues")
    if not flags:
        print(f"    ✓ all checks passed")
    else:
        for f in flags:
            print(f"    {f}")


def _eval_a12(df: pd.DataFrame, result: dict) -> None:
    s = result.get("summary", {})
    comp = result.get("comparison")
    dist = result.get("distribution", [])
    by_cat = result.get("by_category") or []
    top_prod = result.get("top_discounted_products") or []
    trend = result.get("monthly_trend") or []

    if result.get("warning"):
        print(f"  ⚠ {result['warning']}")
        return

    print(f"  Orders:                {s.get('n_orders', 0):>10,}")
    print(f"  Gross revenue:         {s.get('total_gross_revenue', 0):>14,.2f}")
    print(f"  Total discount:        {s.get('total_discount', 0):>14,.2f}")
    print(f"  Discount % of gross:   {s.get('discount_pct_of_gross', 0):>10.2f}%")
    print(f"  Discounted orders:     {s.get('n_discounted', 0):>10,}  ({s.get('discounted_pct', 0):>5.2f}%)")
    print(f"  Full-price orders:     {s.get('n_full_price', 0):>10,}")
    print(f"  Avg discount $:        {s.get('avg_discount_amount', 0):>14,.2f}")
    print(f"  Avg discount %:        {s.get('avg_discount_pct', 0):>10.2f}%")

    if comp:
        d = comp["discounted"]
        f = comp["full_price"]
        print(f"\n  Discounted vs full-price:")
        print(f"    {'TYPE':<14s} {'ORDERS':>8s} {'REVENUE':>14s} {'AOV':>10s}")
        print(f"    {'discounted':<14s} {d['orders']:>8,} {d['revenue']:>14,.2f} {d['aov']:>10,.2f}")
        print(f"    {'full price':<14s} {f['orders']:>8,} {f['revenue']:>14,.2f} {f['aov']:>10,.2f}")
        print(f"    AOV ratio (disc/full): {comp['aov_ratio']:.3f}")

    if dist:
        max_n = max((b["orders"] for b in dist), default=1) or 1
        print(f"\n  Discount % distribution:")
        for b in dist:
            bar = "█" * int(b["orders"] / max_n * 25)
            print(f"    {b['bucket']:<10s} orders={b['orders']:>6,} ({b['pct_of_orders']:>5.2f}%)  "
                  f"disc={b['discount']:>10,.2f}  AOV={b['avg_order_value']:>9,.2f}  {bar}")

    if by_cat:
        print(f"\n  Discount $ by category (top 8):")
        for r in by_cat[:8]:
            print(f"    {r['category'][:24]:<26s} disc={r['discount']:>11,.2f}  "
                  f"({r['discount_pct']:>5.2f}% of {r['gross']:,.0f})")

    if top_prod:
        print(f"\n  Top 5 most-discounted products:")
        for r in top_prod[:5]:
            name = (r.get("name") or r["product_id"])[:30]
            print(f"    {name:<32s} disc={r['discount']:>10,.2f}  "
                  f"({r['avg_discount_pct']:>5.2f}% avg, ×{r['orders']})")

    if trend:
        print(f"\n  Recent 6-month discount trend:")
        for r in trend[-6:]:
            print(f"    {r['period']:<10s} gross={r['gross']:>10,.0f}  disc={r['discount']:>9,.0f}  "
                  f"({r['discount_pct']:>5.2f}%)  disc_orders={r['discounted_orders_pct']:>5.2f}%")

    # ── Quality flags ───────────────────────────────────────────────────────
    print(f"\n  Quality flags:")
    flags = []
    n = s.get("n_orders", 0)
    if n == 0:
        flags.append("✗ no orders to analyze")
    if s.get("discount_pct_of_gross", 0) == 0:
        flags.append("⚠ discount_amount column is all zero — discount program may not be enabled in this data")
    if s.get("discount_pct_of_gross", 0) > 25:
        flags.append(f"⚠ discounts = {s.get('discount_pct_of_gross'):.2f}% of gross revenue — very heavy discounting")
    if comp and comp["aov_ratio"] > 1.2:
        flags.append(f"⚠ discounted AOV is {comp['aov_ratio']:.2f}× full-price AOV — discounts may be on bigger baskets")
    if comp and comp["aov_ratio"] < 0.5 and comp["full_price"]["orders"] > 0:
        flags.append(f"⚠ discounted AOV is only {comp['aov_ratio']:.2f}× full-price — small-basket discount cannibalization")
    if not flags:
        print(f"    ✓ all checks passed")
    else:
        for f in flags:
            print(f"    {f}")


def _eval_a13(df: pd.DataFrame, result: dict) -> None:
    s = result.get("summary", {})
    monthly = result.get("monthly", [])
    quarterly = result.get("quarterly", [])
    yoy = result.get("yoy_summary")

    if result.get("warning"):
        print(f"  ⚠ {result['warning']}")
        return

    print(f"  Months observed:       {s.get('n_months', 0):>10,}")
    print(f"  Period:                {s.get('first_month')} → {s.get('last_month')}")
    print(f"  Total revenue:         {s.get('total_revenue', 0):>14,.2f}")
    print(f"  First-month rev:       {s.get('first_month_revenue', 0):>14,.2f}")
    print(f"  Last-month rev:        {s.get('last_month_revenue', 0):>14,.2f}")
    print(f"  Total growth:          {s.get('total_growth_pct', 0):>+10.2f}%")
    print(f"  CMGR:                  {s.get('cmgr_pct', 0):>+10.3f}%/mo  →  {s.get('trend_label', '?')}")

    best = s.get("best_mom_period")
    worst = s.get("worst_mom_period")
    if best:
        print(f"  Best  MoM:             {best['period']}  {best['growth_pct']:>+7.2f}%")
    if worst:
        print(f"  Worst MoM:             {worst['period']}  {worst['growth_pct']:>+7.2f}%")

    if yoy:
        print(f"\n  Year-over-year (last 12 months vs prior 12):")
        print(f"    Current year:    {yoy['current_year_revenue']:>14,.2f}")
        print(f"    Prior year:      {yoy['prior_year_revenue']:>14,.2f}")
        print(f"    YoY change:      {yoy['yoy_pct']:>+10.2f}%")

    if monthly:
        # Show last 12 months (or all if fewer)
        rows = monthly[-12:]
        print(f"\n  Recent monthly performance (last {len(rows)} months):")
        print(f"    {'PERIOD':<10s} {'REVENUE':>12s} {'ORDERS':>7s} {'AOV':>10s} {'MoM%':>8s} {'YoY%':>8s} {'3mo AVG':>11s}")
        for r in rows:
            mom = f"{r['mom_pct']:+.2f}%" if r["mom_pct"] is not None else "—"
            yoy_v = f"{r['yoy_pct']:+.2f}%" if r["yoy_pct"] is not None else "—"
            print(f"    {r['period']:<10s} {r['revenue']:>12,.0f} {r['orders']:>7,} "
                  f"{r['aov']:>10,.2f} {mom:>8s} {yoy_v:>8s} {r['rolling_3mo_revenue']:>11,.0f}")

    if quarterly:
        print(f"\n  Quarterly:")
        print(f"    {'QUARTER':<10s} {'REVENUE':>12s} {'ORDERS':>7s} {'QoQ%':>8s}")
        for r in quarterly[-8:]:
            qoq = f"{r['qoq_pct']:+.2f}%" if r["qoq_pct"] is not None else "—"
            print(f"    {r['period']:<10s} {r['revenue']:>12,.0f} {r['orders']:>7,} {qoq:>8s}")

    # ── Quality flags ───────────────────────────────────────────────────────
    print(f"\n  Quality flags:")
    flags = []
    n = s.get("n_months", 0)
    if n < 2:
        flags.append("✗ need ≥2 months for any growth metric")
    if not s.get("yoy_available", False) and n >= 1:
        flags.append(f"⚠ only {n} months — YoY metrics unavailable (need ≥13)")
    if monthly:
        # Check for high MoM volatility (stddev / mean of MoM%).
        moms = [r["mom_pct"] for r in monthly if r["mom_pct"] is not None]
        if len(moms) >= 3:
            import statistics
            stdev = statistics.stdev(moms)
            if stdev > 30:
                flags.append(f"⚠ MoM growth stdev = {stdev:.1f}% — highly volatile, consider longer windows")
    if not flags:
        print(f"    ✓ all checks passed")
    else:
        for f in flags:
            print(f"    {f}")


def _eval_a14(df: pd.DataFrame, result: dict) -> None:
    s = result.get("summary", {})
    by_chan = result.get("by_channel", [])
    monthly = result.get("monthly_acquisition") or []
    seg = result.get("channel_x_segment") or []

    if result.get("warning"):
        print(f"  ⚠ {result['warning']}")
        return

    print(f"  Customers:           {s.get('n_customers', 0):>10,}")
    print(f"  Channels:            {s.get('n_channels', 0):>10,}")
    print(f"  Total revenue:       {s.get('total_revenue', 0):>14,.2f}")
    br = s.get("best_channel_revenue")
    ba = s.get("best_channel_aov")
    bl = s.get("best_channel_ltv")
    if br:
        print(f"  Best by REVENUE:     {br['name']:<22s} {br['revenue']:>14,.2f}  ({br['share_pct']:>5.2f}%)")
    if ba:
        print(f"  Best by AOV:         {ba['name']:<22s} {ba['aov']:>14,.2f}")
    if bl:
        print(f"  Best by LTV:         {bl['name']:<22s} {bl['avg_ltv']:>14,.2f}")
    hhi = s.get("channel_concentration", 0)
    print(f"  Channel HHI:         {hhi:>10.4f}  ({'concentrated' if hhi > 0.25 else 'moderate' if hhi > 0.15 else 'diffuse'})")

    if by_chan:
        print(f"\n  Channel breakdown:")
        print(f"    {'#':>2s} {'CHANNEL':<22s} {'CUST':>7s} {'CUST%':>7s} {'ORDERS':>7s} "
              f"{'REVENUE':>14s} {'REV%':>7s} {'AOV':>9s} {'LTV':>9s}")
        for r in by_chan:
            print(f"    {r['rank']:>2} {r['channel']:<22s} {r['customers']:>7,} "
                  f"{r['cust_share_pct']:>6.2f}% {r['orders']:>7,} {r['revenue']:>14,.2f} "
                  f"{r['rev_share_pct']:>6.2f}% {r['aov']:>9,.2f} {r['avg_ltv']:>9,.2f}")

    if monthly:
        # Pivot: last 6 months × top 5 channels by total
        recent_periods = sorted({r["period"] for r in monthly})[-6:]
        # Take top 5 channels overall by total new customers
        chan_totals: dict[str, int] = {}
        for r in monthly:
            chan_totals[r["channel"]] = chan_totals.get(r["channel"], 0) + r["new_customers"]
        top_chans = [c for c, _ in sorted(chan_totals.items(), key=lambda kv: kv[1], reverse=True)[:5]]
        print(f"\n  New customers per channel — last 6 months:")
        header = f"    {'PERIOD':<10s} " + " ".join(f"{c[:9]:>10s}" for c in top_chans)
        print(header)
        for p in recent_periods:
            row = {r["channel"]: r["new_customers"] for r in monthly if r["period"] == p}
            cells = " ".join(f"{row.get(c, 0):>10,}" for c in top_chans)
            print(f"    {p:<10s} {cells}")

    if seg:
        print(f"\n  Channel × segment (top 12 cells):")
        for r in seg[:12]:
            print(f"    {r['channel']:<22s} | {r['segment']:<20s}  cust={r['customers']:,}")

    # ── Quality flags ───────────────────────────────────────────────────────
    print(f"\n  Quality flags:")
    flags = []
    n = s.get("n_channels", 0)
    if n == 0:
        flags.append("✗ no channels found")
    if n == 1:
        flags.append("⚠ only 1 channel — no comparative analysis possible")
    if hhi > 0.5:
        flags.append(f"⚠ extreme channel concentration (HHI={hhi:.4f}) — over-reliance on a single channel")
    if by_chan and len(by_chan) >= 2:
        # Check for big LTV variance across channels
        ltvs = [r["avg_ltv"] for r in by_chan if r["avg_ltv"] > 0]
        if len(ltvs) >= 2 and max(ltvs) / min(ltvs) > 3:
            flags.append(f"⚠ LTV varies {max(ltvs)/min(ltvs):.1f}× across channels — quality differs significantly")
    if not flags:
        print(f"    ✓ all checks passed")
    else:
        for f in flags:
            print(f"    {f}")


def _eval_a15(df: pd.DataFrame, result: dict) -> None:
    s = result.get("summary", {})
    history = result.get("history", [])
    forecast = result.get("forecast", [])
    comp = result.get("components", {})

    if result.get("warning"):
        print(f"  ⚠ {result['warning']}")
        return

    print(f"  Engine:               {s.get('model_engine', '?')}")
    print(f"  Train days:           {s.get('n_train_days', 0):>10,}")
    print(f"  History range:        {s.get('first_date')} → {s.get('last_date')}")
    print(f"  Trend:                {s.get('trend_label', '?'):<10s}  ({s.get('trend_slope_pct_per_day', 0):>+7.4f}%/day)")
    print(f"  Forecast — next 30d:  {s.get('total_revenue_30d_forecast', 0):>14,.2f}")
    print(f"  Forecast — next 60d:  {s.get('total_revenue_60d_forecast', 0):>14,.2f}")
    print(f"  Forecast — next 90d:  {s.get('total_revenue_90d_forecast', 0):>14,.2f}")
    print(f"  Forecast — next 180d: {s.get('total_revenue_180d_forecast', 0):>14,.2f}")
    if s.get("backtest_mae") is not None:
        print(f"  Backtest (30d holdout):")
        print(f"    MAE:                {s.get('backtest_mae', 0):>10,.2f}")
        if s.get("backtest_mape") is not None:
            print(f"    MAPE:               {s.get('backtest_mape', 0):>10,.2f}%")

    if forecast:
        # Compare forecast totals to recent actuals for sanity.
        last_30_actual = sum(h["actual"] or 0 for h in history[-30:])
        next_30_fc = s.get("total_revenue_30d_forecast", 0)
        ratio = next_30_fc / last_30_actual if last_30_actual > 0 else 0
        print(f"\n  Recent 30d actual vs next 30d forecast:")
        print(f"    Last 30d actual:    {last_30_actual:>14,.2f}")
        print(f"    Next 30d forecast:  {next_30_fc:>14,.2f}  ({ratio:>+5.2f}× ratio)")

        print(f"\n  Forecast preview (next 14 days):")
        print(f"    {'DATE':<12s} {'YHAT':>12s} {'LOWER':>12s} {'UPPER':>12s}")
        for r in forecast[:14]:
            print(f"    {r['date']:<12s} {r['yhat']:>12,.2f} {r['lower']:>12,.2f} {r['upper']:>12,.2f}")

    weekly = comp.get("weekly", [])
    if weekly:
        max_w = max((abs(r["value"]) for r in weekly), default=1) or 1
        print(f"\n  Weekly seasonality (Δ from trend):")
        for r in sorted(weekly, key=lambda x: x["day_idx"]):
            v = r["value"]
            sign = "+" if v >= 0 else "-"
            bar_len = int(abs(v) / max_w * 20)
            bar = ("█" if v >= 0 else "░") * bar_len
            print(f"    {r['day']:<5s}  {sign}{abs(v):>10,.2f}  {bar}")

    yearly = comp.get("yearly")
    if yearly and len(yearly) >= 4:
        # Show the four extremes (min, max, and two midpoints) as a peek.
        max_y = max(yearly, key=lambda r: r["value"])
        min_y = min(yearly, key=lambda r: r["value"])
        print(f"\n  Yearly seasonality:")
        print(f"    Peak DOY:    {max_y['day_of_year']:>3}  Δ={max_y['value']:>+10,.2f}")
        print(f"    Trough DOY:  {min_y['day_of_year']:>3}  Δ={min_y['value']:>+10,.2f}")

    # ── Quality flags ───────────────────────────────────────────────────────
    print(f"\n  Quality flags:")
    flags = []
    n = s.get("n_train_days", 0)
    if n == 0:
        flags.append("✗ no training data")
    if 0 < n < 60:
        flags.append(f"⚠ only {n} train days — Prophet's seasonality estimates are unstable below 60 days")
    if n > 0 and s.get("backtest_mape") is not None:
        mape = s.get("backtest_mape", 0)
        if mape > 50:
            flags.append(f"⚠ backtest MAPE {mape:.2f}% — model accuracy is poor on this data")
        elif mape > 25:
            flags.append(f"⚠ backtest MAPE {mape:.2f}% — moderate accuracy, treat forecasts as directional")
    if forecast:
        # Sanity: forecast shouldn't be ridiculously far from recent actuals.
        last_30 = sum(h["actual"] or 0 for h in history[-30:])
        next_30 = s.get("total_revenue_30d_forecast", 0)
        if last_30 > 0 and (next_30 / last_30 > 3 or next_30 / last_30 < 0.3):
            flags.append(f"⚠ next 30d forecast is {next_30/last_30:.2f}× recent actuals — possible overfitting or trend break")
    if not flags:
        print(f"    ✓ all checks passed")
    else:
        for f in flags:
            print(f"    {f}")


def _eval_a16(df: pd.DataFrame, result: dict) -> None:
    s = result.get("summary", {})
    anomalies = result.get("anomalies", [])
    monthly = result.get("monthly_anomaly_counts", [])
    iqr = result.get("iqr_bounds", {})

    if result.get("warning"):
        print(f"  ⚠ {result['warning']}")
        return

    print(f"  Days analyzed:         {s.get('n_days_analyzed', 0):>10,}")
    print(f"  Method:                {s.get('method')}")
    print(f"  Z threshold:           |z| ≥ {s.get('z_threshold', 0):.1f}")
    print(f"  IQR multiplier:        {s.get('iqr_multiplier', 0):.1f}")
    print(f"  Anomalies found:       {s.get('n_anomalies', 0):>10,}  ({s.get('anomaly_rate_pct', 0):>5.2f}%)")
    print(f"    High (spikes):       {s.get('n_high_anomalies', 0):>10,}")
    print(f"    Low (drops):         {s.get('n_low_anomalies', 0):>10,}")

    if iqr:
        print(f"\n  IQR bounds:")
        print(f"    Q1:                  {iqr.get('q1', 0):>14,.2f}")
        print(f"    Q3:                  {iqr.get('q3', 0):>14,.2f}")
        print(f"    Lower fence:         {iqr.get('lower', 0):>14,.2f}")
        print(f"    Upper fence:         {iqr.get('upper', 0):>14,.2f}")

    me = s.get("most_extreme")
    if me:
        marker = "↑" if me["type"] == "high" else "↓"
        print(f"\n  Most extreme day:    {me['date']}  {marker} {me['revenue']:,.2f}  "
              f"(z={me['z_score']:+.2f}, {me['deviation_pct']:+.1f}% vs expected)")

    if anomalies:
        print(f"\n  Top {min(15, len(anomalies))} anomalies (by |z|):")
        print(f"    {'DATE':<12s} {'TYPE':<6s} {'REVENUE':>12s} {'EXPECTED':>12s} {'DEV%':>9s} {'Z':>7s}  FLAGGED")
        for a in anomalies[:15]:
            marker = "↑ high" if a["type"] == "high" else "↓ low"
            flagged = "+".join(a["flagged_by"])
            print(f"    {a['date']:<12s} {marker:<6s} {a['revenue']:>12,.2f} "
                  f"{a['expected_revenue']:>12,.2f} {a['deviation_pct']:>+8.1f}% {a['z_score']:>+7.2f}  {flagged}")

    if monthly:
        active_months = [m for m in monthly if m["n_high"] > 0 or m["n_low"] > 0]
        if active_months:
            print(f"\n  Months with anomalies (top 10):")
            print(f"    {'PERIOD':<10s} {'HIGH':>6s} {'LOW':>5s} {'TOTAL':>7s} {'DAYS':>6s}")
            for m in sorted(active_months, key=lambda r: r["n_high"] + r["n_low"], reverse=True)[:10]:
                total_anom = m["n_high"] + m["n_low"]
                print(f"    {m['period']:<10s} {m['n_high']:>6,} {m['n_low']:>5,} "
                      f"{total_anom:>7,} {m['total_days']:>6,}")

    # ── Quality flags ───────────────────────────────────────────────────────
    print(f"\n  Quality flags:")
    flags = []
    n_days = s.get("n_days_analyzed", 0)
    n_anom = s.get("n_anomalies", 0)
    rate = s.get("anomaly_rate_pct", 0)
    if n_days == 0:
        flags.append("✗ no days to analyze")
    if n_days > 0 and n_anom == 0:
        flags.append("ℹ no anomalies detected — daily revenue is consistently within expected range")
    if rate > 15:
        flags.append(f"⚠ {rate:.1f}% of days flagged — threshold may be too sensitive or data is highly variable")
    if rate > 0 and s.get("n_high_anomalies", 0) > 0 and s.get("n_low_anomalies", 0) == 0:
        flags.append("ℹ all anomalies are positive spikes — likely seasonal/promotional effects")
    if rate > 0 and s.get("n_low_anomalies", 0) > s.get("n_high_anomalies", 0) * 3:
        flags.append("⚠ negative anomalies dominate — investigate fulfillment/operational issues")
    if not flags:
        print(f"    ✓ all checks passed")
    else:
        for f in flags:
            print(f"    {f}")


def _eval_a17(df: pd.DataFrame, result: dict) -> None:
    s = result.get("summary", {})
    horizons = result.get("horizons", {})
    top = result.get("top_customers", [])
    dist = result.get("clv_distribution", [])

    if result.get("warning") and not s.get("n_customers_modeled", 0):
        print(f"  ⚠ {result['warning']}")
        return

    print(f"  Engine:                {s.get('model_engine')}")
    print(f"  Customers modeled:     {s.get('n_customers_modeled', 0):>10,}")
    print(f"  Snapshot date:         {s.get('snapshot_date')}")
    print(f"  Total predicted CLV:   {s.get('total_predicted_clv', 0):>14,.2f}  (365d horizon)")
    print(f"  Avg predicted CLV:     {s.get('avg_predicted_clv', 0):>14,.2f}")
    print(f"  Median predicted CLV:  {s.get('median_predicted_clv', 0):>14,.2f}")
    print(f"  Monetary↔Freq corr:    {s.get('monetary_freq_corr', 0):>+10.4f}  "
          f"({'OK' if abs(s.get('monetary_freq_corr', 0)) < 0.3 else '⚠ G-G assumption shaky'})")

    if horizons:
        print(f"\n  Predicted by horizon:")
        print(f"    {'HORIZON':<10s} {'AVG ORDERS':>12s} {'AVG CLV':>12s} {'TOTAL CLV':>14s}")
        for h in ("90", "180", "365"):
            if h not in horizons:
                continue
            r = horizons[h]
            print(f"    {h+'d':<10s} {r['avg_predicted_orders']:>12.3f} "
                  f"{r['avg_predicted_value']:>12,.2f} {r['total_clv']:>14,.2f}")

    if dist:
        max_cnt = max((b["count"] for b in dist), default=1) or 1
        print(f"\n  365-day CLV distribution:")
        for b in dist:
            bar = "█" * int(b["count"] / max_cnt * 25)
            print(f"    {b['bucket']:<10s} {b['count']:>6,} ({b['pct']:>5.2f}%)  "
                  f"clv={b['predicted_clv']:>12,.2f}  {bar}")

    if top:
        print(f"\n  Top 10 customers by 365-day predicted CLV:")
        print(f"    {'CUSTOMER':<28s} {'HIST $':>10s} {'90d CLV':>10s} {'365d CLV':>11s} {'ALIVE%':>7s}")
        for c in top[:10]:
            cid = c["customer_id"][:26]
            print(f"    {cid:<28s} {c['historical_value']:>10,.2f} "
                  f"{c['predicted_clv_90d']:>10,.2f} {c['predicted_clv_365d']:>11,.2f} "
                  f"{c['alive_probability']*100:>6.2f}%")

    # ── Quality flags ───────────────────────────────────────────────────────
    print(f"\n  Quality flags:")
    flags = []
    n = s.get("n_customers_modeled", 0)
    if n == 0:
        flags.append("✗ no customers modeled")
    if result.get("warning"):
        flags.append(f"⚠ {result['warning']}")
    corr = abs(s.get("monetary_freq_corr", 0))
    if corr > 0.3:
        flags.append(f"⚠ Gamma-Gamma assumption (monetary ⊥ frequency) violated — corr={corr:.3f}")
    avg_clv = s.get("avg_predicted_clv", 0)
    median_clv = s.get("median_predicted_clv", 1)
    if avg_clv > 0 and median_clv > 0 and avg_clv / median_clv > 5:
        flags.append(f"⚠ avg/median CLV ratio = {avg_clv/median_clv:.1f}× — heavy whale concentration")
    if not flags:
        print(f"    ✓ all checks passed")
    else:
        for f in flags:
            print(f"    {f}")


def _eval_a18(df: pd.DataFrame, result: dict) -> None:
    s = result.get("summary", {})
    dist = result.get("score_distribution", [])
    by_cat = result.get("by_category") or []
    top_pos = result.get("top_positive", [])
    top_neg = result.get("top_negative", [])

    if result.get("warning"):
        print(f"  ⚠ {result['warning']}")
        return

    eng = s.get("engines_used", {})
    print(f"  Comments analyzed:     {s.get('n_analyzed', 0):>10,}")
    print(f"  Primary engine:        {s.get('primary_engine')}")
    if eng:
        print(f"  Engine usage:")
        for k, v in eng.items():
            if v > 0:
                print(f"    {k:<22s} {v:>10,}")
    print(f"  Avg sentiment score:   {s.get('avg_score', 0):>+10.4f}  (range -1 to +1)")
    print(f"  Positive:              {s.get('positive_pct', 0):>10.2f}%")
    print(f"  Neutral:               {s.get('neutral_pct', 0):>10.2f}%")
    print(f"  Negative:              {s.get('negative_pct', 0):>10.2f}%")

    if dist:
        max_cnt = max((b["count"] for b in dist), default=1) or 1
        print(f"\n  Score distribution:")
        for b in dist:
            bar = "█" * int(b["count"] / max_cnt * 30)
            label_map = {
                "very_negative": "very neg", "negative": "neg",
                "neutral": "neutral", "positive": "pos", "very_positive": "very pos",
            }
            label = label_map.get(b["bucket"], b["bucket"])
            print(f"    {label:<10s}  {b['count']:>5,}  ({b['pct']:>5.2f}%)  {bar}")

    if by_cat:
        print(f"\n  Sentiment by category (top 8):")
        print(f"    {'CATEGORY':<26s} {'COMMENTS':>9s} {'AVG':>8s} {'POS%':>7s} {'NEG%':>7s}")
        for r in by_cat[:8]:
            cat = r["category"][:24]
            print(f"    {cat:<26s} {r['comments']:>9,} {r['avg_score']:>+8.3f} "
                  f"{r['positive_pct']:>6.2f}% {r['negative_pct']:>6.2f}%")

    if top_pos:
        print(f"\n  Top 3 positive comments:")
        for c in top_pos[:3]:
            text = c["text"].replace("\n", " ")[:90]
            print(f"    [+{c['score']:.3f}]  {text}")

    if top_neg:
        print(f"\n  Top 3 negative comments:")
        for c in top_neg[:3]:
            text = c["text"].replace("\n", " ")[:90]
            print(f"    [{c['score']:+.3f}]  {text}")

    # ── Quality flags ───────────────────────────────────────────────────────
    print(f"\n  Quality flags:")
    flags = []
    n = s.get("n_analyzed", 0)
    if n == 0:
        flags.append("✗ no comments analyzed")
    if eng.get("transformers", 0) == 0 and eng.get("arabic_lexicon", 0) > 0:
        flags.append("ℹ Arabic comments scored by lexicon (install transformers for BERT-quality)")
    if eng.get("transformers", 0) == 0 and (eng.get("vader", 0) + eng.get("arabic_lexicon", 0)) > 0:
        flags.append("ℹ install transformers + torch for BERT-grade multilingual sentiment")
    neu = s.get("neutral_pct", 0)
    if neu > 80:
        flags.append(f"⚠ {neu:.1f}% neutral — engine may be under-classifying or comments are genuinely flat")
    if not flags:
        print(f"    ✓ all checks passed")
    else:
        for f in flags:
            print(f"    {f}")


def _eval_a19(df: pd.DataFrame, result: dict) -> None:
    s = result.get("summary", {})
    clusters = result.get("clusters", []) or []
    tops = result.get("top_customers_per_cluster", []) or []

    if result.get("warning"):
        print(f"  ⚠ {result['warning']}")
        return

    print(f"  Customers clustered:    {s.get('n_customers', 0):>10,}")
    print(f"  Snapshot date:          {s.get('snapshot_date')}")
    print(f"  K (clusters):           {s.get('n_clusters', 0):>10}")
    print(f"  Method:                 {s.get('method')}")
    sil = s.get("silhouette_score")
    print(f"  Silhouette score:       {sil if sil is not None else 'n/a'}"
          + ("  (higher is better; >0.25 is solid, >0.5 is great)" if sil is not None else ""))

    if clusters:
        print(f"\n  Cluster breakdown (sorted by avg monetary):")
        print(f"    {'#':>2s}  {'LABEL':<11s} {'COUNT':>7s} {'PCT':>6s} {'AVG MON':>12s} {'REV%':>6s} "
              f"{'R̄':>6s} {'F̄':>6s} {'M̄ centroid':>13s}")
        for i, c in enumerate(clusters, 1):
            cent = c.get("centroid", {}) or {}
            print(f"    {i:>2}  {c['label']:<11s} {c['count']:>7,} {c['pct']:>5.2f}% "
                  f"{c['avg_monetary']:>12,.2f} {c['rev_pct']:>5.2f}% "
                  f"{c['avg_recency_days']:>6.1f} {c['avg_frequency']:>6.2f} "
                  f"{cent.get('monetary', 0):>13,.2f}")

    if tops:
        # Pick 3 representative customers from each cluster
        print(f"\n  3 closest-to-centroid customers per cluster:")
        for entry in tops:
            cid = entry.get("cluster_id")
            lbl = entry.get("label")
            print(f"    Cluster {cid} ({lbl}):")
            for c in (entry.get("customers") or [])[:3]:
                print(f"      {str(c['customer_id'])[:30]:<30s}  R={c['recency_days']:>4} "
                      f"F={c['frequency']:>4}  M=${c['monetary']:>10,.2f}  "
                      f"d={c['distance_to_centroid']:.3f}")

    # Quality flags
    print(f"\n  Quality flags:")
    flags = []
    if s.get("n_customers", 0) == 0:
        flags.append("✗ no customers — model didn't run")
    if sil is not None:
        if sil < 0.1:
            flags.append(f"⚠ silhouette={sil:.3f} is very low — clusters overlap badly, RFM may not separate this dataset")
        elif sil < 0.25:
            flags.append(f"⚠ silhouette={sil:.3f} is weak — clusters present but blurry")
    if clusters:
        max_pct = max(c["pct"] for c in clusters)
        if max_pct > 80:
            flags.append(f"⚠ one cluster holds {max_pct:.1f}% of customers — K may be too low or data too uniform")
        labels = {c["label"] for c in clusters}
        if "champions" not in labels:
            flags.append("⚠ no 'champions' cluster — top-tier label wasn't assigned (check centroid ranking)")
    if not flags:
        print(f"    ✓ all checks passed")
    else:
        for f in flags:
            print(f"    {f}")


def _eval_a20(df: pd.DataFrame, result: dict) -> None:
    s = result.get("summary", {})
    buckets = result.get("risk_buckets", []) or []
    importance = result.get("feature_importance", []) or []
    top = result.get("top_at_risk", []) or []

    if result.get("warning"):
        print(f"  ⚠ {result['warning']}")
        # Heuristic fallback still produces results — only bail if nothing landed.
        if s.get("n_customers", 0) == 0:
            return
        print()  # separator, then keep printing what we got

    print(f"  Customers scored:          {s.get('n_customers', 0):>10,}")
    print(f"  Snapshot date:             {s.get('snapshot_date')}")
    print(f"  Churn threshold:           {s.get('churn_threshold_days')} days")
    print(f"  Historical churned:        {s.get('n_churned_historical', 0):>10,}"
          f"  ({s.get('churn_rate_historical_pct', 0):.2f}%)")
    print(f"  Mean predicted P(churn):   {s.get('avg_churn_risk', 0):.4f}")
    acc = s.get("model_accuracy")
    print(f"  Holdout accuracy:          {f'{acc:.4f}' if acc is not None else 'n/a'}")
    print(f"  Model:                     {s.get('model_method')}")

    if buckets:
        print(f"\n  Risk distribution:")
        max_count = max((b['count'] for b in buckets), default=1) or 1
        for b in buckets:
            bar = "█" * int(b['count'] / max_count * 25)
            print(f"    {b['bucket']:<18s} {b['count']:>7,} ({b['pct']:>5.2f}%)  {bar}")

    if importance:
        print(f"\n  Feature importance (by |coefficient|):")
        for f in importance:
            sign = "↑ churn" if f["coefficient"] > 0 else "↓ churn"
            print(f"    {f['feature']:<28s}  coef={f['coefficient']:>+8.4f}  ({sign})")

    if top:
        print(f"\n  Top 5 at-risk customers:")
        print(f"    {'CUSTOMER':<32s} {'P(churn)':>9s} {'RECENCY':>8s} {'FREQ':>5s} {'$ SPEND':>12s}")
        for c in top[:5]:
            print(f"    {str(c['customer_id'])[:30]:<32s} "
                  f"{c['churn_probability']:>9.4f} {c['recency_days']:>7}d "
                  f"{c['frequency']:>5} {c['monetary']:>12,.2f}")

    # Quality flags
    print(f"\n  Quality flags:")
    flags = []
    if s.get("n_customers", 0) == 0:
        flags.append("✗ no customers — model didn't run")
    if acc is not None:
        if acc < 0.55:
            flags.append(f"⚠ holdout accuracy {acc:.2f} ≈ coin flip — features may be too noisy")
        elif acc > 0.95:
            flags.append(f"⚠ accuracy {acc:.2f} is suspiciously high — possible label leakage")
    churn_rate = s.get("churn_rate_historical_pct", 0)
    if churn_rate < 5 or churn_rate > 95:
        flags.append(f"⚠ historical churn rate {churn_rate:.1f}% is extreme — model may be unbalanced")
    if buckets:
        crit = next((b for b in buckets if "critical" in b["bucket"]), None)
        low = next((b for b in buckets if "low" in b["bucket"]), None)
        if crit and crit["pct"] > 60:
            flags.append(f"⚠ {crit['pct']:.1f}% of customers are 'critical' — threshold may be too sensitive")
        if low and low["pct"] > 90:
            flags.append(f"⚠ {low['pct']:.1f}% are 'low risk' — model may be flat-lining")
    if not flags:
        print(f"    ✓ all checks passed")
    else:
        for f in flags:
            print(f"    {f}")


EVALUATORS: dict[str, callable] = {
    "A01_revenue_summary": _eval_a01,
    "A02_rfm_scoring": _eval_a02,
    "A03_market_basket": _eval_a03,
    "A04_gross_margin": _eval_a04,
    "A05_cohort_retention": _eval_a05,
    "A06_geographic_revenue": _eval_a06,
    "A07_abc_classification": _eval_a07,
    "A08_aov_trends": _eval_a08,
    "A09_top_n_products": _eval_a09,
    "A10_customer_lifetime": _eval_a10,
    "A11_order_status": _eval_a11,
    "A12_discount_impact": _eval_a12,
    "A13_growth_rates": _eval_a13,
    "A14_acquisition_channel": _eval_a14,
    "A15_prophet_forecast": _eval_a15,
    "A16_anomaly_detection": _eval_a16,
    "A17_clv_prediction": _eval_a17,
    "A18_sentiment_analysis": _eval_a18,
    "A19_customer_segmentation": _eval_a19,
    "A20_churn_prediction": _eval_a20,
}


# ── Argument parsing ───────────────────────────────────────────────────────


def _resolve_module_key(arg: str) -> str | None:
    """Allow short prefixes like `A01` to match `A01_revenue_summary`."""
    if arg in REGISTRY:
        return arg
    matches = [k for k in REGISTRY if k.upper().startswith(arg.upper())]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous module key '{arg}'. Matches: {matches}", file=sys.stderr)
        sys.exit(2)
    return None


def _list_modules() -> None:
    if not REGISTRY:
        print("(no modules registered)")
        return
    print(f"{'KEY':<32s}  {'TYPE':<12s}  REQUIRED COLUMNS")
    print("-" * 80)
    for k, spec in sorted(REGISTRY.items()):
        req = ", ".join(sorted(spec.required_cols)) or "(none)"
        print(f"{k:<32s}  {spec.analysis_type:<12s}  {req}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Run analytics modules against a CSV.")
    ap.add_argument("--csv", help="Path to a CSV (e.g. seed or dirty variant)")
    ap.add_argument("--module", help="Module key (full or short prefix, e.g. A01)")
    ap.add_argument("--all", action="store_true", help="Run every registered module")
    ap.add_argument("--evaluate", action="store_true", help="Print quality + evaluation metrics")
    ap.add_argument("--save", help="Save full result(s) to a JSON file")
    ap.add_argument("--list", action="store_true", help="List registered modules and exit")
    args = ap.parse_args()

    if args.list:
        _list_modules()
        return 0

    if not args.csv:
        ap.error("--csv is required (unless --list)")
    if not args.module and not args.all:
        ap.error("provide --module <key> or --all")

    csv_path = Path(args.csv).expanduser().resolve()
    if not csv_path.exists():
        print(f"ERROR: CSV not found: {csv_path}", file=sys.stderr)
        return 1

    print(f"Loading {csv_path.name} ...")
    # Handle BOM transparently; chardet would be overkill for Windows-saved CSVs.
    df = pd.read_csv(csv_path, encoding="utf-8-sig", on_bad_lines="skip")
    print(f"  rows: {len(df):,}   columns: {len(df.columns)}")

    available = set(df.columns)

    if args.all:
        modules = list(REGISTRY.values())
    else:
        key = _resolve_module_key(args.module)
        if not key:
            print(f"ERROR: module '{args.module}' not found.", file=sys.stderr)
            print(f"Available: {sorted(REGISTRY.keys())}", file=sys.stderr)
            return 1
        modules = [REGISTRY[key]]

    all_results: dict[str, dict] = {}
    for spec in modules:
        eligible, missing = spec.can_run(available)
        print(f"\n{'━' * 78}")
        print(f"[{spec.key}]  {spec.description}")
        print(f"{'━' * 78}")
        if not eligible:
            print(f"  SKIPPED — missing required columns: {sorted(missing)}")
            continue

        t0 = time.time()
        try:
            result = spec.fn(df)
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            print(f"  ✗ FAILED in {ms} ms: {type(e).__name__}: {e}")
            continue

        ms = int((time.time() - t0) * 1000)
        print(f"  ✓ Completed in {ms} ms")
        all_results[spec.key] = result

        if args.evaluate and spec.key in EVALUATORS:
            print()
            EVALUATORS[spec.key](df, result)
        elif args.evaluate:
            print(f"  (no evaluator registered for {spec.key} — pass --save to inspect raw)")

    if args.save:
        out = Path(args.save).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(all_results, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        print(f"\n✓ Saved {len(all_results)} module result(s) to {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
