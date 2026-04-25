import json
import time
import requests
import numpy as np
import redis
from kafka import KafkaConsumer
from datetime import datetime
from collections import defaultdict

# ── Connections ──────────────────────────────────────────────────
session   = requests.Session()
r_client  = redis.Redis(host='localhost', port=6379, decode_responses=True)

TOPIC      = "aura-beth-logs"
BOOTSTRAP  = "localhost:9092"
API_URL    = "http://localhost:8000/score"
GROUP_ID   = "aura-risk-scorer"
FEED_KEY   = "aura:kafka:feed"
MAX_FEED   = 50   # keep last 50 events in Redis

consumer = KafkaConsumer(
    TOPIC,
    bootstrap_servers=BOOTSTRAP,
    group_id=GROUP_ID,
    auto_offset_reset='latest',
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    consumer_timeout_ms=60000
)

print(f"Kafka Consumer connected ✅")
print(f"Listening on topic: {TOPIC}")
print(f"Forwarding to: {API_URL}\n")
print(f"{'Time':<10} {'Event':>7} {'Label':>7} {'Risk':>7} {'Action':<15} {'IF':>7} {'XGB':>7} {'ms':>6}")
print("-" * 75)

stats     = defaultdict(int)
latencies = []

try:
    for msg in consumer:
        event = msg.value

        payload = {k: v for k, v in event.items()
                   if k not in ['event_id', 'true_label', 'timestamp', 'user_id']}
        payload['user_id'] = event.get('user_id', 'anonymous')

        t0 = time.time()
        try:
            resp   = session.post(API_URL, json=payload, timeout=5)
            result = resp.json()
            api_ms = round((time.time() - t0) * 1000, 1)
        except Exception as e:
            print(f"API error: {e}")
            time.sleep(1)
            session.close()
            session = requests.Session()
            continue

        action     = result.get('action', '?')
        risk_score = result.get('risk_score', 0)
        if_score   = result.get('if_score', 0)
        xgb_score  = result.get('xgb_score', 0)
        true_label = event.get('true_label', -1)
        event_id   = event.get('event_id', msg.offset)
        label_str  = "EVIL" if true_label == 1 else "benign"

        # ── Write to Redis feed for Streamlit dashboard ──────────
        feed_entry = json.dumps({
            "time":       datetime.now().strftime("%H:%M:%S"),
            "event_id":   event_id,
            "label":      label_str,
            "risk_score": risk_score,
            "action":     action,
            "if_score":   if_score,
            "xgb_score":  round(xgb_score, 1),
            "latency_ms": api_ms
        })
        r_client.lpush(FEED_KEY, feed_entry)
        r_client.ltrim(FEED_KEY, 0, MAX_FEED - 1)  # keep only last 50

        # ── Track global stats in Redis ──────────────────────────
        r_client.incr("aura:kafka:total")
        r_client.incr(f"aura:kafka:{action.lower().replace(' / ', '_')}")
        if action == "BLOCK" and true_label == 1:
            r_client.incr("aura:kafka:true_blocks")

        # ── Local stats ──────────────────────────────────────────
        stats['total']     += 1
        stats[action]      += 1
        stats['evil_true'] += true_label
        latencies.append(api_ms)

        print(
            f"{datetime.now().strftime('%H:%M:%S'):<10} "
            f"{event_id:>7} "
            f"{label_str:>7} "
            f"{risk_score:>7.1f} "
            f"{action:<15} "
            f"{if_score:>7.1f} "
            f"{xgb_score:>7.1f} "
            f"{api_ms:>6.1f}"
        )

        if stats['total'] % 500 == 0:
            avg_lat = np.mean(latencies[-500:])
            print(f"\n{'─'*75}")
            print(f"  SUMMARY @ {stats['total']:,} events")
            print(f"  BLOCK: {stats['BLOCK']:,}  |  REVIEW: {stats['REVIEW / OTP']:,}  |  ALLOW: {stats['ALLOW']:,}")
            print(f"  True evil events: {stats['evil_true']:,}")
            print(f"  Avg latency:      {avg_lat:.1f}ms")
            print(f"{'─'*75}\n")

except KeyboardInterrupt:
    print(f"\nStopped by user.")
finally:
    consumer.close()
    session.close()
    if stats['total'] > 0:
        print(f"\n{'='*75}")
        print(f"FINAL STATS — {stats['total']:,} events processed")
        print(f"BLOCK: {stats['BLOCK']:,}  REVIEW: {stats['REVIEW / OTP']:,}  ALLOW: {stats['ALLOW']:,}")
        print(f"Avg latency: {np.mean(latencies):.1f}ms")
        print(f"{'='*75}")
    print("Consumer closed ✅")