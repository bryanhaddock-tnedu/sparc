import argparse

from app.db.seed import seed_database
from app.db.session import SessionLocal, create_database, drop_database


def init_db() -> None:
    create_database()
    print("Database schema initialized.")


def seed_db() -> None:
    create_database()
    with SessionLocal() as db:
        seed_database(db)
    print("Seed data applied.")


def reset_db() -> None:
    drop_database()
    create_database()
    with SessionLocal() as db:
        seed_database(db)
    print("Database reset and seeded.")


def main() -> None:
    parser = argparse.ArgumentParser(description="SPARK backend maintenance commands")
    parser.add_argument("command", choices=["init-db", "seed-db", "reset-db"])
    args = parser.parse_args()

    if args.command == "init-db":
        init_db()
    elif args.command == "seed-db":
        seed_db()
    elif args.command == "reset-db":
        reset_db()


if __name__ == "__main__":
    main()
