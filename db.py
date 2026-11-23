"""MySQL connection layer for the Pharmaceutical Stock Level Tracker.

One connection per request is opened lazily, stored on flask.g and closed
automatically when the request ends (see init_app). All settings come from
app.config, which config.py fills from environment variables (.env).

Always pass values as parameters (%s placeholders). Never build SQL by
joining strings with user input.
"""
import logging
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor
from flask import current_app, g

log = logging.getLogger(__name__)


def _connect():
    cfg = current_app.config
    return pymysql.connect(
        host=cfg["DB_HOST"],
        port=int(cfg["DB_PORT"]),
        user=cfg["DB_USER"],
        password=cfg["DB_PASSWORD"],
        database=cfg["DB_NAME"],
        charset="utf8mb4",
        cursorclass=DictCursor,   # rows come back as dicts: row["sku"]
        autocommit=False,
    )


def get_db():
    """Return the connection for the current request, opening it if needed."""
    if "db" not in g:
        g.db = _connect()
    return g.db


def close_db(exc=None):
    """Close the request's connection (registered as a teardown handler)."""
    conn = g.pop("db", None)
    if conn is not None:
        if exc is not None:
            conn.rollback()
        conn.close()


def query(sql, params=None):
    """Run a SELECT and return all rows as a list of dicts."""
    with get_db().cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def query_one(sql, params=None):
    """Run a SELECT and return the first row (dict) or None."""
    with get_db().cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchone()


def execute(sql, params=None):
    """Run a single INSERT/UPDATE/DELETE and commit. Returns lastrowid."""
    with transaction() as cur:
        cur.execute(sql, params or ())
        return cur.lastrowid


@contextmanager
def transaction():
    """Group several writes so they all succeed or all roll back."""
    conn = get_db()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except ValueError as exc:
        # expected business-rule failure (e.g. not enough stock): no traceback
        conn.rollback()
        log.warning("Transaction rolled back: %s", exc)
        raise
    except Exception:
        conn.rollback()
        log.exception("Database transaction rolled back")
        raise
    finally:
        cur.close()


def init_app(app):
    """Register the connection teardown with the Flask app."""
    app.teardown_appcontext(close_db)