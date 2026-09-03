"""Command-line orchestration for the local ETL pipeline."""

import argparse
import json
import logging
import sqlite3
from pathlib import Path

from etl.extract import extract_from_json
from etl.load import load_readings
from etl.transform import transform_readings

SERVICE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_PATH = SERVICE_ROOT / "fixtures" / "demo_readings.json"
DEFAULT_DATABASE_PATH = SERVICE_ROOT / "data" / "enervision_etl.sqlite3"

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ETL local des mesures EnerVision")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help=f"fichier JSON source (défaut: {DEFAULT_INPUT_PATH})",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"base SQLite cible (défaut: {DEFAULT_DATABASE_PATH})",
    )
    return parser


def run(input_path: Path, database_path: Path) -> int:
    """Run extraction, transformation and loading once."""
    try:
        raw_readings = extract_from_json(input_path)
        transformed = transform_readings(raw_readings)
        loaded = load_readings(database_path, transformed.readings)
    except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error):
        LOGGER.exception("Échec du pipeline ETL")
        return 1

    LOGGER.info(
        "ETL terminé: lues=%d valides=%d rejetées=%d insérées=%d doublons_ignorés=%d",
        len(raw_readings),
        len(transformed.readings),
        transformed.rejected_count,
        loaded.inserted_count,
        loaded.skipped_count,
    )
    LOGGER.info("Base SQLite: %s", database_path.resolve())
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    arguments = build_parser().parse_args()
    return run(arguments.input, arguments.database)


if __name__ == "__main__":
    raise SystemExit(main())
