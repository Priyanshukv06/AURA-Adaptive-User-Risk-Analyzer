# 🛡️ AURA — Adaptive User Risk Analyzer

**Real-time behavioral anomaly detection framework for enterprise network security**

[![Streamlit App](https://img.shields.io/badge/Streamlit-Cloud-FF4B4B?logo=streamlit&logoColor=white)](https://aura-adaptive-user-risk-analyzer06.streamlit.app/)
[![API](https://img.shields.io/badge/FastAPI-Render-009639?logo=render&logoColor=white)](https://aura-api-450k.onrender.com)
[![Python](https://img.shields.io/badge/Python-3.9+-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![ML Models](https://img.shields.io/badge/ML-XGBoost%20%2B%20Isolation%20Forest-009688)]()

Leverages ensemble machine learning (Isolation Forest + XGBoost) for zero-day threat identification in enterprise network logs. Processes streaming telemetry via Kafka, integrates with Redis for event persistence, and exposes REST API for real-time model inference.

## 📋 Table of Contents

- [Quick Links](#-quick-links)
- [Architecture](#architecture)
- [Cloud Services](#cloud-services-always-running--no-action-needed)
- [Getting Started](#-getting-started)
- [Local Execution](#local-execution-workflow)
- [Project Structure](#key-files)
- [Configuration](#️-environment-variables-env)
- [API Endpoints](#-api-endpoints)
- [Performance](#-model-performance)
- [Troubleshooting](#-troubleshooting)

## 🚀 Quick Links

| Link | Purpose |
|------|----------|
| **[Live Dashboard](https://aura-adaptive-user-risk-analyzer06.streamlit.app/)** | Real-time monitoring & event simulation |
| **[API Documentation](https://aura-api-450k.onrender.com/docs)** | Interactive Swagger UI |
| **[Health Check](https://aura-api-450k.onrender.com/health)** | Verify API status |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      AURA System Architecture                        │
└─────────────────────────────────────────────────────────────────────┘

BETH Dataset (local)
    │
    ▼
producer.py  ──SASL_SSL──►  Confluent Cloud Kafka (aura-beth-logs)
                                      │
                                      ▼
consumer.py  ◄────────────  Confluent Cloud Kafka
    │
    ├──► https://aura-api-450k.onrender.com/score  (FastAPI on Render)
    │
    └──► Redis Cloud (asia-south1, port 14898)
              │
              ▼
    Streamlit Cloud Dashboard
    https://aura-adaptive-user-risk-analyzer06.streamlit.app/
```

---

## Cloud Services (Always Running — No Action Needed)

| Service | Platform | URL / Host | Status |
|---|---|---|---|
| **FastAPI Scoring API** | Render (free) | `https://aura-api-450k.onrender.com` | ✅ Live |
| **Redis Feed Store** | Redis Cloud | `redis-14898.c330.asia-south1-1.gce.cloud.redislabs.com:14898` | ✅ Live |
| **Kafka Broker** | Confluent Cloud | `pkc-....confluent.cloud:9092` | ✅ Live |
| **Analytics Dashboard** | Streamlit Cloud | `https://aura-adaptive-user-risk-analyzer06.streamlit.app/` | ✅ Live |

---

## 🏁 Getting Started

### Step 0 — Initialize Render Instance (Required for Cold Start)

The Render free-tier service enters a sleep state after 15 minutes of inactivity. Initialize the instance before starting streaming operations:

```powershell
Invoke-RestMethod -Uri "https://aura-api-450k.onrender.com/health"
```

**Expected response:**
```json
{"status":"ok","models_loaded":true}
```

Allow up to 30 seconds for the cold start to complete before proceeding.

---

## Local Execution Workflow

**Prerequisites:**
- Python 3.9+
- Conda environment configured (see `.env` file)
- All dependencies installed (`pip install -r requirements.txt`)

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

## 📁 Key Files

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

## ⚙️ Environment Variables (`.env`)

```env
API_URL=https://aura-api-450k.onrender.com

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

## 📡 API Endpoints

| Endpoint | Method | Purpose | Response Time |
|---|---|---|---|
| `/health` | GET | Service status & model health | <100ms |
| `/score` | POST | Risk scoring inference | ~8ms |
| `/stats` | GET | System statistics | <100ms |
| `/docs` | GET | Interactive Swagger UI | Live |

**Base URL:** `https://aura-api-450k.onrender.com`

### Example Requests

**Health Check:**
```bash
curl https://aura-api-450k.onrender.com/health
```

**Score Prediction:**
```bash
curl -X POST https://aura-api-450k.onrender.com/score \
  -H "Content-Type: application/json" \
  -d '{"uid_external":1.0,"uid_root":0.0,"is_failure":1.0}'
```

---

## 🔧 PowerShell API Testing

```powershell
# Health check
Invoke-RestMethod -Uri "https://aura-api-450k.onrender.com/health"

# Score an attack event
Invoke-RestMethod -Uri "https://aura-api-450k.onrender.com/score" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"uid_external":1.0,"uid_root":0.0,"is_failure":1.0,"process_rarity":1.0,"is_rare_process":1.0,"unknown_parent_child":1.0,"args_entropy":4.5}'
```

---

## 📊 Model Performance

| Metric | Value | Notes |
|---|---|---|
| **PR-AUC** | 0.9937 | Excellent precision-recall balance |
| **Recall (evil events)** | 98.77% | High sensitivity to attacks |
| **Avg Inference Time** | ~8ms | Real-time processing capability |
| **Ensemble Weights** | IF: 40% + XGB: 60% | Isolation Forest + XGBoost hybrid |
| **Training Data** | BETH Dataset | 100K+ enterprise network logs |
| **Features** | 7 behavioral | Process behavior anomalies |

---

## 🐛 Troubleshooting

| Problem | Resolution | Time To Fix |
|---|---|---|
| API returns `null` prefix or JSON parse error | Render instance requires initialization—invoke `/health` endpoint and wait 30 seconds for model loading | ~30s |
| Consumer fails to connect to Kafka | Verify KAFKA_BOOTSTRAP_SERVERS, KAFKA_API_KEY, and KAFKA_API_SECRET in `.env`; confirm Confluent Cloud cluster is active | ~5m |
| Live Stream tab displays no events | Ensure both consumer.py and producer.py are executing concurrently in separate terminals | ~2m |
| Redis connection failure | Validate REDIS_PASSWORD and REDIS_HOST configuration; Redis Cloud free tier may have quota expiration | ~5m |
| Dashboard displays outdated data | Hard refresh browser (Ctrl+Shift+R) or access app reboot control panel and select **Reboot app** | ~1m |

---

## 📽️ System Demonstration Workflow

**Complete evaluation sequence (15 minutes):**

| Step | Action | Command/URL | Expected Result |
|---|---|---|---|
| 1 | Access Dashboard | https://aura-adaptive-user-risk-analyzer06.streamlit.app/ | Live dashboard loads |
| 2 | Initialize API | `Invoke-RestMethod https://aura-api-450k.onrender.com/health` | `{"status":"ok","models_loaded":true}` |
| 3 | Start Consumer | `python src/streaming/consumer.py` (Terminal 1) | "Redis connected ✅" |
| 4 | Start Producer | `python src/streaming/producer.py --mode demo` (Terminal 2) | Events begin streaming |
| 5 | Test Event Simulator | Dashboard → Event Simulator tab | Risk scores displayed in real-time |
| 6 | Monitor Live Stream | Dashboard → Live Kafka Stream tab | Event processing with scores |
| 7 | Explore API Docs | https://aura-api-450k.onrender.com/docs | Interactive Swagger UI |

---

## 📝 License

This project is part of enterprise security research. For production use, please review applicable licensing terms.

## 🤝 Support

For issues or questions:
1. Check the [Troubleshooting](#-troubleshooting) section
2. Verify API health: https://aura-api-450k.onrender.com/health
3. Review logs in respective terminal streams
