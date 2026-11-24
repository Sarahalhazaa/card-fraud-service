"""Data source for training: the ULB credit-card CSV (150 MB), downloaded once into data/."""
import os
import urllib.request
from pathlib import Path

import pandas as pd


def ensure_dataset(url: str, path: Path) -> Path:
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print("Downloading", url)
        part = path.with_suffix(path.suffix + ".part")
        urllib.request.urlretrieve(url, part)
        os.replace(part, path)
    return path


def load_payments(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    expected = {"Time", "Amount", "Class", *(f"V{i}" for i in range(1, 29))}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"data file is missing columns: {sorted(missing)}")
    df["Class"] = df["Class"].astype(int)
    return df
