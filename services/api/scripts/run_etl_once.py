from app.db.init_db import initialize_database
from app.db.session import SessionLocal
from app.services.etl_service import process_stored_readings


def main() -> None:
    with SessionLocal() as db:
        initialize_database(db)
        processed = process_stored_readings(db)
    print(f"{processed} readings processed from the local database.")


if __name__ == "__main__":
    main()