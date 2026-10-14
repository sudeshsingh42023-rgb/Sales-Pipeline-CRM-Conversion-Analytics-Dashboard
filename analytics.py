"""Funnel, conversion, time-in-stage, forecast and activity analytics."""
import pandas as pd

from .config import FUNNEL, OPEN_STAGES, STAGE_PROB


def reached_counts(leads: pd.DataFrame, history: pd.DataFrame) -> pd.DataFrame:
    """How many leads ever reached each funnel stage (skipping a stage still counts as passing it)."""
    idx = {s: i for i, s in enumerate(FUNNEL)}
    h = history[history["to_stage"].isin(idx)].copy()
    h["i"] = h["to_stage"].map(idx)
    best = h.groupby("lead_id")["i"].max()
    rows = [{"stage": s, "reached": int((best >= i).sum())} for s, i in idx.items()]
    out = pd.DataFrame(rows)
    out["conv_from_prev"] = (out["reached"] / out["reached"].shift(1)).round(3)
    out["conv_from_top"] = (out["reached"] / max(out["reached"].iloc[0], 1)).round(3)
    return out


def avg_days_in_stage(history: pd.DataFrame, now=None) -> pd.DataFrame:
    now = pd.Timestamp(now or pd.Timestamp.now())
    rows = []
    for lid, g in history.sort_values("ts").groupby("lead_id"):
        ts, stages = list(g["ts"]), list(g["to_stage"])
        for i, st in enumerate(stages):
            if i + 1 < len(ts):
                end = ts[i + 1]
            elif st in OPEN_STAGES:
                end = now
            else:
                continue
            rows.append({"stage": st, "days": (end - ts[i]).total_seconds() / 86400})
    if not rows:
        return pd.DataFrame(columns=["stage", "avg_days"])
    out = pd.DataFrame(rows).groupby("stage")["days"].mean().round(1).reset_index(name="avg_days")
    return out


def weighted_forecast(leads: pd.DataFrame) -> dict:
    op = leads[leads["stage"].isin(OPEN_STAGES)].copy()
    op["prob"] = op["stage"].map(STAGE_PROB)
    op["weighted"] = op["deal_value"].fillna(0) * op["prob"]
    return {"open_pipeline_value": float(op["deal_value"].fillna(0).sum()),
            "weighted_forecast": float(op["weighted"].sum()),
            "won_value": float(leads.loc[leads["stage"] == "Won", "deal_value"].fillna(0).sum()),
            "by_stage": op.groupby("stage")[["deal_value", "weighted"]].sum().reindex(OPEN_STAGES).fillna(0)}


def weekly_activity(acts: pd.DataFrame) -> pd.DataFrame:
    if acts.empty:
        return pd.DataFrame(columns=["week", "type", "count"])
    a = acts[acts["type"] != "Note"].copy()
    a["week"] = a["ts"].dt.to_period("W").apply(lambda p: p.start_time.date())
    return a.groupby(["week", "type"]).size().reset_index(name="count")


def lost_reasons(leads: pd.DataFrame) -> pd.DataFrame:
    lost = leads[leads["stage"] == "Lost"]
    return lost["lost_reason"].fillna("Unspecified").value_counts().rename_axis("reason").reset_index(name="count")


def segment_win_rate(leads: pd.DataFrame) -> pd.DataFrame:
    df = leads[leads["stage"].isin(["Won", "Lost"])].copy()
    if df.empty:
        return pd.DataFrame(columns=["segment", "closed", "won", "win_rate"])
    g = df.groupby(df["segment"].replace("", "Unknown")).agg(closed=("id", "count"),
                                                              won=("stage", lambda s: (s == "Won").sum()))
    g["win_rate"] = (g["won"] / g["closed"]).round(3)
    return g.reset_index().rename(columns={"segment": "segment"})


def weakest_stage(conv: pd.DataFrame):
    """Funnel step with the lowest conversion from the previous stage (min 5 leads at the previous stage)."""
    c = conv.copy()
    c["prev_reached"] = c["reached"].shift(1)
    c = c[(c["prev_reached"] >= 5) & c["conv_from_prev"].notna()]
    if c.empty:
        return None
    r = c.sort_values("conv_from_prev").iloc[0]
    return {"stage": r["stage"], "conv_from_prev": float(r["conv_from_prev"])}
