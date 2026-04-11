"""
Anomaly Detection Model
-----------------------
Uses Isolation Forest to detect anomalous network behavior.

Isolation Forest works by randomly isolating observations.
Anomalies are easier to isolate so they get lower scores.

Input:  Network telemetry metrics
Output: anomaly_score (-1 = anomaly, 1 = normal)
"""

import pandas as pd
import numpy as np
import joblib
import os
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix


# Features we use for anomaly detection
FEATURES = [
    "cpu_usage_pct",
    "memory_usage_pct",
    "latency_ms",
    "packet_loss_pct",
    "bandwidth_utilization_pct",
    "error_rate",
    "temperature_celsius"
]


def load_data(train_path: str, test_path: str):
    """Loads training and test data."""
    print("📂 Loading training data...")
    train_df = pd.read_csv(train_path)
    test_df = pd.read_csv(test_path)
    print(f"   Training samples: {len(train_df)}")
    print(f"   Test samples    : {len(test_df)}")
    return train_df, test_df


def train_model(train_df: pd.DataFrame):
    """
    Trains the Isolation Forest model.
    We train ONLY on healthy data so it learns what normal looks like.
    """
    print("\n🔧 Training Anomaly Detection model...")

    # Train only on healthy data
    healthy_df = train_df[train_df["is_anomaly"] == 0]
    print(f"   Training on {len(healthy_df)} healthy samples")

    X_train = healthy_df[FEATURES].values

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)

    # Train Isolation Forest
    model = IsolationForest(
        n_estimators=100,
        contamination=0.1,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train_scaled)

    print("✅ Model trained successfully!")
    return model, scaler


def evaluate_model(
    model: IsolationForest,
    scaler: StandardScaler,
    test_df: pd.DataFrame
):
    """Evaluates the model on test data."""
    print("\n📊 Evaluating model...")

    X_test = test_df[FEATURES].values
    X_test_scaled = scaler.transform(X_test)

    # Predict (-1 = anomaly, 1 = normal)
    predictions = model.predict(X_test_scaled)

    # Convert to 0/1 format (1 = anomaly, 0 = normal)
    pred_binary = (predictions == -1).astype(int)
    true_binary = test_df["is_anomaly"].values

    # Print results
    print("\n   Classification Report:")
    print(classification_report(
        true_binary,
        pred_binary,
        target_names=["Normal", "Anomaly"]
    ))

    # Calculate accuracy
    accuracy = (pred_binary == true_binary).mean()
    print(f"   Overall Accuracy: {accuracy:.2%}")

    return accuracy


def save_model(
    model: IsolationForest,
    scaler: StandardScaler,
    output_dir: str = "ml/models"
):
    """Saves the model and scaler to disk."""
    os.makedirs(output_dir, exist_ok=True)

    model_path = os.path.join(output_dir, "anomaly_detection_model.pkl")
    scaler_path = os.path.join(output_dir, "anomaly_scaler.pkl")

    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)

    print(f"\n💾 Model saved: {model_path}")
    print(f"💾 Scaler saved: {scaler_path}")

    return model_path, scaler_path


def predict_single(metrics: dict, model_dir: str = "ml/models") -> dict:
    """
    Predicts if a single device reading is anomalous.
    This is what the AI agent calls in real time.
    """
    model = joblib.load(
        os.path.join(model_dir, "anomaly_detection_model.pkl")
    )
    scaler = joblib.load(
        os.path.join(model_dir, "anomaly_scaler.pkl")
    )

    features = np.array([[
        metrics.get("cpu_usage_pct", 0),
        metrics.get("memory_usage_pct", 0),
        metrics.get("latency_ms", 0),
        metrics.get("packet_loss_pct", 0),
        metrics.get("bandwidth_utilization_pct", 0),
        metrics.get("error_rate", 0),
        metrics.get("temperature_celsius", 0)
    ]])

    features_scaled = scaler.transform(features)
    prediction = model.predict(features_scaled)[0]
    score = model.score_samples(features_scaled)[0]

    return {
        "is_anomaly": bool(prediction == -1),
        "anomaly_score": round(float(score), 4),
        "confidence": round(abs(float(score)), 4)
    }


if __name__ == "__main__":
    # Load data
    train_df, test_df = load_data("ml/data/train.csv", "ml/data/test.csv")

    # Train model
    model, scaler = train_model(train_df)

    # Evaluate model
    accuracy = evaluate_model(model, scaler, test_df)

    # Save model
    save_model(model, scaler)

    # Test with a sample
    print("\n🧪 Testing with sample readings:")

    healthy_sample = {
        "cpu_usage_pct": 25,
        "memory_usage_pct": 40,
        "latency_ms": 5,
        "packet_loss_pct": 0.1,
        "bandwidth_utilization_pct": 30,
        "error_rate": 0.001,
        "temperature_celsius": 42
    }

    faulty_sample = {
        "cpu_usage_pct": 97,
        "memory_usage_pct": 95,
        "latency_ms": 1500,
        "packet_loss_pct": 25,
        "bandwidth_utilization_pct": 98,
        "error_rate": 0.4,
        "temperature_celsius": 78
    }

    result1 = predict_single(healthy_sample)
    result2 = predict_single(faulty_sample)

    print(f"\n   Healthy device  → Anomaly: {result1['is_anomaly']} "
          f"(score: {result1['anomaly_score']})")
    print(f"   Faulty device   → Anomaly: {result2['is_anomaly']} "
          f"(score: {result2['anomaly_score']})")

    print("\n✅ Anomaly Detection model ready!")