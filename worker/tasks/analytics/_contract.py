"""Shared helpers for the Decision-Chart v1 worker output contract.

Every analytics module now emits 4 standardised fields on top of its existing
payload so the frontend can render the new 6-zone shell uniformly:

    question            — frozen owner-voice question this chart answers
    headline            — big number + trend strip
    fallback_bullets    — 3 plain-English bullets (LLM swap later)
    suggested_actions   — 2–3 action chips beneath the chart

These helpers are pure data-shape utilities — they don't compute insights
themselves. Each module still derives its own bullets/actions from its data
and hands them here; this file just enforces consistent shape and length
limits.

Why a helper file
-----------------
Hand-rolling these four fields in every one of the 39 modules invites drift.
Centralising the assembly here means the contract is enforced once, and a
later change (e.g. adding a `confidence` band, swapping in an LLM call)
modifies one file instead of 39.
"""

from __future__ import annotations

from typing import Any, Literal

TrendDirection = Literal["up", "down", "flat"]
ActionKind = Literal[
    "primary", "secondary",
    "brand", "positive", "warning", "danger", "info", "neutral",
]
IconHint = Literal["arrow", "download", "more"]

# Max chars per bullet — enforced at assembly. Matches the frontend
# AIInsightPanel which truncates at the same cap.
BULLET_CHAR_LIMIT = 140


def build_headline(
    *,
    value: float | int,
    label: str,
    trend_pct: float | None = None,
    trend_direction: TrendDirection | None = None,
    period: str = "All time",
) -> dict[str, Any]:
    """Standardise the headline strip the chart's zone 2 renders.

    If `trend_direction` is omitted, it's derived from `trend_pct`:
      pct >  1.0  → "up"
      pct < -1.0  → "down"
      otherwise   → "flat"
    """
    direction: TrendDirection | None = trend_direction
    if direction is None and trend_pct is not None:
        if trend_pct > 1.0:
            direction = "up"
        elif trend_pct < -1.0:
            direction = "down"
        else:
            direction = "flat"

    return {
        "value": value,
        "label": label,
        "trend_pct": trend_pct,
        "trend_direction": direction,
        "period": period,
    }


def safe_bullets(raw: list[str] | None) -> list[str]:
    """Filter, trim, and cap a bullet list to the contract.

    Drops empty strings; truncates each bullet to BULLET_CHAR_LIMIT chars
    (with an ellipsis); returns at most 3.

    Modules that can't produce real bullets yet (e.g. no data) should pass
    sensible static defaults rather than an empty list — the frontend has
    an empty-state, but a populated card with even a generic bullet feels
    more polished than a stub.
    """
    if not raw:
        return []
    out: list[str] = []
    for b in raw:
        if not isinstance(b, str):
            continue
        s = b.strip()
        if not s:
            continue
        if len(s) > BULLET_CHAR_LIMIT:
            s = s[: BULLET_CHAR_LIMIT - 1] + "…"
        out.append(s)
        if len(out) == 3:
            break
    return out


def action(
    label: str,
    *,
    kind: ActionKind = "secondary",
    deeplink: str | None = None,
    icon: IconHint = "arrow",
) -> dict[str, Any]:
    """Single suggested-action object the frontend's ActionChipRow consumes."""
    return {"label": label, "kind": kind, "deeplink": deeplink, "icon": icon}


def build_payload(
    *,
    question: str,
    headline: dict[str, Any],
    fallback_bullets: list[str],
    suggested_actions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Wrap the four contract fields into a dict ready to merge with module
    output via `{**legacy_payload, **build_payload(...)}`."""
    return {
        "question": question,
        "headline": headline,
        "fallback_bullets": safe_bullets(fallback_bullets),
        "suggested_actions": suggested_actions or [],
    }


# ── Convenience formatters ─────────────────────────────────────────────────
# Avoid pulling pandas / babel into modules just for trivial number cleanup.

def fmt_money(n: float | int) -> str:
    """USD-shape compact formatter, used in bullets."""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "$0"
    if abs(n) >= 1_000_000:
        return f"${n/1_000_000:.1f}M"
    if abs(n) >= 1_000:
        return f"${n/1_000:.1f}k"
    return f"${n:.0f}"


def fmt_int(n: float | int) -> str:
    """Compact integer formatter, used in bullets."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "0"
    if abs(n) >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if abs(n) >= 10_000:
        return f"{n/1_000:.1f}k"
    return f"{n:,}"


def fmt_pct(n: float | int, decimals: int = 1) -> str:
    """Percentage formatter, used in bullets and headline labels."""
    try:
        return f"{float(n):.{decimals}f}%"
    except (TypeError, ValueError):
        return "0%"


def trend_from_series(values: list[float]) -> tuple[float | None, TrendDirection | None]:
    """Compute (trend_pct, direction) from a numeric series.

    Compares the last value to the second-to-last. Returns (None, None) if
    the series has fewer than 2 values or the previous value is zero.
    Used by modules that have a per-period series and want to surface the
    most recent period-over-period delta in the headline strip.
    """
    if len(values) < 2:
        return None, None
    last = float(values[-1])
    prev = float(values[-2])
    if prev == 0:
        return None, None
    pct = round((last - prev) / prev * 100.0, 1)
    direction: TrendDirection = "up" if pct > 1.0 else "down" if pct < -1.0 else "flat"
    return pct, direction
