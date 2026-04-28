# 🛡️ AURA — Adaptive User Risk Analyzer
### How to Start the Project (Quick Reference)

---

## Architecture

```
BETH Dataset (local)
    │
    ▼
producer.py  ──SASL_SSL──►  Confluent Cloud Kafka (aura-beth-logs)
                                      │
                                      ▼
consumer.py  ◄────────────  Confluent Cloud Kafka
    │
    ├──► https://aura-api-w3hj.onrender.com/score  (FastAPI on Render)
    │
    └──► Redis Cloud (asia-south1, port 14898)
                  │
                  ▼
    Streamlit Cloud Dashboard (public URL)
```

---

## Cloud Services (Always Running — No Action Needed)

| Service | Platform | URL / Host |
|---|---|---|
| FastAPI Scoring API | Render (free) | `https://aura-api-w3hj.onrender.com` |
| Redis Feed Store | Redis Cloud | `redis-14898.c330.asia-south1-1.gce.cloud.redislabs.com:14898` |
| Kafka Broker | Confluent Cloud | `pkc-....confluent.cloud:9092` |
| Dashboard | Streamlit Cloud | `https://your-app.streamlit.app` |

---

## Every Time You Want to Run the Project

### Step 0 — Wake Up Render (ALWAYS DO THIS FIRST)

Render free tier sleeps after 15 min of inactivity. Wake it before starting:

```powershell
Invoke-RestMethod -Uri "https://aura-api-w3hj.onrender.com/health"
```

Expected response: `{"status":"ok","models_loaded":true}`

Wait until you get this — it may take up to 30 seconds on cold start.

---

### Step 1 — Terminal 1: Start Consumer

```powershell
cd D:\CODE\Projects\AURA\AURA-Adaptive-User-Risk-Analyzer
conda activate aura
python src/streaming/consumer.py
```

Wait for:
```
Redis connected ✅
Kafka Consumer connected ✅
Listening on topic: aura-beth-logs
```

---

### Step 2 — Terminal 2: Start Producer

```powershell
cd D:\CODE\Projects\AURA\AURA-Adaptive-User-Risk-Analyzer
conda activate aura
python src/streaming/producer.py --mode demo
```

You will see events being produced to Kafka.

---

### Step 3 — Terminal 3: Start Dashboard (local only)

Only needed if running locally instead of using the public Streamlit Cloud URL:

```powershell
cd D:\CODE\Projects\AURA\AURA-Adaptive-User-Risk-Analyzer
conda activate aura
streamlit run dashboard/app.py
```

Opens at: `http://localhost:8501`

---

## Key Files

```
AURA-Adaptive-User-Risk-Analyzer/
├── src/
│   ├── api/
│   │   └── main.py               ← FastAPI app (deployed on Render)
│   └── streaming/
│       ├── producer.py           ← Sends BETH events to Kafka (run locally)
│       └── consumer.py           ← Reads Kafka → calls API → writes to Redis (run locally)
├── dashboard/
│   └── app.py                    ← Streamlit dashboard (deployed on Streamlit Cloud)
├── src/models/saved/             ← All .pkl model files
│   ├── isolation_forest.pkl
│   ├── xgboost_model.pkl
│   ├── shap_explainer.pkl
│   ├── scaler.pkl
│   └── ensemble_config.pkl
├── data/processed/
│   ├── scaler_params.npy
│   └── feature_metadata.json
├── render.yaml                   ← Render deployment config
├── requirements.txt
└── .env                          ← Local env vars (never commit)
```

---

## Environment Variables (`.env`)

```env
API_URL=https://aura-api-w3hj.onrender.com

REDIS_HOST=redis-14898.c330.asia-south1-1.gce.cloud.redislabs.com
REDIS_PORT=14898
REDIS_PASSWORD=your_redis_password
REDIS_USERNAME=default
REDIS_SSL=False

KAFKA_BOOTSTRAP_SERVERS=your_confluent_bootstrap_url
KAFKA_API_KEY=your_kafka_api_key
KAFKA_API_SECRET=your_kafka_api_secret
KAFKA_TOPIC=aura-beth-logs
```

---

## Useful URLs

| Purpose | URL |
|---|---|
| Public Dashboard | `https://your-app.streamlit.app` |
| API Health Check | `https://aura-api-w3hj.onrender.com/health` |
| API Swagger Docs | `https://aura-api-w3hj.onrender.com/docs` |
| API Stats | `https://aura-api-w3hj.onrender.com/stats` |

---

## Quick API Test (PowerShell)

```powershell
# Health check
Invoke-RestMethod -Uri "https://aura-api-w3hj.onrender.com/health"

# Score an attack event
Invoke-RestMethod -Uri "https://aura-api-w3hj.onrender.com/score" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"uid_external":1.0,"uid_root":0.0,"is_failure":1.0,"process_rarity":1.0,"is_rare_process":1.0,"unknown_parent_child":1.0,"args_entropy":4.5}'
```

---

## Model Performance

| Metric | Value |
|---|---|
| PR-AUC | 0.9937 |
| Recall (evil events) | 98.77% |
| Avg Inference Time | ~8ms |
| Ensemble Weights | IF: 40% + XGB: 60% |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| API returns `null` prefix or JSON error | Render cold start — hit `/health` first, wait for `ok`, retry |
| Consumer not connecting to Kafka | Check `.env` KAFKA_* vars, confirm Confluent cluster is active |
| Live stream tab shows no events | Make sure consumer.py AND producer.py are both running |
| Redis connection error | Check REDIS_PASSWORD in `.env`, Redis Cloud free tier may have expired |
| Streamlit Cloud shows old version | Go to app dashboard → `Reboot app` |

---

## Demo Order for Recruiters

1. Open public Streamlit URL in browser
2. Wake up Render: `Invoke-RestMethod .../health`
3. Start `consumer.py` (Terminal 1)
4. Start `producer.py` (Terminal 2)
5. Show **Event Simulator** tab — set Attack preset, click Analyze Event
6. Show **Live Kafka Stream** tab — toggle Auto-refresh, watch events flow
7. Show **Swagger UI** at `/docs` for API demo
