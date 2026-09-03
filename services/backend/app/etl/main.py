"""Command-line orchestration for the one-shot ETL pipeline."""

import argparse
import logging
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from app.db.session import SessionLocal
from app.etl.extract import extract_from_json
from app.etl.load import load_readings
from app.etl.transform import transform_readings

ETL_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = ETL_ROOT / "fixtures" / "demo_readings.json"

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ETL ponctuel des mesures EnerVision")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help=f"fichier JSON source (défaut: {DEFAULT_INPUT_PATH})",
    )
    return parser


def run(input_path: Path) -> int:
    """Run extraction, transformation and PostgreSQL loading once."""
    try:
        raw_readings = extract_from_json(input_path)
        transformed = transform_readings(raw_readings)
        with SessionLocal() as db:
            loaded = load_readings(db, transformed.readings)
    except (OSError, ValueError, SQLAlchemyError):
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
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    arguments = build_parser().parse_args()
    return run(arguments.input)


if __name__ == "__main__":
    raise SystemExit(main())
