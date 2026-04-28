"""
AURA Kafka Producer
────────────────────────────────────────────────────────────────
Two modes (set STREAM_MODE at top or pass as CLI arg):

  demo  →  80% benign / 20% attack  — use for Streamlit demos & presentations
  real  →  original BETH distribution  — use for realistic evaluation

Model inference is NOT slowed down.
The Streamlit Live tab has its own delay controls (Replay 2s / Step mode).
"""

import sys
import json
import time
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable
import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────
# CONFIG  — change STREAM_MODE here or pass --mode <demo|real>
# ─────────────────────────────────────────────────────────────
BOOTSTRAP      = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
API_KEY        = os.getenv("KAFKA_API_KEY")
API_SECRET     = os.getenv("KAFKA_API_SECRET")
TOPIC          = os.getenv("KAFKA_TOPIC", "aura-beth-logs")
STREAM_MODE    = os.getenv("STREAM_MODE", "demo")        # "demo" | "real"
PROCESSED_DIR  = Path("data/processed")
SLEEP_BETWEEN  = 0.05          # seconds between messages  (20 events/sec)

DEMO_TOTAL     = 2000          # events to stream in demo mode
DEMO_ATK_RATIO = 0.20          # 20% attacks, 80% benign

REAL_TOTAL     = None          # None = stream entire test set

# ─────────────────────────────────────────────────────────────
# CLI OVERRIDE
# ─────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="AURA Kafka Producer")
parser.add_argument("--mode",  choices=["demo", "real"], default=STREAM_MODE)
parser.add_argument("--total", type=int, default=None,
                    help="Override total events to stream")
parser.add_argument("--sleep", type=float, default=SLEEP_BETWEEN,
                    help="Sleep seconds between events (default 0.05)")
args, _ = parser.parse_known_args()

STREAM_MODE   = args.mode
SLEEP_BETWEEN = args.sleep
if args.total:
    DEMO_TOTAL = args.total
    REAL_TOTAL = args.total

# ─────────────────────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  AURA Kafka Producer  —  mode: {STREAM_MODE.upper()}")
print(f"{'='*60}\n")

print("Loading processed data...")
try:
    X_test = pd.read_csv(PROCESSED_DIR / "X_test.csv")
    y_test = pd.read_csv(PROCESSED_DIR / "y_test_evil.csv")["evil"].values
except FileNotFoundError as e:
    print(f"❌ Could not load data: {e}")
    print("   Make sure data/processed/X_test.csv and y_test_evil.csv exist.")
    sys.exit(1)

df              = X_test.copy()
df["true_label"] = y_test
feature_cols    = [c for c in df.columns if c != "true_label"]

# ─────────────────────────────────────────────────────────────
# BUILD STREAM
# ─────────────────────────────────────────────────────────────
if STREAM_MODE == "demo":
    benign_df = df[df["true_label"] == 0]
    evil_df   = df[df["true_label"] == 1]

    n_evil   = int(DEMO_TOTAL * DEMO_ATK_RATIO)
    n_benign = DEMO_TOTAL - n_evil

    n_evil   = min(n_evil,   len(evil_df))
    n_benign = min(n_benign, len(benign_df))

    evil_sample   = evil_df.sample(n=n_evil,   random_state=None)  # different every run
    benign_sample = benign_df.sample(n=n_benign, random_state=None)

    stream_df = (
        pd.concat([benign_sample, evil_sample])
        .sample(frac=1, random_state=None)   # ← truly random shuffle each run
        .reset_index(drop=True)
    )

    # ── SANITY CHECK: confirm attacks are spread across stream ──
    attack_positions = stream_df.index[stream_df["true_label"] == 1].tolist()
    first_10_attacks = attack_positions[:10]

    actual_atk = (stream_df["true_label"] == 1).sum()
    actual_ben = (stream_df["true_label"] == 0).sum()

    print(f"  Mode   : DEMO  (stratified evaluation stream)")
    print(f"  Benign : {actual_ben:,}  ({actual_ben/len(stream_df)*100:.0f}%)")
    print(f"  Attack : {actual_atk:,}  ({actual_atk/len(stream_df)*100:.0f}%)")
    print(f"  Total  : {len(stream_df):,} events")
    print(f"  First 10 attack positions in stream: {first_10_attacks}")
    print(f"  → Attack expected every ~{len(stream_df)//actual_atk} events on average\n")

else:  # real mode
    stream_df = df.copy()
    if REAL_TOTAL:
        stream_df = stream_df.sample(n=min(REAL_TOTAL, len(stream_df)),
                                     random_state=42).reset_index(drop=True)
    actual_atk = (stream_df["true_label"] == 1).sum()
    actual_ben = (stream_df["true_label"] == 0).sum()

    print(f"  Mode   : REAL  (original BETH distribution)")
    print(f"  Benign : {actual_ben:,}  ({actual_ben/len(stream_df)*100:.1f}%)")
    print(f"  Attack : {actual_atk:,}  ({actual_atk/len(stream_df)*100:.1f}%)")
    print(f"  Total  : {len(stream_df):,} events\n")

# ─────────────────────────────────────────────────────────────
# CONNECT KAFKA
# ─────────────────────────────────────────────────────────────
print(f"Connecting to Kafka at {BOOTSTRAP}...")
try:
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        security_protocol="SASL_SSL",
        sasl_mechanism="PLAIN",
        sasl_plain_username=API_KEY,
        sasl_plain_password=API_SECRET,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: str(k).encode("utf-8"),
        acks=1,
        retries=3,
        linger_ms=5,
    )
    print("Kafka Producer connected ✅")
except NoBrokersAvailable:
    print(f"❌ Cannot reach Kafka at {BOOTSTRAP}. Is it running?")
    sys.exit(1)

print(f"Topic  : {TOPIC}")
print(f"Speed  : {1/SLEEP_BETWEEN:.0f} events/sec  (sleep={SLEEP_BETWEEN}s)\n")
print(f"{'Time':<10} {'Sent':>8} {'Label':>8} {'event_id':>10}")
print("-" * 42)

# ─────────────────────────────────────────────────────────────
# STREAM
# ─────────────────────────────────────────────────────────────
sent = 0
try:
    for i, row in stream_df.iterrows():
        event = {col: float(row[col]) for col in feature_cols}
        event["event_id"]   = int(i)
        event["true_label"] = int(row["true_label"])
        event["timestamp"]  = time.time()
        event["user_id"]    = f"user_{np.random.randint(1, 50)}"

        producer.send(TOPIC, key=str(i), value=event)
        sent += 1

        label_str = "ATTACK" if row["true_label"] == 1 else "benign"

        if sent % 50 == 0:
            from datetime import datetime
            print(
                f"{datetime.now().strftime('%H:%M:%S'):<10} "
                f"{sent:>8,} "
                f"{label_str:>8} "
                f"{i:>10}"
            )

        if sent % 100 == 0:
            producer.flush()

        time.sleep(SLEEP_BETWEEN)

except KeyboardInterrupt:
    print(f"\n\nStopped by user after {sent:,} events.")
finally:
    producer.flush()
    producer.close()
    print(f"\nProducer closed ✅  —  Total sent: {sent:,}")
