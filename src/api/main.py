from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import numpy as np
import pandas as pd
import joblib
import json
import redis
import time
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────
MODELS_DIR    = Path("src/models/saved")
PROCESSED_DIR = Path("data/processed")

# ── Load all models at startup (once, not per request) ─────────
scaler          = joblib.load(MODELS_DIR / "scaler.pkl")
iso_forest      = joblib.load(MODELS_DIR / "isolation_forest.pkl")
xgb_model       = joblib.load(MODELS_DIR / "xgboost_model.pkl")
explainer       = joblib.load(MODELS_DIR / "shap_explainer.pkl")
ensemble_config = joblib.load(MODELS_DIR / "ensemble_config.pkl")
scaler_params   = np.load(PROCESSED_DIR / "scaler_params.npy")

with open(PROCESSED_DIR / "feature_metadata.json") as f:
    meta = json.load(f)

FEATURE_COLS = meta['feature_cols']
RISK_MIN     = scaler_params[0]
RISK_MAX     = scaler_params[1]
W_IF         = ensemble_config['W_IF']
W_XGB        = ensemble_config['W_XGB']

# ── Redis connection ────────────────────────────────────────────
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# ── FastAPI app ─────────────────────────────────────────────────
app = FastAPI(
    title="AURA — Adaptive User Risk Analyzer",
    description="Real-time behavioral anomaly detection using BETH dataset",
    version="1.0.0"
)

# ── Request schema ──────────────────────────────────────────────
class EventLog(BaseModel):
    uid_root: float = 0.0
    uid_daemon: float = 0.0
    uid_external: float = 0.0
    is_failure: float = 0.0
    is_success: float = 1.0
    process_freq: float = 0.5
    process_rarity: float = 0.5
    is_rare_process: float = 0.0
    unknown_parent_child: float = 0.0
    args_entropy: float = 0.0
    user_id: Optional[str] = "anonymous"

# ── Response schema ─────────────────────────────────────────────
class RiskResponse(BaseModel):
    risk_score: float
    severity: str
    action: str
    if_score: float
    xgb_score: float
    top_reasons: list
    inference_ms: float

# ── Helpers ─────────────────────────────────────────────────────
def _get_rolling_failure_rate(user_id: str, is_failure: int) -> float:
    """Track failure rate per user in Redis with 60s TTL window."""
    key_total   = f"aura:user:{user_id}:total"
    key_failure = f"aura:user:{user_id}:failures"

    r.incr(key_total)
    r.expire(key_total, 60)

    if is_failure:
        r.incr(key_failure)
        r.expire(key_failure, 60)

    total    = int(r.get(key_total) or 1)
    failures = int(r.get(key_failure) or 0)
    return failures / total

def _compute_shap(scaled: np.ndarray) -> list:
    """Compute top 3 SHAP reasons."""
    shap_vals = explainer.shap_values(scaled)[0]
    feat_shap = dict(zip(FEATURE_COLS, shap_vals))
    top3 = sorted(feat_shap.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
    return [
        {"feature": f, "shap_value": round(v, 4),
         "impact": "increases_risk" if v < 0 else "decreases_risk"}
        for f, v in top3
    ]

# ── Routes ──────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    return {"status": "ok", "models_loaded": True}

@app.post("/score", response_model=RiskResponse)
def score_event(event: EventLog, background_tasks: BackgroundTasks):
    start = time.time()

    # Build feature vector
    features = {col: getattr(event, col, 0.0) for col in FEATURE_COLS}
    raw = np.array([[features[c] for c in FEATURE_COLS]])
    scaled = scaler.transform(raw)

    # IF score
    if_raw   = iso_forest.decision_function(scaled)[0]
    if_score = float(np.clip(
        (-if_raw - RISK_MIN) / (RISK_MAX - RISK_MIN) * 100, 0, 100
    ))

    # XGBoost score
    xgb_score = float(np.clip(xgb_model.predict(raw)[0], 0, 1)) * 100

    # Ensemble
    final_score = round((W_IF * if_score/100 + W_XGB * xgb_score/100) * 100, 2)

    # Action
    if final_score < 40:
        action, severity = "ALLOW",        "LOW"
    elif final_score < 70:
        action, severity = "REVIEW / OTP", "MEDIUM"
    else:
        action, severity = "BLOCK",        "HIGH"

    # SHAP only for flagged events — run in background for speed
    reasons = []
    if final_score >= 30:
        reasons = _compute_shap(scaled)

    inference_ms = round((time.time() - start) * 1000, 2)

    return RiskResponse(
        risk_score=final_score,
        severity=severity,
        action=action,
        if_score=round(if_score, 2),
        xgb_score=round(xgb_score, 2),
        top_reasons=reasons,
        inference_ms=inference_ms
    )

@app.get("/stats")
def get_stats():
    """Return basic Redis-tracked stats."""
    keys = r.keys("aura:user:*:total")
    return {
        "active_users_tracked": len(keys),
        "redis_connected": r.ping()
    }