"""The notebook's own code (plots removed), kept as the reference for the golden check.

It trains the model exactly as the notebook does, then saves the notebook's answers for
5 payments into golden/. After the reorganisation, scripts/check_golden.py proves the new
service gives the same answers. Do not "improve" this file: its job is to stay the notebook.

    python legacy/notebook_reference.py
"""
import json
import os
import urllib.request

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score

DATA_URL = "https://storage.googleapis.com/download.tensorflow.org/data/creditcard.csv"
DATA_PATH = os.environ.get("FRAUD_TRAIN_DATA_PATH", "data/creditcard.csv")
RANDOM_SEED = 42
TRAIN_SHARE = 0.6
VALID_SHARE = 0.2
MIN_PRECISION = 0.80
THRESHOLDS_TO_TRY = [0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99]

# ---- Get the data
os.makedirs(os.path.dirname(DATA_PATH) or ".", exist_ok=True)
if not os.path.exists(DATA_PATH):
    print("Downloading", DATA_URL)
    urllib.request.urlretrieve(DATA_URL, DATA_PATH + ".part")
    os.replace(DATA_PATH + ".part", DATA_PATH)
df = pd.read_csv(DATA_PATH)
df["Class"] = df["Class"].astype(int)

# ---- Build the inputs and split by time
df = df.sort_values("Time", kind="stable").reset_index(drop=True)
df["hour"] = (df["Time"] // 3600) % 24
FEATURES = [f"V{i}" for i in range(1, 29)] + ["Amount", "hour"]
n = len(df)
train_end = int(n * TRAIN_SHARE)
valid_end = int(n * (TRAIN_SHARE + VALID_SHARE))
train_df = df.iloc[:train_end]
valid_df = df.iloc[train_end:valid_end]
test_df = df.iloc[valid_end:]
X_train, y_train = train_df[FEATURES], train_df["Class"]
X_valid, y_valid = valid_df[FEATURES], valid_df["Class"]
X_test, y_test = test_df[FEATURES], test_df["Class"]

# ---- Train the model
model = HistGradientBoostingClassifier(
    learning_rate=0.05, max_iter=300, max_leaf_nodes=15, l2_regularization=1.0,
    early_stopping=False, random_state=RANDOM_SEED,
)
model.fit(X_train, y_train)

# ---- Choose the alert threshold
valid_scores = model.predict_proba(X_valid)[:, 1]
y_valid_np = y_valid.values
rows = []
for t in THRESHOLDS_TO_TRY:
    alert = valid_scores >= t
    caught = int((alert & (y_valid_np == 1)).sum())
    rows.append({"threshold": t,
                 "alerts that are fraud": caught / alert.sum() if alert.sum() else float("nan")})
tradeoff = pd.DataFrame(rows)
meets_rule = tradeoff[tradeoff["alerts that are fraud"] >= MIN_PRECISION]
THRESHOLD = float(meets_rule["threshold"].min())

# ---- Test
test_scores = model.predict_proba(X_test)[:, 1]
y_true = y_test.values
model_alert = test_scores >= THRESHOLD
notebook_metrics = {
    "threshold": THRESHOLD,
    "alerts": int(model_alert.sum()),
    "frauds_caught": int((model_alert & (y_true == 1)).sum()),
    "false_alarms": int((model_alert & (y_true == 0)).sum()),
    "missed_frauds": int((~model_alert & (y_true == 1)).sum()),
    "average_precision": float(average_precision_score(y_true, test_scores)),
}

# ---- Why did the model say that?
TYPICAL = train_df.loc[train_df["Class"] == 0, FEATURES].median()


def what_if_typical(model, features_row, typical):
    """Set each input alone to its typical value and see how far the fraud score drops."""
    base_score = model.predict_proba(pd.DataFrame([features_row]))[0, 1]
    variants = pd.DataFrame([features_row] * len(features_row))
    for i, name in enumerate(features_row.index):
        variants.iloc[i, i] = typical[name]
    new_scores = model.predict_proba(variants)[:, 1]
    reasons = pd.DataFrame({
        "value": features_row.values,
        "typical": typical[features_row.index].values,
        "score if typical": new_scores,
        "drop": base_score - new_scores,
    }, index=features_row.index)
    return base_score, reasons.sort_values("drop", ascending=False)


# ---- The notebook's last cell: a real fraud from the test period, as a request would arrive
notebook_payment = {
    "Time": 154278.0, "Amount": 1504.93,
    "V1": -1.60021129907252, "V2": -3.48813018118561, "V3": -6.45930280667571, "V4": 3.24681566349703,
    "V5": -1.61460769860713, "V6": -1.26037454854632, "V7": 0.288223321921388, "V8": -0.0489639910109505,
    "V9": -0.734974617920653, "V10": -4.44148408070017, "V11": 2.94437484242405, "V12": -3.80546898374331,
    "V13": -2.10222683492697, "V14": -6.1061832734711, "V15": -0.641736399701777, "V16": -1.55596289626148,
    "V17": -2.08406707082134, "V18": 0.394247352869229, "V19": 0.0833797227600835, "V20": 3.18935489592753,
    "V21": 1.19117480721903, "V22": -0.96714144500067, "V23": -1.46342052446637, "V24": -0.624230851495284,
    "V25": -0.176461532068143, "V26": 0.400348351070197, "V27": 0.152946864261687, "V28": 0.477774924576796,
}


def as_request(row: pd.Series) -> dict:
    return {name: float(row[name]) for name in ["Time", "Amount", *[f"V{i}" for i in range(1, 29)]]}


# Five reference payments: the notebook's example, plus real cases from the test period
examples = {"notebook_last_cell": notebook_payment}
caught_ids = test_df.index[model_alert & (y_true == 1)]
false_alarm_ids = test_df.index[model_alert & (y_true == 0)]
missed_ids = test_df.index[~model_alert & (y_true == 1)]
normal_ids = test_df.index[~model_alert & (y_true == 0)]
for label, ids in [("caught_fraud", caught_ids), ("false_alarm", false_alarm_ids),
                   ("missed_fraud", missed_ids), ("normal", normal_ids)]:
    if len(ids):
        examples[label] = as_request(test_df.loc[ids[0]])

golden = []
for label, payment in examples.items():
    features = dict(payment)
    features["hour"] = (features["Time"] // 3600) % 24
    row = pd.DataFrame([features])[FEATURES]
    score, reasons = what_if_typical(model, row.iloc[0], TYPICAL)
    golden.append({
        "label": label,
        "payment": payment,
        "fraud_score": float(score),
        "alert": bool(score >= THRESHOLD),
        "top_reasons": [
            {"input": name, "drop": float(r["drop"]), "score_if_typical": float(r["score if typical"])}
            for name, r in reasons.head(3).iterrows()
        ],
    })
    print(f"{label:20s} score {score:.6f} alert {score >= THRESHOLD} "
          f"top reason {reasons.index[0]}")

os.makedirs("golden", exist_ok=True)
with open("golden/golden_payments.json", "w") as f:
    json.dump(golden, f, indent=2)
with open("golden/notebook_metrics.json", "w") as f:
    json.dump(notebook_metrics, f, indent=2)
print("Notebook metrics:", json.dumps(notebook_metrics))
print("Saved golden/golden_payments.json and golden/notebook_metrics.json")
