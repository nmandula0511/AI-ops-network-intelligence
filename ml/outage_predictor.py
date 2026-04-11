"""
Outage Predictor Model
----------------------
Predicts if a device will have an outage in the next 15-30 minutes.

Uses gradient boosting to detect early warning patterns
BEFORE a full outage occurs.

Input:  Current + recent telemetry metrics
Output: outage_probability (0-1) + time_to_outage estimate
"""

import pandas as pd
import numpy as np
import joblib
import os
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
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

# Warning thresholds — early signs of outage
WARNING_THRESHOLDS = {
    "cpu_usage_pct": 75,
    "memory_usage_pct": 80,
    "latency_ms": 100,
    "packet_loss_pct": 2,
    "bandwidth_utilization_pct": 85,
    "error_rate": 0.02,
    "temperature_celsius": 65
}


def create_outage_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Creates outage prediction labels.
    A device is "at risk" if it shows early warning signs.
    """
    df = df.copy()

    # Device is at risk if metrics exceed warning thresholds
    at_risk = (
        (df["cpu_usage_pct"] > WARNING_THRESHOLDS["cpu_usage_pct"]) |
        (df["memory_usage_pct"] > WARNING_THRESHOLDS["memory_usage_pct"]) |
        (df["latency_ms"] > WARNING_THRESHOLDS["latency_ms"]) |
        (df["packet_loss_pct"] > WARNING_THRESHOLDS["packet_loss_pct"]) |
        (df["error_rate"] > WARNING_THRESHOLDS["error_rate"])
    )

    df["outage_risk"] = at_risk.astype(int)
    return df


def load_data(train_path: str, test_path: str):
    """Loads and prepares training data."""
    print("📂 Loading training data...")
    train_df = pd.read_csv(train_path)
    test_df = pd.read_csv(test_path)

    # Add outage risk labels
    train_df = create_outage_labels(train_df)
    test_df = create_outage_labels(test_df)

    at_risk_count = train_df["outage_risk"].sum()
    print(f"   Training samples : {len(train_df)}")
    print(f"   At-risk samples  : {at_risk_count}")
    print(f"   Healthy samples  : {len(train_df) - at_risk_count}")

    return train_df, test_df


def train_model(train_df: pd.DataFrame):
    """Trains the Gradient Boosting outage predictor."""
    print("\n🔧 Training Outage Predictor model...")

    X_train = train_df[FEATURES].values
    y_train = train_df["outage_risk"].values

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)

    # Train Gradient Boosting
    model = GradientBoostingClassifier(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=4,
        random_state=42
    )
    model.fit(X_train_scaled, y_train)

    print("✅ Model trained successfully!")

    # Feature importance
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
    model: GradientBoostingClassifier,
    scaler: StandardScaler,
    test_df: pd.DataFrame
):
    """Evaluates the model."""
    print("\n📊 Evaluating model...")

    X_test = test_df[FEATURES].values
    y_test = test_df["outage_risk"].values

    X_test_scaled = scaler.transform(X_test)
    predictions = model.predict(X_test_scaled)

    accuracy = accuracy_score(y_test, predictions)
    print(f"\n   Overall Accuracy: {accuracy:.2%}")

    print("\n   Classification Report:")
    print(classification_report(
        y_test,
        predictions,
        target_names=["Stable", "At Risk"]
    ))

    return accuracy


def save_model(
    model: GradientBoostingClassifier,
    scaler: StandardScaler,
    output_dir: str = "ml/models"
):
    """Saves the model to disk."""
    os.makedirs(output_dir, exist_ok=True)

    model_path = os.path.join(output_dir, "outage_predictor_model.pkl")
    scaler_path = os.path.join(output_dir, "outage_predictor_scaler.pkl")

    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)

    print(f"\n💾 Model saved: {model_path}")
    print(f"💾 Scaler saved: {scaler_path}")

    return model_path, scaler_path


def predict_single(metrics: dict, model_dir: str = "ml/models") -> dict:
    """
    Predicts outage risk for a single device.
    This is what the AI agent calls in real time.
    """
    model = joblib.load(
        os.path.join(model_dir, "outage_predictor_model.pkl")
    )
    scaler = joblib.load(
        os.path.join(model_dir, "outage_predictor_scaler.pkl")
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
    probability = model.predict_proba(features_scaled)[0]
    outage_probability = float(probability[1])

    # Estimate time to outage based on probability
    if outage_probability > 0.9:
        time_to_outage = "< 5 minutes"
        risk_level = "CRITICAL"
    elif outage_probability > 0.7:
        time_to_outage = "5-15 minutes"
        risk_level = "HIGH"
    elif outage_probability > 0.5:
        time_to_outage = "15-30 minutes"
        risk_level = "MEDIUM"
    else:
        time_to_outage = "No outage predicted"
        risk_level = "LOW"

    return {
        "outage_predicted": bool(prediction == 1),
        "outage_probability": round(outage_probability, 4),
        "risk_level": risk_level,
        "estimated_time_to_outage": time_to_outage
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

    stable_sample = {
        "cpu_usage_pct": 30,
        "memory_usage_pct": 45,
        "latency_ms": 8,
        "packet_loss_pct": 0.05,
        "bandwidth_utilization_pct": 35,
        "error_rate": 0.001,
        "temperature_celsius": 40
    }

    at_risk_sample = {
        "cpu_usage_pct": 78,
        "memory_usage_pct": 85,
        "latency_ms": 150,
        "packet_loss_pct": 3,
        "bandwidth_utilization_pct": 88,
        "error_rate": 0.03,
        "temperature_celsius": 68
    }

    critical_sample = {
        "cpu_usage_pct": 95,
        "memory_usage_pct": 97,
        "latency_ms": 1800,
        "packet_loss_pct": 28,
        "bandwidth_utilization_pct": 98,
        "error_rate": 0.45,
        "temperature_celsius": 79
    }

    r1 = predict_single(stable_sample)
    r2 = predict_single(at_risk_sample)
    r3 = predict_single(critical_sample)