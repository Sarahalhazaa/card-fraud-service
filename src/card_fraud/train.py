"""Entry point: train the model and save it to artifacts/.

    python -m card_fraud.train
"""
from card_fraud.adapters.payments_csv import ensure_dataset, load_payments
from card_fraud.config import TrainingSettings
from card_fraud.training.pipeline import run


def main() -> None:
    settings = TrainingSettings()
    path = ensure_dataset(settings.data_url, settings.data_path)
    run(load_payments(path), settings)


if __name__ == "__main__":
    main()
