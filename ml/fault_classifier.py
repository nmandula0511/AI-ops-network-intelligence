"""
Fault Classifier Model
----------------------
Uses Random Forest to classify what TYPE of fault is occurring.

When anomaly detection flags a device, this model answers:
"Is it high CPU, memory exhaustion, packet loss, BGP flapping, or DDoS?"

Input:  Network telemetry metrics
Output: fault_type (string) + confidence score
"""

import pandas as pd
import numpy as np
import joblib
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import classification_report, accuracy_score


FEATURES = [
    "cpu_usage_pct",
    "memory_usage_pct",
    "latency_ms",
    "packet_loss_pct",
    "bandwidth_utilization_pct",
    "error_rate",
    "temperature_celsius"
]

FAULT_LABELS = {
    0: "healthy",
    1: "high_cpu",
    2: "memory_exhaustion",
    3: "packet_loss",
    4: "bgp_flapping",
    5: "ddos_attack"
}


def load_data(train_path: str, test_path: str):
    """Loads training and test data."""
    print("📂 Loading training data...")
    train_df = pd.read_csv(train_path)
    test_df = pd.read_csv(test_path)
    print(f"   Training samples: {len(train_df)}")
    print(f"   Test samples    : {len(test_df)}")
    return train_df, test_df


def train_model(train_df: pd.DataFrame):
    """Trains the Random Forest classifier."""
    print("\n🔧 Training Fault Classifier model...")

    X_train = train_df[FEATURES].values
    y_train = train_df["fault_label"].values

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)

    # Train Random Forest
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train_scaled, y_train)

    print("✅ Model trained successfully!")

    # Show feature importance
    importances = model.feature_importances_
    print("\n📊 Feature Importance:")
    for feature, importance in sorted(
        zip(FEATURES, importances),
        key=lambda x: x[1],
        reverse=True
    ):
        bar = "█" * int(importance * 50)
        print(f"   {feature:<35} {bar} {importance:.3f}")

    return model, scaler


def evaluate_model(
    model: RandomForestClassifier,
    scaler: StandardScaler,
    test_df: pd.DataFrame
):
    """Evaluates the model on test data."""
    print("\n📊 Evaluating model...")

    X_test = test_df[FEATURES].values
    y_test = test_df["fault_label"].values

    X_test_scaled = scaler.transform(X_test)
    predictions = model.predict(X_test_scaled)

    accuracy = accuracy_score(y_test, predictions)
    print(f"\n   Overall Accuracy: {accuracy:.2%}")

    print("\n   Classification Report:")
    print(classification_report(
        y_test,
        predictions,
        target_names=list(FAULT_LABELS.values())
    ))

    return accuracy


def save_model(
    model: RandomForestClassifier,
    scaler: StandardScaler,
    output_dir: str = "ml/models"
):
    """Saves the model to disk."""
    os.makedirs(output_dir, exist_ok=True)

    model_path = os.path.join(output_dir, "fault_classifier_model.pkl")
    scaler_path = os.path.join(output_dir, "fault_classifier_scaler.pkl")

    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)

    print(f"\n💾 Model saved: {model_path}")
    print(f"💾 Scaler saved: {scaler_path}")

    return model_path, scaler_path


def predict_single(metrics: dict, model_dir: str = "ml/models") -> dict:
    """
    Predicts fault type for a single device reading.
    This is what the AI agent calls in real time.
    """
    model = joblib.load(
        os.path.join(model_dir, "fault_classifier_model.pkl")
    )
    scaler = joblib.load(
        os.path.join(model_dir, "fault_classifier_scaler.pkl")
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
    probabilities = model.predict_proba(features_scaled)[0]
    confidence = float(probabilities.max())

    fault_type = FAULT_LABELS.get(int(prediction), "unknown")

    return {
        "fault_type": fault_type,
        "fault_label": int(prediction),
        "confidence": round(confidence, 4),
        "all_probabilities": {
            FAULT_LABELS[i]: round(float(p), 4)
            for i, p in enumerate(probabilities)
        }
    }


if __name__ == "__main__":
    # Load data
    train_df, test_df = load_data("ml/data/train.csv", "ml/data/test.csv")

    # Train model
    model, scaler = train_model(train_df)

    # Evaluate model
    evaluate_model(model, scaler, test_df)

    # Save model
    save_model(model, scaler)

    # Test with samples
    print("\n🧪 Testing with sample readings:")

    bgp_sample = {
        "cpu_usage_pct": 88,
        "memory_usage_pct": 75,
        "latency_ms": 1200,
        "packet_loss_pct": 22,
        "bandwidth_utilization_pct": 82,
        "error_rate": 0.3,
        "temperature_celsius": 68
    }

    ddos_sample = {
        "cpu_usage_pct": 98,
        "memory_usage_pct": 95,
        "latency_ms": 3000,
        "packet_loss_pct": 45,
        "bandwidth_utilization_pct": 99,
        "error_rate": 0.6,
        "temperature_celsius": 80
    }

    result1 = predict_single(bgp_sample)
    result2 = predict_single(ddos_sample)

    print(f"\n   BGP sample  → Fault: {result1['fault_type']} "
          f"(confidence: {result1['confidence']:.2%})")
    print(f"   DDoS sample → Fault: {result2['fault_type']} "
          f"(confidence: {result2['confidence']:.2%})")

    print("\n✅ Fault Classifier model ready!")