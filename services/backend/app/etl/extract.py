"""Extraction adapters for the ETL pipeline."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def extract_from_json(file_path: Path) -> list[Any]:
    """Read a JSON array from *file_path* without altering its entries."""
    with file_path.open(encoding="utf-8") as source_file:
        payload = json.load(source_file)

    if not isinstance(payload, list):
        raise ValueError("Le fichier source doit contenir un tableau JSON")

    return payload


@dataclass(frozen=True)
class RawReadingRow:
    """Une mesure brute lue dans raw_readings."""

    id: int
    received_at: datetime
    payload: dict[str, Any]


def extract_from_raw_readings(
    db: Session,
    window_start: datetime,
    window_end: datetime,
    after_id: int,
    limit: int,
) -> list[RawReadingRow]:
    """Rend un lot de mesures brutes recues dans la fenetre demandee.

    Rien n est ecrit sur raw_readings : la table reste en insertion seule. Ce
    qui a deja ete transforme est simplement relu, et la cle unique de readings
    absorbe le rechargement.

    La pagination se fait par identifiant croissant, pas par OFFSET : *after_id*
    est le dernier identifiant du lot precedent. Une fenetre de plusieurs
    dizaines de milliers de lignes se lit ainsi sans tout charger en memoire, et
    le cout de chaque lot reste le meme du premier au dernier.
    """
    result = db.execute(
        text(
            "SELECT id, received_at, payload FROM raw_readings "
            "WHERE received_at >= :window_start "
            "AND received_at < :window_end "
            "AND id > :after_id "
            "ORDER BY id "
            "LIMIT :limit"
        ),
        {
            "window_start": window_start,
            "window_end": window_end,
            "after_id": after_id,
            "limit": limit,
        },
    )
    return [
        RawReadingRow(id=row.id, received_at=row.received_at, payload=row.payload) for row in result
    ]


@dataclass(frozen=True)
class SnapshotRow:
    """Un instantane de referentiel lu dans raw_snapshots."""

    received_at: datetime
    payload: Any


def extract_latest_sensors(db: Session) -> SnapshotRow | None:
    """Rend le dernier etat des capteurs recu, ou None si aucun n est arrive.

    L horodatage de reception est rendu avec le contenu : c est lui qui sert
    d observed_at a l etage 2. Relire deux fois le meme instantane produit donc
    les memes lignes, que la cle unique de sensor_status ignore.
    """
    row = db.execute(
        text(
            "SELECT received_at, payload FROM raw_snapshots "
            "WHERE source = 'api_sensors' "
            "ORDER BY received_at DESC, id DESC "
            "LIMIT 1"
        )
    ).first()
    if row is None:
        return None
    if not isinstance(row.payload, dict):
        raise ValueError("Un instantane api_sensors doit contenir un objet JSON")
    return SnapshotRow(received_at=row.received_at, payload=row.payload)


def extract_latest_sites(db: Session) -> list[Any]:
    """Rend le dernier referentiel de sites recu par le collecteur.

    Liste vide tant qu aucun instantane n est arrive. Le referentiel reste alors
    inchange et le passage continue : l absence de referentiel n est pas une
    erreur, c est l etat normal avant la premiere reprise d historique.
    """
    payload = db.scalar(
        text(
            "SELECT payload FROM raw_snapshots "
            "WHERE source = 'api_sites' "
            "ORDER BY received_at DESC, id DESC "
            "LIMIT 1"
        )
    )
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ValueError("Un instantane api_sites doit contenir un tableau JSON")
    return payload
