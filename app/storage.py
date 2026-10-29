from contextlib import contextmanager, closing
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import os
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("API_DOC_DB", str(ROOT/"data"/"projects.sqlite3")))


@contextmanager
def connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DB_PATH, timeout=15)) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.row_factory = sqlite3.Row
        with db:
            yield db


def initialize():
    with connection() as db:
        db.execute("CREATE TABLE IF NOT EXISTS projects (number INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT NOT NULL)")


def insert(record):
    value = {**record, "created_at":datetime.now(timezone(timedelta(hours=5,minutes=30))).isoformat(timespec="seconds")}
    with connection() as db:
        cursor = db.execute("INSERT INTO projects(body) VALUES ('{}')")
        value["id"] = f"DOC-{cursor.lastrowid:04d}"
        db.execute("UPDATE projects SET body=? WHERE number=?", (json.dumps(value),cursor.lastrowid))
    return value


def get(identifier):
    if not isinstance(identifier,str) or not identifier.startswith("DOC-") or not identifier[4:].isdigit():
        return None
    with connection() as db:
        row = db.execute("SELECT body FROM projects WHERE number=?", (int(identifier[4:]),)).fetchone()
    return json.loads(row["body"]) if row else None


def all_records():
    with connection() as db:
        rows = db.execute("SELECT body FROM projects ORDER BY number DESC").fetchall()
    return [json.loads(row["body"]) for row in rows]


def update(identifier, updater):
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT body FROM projects WHERE number=?", (int(identifier[4:]),)).fetchone()
        if not row:
            return None
        value = json.loads(row["body"])
        updater(value)
        db.execute("UPDATE projects SET body=? WHERE number=?", (json.dumps(value),int(identifier[4:])))
    return value
