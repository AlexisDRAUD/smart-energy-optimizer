from collections.abc import Generator
from datetime import UTC, datetime, time, timedelta

import pytest
from app.db.models.quality import DataQualityDaily
from app.db.models.reading import Reading
from app.db.models.site import Site
from app.db.session import SessionLocal
from app.etl.main import run_once
from app.etl.quality import (
    MINUTES_PER_DAY,
    compute_daily_quality,
    days_touched,
    expected_points,
)
from sqlalchemy import delete, select

SITE_ID = "QUA-01"
# Un jour bien avant l historique du seed : ce module ne doit rien changer aux
# journees que les autres tests observent.
DAY = (datetime.now(UTC) - timedelta(days=30)).date()
DAY_START = datetime.combine(DAY, time.min, tzinfo=UTC)


def _reading(minute: int, raw: float | None, imputed: bool) -> Reading:
    return Reading(
        site_id=SITE_ID,
        measured_at=DAY_START + timedelta(minutes=minute),
        consumption_kwh=raw if raw is not None else 100.0 if imputed else None,
        consumption_kwh_raw=raw,
        is_imputed=imputed,
        imputation_method="report" if imputed else None,
        temperature_celsius=None,
        humidity_percent=None,
        data_quality="good" if raw is not None else "partial",
        null_reasons=[] if raw is not None else ["sensor_failure"],
        ingested_at=DAY_START,
    )


@pytest.fixture
def journee_mesuree(database: None) -> Generator[None, None, None]:
    """Une journee de mesures : trois valeurs recues, deux nulles dont une reparee."""
    with SessionLocal() as db:
        db.add(
            Site(
                site_id=SITE_ID,
                site_type="office",
                site_name="Site de qualite",
                location="Niort, France",
                capacity_kw=100,
                status="active",
                first_seen_at=DAY_START,
                last_seen_at=DAY_START,
            )
        )
        db.add_all(
            [
                _reading(0, 10.0, False),
                _reading(1, 11.0, False),
                _reading(2, None, True),
                _reading(3, None, False),
                _reading(4, 12.0, False),
            ]
        )
        db.commit()
    yield
    with SessionLocal() as db:
        db.execute(delete(DataQualityDaily).where(DataQualityDaily.day == DAY))
        db.execute(delete(Reading).where(Reading.site_id == SITE_ID))
        db.execute(delete(Site).where(Site.site_id == SITE_ID))
        db.commit()


def _resume(site_id: str) -> DataQualityDaily | None:
    with SessionLocal() as db:
        return db.scalar(
            select(DataQualityDaily).where(
                DataQualityDaily.site_id == site_id, DataQualityDaily.day == DAY
            )
        )


def test_le_resume_compte_les_recus_les_nuls_et_les_repares(journee_mesuree: None) -> None:
    with SessionLocal() as db:
        compute_daily_quality(db, [DAY])

    resume = _resume(SITE_ID)
    assert resume is not None
    assert resume.expected_points == MINUTES_PER_DAY
    assert resume.received_points == 5
    # Ce qui n est jamais arrive : le trou de collecte.
    assert resume.missing_points == MINUTES_PER_DAY - 5
    # Recus sans valeur, que la reparation les ait remplis ou non.
    assert resume.null_points == 2
    assert resume.imputed_points == 1


def test_un_site_muet_toute_la_journee_a_son_resume_a_zero(journee_mesuree: None) -> None:
    """Sans ligne, le trou ne se lit nulle part ailleurs : il faut l ecrire."""
    with SessionLocal() as db:
        compute_daily_quality(db, [DAY])

    resume = _resume("LYO-01")
    assert resume is not None
    assert resume.received_points == 0
    assert resume.missing_points == MINUTES_PER_DAY


def test_repasser_sur_le_meme_jour_recrit_les_memes_chiffres(journee_mesuree: None) -> None:
    with SessionLocal() as db:
        compute_daily_quality(db, [DAY])
        premier = _resume(SITE_ID)
        assert premier is not None
        attendu = (premier.received_points, premier.null_points, premier.imputed_points)

        compute_daily_quality(db, [DAY])

    with SessionLocal() as db:
        lignes = list(
            db.scalars(
                select(DataQualityDaily).where(
                    DataQualityDaily.site_id == SITE_ID, DataQualityDaily.day == DAY
                )
            )
        )

    assert len(lignes) == 1
    assert (lignes[0].received_points, lignes[0].null_points, lignes[0].imputed_points) == attendu


def test_le_jour_en_cours_n_attend_que_les_minutes_ecoulees() -> None:
    """Sinon la journee pas encore vecue passerait pour un trou de collecte."""
    maintenant = datetime(2026, 9, 8, 8, 30, tzinfo=UTC)

    assert expected_points(maintenant.date(), maintenant) == 8 * 60 + 30 + 1
    assert expected_points(maintenant.date() - timedelta(days=1), maintenant) == MINUTES_PER_DAY
    assert expected_points(maintenant.date() + timedelta(days=1), maintenant) == 0


def test_les_jours_touches_couvrent_les_deux_bornes() -> None:
    debut = datetime(2026, 9, 6, 23, 50, tzinfo=UTC)
    fin = datetime(2026, 9, 8, 0, 10, tzinfo=UTC)

    assert days_touched(debut, fin) == {debut.date(), debut.date() + timedelta(days=1), fin.date()}


def test_le_passage_etl_ecrit_le_resume_du_jour(database: None) -> None:
    """Sans cet appel dans la passe, /api/v1/quality reste vide au demarrage."""
    aujourd_hui = datetime.now(UTC).date()
    with SessionLocal() as db:
        db.execute(delete(DataQualityDaily).where(DataQualityDaily.day == aujourd_hui))
        db.commit()

    assert run_once() == 0

    with SessionLocal() as db:
        lignes = list(
            db.scalars(select(DataQualityDaily).where(DataQualityDaily.day == aujourd_hui))
        )

    assert {ligne.site_id for ligne in lignes} == {"LYO-01", "GRE-01", "NAN-01"}
    lyon = next(ligne for ligne in lignes if ligne.site_id == "LYO-01")
    assert lyon.received_points > 0
    assert lyon.expected_points <= MINUTES_PER_DAY
