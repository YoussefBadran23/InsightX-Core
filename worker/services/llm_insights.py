"""
InsightX — Gemini 2.0 Flash LLM enrichment service (Phase 4).

Public API:
    enrich_with_llm(payload, locale, redis) -> dict
    get_redis_client() -> redis.Redis | None
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

_DAILY_QUOTA = 1_400
_CACHE_TTL   = 3_600   # 1 hour
_QUOTA_TTL   = 86_400  # 1 day

_model = None  # lazy-initialised singleton


# ── Model init ────────────────────────────────────────────────────────────────

def _get_model():
    global _model
    if _model is not None:
        return _model
    api_key = os.getenv("GOOGLE_AI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        _model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config={"response_mime_type": "application/json"},
        )
        logger.info("Gemini 2.0 Flash model initialised.")
    except Exception as exc:
        logger.warning(f"Gemini init failed: {exc}")
        _model = None
    return _model


# ── Redis helpers ─────────────────────────────────────────────────────────────

def get_redis_client():
    url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    try:
        import redis as _redis
        client = _redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
        client.ping()
        return client
    except Exception as exc:
        logger.warning(f"Redis unavailable for LLM cache: {exc}")
        return None


def _build_cache_key(payload: dict, locale: str) -> str:
    stable = {
        "module_key": payload.get("module_key"),
        "locale":     locale,
        "headline":   payload.get("headline"),
        "top3":       (payload.get("fallback_bullets") or [])[:3],
    }
    digest = hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return f"llm_cache:{digest}"


def _quota_exceeded(redis_client) -> bool:
    key = f"llm_calls:{date.today().isoformat()}"
    calls = int(redis_client.get(key) or 0)
    return calls >= _DAILY_QUOTA


def _increment_quota(redis_client) -> None:
    key = f"llm_calls:{date.today().isoformat()}"
    redis_client.incr(key)
    redis_client.expire(key, _QUOTA_TTL)


# ── Prompts ───────────────────────────────────────────────────────────────────

_SYSTEM_EN = (
    "You are a senior e-commerce analyst. "
    "Given a JSON analytics payload, produce concise, actionable insights in English. "
    "Respond ONLY with valid JSON matching the schema provided."
)
_SYSTEM_AR = (
    "أنت محلل تجارة إلكترونية أول. "
    "بناءً على حمولة JSON التحليلية المقدمة، اكتب رؤى موجزة وقابلة للتنفيذ باللغة العربية. "
    "أجب بـ JSON صالح فقط يطابق المخطط المقدم."
)

_USER_TMPL = """\
Module: {module_key}
Headline: {headline_value} {headline_label} ({trend_pct:+.1f}% {trend_direction} vs {period})

Current fallback bullets:
{bullets}

Return JSON with this exact schema:
{{
  "llm_bullets": ["<insight 1>", "<insight 2>", "<insight 3>"],
  "llm_actions": [
    {{"label": "<CTA>", "kind": "navigate|filter|export", "deeplink": "<path>", "icon": "<lucide-icon>"}}
  ]
}}
Rules:
- llm_bullets: exactly 3 strings, each <= 200 characters, language = {lang}
- llm_actions: 1-4 items
- No markdown, no extra keys
"""


def _build_prompt(payload: dict, locale: str) -> tuple[str, str]:
    system = _SYSTEM_AR if locale == "ar" else _SYSTEM_EN
    lang   = "Arabic" if locale == "ar" else "English"
    h      = payload.get("headline") or {}
    bullets = "\n".join(f"- {b}" for b in (payload.get("fallback_bullets") or []))
    user = _USER_TMPL.format(
        module_key      = payload.get("module_key", "unknown"),
        headline_value  = h.get("value", ""),
        headline_label  = h.get("label", ""),
        trend_pct       = float(h.get("trend_pct", 0)),
        trend_direction = h.get("trend_direction", ""),
        period          = h.get("period", ""),
        bullets         = bullets or "(none)",
        lang            = lang,
    )
    return system, user


# ── Validation ────────────────────────────────────────────────────────────────

def _valid_insights(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    bullets = data.get("llm_bullets")
    actions = data.get("llm_actions")
    if not isinstance(bullets, list) or len(bullets) != 3:
        return False
    if any(not isinstance(b, str) or len(b) > 200 for b in bullets):
        return False
    if not isinstance(actions, list) or not (1 <= len(actions) <= 4):
        return False
    return True


# ── Fallback ──────────────────────────────────────────────────────────────────

_FALLBACK_BULLETS_EN = [
    "Review the headline metric and compare against your industry benchmark.",
    "Identify the top contributing segment and focus optimisation efforts there.",
    "Set a 30-day target and monitor weekly to stay on track.",
]
_FALLBACK_BULLETS_AR = [
    "راجع المقياس الرئيسي وقارنه بمعيار الصناعة الخاص بك.",
    "حدد الشريحة الأعلى مساهمةً وركّز جهود التحسين عليها.",
    "ضع هدفاً لمدة 30 يوماً وراقب الأداء أسبوعياً للبقاء على المسار الصحيح.",
]
_FALLBACK_ACTIONS = [
    {"label": "View Details", "kind": "navigate", "deeplink": "/dashboard/analytics", "icon": "BarChart2"},
]
_FALLBACK_ACTIONS_AR = [
    {"label": "عرض التفاصيل", "kind": "navigate", "deeplink": "/dashboard/analytics", "icon": "BarChart2"},
]


def _fallback_payload(payload: dict, locale: str) -> dict:
    bullets = _FALLBACK_BULLETS_AR if locale == "ar" else _FALLBACK_BULLETS_EN
    actions = _FALLBACK_ACTIONS_AR if locale == "ar" else _FALLBACK_ACTIONS
    return {**payload, "llm_bullets": bullets, "llm_actions": actions}


# ── Public entry point ────────────────────────────────────────────────────────

def enrich_with_llm(payload: dict, locale: str = "en", redis=None) -> dict:
    """
    Enrich an analytics payload with Gemini-generated bullets and actions.
    Always returns a dict — never raises.
    """
    model = _get_model()
    if model is None:
        return _fallback_payload(payload, locale)

    # Cache hit
    cache_key = _build_cache_key(payload, locale)
    if redis:
        try:
            cached = redis.get(cache_key)
            if cached:
                return {**payload, **json.loads(cached)}
        except Exception:
            pass

    # Quota check
    if redis:
        try:
            if _quota_exceeded(redis):
                logger.warning("LLM daily quota reached — returning fallback.")
                return _fallback_payload(payload, locale)
        except Exception:
            pass

    # Call Gemini
    try:
        system_prompt, user_prompt = _build_prompt(payload, locale)
        response = model.generate_content(
            [{"role": "user", "parts": [system_prompt + "\n\n" + user_prompt]}]
        )
        insights = json.loads(response.text)
        if not _valid_insights(insights):
            raise ValueError(f"Schema mismatch: {list(insights.keys())}")

        enriched = {"llm_bullets": insights["llm_bullets"], "llm_actions": insights["llm_actions"]}
        if redis:
            try:
                redis.setex(cache_key, _CACHE_TTL, json.dumps(enriched, ensure_ascii=False))
                _increment_quota(redis)
            except Exception:
                pass
        return {**payload, **enriched}

    except Exception as exc:
        logger.warning(f"LLM enrichment failed for '{payload.get('module_key')}': {exc}")
        return _fallback_payload(payload, locale)
