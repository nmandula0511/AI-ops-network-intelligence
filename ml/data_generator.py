"""
ML Training Data Generator
---------------------------
Generates synthetic network telemetry data for training ML models.

Creates 10,000 labeled events:
- 8,000 healthy events (normal network behavior)
- 2,000 faulty events (various fault types)

Each event has metrics + a label for supervised learning.
"""

import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime, timezone, timedelta
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Fault types our classifier will learn to identify
FAULT_TYPES = {
    "healthy": 0,
    "high_cpu": 1,
    "memory_exhaustion": 2,
    "packet_loss": 3,
    "bgp_flapping": 4,
    "ddos_attack": 5
}

DEVICE_TYPES = ["router", "switch", "firewall", "server", "load_balancer"]
LOCATIONS = [
    "datacenter-east", "datacenter-west", "datacenter-central",
    "branch-chicago", "branch-newyork", "branch-losangeles"
]


def generate_healthy_event(timestamp: datetime, device_id: str) -> dict:
    """Generates a healthy network event."""
    return {
        "timestamp": timestamp.isoformat(),
        "device_id": device_id,
        "device_type": random.choice(DEVICE_TYPES),
        "location": random.choice(LOCATIONS),
        "cpu_usage_pct": round(random.uniform(5, 65), 2),
        "memory_usage_pct": round(random.uniform(10, 70), 2),
        "latency_ms": round(random.uniform(1, 45), 2),
        "packet_loss_pct": round(random.uniform(0, 0.3), 4),
        "bandwidth_utilization_pct": round(random.uniform(5, 65), 2),
        "error_rate": round(random.uniform(0, 0.005), 5),
        "temperature_celsius": round(random.uniform(30, 50), 1),
        "fault_type": "healthy",
        "fault_label": FAULT_TYPES["healthy"],
        "is_anomaly": 0
    }


def generate_high_cpu_event(timestamp: datetime, device_id: str) -> dict:
    """Generates a high CPU fault event."""
    return {
        "timestamp": timestamp.isoformat(),
        "device_id": device_id,
        "device_type": random.choice(["router", "server"]),
        "location": random.choice(LOCATIONS),
        "cpu_usage_pct": round(random.uniform(85, 99), 2),
        "memory_usage_pct": round(random.uniform(60, 85), 2),
        "latency_ms": round(random.uniform(80, 300), 2),
        "packet_loss_pct": round(random.uniform(0.5, 3), 4),
        "bandwidth_utilization_pct": round(random.uniform(70, 90), 2),
        "error_rate": round(random.uniform(0.01, 0.05), 5),
        "temperature_celsius": round(random.uniform(60, 80), 1),
        "fault_type": "high_cpu",
        "fault_label": FAULT_TYPES["high_cpu"],
        "is_anomaly": 1
    }


def generate_memory_exhaustion_event(timestamp: datetime, device_id: str) -> dict:
    """Generates a memory exhaustion fault event."""
    return {
        "timestamp": timestamp.isoformat(),
        "device_id": device_id,
        "device_type": random.choice(["server", "switch"]),
        "location": random.choice(LOCATIONS),
        "cpu_usage_pct": round(random.uniform(40, 75), 2),
        "memory_usage_pct": round(random.uniform(88, 99), 2),
        "latency_ms": round(random.uniform(100, 500), 2),
        "packet_loss_pct": round(random.uniform(1, 8), 4),
        "bandwidth_utilization_pct": round(random.uniform(50, 80), 2),
        "error_rate": round(random.uniform(0.02, 0.1), 5),
        "temperature_celsius": round(random.uniform(55, 75), 1),
        "fault_type": "memory_exhaustion",
        "fault_label": FAULT_TYPES["memory_exhaustion"],
        "is_anomaly": 1
    }


def generate_packet_loss_event(timestamp: datetime, device_id: str) -> dict:
    """Generates a packet loss fault event."""
    return {
        "timestamp": timestamp.isoformat(),
        "device_id": device_id,
        "device_type": random.choice(["router", "switch"]),
        "location": random.choice(LOCATIONS),
        "cpu_usage_pct": round(random.uniform(20, 55), 2),
        "memory_usage_pct": round(random.uniform(20, 60), 2),
        "latency_ms": round(random.uniform(200, 2000), 2),
        "packet_loss_pct": round(random.uniform(10, 40), 4),
        "bandwidth_utilization_pct": round(random.uniform(30, 70), 2),
        "error_rate": round(random.uniform(0.05, 0.3), 5),
        "temperature_celsius": round(random.uniform(35, 55), 1),
        "fault_type": "packet_loss",
        "fault_label": FAULT_TYPES["packet_loss"],
        "is_anomaly": 1
    }


def generate_bgp_flapping_event(timestamp: datetime, device_id: str) -> dict:
    """Generates a BGP flapping fault event."""
    return {
        "timestamp": timestamp.isoformat(),
        "device_id": device_id,
        "device_type": "router",
        "location": random.choice(LOCATIONS),
        "cpu_usage_pct": round(random.uniform(70, 95), 2),
        "memory_usage_pct": round(random.uniform(60, 90), 2),
        "latency_ms": round(random.uniform(500, 3000), 2),
        "packet_loss_pct": round(random.uniform(15, 35), 4),
        "bandwidth_utilization_pct": round(random.uniform(60, 95), 2),
        "error_rate": round(random.uniform(0.1, 0.5), 5),
        "temperature_celsius": round(random.uniform(55, 75), 1),
        "fault_type": "bgp_flapping",
        "fault_label": FAULT_TYPES["bgp_flapping"],
        "is_anomaly": 1
    }


def generate_ddos_event(timestamp: datetime, device_id: str) -> dict:
    """Generates a DDoS attack event."""
    return {
        "timestamp": timestamp.isoformat(),
        "device_id": device_id,
        "device_type": random.choice(["firewall", "load_balancer"]),
        "location": random.choice(LOCATIONS),
        "cpu_usage_pct": round(random.uniform(90, 99), 2),
        "memory_usage_pct": round(random.uniform(80, 99), 2),
        "latency_ms": round(random.uniform(1000, 5000), 2),
        "packet_loss_pct": round(random.uniform(20, 60), 4),
        "bandwidth_utilization_pct": round(random.uniform(95, 100), 2),
        "error_rate": round(random.uniform(0.2, 0.8), 5),
        "temperature_celsius": round(random.uniform(65, 85), 1),
        "fault_type": "ddos_attack",
        "fault_label": FAULT_TYPES["ddos_attack"],
        "is_anomaly": 1
    }


def generate_dataset(
    total_events: int = 10000,
    fault_ratio: float = 0.2
) -> pd.DataFrame:
    """
    Generates the full training dataset.

    total_events: total number of events to generate
    fault_ratio:  proportion of events that are faulty (0.2 = 20%)
    """
    print(f"🔧 Generating {total_events} training events...")
    print(f"   Healthy events : {int(total_events * (1-fault_ratio))}")
    print(f"   Faulty events  : {int(total_events * fault_ratio)}")

    events = []
    base_time = datetime.now(timezone.utc) - timedelta(days=30)

    # Generate healthy events
    healthy_count = int(total_events * (1 - fault_ratio))
    for i in range(healthy_count):
        timestamp = base_time + timedelta(minutes=i * 2)
        device_id = f"device-{random.randint(1, 50):02d}"
        events.append(generate_healthy_event(timestamp, device_id))

    # Generate faulty events (equal split across fault types)
    fault_count = total_events - healthy_count
    fault_generators = [
        generate_high_cpu_event,
        generate_memory_exhaustion_event,
        generate_packet_loss_event,
        generate_bgp_flapping_event,
        generate_ddos_event
    ]

    per_fault = fault_count // len(fault_generators)
    for generator in fault_generators:
        for i in range(per_fault):
            timestamp = base_time + timedelta(
                minutes=random.randint(0, total_events * 2)
            )
            device_id = f"device-{random.randint(1, 50):02d}"
            events.append(generator(timestamp, device_id))

    # Shuffle so healthy and faulty are mixed
    random.shuffle(events)

    df = pd.DataFrame(events)
    print(f"✅ Dataset generated: {len(df)} events")
    print(f"\n📊 Fault distribution:")
    print(df["fault_type"].value_counts())

    return df


def save_dataset(df: pd.DataFrame, output_dir: str = "ml/data"):
    """Saves the dataset to CSV files."""
    os.makedirs(output_dir, exist_ok=True)

    # Save full dataset
    full_path = os.path.join(output_dir, "network_telemetry.csv")
    df.to_csv(full_path, index=False)
    print(f"\n💾 Full dataset saved: {full_path}")

    # Split into train/test (80/20)
    split_idx = int(len(df) * 0.8)
    train_df = df[:split_idx]
    test_df = df[split_idx:]

    train_path = os.path.join(output_dir, "train.csv")
    test_path = os.path.join(output_dir, "test.csv")

    train_df.to_csv(train_path, index=False)
    test_df.to_csv(test_path, index=False)

    print(f"💾 Training set saved: {train_path} ({len(train_df)} events)")
    print(f"💾 Test set saved    : {test_path} ({len(test_df)} events)")

    return train_path, test_path


if __name__ == "__main__":
    df = generate_dataset(total_events=10000, fault_ratio=0.2)
    save_dataset(df)
    print("\n✅ Training data ready for ML models!")