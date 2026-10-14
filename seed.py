"""Generate SYNTHETIC demo data so the dashboard has something to show. Not real prospects or results."""
import random
from datetime import datetime, timedelta

from . import db
from .config import ACTIVITY_TYPES, LOST_REASONS

SEGMENTS = ["Automation", "Mobile App", "MVP / Product Build", "SaaS / Platform"]
# probability of advancing from one stage to the next (demo funnel shape)
ADV = [("Contacted", 0.9), ("Replied", 0.30), ("Call Booked", 0.55), ("Proposal", 0.5), ("Won", 0.35)]


def seed(con, n=80, seed_=11, today=None):
    rnd = random.Random(seed_)
    today = today or datetime.now().replace(microsecond=0)
    for i in range(1, n + 1):
        start = today - timedelta(days=rnd.randint(2, 60))
        lid = db.add_lead(con, f"Sample Business {i:02d}", f"Contact {i:02d}", "Founder",
                          f"contact{i:02d}@sample.example", "", "SYNTHETIC", rnd.choice(SEGMENTS),
                          rnd.randint(25, 95), rnd.choice([40000, 80000, 150000, 300000]), ts=start)
        t, stage = start, "Lead"
        for nxt, p in ADV:
            if rnd.random() > p:
                if stage != "Lead" and rnd.random() < 0.7:
                    t += timedelta(days=rnd.randint(1, 6))
                    if t < today:
                        db.move_stage(con, lid, "Lost", rnd.choice(LOST_REASONS), ts=t)
                        stage = "Lost"
                break
            t += timedelta(days=rnd.randint(1, 6))
            if t >= today:
                break
            db.log_activity(con, lid, rnd.choice(ACTIVITY_TYPES[:5]), "demo", ts=t)
            db.move_stage(con, lid, nxt, ts=t)
            stage = nxt
