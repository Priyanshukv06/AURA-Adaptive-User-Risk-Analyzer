import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import json
import redis
import time

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AURA — Adaptive User Risk Analyzer",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

API_URL  = "http://127.0.0.1:8000"
FEED_KEY = "aura:kafka:feed"

# ─────────────────────────────────────────────────────────────
# REDIS
# ─────────────────────────────────────────────────────────────
@st.cache_resource
def get_redis():
    try:
        rc = redis.Redis(host="localhost", port=6379, decode_responses=True)
        rc.ping()
        return rc
    except Exception:
        return None

r_client = get_redis()

# ─────────────────────────────────────────────────────────────
# GLOBAL CSS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .live-dot {
    display: inline-block; width: 10px; height: 10px;
    background: #e74c3c; border-radius: 50%;
    animation: pulse 1.2s ease-in-out infinite;
  }
  @keyframes pulse {
    0%,100% { opacity:1; transform:scale(1); }
    50%      { opacity:0.4; transform:scale(0.7); }
  }
  .event-card {
    background: #1e1e2e; border-radius: 10px;
    padding: 16px 20px; margin-bottom: 10px;
    border-left: 5px solid #444;
  }
  .event-card.block  { border-left-color: #e74c3c; }
  .event-card.review { border-left-color: #f39c12; }
  .event-card.allow  { border-left-color: #27ae60; }
  .risk-val { font-size: 2rem; font-weight: 800; }
  .risk-block  { color: #e74c3c; }
  .risk-review { color: #f39c12; }
  .risk-allow  { color: #27ae60; }
  .step-meta   { color: #aaa; font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────
defaults = {
    "history":        [],
    "preset":         "normal",
    "playback_mode":  "live",   # "live" | "replay" | "step"
    "playback_index": 0,
    "playback_cache": [],
    "auto_refresh":   False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def score_event(payload: dict) -> dict:
    try:
        resp = requests.post(f"{API_URL}/score", json=payload, timeout=5)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def risk_emoji(action: str) -> str:
    return {"BLOCK": "🚫", "REVIEW / OTP": "⚠️", "ALLOW": "✅"}.get(action, "❓")

def action_css_class(action: str) -> str:
    return {"BLOCK": "block", "REVIEW / OTP": "review", "ALLOW": "allow"}.get(action, "allow")

def action_color(action: str) -> str:
    return {"BLOCK": "#e74c3c", "REVIEW / OTP": "#f39c12", "ALLOW": "#27ae60"}.get(action, "#888")

def risk_css_class(action: str) -> str:
    return {"BLOCK": "risk-block", "REVIEW / OTP": "risk-review", "ALLOW": "risk-allow"}.get(action, "risk-allow")

def get_kafka_feed() -> list:
    if r_client is None:
        return []
    try:
        raw = r_client.lrange(FEED_KEY, 0, 199)
        return [json.loads(x) for x in raw]
    except Exception:
        return []

def get_kafka_stats() -> dict:
    if r_client is None:
        return {"total": 0, "block": 0, "review": 0, "allow": 0, "true_blocks": 0}
    try:
        return {
            "total":       int(r_client.get("aura:kafka:total") or 0),
            "block":       int(r_client.get("aura:kafka:block") or 0),
            "review":      int(r_client.get("aura:kafka:review_/_otp") or 0),
            "allow":       int(r_client.get("aura:kafka:allow") or 0),
            "true_blocks": int(r_client.get("aura:kafka:true_blocks") or 0),
        }
    except Exception:
        return {"total": 0, "block": 0, "review": 0, "allow": 0, "true_blocks": 0}

def feed_to_df(feed: list) -> pd.DataFrame:
    if not feed:
        return pd.DataFrame()
    df = pd.DataFrame(feed)
    df.columns = ["Time", "Event ID", "Label", "Risk Score",
                  "Action", "IF Score", "XGB Score", "Latency ms"]
    return df

def styled_df(df: pd.DataFrame):
    def hl(val):
        colors = {
            "BLOCK":        "background-color:#fadbd8; color:#e74c3c; font-weight:bold",
            "REVIEW / OTP": "background-color:#fdebd0; color:#f39c12; font-weight:bold",
            "ALLOW":        "background-color:#d5f5e3; color:#27ae60; font-weight:bold",
        }
        return colors.get(val, "")
    return df.style.applymap(hl, subset=["Action"])

# ─────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────
c1, c2 = st.columns([1, 11])
with c1:
    st.markdown("# 🛡️")
with c2:
    st.markdown("## AURA — Adaptive User Risk Analyzer")
    st.caption("Real-time behavioral anomaly detection · BETH Dataset · IF + XGBoost Ensemble · PR-AUC: 0.9937")
st.divider()

# ─────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["🎛️ Event Simulator", "🔴 Live Kafka Stream"])


# ═════════════════════════════════════════════════════════════
# TAB 1 — MANUAL EVENT SIMULATOR
# ═════════════════════════════════════════════════════════════
with tab1:

    with st.sidebar:
        st.markdown("### 🎛️ Simulate Event")

        c1s, c2s, c3s = st.columns(3)
        with c1s:
            if st.button("🔴 Attack", use_container_width=True):
                st.session_state.preset = "attack"
                st.rerun()
        with c2s:
            if st.button("🟡 Medium", use_container_width=True):
                st.session_state.preset = "medium"
                st.rerun()
        with c3s:
            if st.button("🟢 Normal", use_container_width=True):
                st.session_state.preset = "normal"
                st.rerun()

        presets = {
            "attack": dict(uid_external=1.0, uid_root=0.0, is_failure=1.0,
                           process_rarity=1.0, is_rare_proc=1.0,
                           unk_parent=1.0, args_entropy=4.5),
            "medium": dict(uid_external=1.0, uid_root=0.0, is_failure=0.5,
                           process_rarity=0.6, is_rare_proc=0.0,
                           unk_parent=1.0, args_entropy=3.0),
            "normal": dict(uid_external=0.0, uid_root=1.0, is_failure=0.0,
                           process_rarity=0.05, is_rare_proc=0.0,
                           unk_parent=0.0, args_entropy=0.5),
        }
        d = presets.get(st.session_state.preset, presets["normal"])

        st.divider()
        uid_external   = st.slider("External User (UID 1000+)", 0.0, 1.0, d["uid_external"], 0.1)
        uid_root       = st.slider("Root User (UID 0)",         0.0, 1.0, d["uid_root"],     0.1)
        is_failure     = st.slider("Failure Rate",              0.0, 1.0, d["is_failure"],   0.1)
        process_rarity = st.slider("Process Rarity",            0.0, 1.0, d["process_rarity"], 0.1)
        is_rare_proc   = st.slider("Rare Process",              0.0, 1.0, d["is_rare_proc"], 1.0)
        unk_parent     = st.slider("Unknown Parent-Child",      0.0, 1.0, d["unk_parent"],   1.0)
        args_entropy   = st.slider("Args Entropy",              0.0, 5.0, d["args_entropy"], 0.1)

        st.divider()
        score_btn = st.button("⚡ Analyze Event", type="primary", use_container_width=True)
        if st.button("🗑️ Clear History", use_container_width=True):
            st.session_state.history = []
            st.rerun()

    if score_btn:
        payload = {
            "uid_root": uid_root, "uid_external": uid_external,
            "uid_daemon": 0.0, "is_failure": is_failure,
            "is_success": round(1.0 - is_failure, 1),
            "process_freq": round(1.0 - process_rarity, 2),
            "process_rarity": process_rarity,
            "is_rare_process": is_rare_proc,
            "unknown_parent_child": unk_parent,
            "args_entropy": args_entropy,
        }
        with st.spinner("Analyzing event..."):
            result = score_event(payload)

        if "error" in result:
            st.error(f"❌ API Error: {result['error']}")
        else:
            result["timestamp"] = datetime.now().strftime("%H:%M:%S")
            st.session_state.history.insert(0, result)

            st.markdown("## 🔍 Analysis Result")
            m1, m2, m3, m4 = st.columns(4)
            with m1: st.metric("Risk Score",  f"{result['risk_score']}/100")
            with m2: st.metric("Action",      f"{risk_emoji(result['action'])} {result['action']}")
            with m3: st.metric("IF Score",    f"{result['if_score']}/100")
            with m4: st.metric("XGB Score",   f"{result['xgb_score']:.1f}/100")

            score     = result["risk_score"]
            bar_color = "#e74c3c" if score >= 70 else "#f39c12" if score >= 40 else "#27ae60"
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=score,
                title={"text": "Ensemble Risk Score", "font": {"size": 16}},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar":  {"color": bar_color},
                    "steps": [
                        {"range": [0,  40], "color": "#d5f5e3"},
                        {"range": [40, 70], "color": "#fdebd0"},
                        {"range": [70, 100],"color": "#fadbd8"},
                    ],
                    "threshold": {"line": {"color": "red", "width": 3},
                                  "thickness": 0.75, "value": 70},
                }
            ))
            fig_gauge.update_layout(height=260, margin=dict(t=40, b=0))
            st.plotly_chart(fig_gauge, use_container_width=True)

            if result.get("top_reasons"):
                st.markdown("### 📊 SHAP Feature Explanation")
                reasons_df = pd.DataFrame(result["top_reasons"])
                reasons_df["abs_shap"] = reasons_df["shap_value"].abs()
                fig_shap = px.bar(
                    reasons_df.sort_values("abs_shap"),
                    x="abs_shap", y="feature", orientation="h",
                    color="impact",
                    color_discrete_map={
                        "increases_risk":  "#e74c3c",
                        "decreases_risk":  "#27ae60"
                    },
                    labels={"abs_shap": "|SHAP Value|", "feature": "Feature"},
                    title="Top 3 Contributing Features",
                )
                fig_shap.update_layout(height=250)
                st.plotly_chart(fig_shap, use_container_width=True)
            else:
                st.success("✅ Event scored as LOW risk — no SHAP explanation needed.")

    if st.session_state.history:
        st.divider()
        st.markdown("### 📋 Recent Events")
        rows = [{
            "Time":       h["timestamp"],
            "Risk Score": h["risk_score"],
            "Severity":   h["severity"],
            "Action":     h["action"],
            "IF Score":   h["if_score"],
            "XGB Score":  round(h["xgb_score"], 1),
            "Latency ms": h.get("inference_ms", "-"),
        } for h in st.session_state.history[:15]]
        hist_df = pd.DataFrame(rows)
        st.dataframe(hist_df, use_container_width=True, hide_index=True)

        if len(rows) > 1:
            trend_df = pd.DataFrame(rows[::-1])
            fig_trend = px.line(
                trend_df, x="Time", y="Risk Score",
                title="Risk Score Trend", markers=True,
                color_discrete_sequence=["#e74c3c"],
            )
            fig_trend.add_hline(y=70, line_dash="dash", line_color="red",
                                 annotation_text="BLOCK threshold")
            fig_trend.add_hline(y=40, line_dash="dash", line_color="orange",
                                 annotation_text="REVIEW threshold")
            fig_trend.update_layout(height=300)
            st.plotly_chart(fig_trend, use_container_width=True)


# ═════════════════════════════════════════════════════════════
# TAB 2 — LIVE KAFKA STREAM  (3 view modes)
# ═════════════════════════════════════════════════════════════
with tab2:

    st.markdown(
        "### <span class='live-dot'></span>&nbsp; Live Kafka Event Stream",
        unsafe_allow_html=True,
    )
    st.caption(
        "Kafka Consumer → FastAPI /score (20–40ms) → Redis list → Streamlit. "
        "Use **Replay** or **Step** mode to slow down display for demos."
    )

    # ── Kafka global stats ────────────────────────────────────
    stats = get_kafka_stats()
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1: st.metric("Total Scored", f"{stats['total']:,}")
    with k2: st.metric("🚫 Blocked",   f"{stats['block']:,}")
    with k3: st.metric("⚠️ Reviewed",  f"{stats['review']:,}")
    with k4: st.metric("✅ Allowed",   f"{stats['allow']:,}")
    with k5:
        pct = (stats["true_blocks"] / max(stats["block"], 1)) * 100
        st.metric("True Block Rate", f"{pct:.1f}%")

    st.divider()

    # ── Mode controls ─────────────────────────────────────────
    ctl1, ctl2, ctl3, ctl4, ctl5 = st.columns([3, 2, 2, 2, 3])

    with ctl1:
        mode = st.radio(
            "View Mode",
            ["🔴 Live", "⏯️ Replay 2s", "👆 Step-by-Step"],
            horizontal=True,
            index=["🔴 Live", "⏯️ Replay 2s", "👆 Step-by-Step"].index(
                {"live": "🔴 Live", "replay": "⏯️ Replay 2s", "step": "👆 Step-by-Step"}
                .get(st.session_state.playback_mode, "🔴 Live")
            ),
        )
        st.session_state.playback_mode = (
            {"🔴 Live": "live", "⏯️ Replay 2s": "replay", "👆 Step-by-Step": "step"}[mode]
        )

    with ctl2:
        if st.button("▶ Start / Reload", use_container_width=True):
            full_feed = get_kafka_feed()
            st.session_state.playback_cache = full_feed[::-1]   # oldest → newest
            st.session_state.playback_index = 1
            st.rerun()

    with ctl3:
        if st.button("↺ Reset", use_container_width=True):
            st.session_state.playback_index = 0
            st.session_state.playback_cache = []
            st.rerun()

    with ctl4:
        if st.button("↻ Refresh Now", use_container_width=True):
            st.rerun()

    with ctl5:
        st.caption(
            f"Cache: **{len(st.session_state.playback_cache)}** events  "
            f"| Showing: **{st.session_state.playback_index}**"
        )

    st.divider()

    # ─────────────────────────────────────────────────────────
    # LIVE MODE — latest 20 events from Redis, no delay
    # ─────────────────────────────────────────────────────────
    if st.session_state.playback_mode == "live":

        feed = get_kafka_feed()

        if not feed:
            st.info(
                "⏳ No events yet. Start the producer:\n"
                "```powershell\npython src/streaming/producer.py\n```"
            )
        else:
            live_df = feed_to_df(feed[:20])
            st.dataframe(styled_df(live_df), use_container_width=True,
                         hide_index=True, height=480)

            # charts row
            col_l, col_r = st.columns([1, 2])
            with col_l:
                action_counts = (
                    live_df["Action"].value_counts()
                    .reset_index()
                    .rename(columns={"index": "Action", "Action": "Count"})
                )
                action_counts.columns = ["Action", "Count"]
                fig_pie = px.pie(
                    action_counts, names="Action", values="Count",
                    color="Action",
                    color_discrete_map={
                        "BLOCK":        "#e74c3c",
                        "REVIEW / OTP": "#f39c12",
                        "ALLOW":        "#27ae60",
                    },
                    hole=0.4, title="Action Distribution (last 20)",
                )
                fig_pie.update_layout(height=300)
                st.plotly_chart(fig_pie, use_container_width=True)

            with col_r:
                fig_spark = px.line(
                    live_df[::-1], x="Time", y="Risk Score",
                    title="Risk Score — Last 20 Events",
                    markers=True, color_discrete_sequence=["#e74c3c"],
                )
                fig_spark.add_hline(y=70, line_dash="dash", line_color="red",
                                    annotation_text="BLOCK")
                fig_spark.add_hline(y=40, line_dash="dash", line_color="orange",
                                    annotation_text="REVIEW")
                fig_spark.update_layout(height=300)
                st.plotly_chart(fig_spark, use_container_width=True)

        # auto-refresh
        auto = st.toggle("🔄 Auto-refresh (2s)", value=st.session_state.auto_refresh,
                         key="live_auto")
        st.session_state.auto_refresh = auto
        if auto:
            time.sleep(2)
            st.rerun()

    # ─────────────────────────────────────────────────────────
    # REPLAY MODE — 1 new row every 2 seconds, table grows
    # ─────────────────────────────────────────────────────────
    elif st.session_state.playback_mode == "replay":

        cache = st.session_state.playback_cache
        idx   = st.session_state.playback_index

        if not cache:
            st.warning(
                "Press **▶ Start / Reload** to snapshot the feed and begin 2s replay."
            )
        else:
            visible = cache[:idx]
            total   = len(cache)

            # Progress bar
            st.progress(min(idx / total, 1.0),
                        text=f"Replaying event {idx} of {total}")

            if visible:
                vis_df  = feed_to_df(visible)
                # show newest on top for replay display
                show_df = vis_df.iloc[::-1].reset_index(drop=True)
                st.dataframe(styled_df(show_df), use_container_width=True,
                             hide_index=True, height=460)

                # ── Highlighted latest event card ──────────────
                latest  = visible[-1]
                action  = latest["action"]
                css_cls = action_css_class(action)
                risk_cl = risk_css_class(action)
                st.markdown(
                    f"""
                    <div class="event-card {css_cls}">
                      <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                          <span class="step-meta">Event {latest['event_id']} &nbsp;·&nbsp;
                          {latest['time']} &nbsp;·&nbsp; {latest['label']}</span><br>
                          <b style="font-size:1.1rem">{risk_emoji(action)} &nbsp;{action}</b>
                        </div>
                        <div class="risk-val {risk_cl}">{latest['risk_score']}</div>
                      </div>
                      <div style="margin-top:8px; color:#aaa; font-size:0.82rem;">
                        IF: {latest['if_score']} &nbsp;|&nbsp;
                        XGB: {latest['xgb_score']} &nbsp;|&nbsp;
                        {latest['latency_ms']} ms
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.info("Starting replay…")

            # advance index and loop
            if idx < total:
                time.sleep(2)
                st.session_state.playback_index += 1
                st.rerun()
            else:
                st.success(f"✅ Replay complete — {total} events shown.")
                if st.button("🔁 Replay Again"):
                    st.session_state.playback_index = 1
                    st.rerun()

    # ─────────────────────────────────────────────────────────
    # STEP-BY-STEP MODE — manual Next / Prev buttons
    # perfect for live presentations / judges demo
    # ─────────────────────────────────────────────────────────
    elif st.session_state.playback_mode == "step":

        cache = st.session_state.playback_cache
        idx   = st.session_state.playback_index

        if not cache:
            st.warning(
                "Press **▶ Start / Reload** to snapshot the feed, then use "
                "**Next Event** to walk through one event at a time."
            )
        else:
            total = len(cache)

            # nav buttons
            nb1, nb2, nb3, nb4 = st.columns([2, 2, 2, 6])
            with nb1:
                if st.button("⬅ Prev", use_container_width=True, disabled=(idx <= 1)):
                    st.session_state.playback_index = max(1, idx - 1)
                    st.rerun()
            with nb2:
                if st.button("Next ➡", use_container_width=True,
                             type="primary", disabled=(idx >= total)):
                    st.session_state.playback_index = min(total, idx + 1)
                    st.rerun()
            with nb3:
                if st.button("⏭ Jump to End", use_container_width=True):
                    st.session_state.playback_index = total
                    st.rerun()
            with nb4:
                st.caption(f"Event **{idx}** of **{total}**")

            st.markdown("---")

            if idx == 0:
                st.info("Press **▶ Start / Reload** first, then use Next ➡")
            else:
                # Current event card (large)
                current = cache[idx - 1]
                action  = current["action"]
                css_cls = action_css_class(action)
                risk_cl = risk_css_class(action)
                col_ev, col_meta = st.columns([3, 5])

                with col_ev:
                    st.markdown(
                        f"""
                        <div class="event-card {css_cls}" style="padding:24px 28px;">
                          <div class="step-meta" style="margin-bottom:6px;">
                            Event ID: <b>{current['event_id']}</b>
                            &nbsp;·&nbsp; Time: <b>{current['time']}</b>
                            &nbsp;·&nbsp; Label: <b>{current['label']}</b>
                          </div>
                          <div class="risk-val {risk_cl}" style="font-size:3rem;">
                            {current['risk_score']}
                          </div>
                          <div style="font-size:1.2rem; font-weight:700; margin-top:4px;">
                            {risk_emoji(action)}&nbsp; {action}
                          </div>
                          <div class="step-meta" style="margin-top:12px;">
                            IF Score: <b>{current['if_score']}</b>
                            &nbsp;|&nbsp; XGB Score: <b>{current['xgb_score']}</b>
                            &nbsp;|&nbsp; Latency: <b>{current['latency_ms']} ms</b>
                          </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                with col_meta:
                    # gauge for current event
                    score     = current["risk_score"]
                    bar_color = "#e74c3c" if score >= 70 else "#f39c12" if score >= 40 else "#27ae60"
                    fig_g = go.Figure(go.Indicator(
                        mode="gauge+number", value=score,
                        title={"text": "Risk Score", "font": {"size": 14}},
                        gauge={
                            "axis": {"range": [0, 100]},
                            "bar":  {"color": bar_color},
                            "steps": [
                                {"range": [0,  40], "color": "#d5f5e3"},
                                {"range": [40, 70], "color": "#fdebd0"},
                                {"range": [70, 100],"color": "#fadbd8"},
                            ],
                            "threshold": {
                                "line": {"color": "red", "width": 3},
                                "thickness": 0.75, "value": 70,
                            },
                        },
                    ))
                    fig_g.update_layout(height=220, margin=dict(t=30, b=0, l=0, r=0))
                    st.plotly_chart(fig_g, use_container_width=True)

                st.markdown("---")

                # History table of events so far
                if idx > 1:
                    st.markdown(f"##### Events seen so far (1 – {idx})")
                    hist_visible = cache[:idx]
                    hist_df      = feed_to_df(hist_visible)
                    show_hist    = hist_df.iloc[::-1].reset_index(drop=True)
                    st.dataframe(styled_df(show_hist), use_container_width=True,
                                 hide_index=True, height=300)

                    # mini risk trend
                    fig_t = px.line(
                        hist_df, x="Time", y="Risk Score",
                        markers=True, color_discrete_sequence=["#e74c3c"],
                        title="Risk Score so far",
                    )
                    fig_t.add_hline(y=70, line_dash="dash", line_color="red")
                    fig_t.add_hline(y=40, line_dash="dash", line_color="orange")
                    fig_t.update_layout(height=250)
                    st.plotly_chart(fig_t, use_container_width=True)

# ─────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────
st.divider()
f1, f2, f3 = st.columns(3)
with f1: st.caption("🔬 Models: Isolation Forest + XGBoost Distilled Ensemble")
with f2: st.caption("📊 Dataset: BETH Cybersecurity (UCL 2021) · 1.1M events")
with f3: st.caption("⚡ Inference: ~20–40ms · PR-AUC: 0.9937 · Recall: 98.77%")
