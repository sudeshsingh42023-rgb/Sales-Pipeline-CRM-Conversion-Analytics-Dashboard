from datetime import datetime, timedelta

from crm import analytics as A, db
from crm.seed import seed


def test_stage_flow_and_queue():
    con = db.connect(":memory:")
    t0 = datetime(2026, 10, 1, 9, 0)
    a = db.add_lead(con, "A Co", ts=t0)
    b = db.add_lead(con, "B Co", ts=t0)
    db.log_activity(con, a, "Email", "intro", ts=t0)
    db.move_stage(con, a, "Contacted", ts=t0)
    q = db.todays_queue(con, today=(t0 + timedelta(days=4)).date())
    assert set(q["company"]) == {"A Co", "B Co"}      # both due
    db.move_stage(con, a, "Lost", "No response", ts=t0 + timedelta(days=5))
    q = db.todays_queue(con, today=(t0 + timedelta(days=6)).date())
    assert "A Co" not in set(q["company"])


def test_conversion_counts_skipped_stages():
    con = db.connect(":memory:")
    t0 = datetime(2026, 10, 1)
    x = db.add_lead(con, "X", ts=t0)
    db.move_stage(con, x, "Call Booked", ts=t0 + timedelta(days=1))   # skipped Contacted/Replied
    conv = A.reached_counts(db.leads_df(con), db.history_df(con)).set_index("stage")
    assert conv.loc["Replied", "reached"] == 1 and conv.loc["Proposal", "reached"] == 0


def test_forecast_and_demo_seed():
    con = db.connect(":memory:")
    seed(con, n=60)
    leads, hist = db.leads_df(con), db.history_df(con)
    fc = A.weighted_forecast(leads)
    assert fc["weighted_forecast"] <= fc["open_pipeline_value"]
    conv = A.reached_counts(leads, hist)
    assert conv["reached"].is_monotonic_decreasing
    assert len(A.avg_days_in_stage(hist)) > 0
