# 🛡️ AURA — Adaptive User Risk Analyzer

Real-time behavioral anomaly detection framework leveraging ensemble machine learning (Isolation Forest + XGBoost) for zero-day threat identification in enterprise network logs. Processes streaming telemetry via Kafka, integrates with Redis for event persistence, and exposes REST API for model inference.

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

## Deployment & Runtime

### Step 0 — Initialize Render Instance (Required for Cold Start)

The Render free-tier service enters a sleep state after 15 minutes of inactivity. Initialize the instance before starting streaming operations:

```powershell
Invoke-RestMethod -Uri "https://aura-api-w3hj.onrender.com/health"
```

**Expected response:**
```json
{"status":"ok","models_loaded":true}
```

Allow up to 30 seconds for the cold start to complete before proceeding.

---

## Local Execution Workflow

### 1. Start Kafka Consumer Stream

Start the consumer in the first terminal to initialize Kafka subscription and establish Redis connectivity:

```powershell
cd D:\CODE\Projects\AURA\AURA-Adaptive-User-Risk-Analyzer
conda activate aura
python src/streaming/consumer.py
```

**Verify successful initialization:**
```
Redis connected ✅
Kafka Consumer connected ✅
Listening on topic: aura-beth-logs
```

---

### 2. Start Kafka Producer Stream

In a second terminal, initiate the event producer to stream BETH dataset records to Kafka:

```powershell
cd D:\CODE\Projects\AURA\AURA-Adaptive-User-Risk-Analyzer
conda activate aura
python src/streaming/producer.py --mode demo
```

The producer will begin transmitting event records. Verify messages are being published to the Kafka topic.

---

### 3. Launch Analytics Dashboard (Local Development Only)

Optionally run the Streamlit dashboard locally for development and testing (production instance deployed on Streamlit Cloud):

```powershell
cd D:\CODE\Projects\AURA\AURA-Adaptive-User-Risk-Analyzer
conda activate aura
streamlit run dashboard/app.py
```

**Access point:** `http://localhost:8501`

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

| Problem | Resolution |
|---|---|
| API returns `null` prefix or JSON parse error | Render instance requires initialization—invoke `/health` endpoint and wait 30 seconds for model loading |
| Consumer fails to connect to Kafka | Verify KAFKA_BOOTSTRAP_SERVERS, KAFKA_API_KEY, and KAFKA_API_SECRET in `.env`; confirm Confluent Cloud cluster is active |
| Live Stream tab displays no events | Ensure both consumer.py and producer.py are executing concurrently |
| Redis connection failure | Validate REDIS_PASSWORD and REDIS_HOST configuration; Redis Cloud free tier may have quota expiration |
| Streamlit Cloud dashboard displays stale version | Access app reboot control panel and select **Reboot app**

---

## System Demonstration Workflow

**Standard evaluation sequence:**

1. Access the public Streamlit dashboard
2. Initialize Render instance: `Invoke-RestMethod .../health`
3. Execute consumer stream (Terminal 1): `python src/streaming/consumer.py`
4. Execute producer stream (Terminal 2): `python src/streaming/producer.py`
5. Navigate to **Event Simulator** tab and execute test scenarios
6. Monitor **Live Kafka Stream** tab for real-time event processing and risk scoring
7. Show **Swagger UI** at `/docs` for API demo
