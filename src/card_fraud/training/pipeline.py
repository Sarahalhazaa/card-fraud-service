"""Training job: the notebook's steps, as small functions with explicit inputs and outputs.

Training is an outer-ring job (it uses pandas and scikit-learn directly), but it takes the
input rules from the domain, so the model is trained on exactly what the service will send.
"""
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score

from card_fraud.config import TrainingSettings
from card_fraud.domain.payment import FEATURE_NAMES, hour_of_day

FEATURES = list(FEATURE_NAMES)


@dataclass
class Split:
    train: pd.DataFrame
    valid: pd.DataFrame
    test: pd.DataFrame


def add_inputs_and_split(df: pd.DataFrame, s: TrainingSettings) -> Split:
    """Sort by time, add the hour, and split: learn from the past, judge on the future."""
    df = df.sort_values("Time", kind="stable").reset_index(drop=True)
    df["hour"] = hour_of_day(df["Time"])
    n = len(df)
    train_end = int(n * s.train_share)
    valid_end = int(n * (s.train_share + s.valid_share))
    return Split(df.iloc[:train_end], df.iloc[train_end:valid_end], df.iloc[valid_end:])


def train_model(train: pd.DataFrame, s: TrainingSettings) -> HistGradientBoostingClassifier:
    model = HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_iter=300,
        max_leaf_nodes=15,
        l2_regularization=1.0,
        early_stopping=False,
        random_state=s.random_seed,
    )
    return model.fit(train[FEATURES], train["Class"])


def threshold_tradeoff(scores: np.ndarray, y: np.ndarray, thresholds: list[float]) -> pd.DataFrame:
    rows = []
    for t in thresholds:
        alert = scores >= t
        caught = int((alert & (y == 1)).sum())
        rows.append({
            "threshold": t,
            "alerts": int(alert.sum()),
            "real frauds in alerts": caught,
            "alerts that are fraud": caught / alert.sum() if alert.sum() else float("nan"),
            "frauds caught": caught / y.sum(),
        })
    return pd.DataFrame(rows)


def choose_threshold(tradeoff: pd.DataFrame, min_precision: float) -> float:
    """The fraud team's rule: the lowest threshold where enough alerts are real fraud."""
    meets_rule = tradeoff[tradeoff["alerts that are fraud"] >= min_precision]
    if meets_rule.empty:
        raise ValueError("No threshold meets the fraud team's rule; try a lower min_precision")
    return float(meets_rule["threshold"].min())


def evaluate(model, test: pd.DataFrame, threshold: float, s: TrainingSettings) -> dict:
    """Test the model on unseen payments and compare it with two simple baselines."""
    scores = model.predict_proba(test[FEATURES])[:, 1]
    y = test["Class"].values
    candidates = {
        "always_not_fraud": np.zeros(len(y), dtype=bool),
        "amount_rule": test["Amount"].values > s.amount_rule,
        "model": scores >= threshold,
    }
    out = {}
    for name, alert in candidates.items():
        caught = int((alert & (y == 1)).sum())
        out[name] = {
            "accuracy": float((alert == (y == 1)).mean()),
            "alerts": int(alert.sum()),
            "frauds_caught": caught,
            "precision": caught / alert.sum() if alert.sum() else float("nan"),
            "recall": caught / y.sum(),
        }
    model_alert = candidates["model"]
    out["model"].update({
        "false_alarms": int((model_alert & (y == 0)).sum()),
        "missed_frauds": int((~model_alert & (y == 1)).sum()),
        "average_precision": float(average_precision_score(y, scores)),
    })
    return out


def typical_values(train: pd.DataFrame) -> dict[str, float]:
    """The usual value of each input among normal payments (used by the reasons)."""
    medians = train.loc[train["Class"] == 0, FEATURES].median()
    return {name: float(value) for name, value in medians.items()}


def build_model_info(df, split: Split, threshold, typical, metrics, s: TrainingSettings) -> dict:
    m = metrics["model"]
    return {
        "model_version": s.model_version,
        "model_type": "HistGradientBoostingClassifier",
        "trained_on": datetime.now(UTC).strftime("%Y-%m-%d"),
        "scikit_learn_version": sklearn.__version__,
        "features": FEATURES,
        "threshold": threshold,
        "threshold_rule": f"lowest tried threshold where at least {s.min_precision:.0%} "
                          "of validation alerts are real fraud",
        "typical_values": typical,
        "data": {
            "source": s.data_url,
            "period": "two days of September 2013 (exact dates not published)",
            "rows": int(len(df)),
            "frauds": int(df["Class"].sum()),
            "train_rows": int(len(split.train)),
            "train_frauds": int(split.train["Class"].sum()),
            "train_hours": [float(split.train["Time"].min() / 3600),
                            float(split.train["Time"].max() / 3600)],
            "valid_rows": int(len(split.valid)),
            "test_rows": int(len(split.test)),
            "test_frauds": int(split.test["Class"].sum()),
        },
        "test_metrics": {
            "alerts": m["alerts"],
            "frauds_caught": m["frauds_caught"],
            "precision": float(m["precision"]),
            "recall": float(m["recall"]),
            "false_alarms": m["false_alarms"],
            "missed_frauds": m["missed_frauds"],
            "average_precision": m["average_precision"],
            "accuracy": m["accuracy"],
        },
        "baselines_on_test": {
            "always_not_fraud_accuracy": metrics["always_not_fraud"]["accuracy"],
            "amount_rule_recall": float(metrics["amount_rule"]["recall"]),
            "amount_rule_precision": float(metrics["amount_rule"]["precision"]),
        },
    }


def save_artifacts(model, info: dict, model_path: Path, info_path: Path) -> None:
    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    Path(info_path).write_text(json.dumps(info, indent=2), encoding="utf-8")


def run(df: pd.DataFrame, s: TrainingSettings) -> dict:
    split = add_inputs_and_split(df, s)
    for name, part in [("train", split.train), ("valid", split.valid), ("test", split.test)]:
        print(f"{name:5s}: {len(part):7,} payments, {part['Class'].sum():3d} frauds")

    start = time.time()
    model = train_model(split.train, s)
    print(f"Trained in {time.time() - start:.1f} s")

    valid_scores = model.predict_proba(split.valid[FEATURES])[:, 1]
    tradeoff = threshold_tradeoff(valid_scores, split.valid["Class"].values, s.thresholds_to_try)
    threshold = choose_threshold(tradeoff, s.min_precision)
    print(f"Chosen threshold: {threshold}")

    metrics = evaluate(model, split.test, threshold, s)
    typical = typical_values(split.train)
    info = build_model_info(df, split, threshold, typical, metrics, s)
    save_artifacts(model, info, s.model_path, s.model_info_path)

    m = info["test_metrics"]
    print(f"Test: {m['frauds_caught']} of {info['data']['test_frauds']} frauds caught, "
          f"{m['alerts']} alerts, {m['false_alarms']} false alarms, "
          f"average precision {m['average_precision']:.3f}")
    print(f"Saved {s.model_path} and {s.model_info_path}")
    return info
