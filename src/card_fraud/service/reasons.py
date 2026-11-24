"""The "what if typical?" explanation, taken from the notebook.

For each input alone: replace its value with its typical value (the median among normal
payments), score again, and measure how far the fraud score drops. The bigger the drop,
the stronger the reason. It works with any model, because it only needs scores.
"""
from collections.abc import Mapping

from card_fraud.domain.assessment import Reason
from card_fraud.service.ports import ScoringModel


def what_if_typical(
    model: ScoringModel,
    features: Mapping[str, float],
    typical: Mapping[str, float],
) -> tuple[float, list[Reason]]:
    """Return the payment's score and every input as a reason, strongest first."""
    names = list(features)
    variants = []
    for name in names:
        variant = dict(features)
        variant[name] = typical[name]
        variants.append(variant)

    # One call to the model: the payment itself, then one variant per input.
    scores = model.predict_scores([dict(features), *variants])
    base_score, new_scores = scores[0], scores[1:]

    reasons = [
        Reason(
            input_name=name,
            value=float(features[name]),
            typical=float(typical[name]),
            score_if_typical=new_score,
            drop=base_score - new_score,
        )
        for name, new_score in zip(names, new_scores, strict=True)
    ]
    reasons.sort(key=lambda r: r.drop, reverse=True)  # stable: ties keep input order
    return base_score, reasons
