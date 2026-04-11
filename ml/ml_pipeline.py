"""
ML Pipeline
-----------
Combines all 3 models into one single prediction call.

The AI agent calls this with device metrics and gets back:
1. Is it anomalous?
2. What type of fault is it?
3. Will it have an outage soon?
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.anomaly_detection import predict_single as detect_anomaly
from ml.fault_classifier import predict_single as classify_fault
from ml.outage_predictor import predict_single as predict_outage


def analyze_device(metrics: dict, device_id: str = "unknown") -> dict:
    """
    Full ML analysis of a single device.

    Runs all 3 models and returns a combined result.
    This is the main entry point for the AI agent.
    """
    # Step 1: Detect anomaly
    anomaly_result = detect_anomaly(metrics)

    # Step 2: Classify fault type
    fault_result = classify_fault(metrics)

    # Step 3: Predict outage
    outage_result = predict_outage(metrics)

    # Combine into single result
    analysis = {
        "device_id": device_id,
        "anomaly": {
            "is_anomaly": anomaly_result["is_anomaly"],
            "score": anomaly_result["anomaly_score"]
        },
        "fault": {
            "type": fault_result["fault_type"],
            "confidence": fault_result["confidence"]
        },
        "outage": {
            "predicted": outage_result["outage_predicted"],
            "probability": outage_result["outage_probability"],
            "risk_level": outage_result["risk_level"],
            "eta": outage_result["estimated_time_to_outage"]
        },
        "summary": generate_summary(
            device_id, anomaly_result,
            fault_result, outage_result
        )
    }

    return analysis


def generate_summary(
    device_id: str,
    anomaly: dict,
    fault: dict,
    outage: dict
) -> str:
    """Generates a human readable summary for the AI agent."""
    if not anomaly["is_anomaly"]:
        return f"Device {device_id} is operating normally."

    summary = (
        f"Device {device_id} is showing anomalous behavior. "
        f"Fault type identified as '{fault['fault_type']}' "
        f"with {fault['confidence']:.0%} confidence. "
        f"Outage risk is {outage['risk_level']} "
        f"({outage['outage_probability']:.0%} probability). "
        f"Estimated time to outage: {outage['estimated_time_to_outage']}."
    )
    return summary


def analyze_batch(telemetry_batch: list) -> list:
    """
    Analyzes a batch of device telemetry events.
    Returns only anomalous devices.
    """
    results = []
    for event in telemetry_batch:
        metrics = event.get("metrics", {})
        device_id = event.get("device_id", "unknown")
        analysis = analyze_device(metrics, device_id)
        if analysis["anomaly"]["is_anomaly"]:
            results.append(analysis)
    return results


if __name__ == "__main__":
    print("🧪 Testing Full ML Pipeline\n")

    # Test 1: Healthy device
    healthy = {
        "cpu_usage_pct": 25,
        "memory_usage_pct": 40,
        "latency_ms": 5,
        "packet_loss_pct": 0.1,
        "bandwidth_utilization_pct": 30,
        "error_rate": 0.001,
        "temperature_celsius": 42
    }

    # Test 2: Critical device
    critical = {
        "cpu_usage_pct": 96,
        "memory_usage_pct": 94,
        "latency_ms": 1800,
        "packet_loss_pct": 28,
        "bandwidth_utilization_pct": 97,
        "error_rate": 0.42,
        "temperature_celsius": 77
    }

    print("📊 Healthy Device Analysis:")
    result1 = analyze_device(healthy, "router-core-01")
    print(f"   {result1['summary']}")

    print("\n📊 Critical Device Analysis:")
    result2 = analyze_device(critical, "switch-dist-03")
    print(f"   {result2['summary']}")
    print(f"   Fault type : {result2['fault']['type']}")
    print(f"   Risk level : {result2['outage']['risk_level']}")
    print(f"   Outage ETA : {result2['outage']['eta']}")

    print("\n✅ ML Pipeline ready for AI Agent!")