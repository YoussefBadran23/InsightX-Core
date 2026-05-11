"""run_matrix.py — Full validation pipeline.

Runs every registered analytics module against every CSV in datasets/output/.
For each (csv, module) cell, records: status (ok|warning|skipped|fail),
duration, warning text, error, output digest.

Output:
  1. A compact pass/fail matrix (CSVs as rows, modules as columns).
  2. A per-CSV summary table.
  3. A detailed error log for every fail / warning so we know what to fix.
  4. A JSON dump at out/matrix_results.json for later inspection.

Usage:
  python run_matrix.py
  python run_matrix.py --only A21,A22       # filter to specific modules
  python run_matrix.py --csv arabic_seed    # filter to one CSV
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import schema  # noqa: E402
import tasks.analytics  # noqa: E402,F401  # populates registry

from rapidfuzz import fuzz, process  # noqa: E402


# ── Paths ───────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent
CSV_DIR = (ROOT / ".." / "datasets" / "output").resolve()
OUT_DIR = ROOT / "out"
OUT_DIR.mkdir(exist_ok=True)


# ── Header normalization (fuzzy match to schema.COLUMNS aliases) ────────────

def _norm(s: str) -> str:
    # Preserve Unicode word characters so Arabic / Hebrew / CJK header names
    # survive the normalization step. Without re.UNICODE, "رقم الطلب" becomes
    # empty string and the alias pool can't contain non-Latin keys.
    s = s.lower().strip()
    s = re.sub(r"[^\w]+", "_", s, flags=re.UNICODE)
    return s.strip("_")


def _build_alias_pool() -> dict[str, str]:
    pool: dict[str, str] = {}
    for col in schema.COLUMNS:
        for cand in (col.internal_column, col.display_name, *col.aliases):
            key = _norm(cand)
            if key:
                pool.setdefault(key, col.internal_column)
    return pool


ALIAS_POOL = _build_alias_pool()
POOL_KEYS = tuple(ALIAS_POOL.keys())


def normalize_headers(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """Return (renamed_df, mapping). Mapping = {original → internal_column}."""
    rename: dict[str, str] = {}
    seen_internal: set[str] = set()
    for c in df.columns:
        key = _norm(c)
        target = None
        if key in ALIAS_POOL:
            target = ALIAS_POOL[key]
        else:
            best = process.extractOne(key, POOL_KEYS, scorer=fuzz.WRatio)
            if best and best[1] >= 75:
                target = ALIAS_POOL[best[0]]
        if target and target not in seen_internal:
            rename[c] = target
            seen_internal.add(target)
    return df.rename(columns=rename), rename


# ── Safe CSV reading ────────────────────────────────────────────────────────

def safe_read_csv(path: Path) -> pd.DataFrame:
    """Try a sequence of encodings + on_bad_lines='skip'."""
    last_err = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return pd.read_csv(path, encoding=enc, on_bad_lines="skip", low_memory=False)
        except UnicodeDecodeError as e:
            last_err = e
            continue
    raise last_err or RuntimeError(f"Could not decode {path}")


# ── Result digest (helps reading the matrix output) ─────────────────────────

def _digest(result: dict) -> str:
    """One-line digest of the module's output for the report."""
    if not isinstance(result, dict):
        return f"<non-dict result: {type(result).__name__}>"
    summary = result.get("summary") or {}
    bits = []
    for k in ("n_customers", "n_products", "n_orders", "n_returns",
              "n_anomalies", "n_clusters", "n_brands", "n_categories",
              "total_revenue", "overall_return_rate_pct",
              "avg_delivery_days", "sla_compliance_pct",
              "silhouette_score", "avg_churn_risk",
              "pearson_correlation"):
        if k in summary and summary[k] is not None:
            v = summary[k]
            if isinstance(v, float):
                bits.append(f"{k}={v:.3f}".rstrip("0").rstrip("."))
            else:
                bits.append(f"{k}={v}")
        if len(bits) >= 3:
            break
    return ", ".join(bits) or "ok"


# ── Matrix execution ────────────────────────────────────────────────────────

def run_matrix(only_modules: list[str] | None, only_csvs: list[str] | None) -> list[dict]:
    results: list[dict] = []
    csvs = sorted(CSV_DIR.glob("*.csv"))
    if only_csvs:
        csvs = [p for p in csvs if any(s in p.name for s in only_csvs)]

    module_keys = sorted(schema.MODULES.keys())
    if only_modules:
        module_keys = [k for k in module_keys if any(k.startswith(m) for m in only_modules)]

    for csv_path in csvs:
        try:
            df_raw = safe_read_csv(csv_path)
        except Exception as e:
            print(f"  CSV READ FAIL  {csv_path.name}: {e}")
            results.append({
                "csv": csv_path.name, "module": "__READ__",
                "status": "fail", "error": str(e),
            })
            continue

        df, mapping = normalize_headers(df_raw)
        avail = set(df.columns)
        eligibility = schema.check_eligibility(avail)
        n_rows = len(df)

        print(f"\n— {csv_path.name}  ({n_rows:,} rows, {len(df.columns)} cols, {len(mapping)} matched)")

        for key in module_keys:
            mod = schema.MODULES[key]
            if mod.fn is None:
                continue
            elig = eligibility[key]
            if not elig["can_run"]:
                results.append({
                    "csv": csv_path.name, "module": key,
                    "status": "skipped",
                    "missing": elig["missing_required"],
                    "duration_ms": 0,
                })
                continue

            t0 = time.time()
            try:
                out = mod.fn(df.copy())
                dur = int((time.time() - t0) * 1000)
                warning = out.get("warning") if isinstance(out, dict) else None
                results.append({
                    "csv": csv_path.name, "module": key,
                    "status": "warning" if warning else "ok",
                    "warning": warning,
                    "digest": _digest(out),
                    "duration_ms": dur,
                })
            except Exception as e:
                dur = int((time.time() - t0) * 1000)
                tb = traceback.format_exc(limit=3)
                results.append({
                    "csv": csv_path.name, "module": key,
                    "status": "fail",
                    "error": f"{type(e).__name__}: {e}",
                    "traceback": tb,
                    "duration_ms": dur,
                })

    return results


# ── Reporting ───────────────────────────────────────────────────────────────

STATUS_GLYPH = {"ok": "✓", "warning": "!", "fail": "X", "skipped": "·"}


def print_matrix(results: list[dict]) -> None:
    csvs = sorted({r["csv"] for r in results if r["module"] != "__READ__"})
    modules = sorted({r["module"] for r in results if r["module"] != "__READ__"})
    by_cell: dict[tuple[str, str], str] = {(r["csv"], r["module"]): r["status"] for r in results}

    # Compact matrix: short labels
    print("\n" + "=" * 100)
    print("MATRIX  (✓=ok  !=warning  X=fail  ·=skipped)")
    print("=" * 100)
    # Header — short module keys (A01, A02, ..., A26, C01, ..., P07)
    short_keys = [m.split("_", 1)[0] for m in modules]
    header = "CSV".ljust(36) + " ".join(k.rjust(3) for k in short_keys)
    print(header)
    for csv in csvs:
        cells = []
        for m in modules:
            status = by_cell.get((csv, m), "·")
            cells.append(STATUS_GLYPH.get(status, "?").rjust(3))
        print(csv[:35].ljust(36) + " ".join(cells))


def print_summary(results: list[dict]) -> None:
    csvs = sorted({r["csv"] for r in results if r["module"] != "__READ__"})
    print("\n" + "=" * 100)
    print("PER-CSV SUMMARY")
    print("=" * 100)
    print(f"{'CSV':<36}  {'ok':>4}  {'warn':>4}  {'fail':>4}  {'skip':>4}")
    for csv in csvs:
        ok = sum(1 for r in results if r["csv"] == csv and r["status"] == "ok")
        w  = sum(1 for r in results if r["csv"] == csv and r["status"] == "warning")
        f  = sum(1 for r in results if r["csv"] == csv and r["status"] == "fail")
        s  = sum(1 for r in results if r["csv"] == csv and r["status"] == "skipped")
        print(f"{csv[:35]:<36}  {ok:>4}  {w:>4}  {f:>4}  {s:>4}")


def print_per_module_summary(results: list[dict]) -> None:
    modules = sorted({r["module"] for r in results if r["module"] != "__READ__"})
    print("\n" + "=" * 100)
    print("PER-MODULE SUMMARY")
    print("=" * 100)
    print(f"{'MODULE':<32}  {'ok':>4}  {'warn':>4}  {'fail':>4}  {'skip':>4}")
    for m in modules:
        ok = sum(1 for r in results if r["module"] == m and r["status"] == "ok")
        w  = sum(1 for r in results if r["module"] == m and r["status"] == "warning")
        f  = sum(1 for r in results if r["module"] == m and r["status"] == "fail")
        s  = sum(1 for r in results if r["module"] == m and r["status"] == "skipped")
        print(f"{m[:31]:<32}  {ok:>4}  {w:>4}  {f:>4}  {s:>4}")


def print_failures(results: list[dict]) -> None:
    fails = [r for r in results if r["status"] == "fail"]
    if not fails:
        return
    print("\n" + "=" * 100)
    print(f"FAILURES ({len(fails)})")
    print("=" * 100)
    for r in fails:
        print(f"\n  ✗ {r['csv']}  /  {r['module']}")
        print(f"    {r.get('error', '')}")
        tb = r.get("traceback")
        if tb:
            for line in tb.splitlines()[-6:]:
                print(f"      {line}")


def print_warnings(results: list[dict]) -> None:
    warns = [r for r in results if r["status"] == "warning"]
    if not warns:
        return
    print("\n" + "=" * 100)
    print(f"WARNINGS ({len(warns)})")
    print("=" * 100)
    for r in warns:
        print(f"  ! {r['csv']:<36}  {r['module']:<32}  {r.get('warning')}")


def headline(results: list[dict]) -> tuple[int, int, int, int]:
    ok   = sum(1 for r in results if r["status"] == "ok")
    warn = sum(1 for r in results if r["status"] == "warning")
    fail = sum(1 for r in results if r["status"] == "fail")
    skip = sum(1 for r in results if r["status"] == "skipped")
    return ok, warn, fail, skip


# ── Main ────────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="Comma-separated module-key prefixes", default=None)
    ap.add_argument("--csv",  help="Comma-separated CSV name substrings",  default=None)
    args = ap.parse_args()

    only_modules = args.only.split(",") if args.only else None
    only_csvs    = args.csv.split(",")  if args.csv  else None

    print(f"\nRunning matrix across {CSV_DIR}")
    print(f"  Modules: {len([k for k in schema.MODULES if schema.MODULES[k].fn])} with fn")
    print(f"  CSVs:    {sum(1 for _ in CSV_DIR.glob('*.csv'))}")

    t0 = time.time()
    results = run_matrix(only_modules, only_csvs)
    elapsed = time.time() - t0

    # Persist
    json_path = OUT_DIR / "matrix_results.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nWrote {json_path}  ({len(results)} cells, {elapsed:.1f}s)")

    print_matrix(results)
    print_summary(results)
    print_per_module_summary(results)
    print_warnings(results)
    print_failures(results)

    ok, warn, fail, skip = headline(results)
    total = ok + warn + fail + skip
    print("\n" + "=" * 100)
    print(f"HEADLINE  {ok}/{total} OK  ·  {warn} warnings  ·  {fail} fails  ·  {skip} skipped")
    print("=" * 100)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
