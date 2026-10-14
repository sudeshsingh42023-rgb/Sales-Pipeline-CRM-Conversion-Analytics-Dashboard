"""SQLite data layer: leads, activities, stage history."""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from .config import ACTIVITY_TYPES, DB_PATH, FOLLOWUP_GAP_DAYS, OPEN_STAGES, STAGES, STALE_DAYS

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company TEXT NOT NULL, contact_name TEXT, role TEXT, email TEXT, phone TEXT,
  source TEXT, segment TEXT, score INTEGER, stage TEXT NOT NULL DEFAULT 'Lead',
  deal_value REAL DEFAULT 0, lost_reason TEXT, notes TEXT,
  created_at TEXT NOT NULL, stage_changed_at TEXT NOT NULL,
  last_contacted TEXT, next_followup TEXT
);
CREATE TABLE IF NOT EXISTS activities (
  id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER NOT NULL, type TEXT, note TEXT, ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stage_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER NOT NULL, from_stage TEXT, to_stage TEXT NOT NULL, ts TEXT NOT NULL
);
"""


def now() -> datetime:
    return datetime.now().replace(microsecond=0)


def connect(path: str = DB_PATH) -> sqlite3.Connection:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def add_lead(con, company, contact_name="", role="", email="", phone="", source="", segment="",
             score=None, deal_value=0.0, notes="", ts: datetime | None = None) -> int:
    ts = ts or now()
    cur = con.execute(
        "INSERT INTO leads (company,contact_name,role,email,phone,source,segment,score,stage,deal_value,notes,"
        "created_at,stage_changed_at,next_followup) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (company, contact_name, role, email, phone, source, segment, score, "Lead", deal_value, notes,
         ts.isoformat(), ts.isoformat(), ts.date().isoformat()))
    lid = cur.lastrowid
    con.execute("INSERT INTO stage_history (lead_id,from_stage,to_stage,ts) VALUES (?,?,?,?)",
                (lid, None, "Lead", ts.isoformat()))
    con.commit()
    return lid


def move_stage(con, lead_id, new_stage, lost_reason=None, ts: datetime | None = None):
    assert new_stage in STAGES, f"unknown stage {new_stage}"
    ts = ts or now()
    cur = con.execute("SELECT stage FROM leads WHERE id=?", (lead_id,)).fetchone()
    if cur is None or cur["stage"] == new_stage:
        return
    nxt = None if new_stage in ("Won", "Lost") else (ts + timedelta(days=FOLLOWUP_GAP_DAYS)).date().isoformat()
    con.execute("UPDATE leads SET stage=?, stage_changed_at=?, lost_reason=?, next_followup=? WHERE id=?",
                (new_stage, ts.isoformat(), lost_reason if new_stage == "Lost" else None, nxt, lead_id))
    con.execute("INSERT INTO stage_history (lead_id,from_stage,to_stage,ts) VALUES (?,?,?,?)",
                (lead_id, cur["stage"], new_stage, ts.isoformat()))
    con.commit()


def log_activity(con, lead_id, type_, note="", gap_days: int = FOLLOWUP_GAP_DAYS, ts: datetime | None = None):
    """Log an interaction; automatically schedules the next follow-up."""
    assert type_ in ACTIVITY_TYPES
    ts = ts or now()
    con.execute("INSERT INTO activities (lead_id,type,note,ts) VALUES (?,?,?,?)", (lead_id, type_, note, ts.isoformat()))
    if type_ != "Note":
        con.execute("UPDATE leads SET last_contacted=?, next_followup=? WHERE id=?",
                    (ts.isoformat(), (ts + timedelta(days=gap_days)).date().isoformat(), lead_id))
    con.commit()


def set_followup(con, lead_id, date_str):
    con.execute("UPDATE leads SET next_followup=? WHERE id=?", (date_str, lead_id))
    con.commit()


def update_fields(con, lead_id, **fields):
    allowed = {"company", "contact_name", "role", "email", "phone", "segment", "deal_value", "notes"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if sets:
        con.execute(f"UPDATE leads SET {', '.join(k + '=?' for k in sets)} WHERE id=?", (*sets.values(), lead_id))
        con.commit()


def import_scored_csv(con, df: pd.DataFrame) -> int:
    """Import leads_scored.csv from the Lead Discovery & Outreach Engine (or any CSV with a 'company' column)."""
    existing = {r["company"] for r in con.execute("SELECT company FROM leads")}
    n = 0
    for _, r in df.iterrows():
        if r["company"] in existing:
            continue
        g = lambda k: "" if pd.isna(r.get(k)) else r.get(k)
        add_lead(con, r["company"], g("contact_name"), g("contact_role"), g("email"), "", g("source"),
                 g("segment"), int(r["score"]) if pd.notna(r.get("score")) else None)
        n += 1
    return n


def leads_df(con) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM leads", con)


def activities_df(con) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM activities", con, parse_dates=["ts"])


def history_df(con) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM stage_history", con, parse_dates=["ts"])


def todays_queue(con, today=None) -> pd.DataFrame:
    """Open leads that are due for follow-up today or overdue, or stale. Most overdue first."""
    today = pd.Timestamp(today or now().date())
    df = leads_df(con)
    df = df[df["stage"].isin(OPEN_STAGES)].copy()
    if df.empty:
        return df
    df["next_followup"] = pd.to_datetime(df["next_followup"])
    df["last_contacted"] = pd.to_datetime(df["last_contacted"])
    df["days_overdue"] = (today - df["next_followup"]).dt.days
    ref = df["last_contacted"].fillna(pd.to_datetime(df["created_at"]))
    df["days_since_contact"] = (today - ref.dt.normalize()).dt.days
    due = df[(df["days_overdue"] >= 0) | (df["days_since_contact"] >= STALE_DAYS)]
    return due.sort_values(["days_overdue", "score"], ascending=[False, False])
