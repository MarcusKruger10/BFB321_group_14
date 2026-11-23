"""Build the MySQL database from nothing in one command.

    python init_db.py               # create database, load schema + seed data
    python init_db.py --no-seed     # schema only (empty tables)
    python init_db.py --test        # same, into TEST_DB_NAME (for pytest)

Reads the connection settings from .env (see .env.example). WARNING: the
schema drops and recreates every table, so existing data in DB_NAME is lost.
Back up first if needed:  mysqldump -u <user> -p pharmacy_tracker > backup.sql
"""
import argparse
import os
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
SCHEMA = BASE / "database" / "schema.sql"
SEED = BASE / "database" / "seed.sql"


def split_sql(script):
    """Split a .sql script into statements on ';', ignoring ';' inside quotes
    and skipping -- comments."""
    statements, buf, quote = [], [], None
    i = 0
    while i < len(script):
        ch = script[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                if i + 1 < len(script) and script[i + 1] == quote:  # escaped ''
                    buf.append(script[i + 1])
                    i += 1
                else:
                    quote = None
        elif ch in ("'", '"', "`"):
            quote = ch
            buf.append(ch)
        elif script.startswith("--", i):
            while i < len(script) and script[i] != "\n":
                i += 1
            continue
        elif ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
        else:
            buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def run_file(conn, path):
    statements = split_sql(path.read_text(encoding="utf-8"))
    with conn.cursor() as cur:
        for stmt in statements:
            cur.execute(stmt)
    conn.commit()
    print(f"  ran {len(statements):3d} statements from {path.relative_to(BASE)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-seed", action="store_true", help="load the schema only")
    parser.add_argument("--test", action="store_true", help="use TEST_DB_NAME instead of DB_NAME")
    args = parser.parse_args()

    load_dotenv(BASE / ".env")
    db_name = os.getenv("TEST_DB_NAME", "pharmacy_tracker_test") if args.test else os.getenv("DB_NAME", "pharmacy_tracker")

    try:
        conn = pymysql.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            charset="utf8mb4",
        )
    except pymysql.err.OperationalError as exc:
        sys.exit(f"Could not connect to MySQL - check DB_HOST/DB_USER/DB_PASSWORD in .env\n{exc}")

    with conn.cursor() as cur:
        # db_name comes from our own .env, not from a user; backticks guard odd names
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cur.execute(f"USE `{db_name}`")
    print(f"Database: {db_name}")

    run_file(conn, SCHEMA)
    if not args.no_seed:
        run_file(conn, SEED)

    counts = []
    with conn.cursor() as cur:
        for table in ("products", "batches", "stock_movements", "alerts"):
            cur.execute(f"SELECT COUNT(*) FROM {table}")  # fixed table names, no user input
            counts.append(f"{cur.fetchone()[0]} {table}")
    conn.close()
    print("Done: " + ", ".join(counts))


if __name__ == "__main__":
    main()