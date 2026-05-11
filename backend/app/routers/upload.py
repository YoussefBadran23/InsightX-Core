"""CSV Upload Router — handles receiving files, sniffing, and confirming mappings."""

import os
import re
import uuid
import shutil
import csv
import io
import chardet
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from rapidfuzz import fuzz

from app.core.celery_client import celery_client
from app.core.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.upload_job import UploadJob
from app.models.user import User
from app.models.csv_column_mapping import CsvColumnMapping
import schema

router = APIRouter(prefix="/upload", tags=["Upload"])

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "pending"), exist_ok=True)

_ALLOWED_CONTENT_TYPES = {"text/csv", "application/csv", "application/vnd.ms-excel"}


# ── Header matcher: fuzzy + (optional) semantic ───────────────────────────────

_MATCHED_THRESHOLD = 0.72
_AMBIGUOUS_THRESHOLD = 0.55
_FUZZY_SCORERS = (fuzz.WRatio, fuzz.token_sort_ratio, fuzz.token_set_ratio, fuzz.partial_ratio)


def _normalize(text: str) -> str:
    """Lowercase, strip, collapse non-word runs to a single underscore.

    Uses re.UNICODE so Arabic / Hebrew / CJK headers survive — without it the
    Arabic dirty CSV's headers (e.g. "رقم الطلب") get reduced to empty
    strings and never match the alias pool.
    """
    text = text.lower().strip()
    text = re.sub(r"[^\w]+", "_", text, flags=re.UNICODE)
    return text.strip("_")


def _build_match_pool() -> dict[str, str]:
    """Build {normalized_key: internal_column}.

    Includes the canonical internal_column and display_name in addition to
    the hand-written aliases — fixes the bug where a CSV with a header named
    exactly 'customer_id' or 'order_date' would not match because those names
    were absent from the alias pool.
    """
    pool: dict[str, str] = {}
    for col in schema.COLUMNS:
        for cand in (col.internal_column, col.display_name, *col.aliases):
            key = _normalize(cand)
            if key:
                pool.setdefault(key, col.internal_column)
    return pool


_MATCH_POOL: dict[str, str] = _build_match_pool()
_POOL_KEYS: tuple[str, ...] = tuple(_MATCH_POOL.keys())


# Lazy-loaded sentence-transformer for semantic matching. If the library isn't
# installed (or model load fails) we silently fall back to fuzzy-only matching.
_EMBED_STATE: dict = {"tried": False, "model": None, "vecs": None, "keys": None}


def _semantic_resources():
    """Return (model, schema_vectors, internal_column_keys) or (None, None, None)."""
    if _EMBED_STATE["tried"]:
        return _EMBED_STATE["model"], _EMBED_STATE["vecs"], _EMBED_STATE["keys"]
    _EMBED_STATE["tried"] = True
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        model = SentenceTransformer("all-MiniLM-L6-v2")
        texts: list[str] = []
        keys: list[str] = []
        for col in schema.COLUMNS:
            blob = f"{col.display_name}. {col.internal_column}. " + " ".join(col.aliases)
            texts.append(blob)
            keys.append(col.internal_column)
        vecs = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        _EMBED_STATE["model"], _EMBED_STATE["vecs"], _EMBED_STATE["keys"] = model, vecs, keys
        return model, vecs, keys
    except Exception:
        return None, None, None


def _semantic_match(header: str) -> tuple[Optional[str], float]:
    """Return (internal_column, cosine_similarity) or (None, 0.0) if unavailable."""
    model, vecs, keys = _semantic_resources()
    if model is None or vecs is None or not keys:
        return None, 0.0
    import numpy as np

    q = model.encode(header, normalize_embeddings=True, convert_to_numpy=True)
    sims = vecs @ q  # cosine, since both sides are L2-normalized
    idx = int(np.argmax(sims))
    return keys[idx], float(sims[idx])


def _fuzzy_match(header_norm: str) -> tuple[Optional[str], float, list[tuple[str, float]]]:
    """Best fuzzy match using max() over multiple RapidFuzz scorers.

    When two pool keys score the same (commonly happens with partial_ratio=100
    because a short alias is a substring of the header — e.g. "count" inside
    "customer_country"), prefer the LONGER matching alias. Ties on raw score
    are broken by alias length so the more "specific" match wins.

    Returns (best_internal_column, score, top_3_distinct).
    """
    if not _POOL_KEYS:
        return None, 0.0, []
    if header_norm in _MATCH_POOL:
        return _MATCH_POOL[header_norm], 1.0, []

    # Track (score, matched_alias_length) per internal column. Tuple comparison
    # gives us score-first, length-as-tiebreaker for free.
    best_per_col: dict[str, tuple[float, int]] = {}
    for key in _POOL_KEYS:
        s = max(scorer(header_norm, key) for scorer in _FUZZY_SCORERS) / 100.0
        internal = _MATCH_POOL[key]
        candidate = (s, len(key))
        if candidate > best_per_col.get(internal, (0.0, 0)):
            best_per_col[internal] = candidate

    if not best_per_col:
        return None, 0.0, []
    ranked = sorted(best_per_col.items(), key=lambda kv: kv[1], reverse=True)
    top_3 = [(col, sc[0]) for col, sc in ranked[:3]]
    return ranked[0][0], ranked[0][1][0], top_3


def _resolve_header(header: str) -> tuple[Optional[str], float, str, list[dict]]:
    """Combine fuzzy + semantic. Returns (internal_col_or_None, confidence, status, alternatives)."""
    norm = _normalize(header)
    if not norm:
        return None, 0.0, "unmatched", []

    fuzzy_col, fuzzy_score, fuzzy_top = _fuzzy_match(norm)
    sem_col, sem_score = _semantic_match(header)

    if len(norm) <= 4:
        # Embeddings are unreliable on very short tokens; trust fuzzy only.
        chosen, conf = fuzzy_col, fuzzy_score
    elif fuzzy_col and fuzzy_col == sem_col:
        # Both methods agree → small confidence bonus
        chosen = fuzzy_col
        conf = min(1.0, max(fuzzy_score, sem_score) + 0.05)
    elif fuzzy_score >= sem_score:
        chosen, conf = fuzzy_col, fuzzy_score
    else:
        chosen, conf = sem_col, sem_score

    if conf >= _MATCHED_THRESHOLD:
        status_val = "matched"
    elif conf >= _AMBIGUOUS_THRESHOLD:
        status_val = "ambiguous"
    else:
        status_val = "unmatched"

    alternatives: list[dict] = []
    if status_val == "ambiguous":
        seen: set[str] = set()
        for col_key, score in fuzzy_top:
            if col_key in seen:
                continue
            seen.add(col_key)
            col_def = schema.COLUMN_MAP.get(col_key)
            if col_def:
                alternatives.append({
                    "internal_column": col_key,
                    "display_name": col_def.display_name,
                    "confidence": round(score, 3),
                })
        if sem_col and sem_col not in seen:
            col_def = schema.COLUMN_MAP.get(sem_col)
            if col_def:
                alternatives.append({
                    "internal_column": sem_col,
                    "display_name": col_def.display_name,
                    "confidence": round(sem_score, 3),
                })

    return (chosen if status_val != "unmatched" else None), conf, status_val, alternatives


# ── Pydantic models ───────────────────────────────────────────────────────────


class ConfirmedMapping(BaseModel):
    csv_header: str
    internal_column: Optional[str]


class ConfirmRequest(BaseModel):
    sniff_id: str
    confirmed_mappings: list[ConfirmedMapping]


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post("/sniff", status_code=status.HTTP_200_OK)
async def sniff_csv(
    file: UploadFile,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Read headers + 5 rows, fuzzy + semantic match, return mapping preview.
    Saves the file to a pending directory for the subsequent /confirm call."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    sample_bytes = await file.read(64 * 1024)
    encoding = chardet.detect(sample_bytes)["encoding"] or "utf-8"
    await file.seek(0)

    try:
        content = sample_bytes.decode(encoding, errors="replace")
        reader = csv.reader(io.StringIO(content))
        headers = next(reader)
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to parse CSV headers.")

    headers = [h.strip() for h in headers if h.strip()]
    if not headers:
        raise HTTPException(status_code=400, detail="No headers found in CSV.")

    sniff_id = uuid.uuid4().hex
    unique_filename = f"{sniff_id}_{file.filename}"
    pending_path = os.path.join(UPLOAD_DIR, "pending", unique_filename)
    try:
        with open(pending_path, "wb") as buf:
            shutil.copyfileobj(file.file, buf)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save pending file: {e}")

    mappings: list[dict] = []
    matched_internal_cols: set[str] = set()

    for header in headers:
        internal_col, confidence, mapping_status, alternatives = _resolve_header(header)
        col_def = schema.COLUMN_MAP.get(internal_col) if internal_col else None
        if mapping_status == "matched" and internal_col:
            matched_internal_cols.add(internal_col)

        mappings.append({
            "csv_header": header,
            "status": mapping_status,
            "internal_column": internal_col,
            "display_name": col_def.display_name if col_def else None,
            "group": col_def.group if col_def else None,
            "confidence": round(confidence, 3),
            "alternatives": alternatives,
        })

    # Missing-columns analysis (transaction-group columns block specific modules)
    missing_columns: list[dict] = []
    for col in schema.COLUMNS:
        if col.internal_column in matched_internal_cols:
            continue
        is_blocking = False
        blocked_modules: list[str] = []
        if col.group == "transaction":
            for mod in schema.MODULES.values():
                if col.internal_column in mod.required_cols:
                    blocked_modules.append(f"{mod.key.split('_')[0]} — {mod.name}")
                    is_blocking = True
        missing_columns.append({
            "internal_column": col.internal_column,
            "display_name": col.display_name,
            "group": col.group,
            "type": "blocking" if is_blocking else "enrichment",
            "blocked_modules": blocked_modules,
        })

    eligibility = schema.check_eligibility(matched_internal_cols)
    eligible_count = sum(1 for v in eligibility.values() if v["can_run"])

    return {
        "sniff_id": unique_filename,
        "csv_headers": headers,
        "mappings": mappings,
        "missing_columns": missing_columns,
        "module_summary": {
            "total": len(schema.MODULES),
            "eligible": eligible_count,
            "blocked": len(schema.MODULES) - eligible_count,
        },
    }


@router.post("/confirm", status_code=status.HTTP_200_OK)
async def confirm_mappings(
    req: ConfirmRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    pending_path = os.path.join(UPLOAD_DIR, "pending", req.sniff_id)
    if not os.path.exists(pending_path):
        raise HTTPException(status_code=404, detail="Pending upload not found or expired.")

    original_filename = req.sniff_id.split("_", 1)[1] if "_" in req.sniff_id else req.sniff_id

    upload_job = UploadJob(
        user_id=current_user.id,
        s3_key=original_filename,
        original_filename=original_filename,
        status="pending",
    )
    db.add(upload_job)
    db.flush()

    job_id_str = str(upload_job.id)
    final_filename = f"{job_id_str}_{original_filename}"
    upload_job.s3_key = final_filename

    final_path = os.path.join(UPLOAD_DIR, final_filename)
    shutil.move(pending_path, final_path)

    for mapping in req.confirmed_mappings:
        if mapping.internal_column:
            db.add(CsvColumnMapping(
                upload_job_id=upload_job.id,
                csv_header=mapping.csv_header,
                mapped_table="auto",
                mapped_column_name=mapping.internal_column,
                match_score=1.0,
                match_method="user_confirmed",
                is_confirmed=True,
            ))

    try:
        db.commit()
        db.refresh(upload_job)
        task = celery_client.send_task("tasks.pipeline.stage3_preprocess", args=[job_id_str])
        upload_job.celery_task_id = task.id
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=503, detail=f"Task dispatch failed: {e}")

    return {"job_id": job_id_str, "status": "processing"}


@router.post("/csv", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
async def upload_csv_legacy():
    raise HTTPException(status_code=503, detail="Upload flow is being upgraded. Back shortly.")


@router.get("/schema/columns", status_code=status.HTTP_200_OK)
async def get_schema_columns():
    """Return the full schema column list for frontend dropdowns."""
    return [
        {
            "internal_column": col.internal_column,
            "display_name": col.display_name,
            "group": col.group,
        }
        for col in schema.COLUMNS
    ]
