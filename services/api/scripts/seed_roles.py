from app.db.init_db import initialize_database
from app.db.session import SessionLocal


if __name__ == "__main__":
    with SessionLocal() as db:
        initialize_database(db)
    print("Roles and demonstration data initialized.")