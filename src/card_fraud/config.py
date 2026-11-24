"""All settings in ONE place. Nothing else in the codebase reads os.environ or hard-codes a path.

Every value can be changed with an environment variable (or a .env file), for example
FRAUD_BLOCK_THRESHOLD=0.95 or FRAUD_TRAIN_DATA_PATH=/tmp/creditcard.csv.
"""
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    """Settings for the running service (API and command line)."""

    model_config = SettingsConfigDict(env_prefix="FRAUD_", env_file=".env", extra="ignore")

    model_path: Path = Path("artifacts/fraud_model.joblib")
    model_info_path: Path = Path("artifacts/model_info.json")

    # The fraud team's rules. "review" = send to the fraud team for a check.
    # None means: use the threshold chosen during training (saved in model_info.json).
    review_threshold: float | None = Field(None, ge=0.0, le=1.0)
    # "block" is a business rule the notebook does not have. Agree on it with the fraud team.
    block_threshold: float = Field(0.9, ge=0.0, le=1.0)

    top_reasons: int = Field(3, ge=1, le=30)
    log_level: str = "INFO"
    git_sha: str = "dev"


class TrainingSettings(BaseSettings):
    """Settings for training (the notebook's "Settings" cell)."""

    model_config = SettingsConfigDict(env_prefix="FRAUD_TRAIN_", env_file=".env", extra="ignore")

    # ULB credit-card fraud data, public copy kept for TensorFlow's tutorials
    # (same data, if this address ever fails: https://www.openml.org/d/1597)
    data_url: str = "https://storage.googleapis.com/download.tensorflow.org/data/creditcard.csv"
    data_path: Path = Path("data/creditcard.csv")
    model_path: Path = Path("artifacts/fraud_model.joblib")
    model_info_path: Path = Path("artifacts/model_info.json")

    model_version: str = "1.0.0"
    random_seed: int = 42
    train_share: float = Field(0.6, gt=0, lt=1)  # first 60% of the time line: training
    valid_share: float = Field(0.2, gt=0, lt=1)  # next 20%: choosing the threshold; last 20%: test
    min_precision: float = Field(0.80, gt=0, le=1)  # at least 8 of every 10 alerts must be real fraud
    thresholds_to_try: list[float] = [
        0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99,
    ]
    amount_rule: float = 1000  # baseline rule: alert on every payment above this amount
