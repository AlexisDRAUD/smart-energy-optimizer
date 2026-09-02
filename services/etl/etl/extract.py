"""Extraction adapters for the ETL pipeline."""

import json
from pathlib import Path
from typing import Any


def extract_from_json(file_path: Path) -> list[Any]:
    """Read a JSON array from *file_path* without altering its entries."""
    with file_path.open(encoding="utf-8") as source_file:
        payload = json.load(source_file)

    if not isinstance(payload, list):
        raise ValueError("Le fichier source doit contenir un tableau JSON")

    return payload
