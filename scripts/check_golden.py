"""Golden check: does the reorganised code give the notebook's answers?

    python legacy/notebook_reference.py   # once: saves the notebook's answers in golden/
    python -m card_fraud.train            # trains with the new code into artifacts/
    python scripts/check_golden.py        # compares the two
"""
import json
import sys
from pathlib import Path

from card_fraud.composition import build_scorer
from card_fraud.config import ServiceSettings
from card_fraud.domain.assessment import Decision
from card_fraud.score_one import payment_from_dict

TOLERANCE = 1e-6
golden = json.loads(Path("golden/golden_payments.json").read_text())
notebook_metrics = json.loads(Path("golden/notebook_metrics.json").read_text())

settings = ServiceSettings(top_reasons=3)
scorer, card = build_scorer(settings)
problems = []

# 1) The training numbers: same threshold and same test results as the notebook
for key, expected in notebook_metrics.items():
    actual = card.threshold if key == "threshold" else card.test_metrics[key]
    same = abs(actual - expected) <= TOLERANCE
    print(f"{'OK  ' if same else 'DIFF'} {key:18s} notebook {expected:<10.6g} new code {actual:.6g}")
    if not same:
        problems.append(key)

# 2) The answers for each reference payment: score, alert, and top reasons
for case in golden:
    result = scorer.assess(payment_from_dict(case["payment"]))
    alert = result.decision in (Decision.REVIEW, Decision.BLOCK)
    score_ok = abs(result.fraud_score - case["fraud_score"]) <= TOLERANCE
    drops_ok = all(
        abs(r.drop - g["drop"]) <= TOLERANCE
        for r, g in zip(result.reasons, case["top_reasons"], strict=True)
    )
    top_ok = result.reasons[0].input_name == case["top_reasons"][0]["input"] or drops_ok
    ok = score_ok and alert == case["alert"] and drops_ok and top_ok
    print(f"{'OK  ' if ok else 'DIFF'} {case['label']:20s} notebook {case['fraud_score']:.6f} "
          f"new code {result.fraud_score:.6f}  top reason {result.reasons[0].input_name}")
    if not ok:
        problems.append(case["label"])

if problems:
    print(f"\nGOLDEN CHECK FAILED for: {problems}")
    sys.exit(1)
print(f"\nGolden check passed: {len(golden)} payments and {len(notebook_metrics)} training numbers match.")
