"""Entry point: score one payment from a JSON file, without the API.

    python -m card_fraud.score_one payloads/notebook_fraud.json

A second entry point on the same FraudScorer: proof the service layer does not depend on the web.
"""
import argparse
import json
from pathlib import Path

from card_fraud.composition import build_scorer
from card_fraud.config import ServiceSettings
from card_fraud.domain.payment import V_NAMES, Payment


def payment_from_dict(data: dict) -> Payment:
    return Payment(
        time_seconds=float(data["Time"]),
        amount=float(data["Amount"]),
        v=tuple(float(data[name]) for name in V_NAMES),
        payment_id=data.get("payment_id"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Score one payment")
    parser.add_argument("payment", type=Path, help="JSON file with Time, Amount and V1..V28")
    args = parser.parse_args()

    scorer, _ = build_scorer(ServiceSettings())
    result = scorer.assess(payment_from_dict(json.loads(args.payment.read_text())))

    print(f"Fraud score {result.fraud_score:.3f} -> {result.decision.value} "
          f"(review at {result.policy.review_threshold}, block at {result.policy.block_threshold})")
    print("Top reasons:")
    for r in result.reasons:
        print(f"  - {r.input_name} is {r.value:.2f} (typical {r.typical:.2f}): "
              f"if it were typical, the score would fall to {r.score_if_typical:.3f}")


if __name__ == "__main__":
    main()
