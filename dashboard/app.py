import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import json

# ── Page config ─────────────────────────────────────────────────
st.set_page_config(
    page_title="AURA — Adaptive User Risk Analyzer",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

API_URL = "http://localhost:8000"

# ── Custom CSS ───────────────────────────────────────────────────
st.markdown("""
<style>
    .risk-high   { color: #e74c3c; font-weight: bold; font-size: 1.4rem; }
    .risk-medium { color: #f39c12; font-weight: bold; font-size: 1.4rem; }
    .risk-low    { color: #27ae60; font-weight: bold; font-size: 1.4rem; }
</style>
""", unsafe_allow_html=True)

# ── Session state ────────────────────────────────────────────────
if 'history' not in st.session_state:
    st.session_state.history = []
if 'preset' not in st.session_state:
    st.session_state.preset = "normal"

# ── Helper functions ─────────────────────────────────────────────
def score_event(payload: dict) -> dict:
    try:
        r = requests.post(f"{API_URL}/score", json=payload, timeout=5)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def risk_emoji(action: str) -> str:
    return {"BLOCK": "🚫", "REVIEW / OTP": "⚠️", "ALLOW": "✅"}.get(action, "❓")

# ── Header ───────────────────────────────────────────────────────
col_logo, col_title = st.columns([1, 8])
with col_logo:
    st.markdown("# 🛡️")
with col_title:
    st.markdown("## AURA — Adaptive User Risk Analyzer")
    st.caption("Real-time behavioral anomaly detection | BETH Dataset | IF + XGBoost Ensemble | PR-AUC: 0.9937")

st.divider()

# ── Sidebar ──────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎛️ Simulate Event")

    # Preset buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔴 Attack", use_container_width=True):
            st.session_state.preset = "attack"
            st.rerun()
    with col2:
        if st.button("🟡 Medium", use_container_width=True):
            st.session_state.preset = "medium"
            st.rerun()
    with col3:
        if st.button("🟢 Normal", use_container_width=True):
            st.session_state.preset = "normal"
            st.rerun()

    # Preset default values
    preset_vals = {
        "attack": dict(uid_external=1.0, uid_root=0.0, is_failure=1.0,
                       process_rarity=1.0, is_rare_proc=1.0,
                       unk_parent=1.0, args_entropy=4.5),
        "medium": dict(uid_external=1.0, uid_root=0.0, is_failure=0.5,
                       process_rarity=0.6, is_rare_proc=0.0,
                       unk_parent=1.0, args_entropy=3.0),
        "normal": dict(uid_external=0.0, uid_root=1.0, is_failure=0.0,
                       process_rarity=0.05, is_rare_proc=0.0,
                       unk_parent=0.0, args_entropy=0.5)
    }
    d = preset_vals.get(st.session_state.preset, preset_vals["normal"])

    st.divider()

    uid_external   = st.slider("External User (UID 1000+)", 0.0, 1.0, d['uid_external'], 0.1)
    uid_root       = st.slider("Root User (UID 0)",         0.0, 1.0, d['uid_root'],     0.1)
    is_failure     = st.slider("Failure Rate",              0.0, 1.0, d['is_failure'],   0.1)
    process_rarity = st.slider("Process Rarity",            0.0, 1.0, d['process_rarity'], 0.1)
    is_rare_proc   = st.slider("Rare Process",              0.0, 1.0, d['is_rare_proc'], 1.0)
    unk_parent     = st.slider("Unknown Parent-Child",      0.0, 1.0, d['unk_parent'],   1.0)
    args_entropy   = st.slider("Args Entropy",              0.0, 5.0, d['args_entropy'], 0.1)

    st.divider()
    score_btn = st.button("⚡ Analyze Event", type="primary", use_container_width=True)

    if st.button("🗑️ Clear History", use_container_width=True):
        st.session_state.history = []
        st.rerun()

# ── Main Panel ───────────────────────────────────────────────────
if score_btn:
    payload = {
        "uid_root":             uid_root,
        "uid_external":         uid_external,
        "uid_daemon":           0.0,
        "is_failure":           is_failure,
        "is_success":           round(1.0 - is_failure, 1),
        "process_freq":         round(1.0 - process_rarity, 2),
        "process_rarity":       process_rarity,
        "is_rare_process":      is_rare_proc,
        "unknown_parent_child": unk_parent,
        "args_entropy":         args_entropy
    }

    with st.spinner("Analyzing event..."):
        result = score_event(payload)

    if "error" in result:
        st.error(f"❌ API Error: {result['error']}\n\nMake sure FastAPI is running: `python src/api/run.py`")
    else:
        result['timestamp'] = datetime.now().strftime("%H:%M:%S")
        result['payload']   = payload
        st.session_state.history.insert(0, result)

        # ── Result Metrics ────────────────────────────────────
        st.markdown("## Analysis Result")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Risk Score", f"{result['risk_score']}/100")
        with c2:
            st.metric("Action", f"{risk_emoji(result['action'])} {result['action']}")
        with c3:
            st.metric("IF Score", f"{result['if_score']}/100")
        with c4:
            st.metric("XGB Score", f"{result['xgb_score']:.1f}/100")

        # ── Gauge Chart ───────────────────────────────────────
        score = result['risk_score']
        bar_color = "#e74c3c" if score >= 70 else "#f39c12" if score >= 30 else "#27ae60"

        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            title={'text': "Ensemble Risk Score", 'font': {'size': 16}},
            gauge={
                'axis': {'range': [0, 100]},
                'bar':  {'color': bar_color},
                'steps': [
                    {'range': [0,  30], 'color': '#d5f5e3'},
                    {'range': [30, 70], 'color': '#fdebd0'},
                    {'range': [70, 100],'color': '#fadbd8'}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 3},
                    'thickness': 0.75,
                    'value': 70
                }
            }
        ))
        fig_gauge.update_layout(height=260, margin=dict(t=40, b=0))
        st.plotly_chart(fig_gauge, use_container_width=True)

        # ── SHAP Explanation ──────────────────────────────────
        if result.get('top_reasons'):
            st.markdown("### 🔍 Why Flagged — SHAP Explanation")
            reasons_df = pd.DataFrame(result['top_reasons'])
            reasons_df['abs_shap'] = reasons_df['shap_value'].abs()

            fig_shap = px.bar(
                reasons_df.sort_values('abs_shap'),
                x='abs_shap',
                y='feature',
                orientation='h',
                color='impact',
                color_discrete_map={
                    'increases_risk': '#e74c3c',
                    'decreases_risk': '#27ae60'
                },
                labels={'abs_shap': '|SHAP Value|', 'feature': 'Feature'},
                title='Top 3 Contributing Features'
            )
            fig_shap.update_layout(height=250, showlegend=True)
            st.plotly_chart(fig_shap, use_container_width=True)
        else:
            st.info("✅ Event scored as LOW risk — no SHAP explanation needed.")

# ── Event History ─────────────────────────────────────────────────
if st.session_state.history:
    st.divider()
    st.markdown("### 📋 Recent Events")

    rows = []
    for h in st.session_state.history[:15]:
        rows.append({
            "Time":       h['timestamp'],
            "Risk Score": h['risk_score'],
            "Severity":   h['severity'],
            "Action":     h['action'],
            "IF Score":   h['if_score'],
            "XGB Score":  round(h['xgb_score'], 1),
            "Latency ms": h.get('inference_ms', '-')
        })

    hist_df = pd.DataFrame(rows)
    st.dataframe(hist_df, use_container_width=True, hide_index=True)

    # Risk trend chart
    if len(rows) > 1:
        trend_df = pd.DataFrame(rows[::-1])  # chronological order
        fig_trend = px.line(
            trend_df,
            x='Time',
            y='Risk Score',
            title='Risk Score Trend',
            markers=True,
            color_discrete_sequence=['#e74c3c']
        )
        fig_trend.add_hline(y=70, line_dash="dash", line_color="red",
                            annotation_text="BLOCK threshold")
        fig_trend.add_hline(y=40, line_dash="dash", line_color="orange",
                            annotation_text="REVIEW threshold")
        fig_trend.update_layout(height=300)
        st.plotly_chart(fig_trend, use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────
st.divider()
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    st.caption("🔬 Models: Isolation Forest + XGBoost Distilled")
with col_f2:
    st.caption("📊 Dataset: BETH Cybersecurity (UCL, 2021) — 1.1M events")
with col_f3:
    st.caption("⚡ Inference: ~20ms | PR-AUC: 0.9937 | Recall: 98.77%")