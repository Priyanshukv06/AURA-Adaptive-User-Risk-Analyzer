"""
AURA Kafka Consumer — Cloud Ready
Confluent Cloud → FastAPI (Render) → Redis Cloud
"""

import os
import json
import time
import requests
import numpy as np
import redis
from kafka import KafkaConsumer
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

# ── Config from environment ──────────────────────────────────────
BOOTSTRAP  = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
API_KEY    = os.getenv("KAFKA_API_KEY")
API_SECRET = os.getenv("KAFKA_API_SECRET")
TOPIC      = os.getenv("KAFKA_TOPIC", "aura-beth-logs")
API_URL    = os.getenv("API_URL", "http://127.0.0.1:8000") + "/score"

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASS = os.getenv("REDIS_PASSWORD", "")
REDIS_USER = os.getenv("REDIS_USERNAME", "default")
REDIS_SSL  = os.getenv("REDIS_SSL", "False").lower() == "true"

FEED_KEY  = "aura:kafka:feed"
MAX_FEED  = 200
GROUP_ID  = f"aura-risk-scorer-{int(time.time())}"   # fresh offset every run

# ── Redis connection ─────────────────────────────────────────────
r_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASS,
    username=REDIS_USER,
    decode_responses=True,
    ssl=REDIS_SSL,
)

try:
    r_client.ping()
    print("Redis connected ✅")
except Exception as e:
    print(f"Redis connection failed ❌: {e}")
    raise

# ── Kafka connection ─────────────────────────────────────────────
print(f"Connecting to Kafka: {BOOTSTRAP}")
consumer = KafkaConsumer(
    TOPIC,
    bootstrap_servers=BOOTSTRAP,
    security_protocol="SASL_SSL",
    sasl_mechanism="PLAIN",
    sasl_plain_username=API_KEY,
    sasl_plain_password=API_SECRET,
    group_id=GROUP_ID,
    auto_offset_reset="latest",
    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    consumer_timeout_ms=120000,
)
print(f"Kafka Consumer connected ✅  |  Topic: {TOPIC}")
print(f"Forwarding to: {API_URL}\n")
print(f"{'Time':<10} {'Event':>7} {'Label':>8} {'Risk':>6} {'Action':<16} {'IF':>6} {'XGB':>6} {'ms':>6}")
print("─" * 75)

# ── Session + stats ──────────────────────────────────────────────
session   = requests.Session()
stats     = defaultdict(int)
latencies = []

try:
    for msg in consumer:
        event = msg.value

        payload = {k: v for k, v in event.items()
                   if k not in ["event_id", "true_label", "timestamp", "user_id"]}
        payload["user_id"] = event.get("user_id", "anonymous")

        t0 = time.time()
        try:
            resp   = session.post(API_URL, json=payload, timeout=10)
            result = resp.json()
            api_ms = round((time.time() - t0) * 1000, 1)
        except Exception as e:
            print(f"API error: {e}")
            time.sleep(2)
            session.close()
            session = requests.Session()
            continue

        action     = result.get("action", "?")
        risk_score = result.get("risk_score", 0)
        if_score   = result.get("if_score", 0)
        xgb_score  = result.get("xgb_score", 0)
        true_label = event.get("true_label", -1)
        event_id   = event.get("event_id", msg.offset)
        label_str  = "ATTACK" if true_label == 1 else "benign"

        # ── Write to Redis feed ──────────────────────────────────
        feed_entry = json.dumps({
            "time":       datetime.now().strftime("%H:%M:%S"),
            "event_id":   event_id,
            "label":      label_str,
            "risk_score": risk_score,
            "action":     action,
            "if_score":   if_score,
            "xgb_score":  round(xgb_score, 1),
            "latency_ms": api_ms,
        })
        r_client.lpush(FEED_KEY, feed_entry)
        r_client.ltrim(FEED_KEY, 0, MAX_FEED - 1)

        # ── Redis stats counters ─────────────────────────────────
        r_client.incr("aura:kafka:total")
        action_key = action.lower().replace(" / ", "_").replace(" ", "_")
        r_client.incr(f"aura:kafka:{action_key}")
        if action == "BLOCK" and true_label == 1:
            r_client.incr("aura:kafka:true_blocks")

        # ── Local stats ──────────────────────────────────────────
        stats["total"]     += 1
        stats[action]      += 1
        stats["evil_true"] += (true_label == 1)
        latencies.append(api_ms)

        print(
            f"{datetime.now().strftime('%H:%M:%S'):<10} "
            f"{event_id:>7} "
            f"{label_str:>8} "
            f"{risk_score:>6.1f} "
            f"{action:<16} "
            f"{if_score:>6.1f} "
            f"{xgb_score:>6.1f} "
            f"{api_ms:>6.1f}"
        )

        if stats["total"] % 500 == 0:
            avg_lat = np.mean(latencies[-500:])
            print(f"\n{'─'*75}")
            print(f"  SUMMARY @ {stats['total']:,} events")
            print(f"  BLOCK: {stats.get('BLOCK',0):,}  "
                  f"REVIEW: {stats.get('REVIEW / OTP',0):,}  "
                  f"ALLOW: {stats.get('ALLOW',0):,}")
            print(f"  Avg latency: {avg_lat:.1f}ms")
            print(f"{'─'*75}\n")

except KeyboardInterrupt:
    print(f"\nStopped by user after {stats['total']:,} events.")
finally:
    consumer.close()
    session.close()
    if stats["total"] > 0:
        print(f"\n{'='*75}")
        print(f"FINAL: {stats['total']:,} events  |  "
              f"BLOCK: {stats.get('BLOCK',0):,}  "
              f"REVIEW: {stats.get('REVIEW / OTP',0):,}  "
              f"ALLOW: {stats.get('ALLOW',0):,}")
        if latencies:
            print(f"Avg latency: {np.mean(latencies):.1f}ms")
        print(f"{'='*75}")
    print("Consumer closed ✅")
