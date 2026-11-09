"""
db.py — the database layer.

We use SQLite: a tiny database that lives in a single file (trends.db).
Nothing to install or run as a server — Python talks to the file directly.

Every "trend" we capture becomes one row. We take snapshots over time, so the
same hashtag captured on two different days = two rows. That's on purpose: it
lets the dashboard show what's RISING (moving up the list) vs fading.
"""

import sqlite3
import os
from datetime import datetime, timezone

# The database file sits right next to this script.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trends.db")


def get_conn():
    """Open a connection to the database file."""
    conn = sqlite3.connect(DB_PATH)
    # This makes rows behave like dictionaries (row["name"]) instead of tuples.
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the table the first time we run. Safe to call every startup."""
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trends (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_at   TEXT NOT NULL,   -- when WE recorded it (ISO timestamp)
            captured_day  TEXT NOT NULL,   -- just the date, e.g. 2026-06-05
            source        TEXT NOT NULL,   -- tiktok | instagram | manual
            category      TEXT NOT NULL,   -- clothes | hashtag | sound | other
            name          TEXT NOT NULL,   -- the trend itself, e.g. "#mobwife"
            detail        TEXT,            -- free notes / description
            metric        REAL,            -- a number if we have one (views, posts)
            metric_label  TEXT,            -- what that number means ("posts")
            rank          INTEGER,         -- its position in the trending list
            url           TEXT             -- link if we have one
        )
        """
    )
    conn.commit()
    conn.close()


def add_trend(source, category, name, detail=None, metric=None,
              metric_label=None, rank=None, url=None):
    """Insert one trend row. Used by both the auto-collector and the manual form."""
    now = datetime.now(timezone.utc)
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO trends
            (captured_at, captured_day, source, category, name,
             detail, metric, metric_label, rank, url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now.isoformat(),
            now.date().isoformat(),
            source,
            category,
            name,
            detail,
            metric,
            metric_label,
            rank,
            url,
        ),
    )
    conn.commit()
    conn.close()


def latest_per_source(source, limit=50):
    """
    Get the most recent snapshot's trends for one source (e.g. 'tiktok'),
    ordered by their rank. This is what 'trending right now' shows.
    """
    conn = get_conn()
    # Find the newest capture_day we have for this source...
    row = conn.execute(
        "SELECT MAX(captured_day) AS d FROM trends WHERE source = ?", (source,)
    ).fetchone()
    newest_day = row["d"] if row else None
    if not newest_day:
        conn.close()
        return []
    # ...then return everything captured on that day.
    rows = conn.execute(
        """
        SELECT * FROM trends
        WHERE source = ? AND captured_day = ?
        ORDER BY rank IS NULL, rank ASC, id DESC
        LIMIT ?
        """,
        (source, newest_day, limit),
    ).fetchall()
    conn.close()
    return rows


def recent_manual(limit=50):
    """Most recently logged manual / Instagram entries, newest first."""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT * FROM trends
        WHERE source IN ('manual', 'instagram')
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return rows


def fashion_highlights(limit=25):
    """
    Clothing-related trends across ALL sources, newest snapshot first.
    Pulls anything tagged category='clothes' (auto-flagged Google trends +
    anything you logged as Clothes).
    """
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT * FROM trends
        WHERE category = 'clothes'
        ORDER BY captured_day DESC, rank IS NULL, rank ASC, id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return rows


def stats():
    """Quick numbers for the top of the dashboard."""
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) AS c FROM trends").fetchone()["c"]
    days = conn.execute(
        "SELECT COUNT(DISTINCT captured_day) AS c FROM trends"
    ).fetchone()["c"]
    last = conn.execute(
        "SELECT MAX(captured_at) AS t FROM trends"
    ).fetchone()["t"]
    conn.close()
    return {"total": total, "days": days, "last": last}


def rising(source="tiktok", limit=10):
    """
    Compare the newest snapshot to the previous one and find hashtags that
    moved UP in rank (or are brand new). This is the 'momentum' view.
    Returns a list of dicts: name, today_rank, change ('NEW' or +n).
    """
    conn = get_conn()
    days = conn.execute(
        """
        SELECT DISTINCT captured_day FROM trends
        WHERE source = ? ORDER BY captured_day DESC LIMIT 2
        """,
        (source,),
    ).fetchall()
    conn.close()

    if not days:
        return []
    today = days[0]["captured_day"]
    yesterday = days[1]["captured_day"] if len(days) > 1 else None

    conn = get_conn()
    today_rows = conn.execute(
        "SELECT name, rank FROM trends WHERE source=? AND captured_day=?",
        (source, today),
    ).fetchall()
    prev = {}
    if yesterday:
        for r in conn.execute(
            "SELECT name, rank FROM trends WHERE source=? AND captured_day=?",
            (source, yesterday),
        ).fetchall():
            prev[r["name"]] = r["rank"]
    conn.close()

    out = []
    for r in today_rows:
        if r["rank"] is None:
            continue
        if r["name"] not in prev:
            out.append({"name": r["name"], "rank": r["rank"], "change": "NEW"})
        else:
            delta = prev[r["name"]] - r["rank"]  # positive = moved up
            if delta > 0:
                out.append({"name": r["name"], "rank": r["rank"], "change": f"+{delta}"})
    # New entries first, then biggest climbers.
    out.sort(key=lambda x: (x["change"] != "NEW", -(0 if x["change"] == "NEW" else int(x["change"]))))
    return out[:limit]
