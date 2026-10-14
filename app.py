"""Streamlit front end. Run: streamlit run app.py"""
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from crm import analytics as A, db
from crm.config import ACTIVITY_TYPES, FUNNEL, LOST_REASONS, OPEN_STAGES, STAGES, STALE_DAYS
from crm.seed import seed

st.set_page_config(page_title="Sales Pipeline CRM", layout="wide")
con = db.connect()

st.sidebar.title("Sales Pipeline CRM")
page = st.sidebar.radio("Go to", ["Today's queue", "Pipeline", "Add / import leads", "Analytics"])
if st.sidebar.button("Load SYNTHETIC demo data"):
    seed(con)
    st.sidebar.success("Demo data loaded (synthetic)")
leads = db.leads_df(con)


def lead_picker(df, key):
    labels = {int(r.id): f"{r.company} ({r.stage})" for r in df.itertuples()}
    return st.selectbox("Lead", list(labels), format_func=labels.get, key=key)


if page == "Today's queue":
    st.header("Today's action queue")
    q = db.todays_queue(con)
    c1, c2, c3 = st.columns(3)
    c1.metric("Due / overdue", len(q))
    c2.metric("Open leads", int(leads["stage"].isin(OPEN_STAGES).sum()))
    c3.metric("Stale (> %d days)" % STALE_DAYS, int((q.get("days_since_contact", pd.Series(dtype=int)) >= STALE_DAYS).sum()) if len(q) else 0)
    if q.empty:
        st.success("Nothing due. Inbox zero for follow-ups.")
    else:
        st.dataframe(q[["id", "company", "contact_name", "stage", "segment", "score", "next_followup",
                        "days_overdue", "days_since_contact"]], width="stretch", hide_index=True)
        st.subheader("Log an interaction")
        with st.form("log"):
            lid = lead_picker(q, "q_pick")
            t = st.selectbox("Type", ACTIVITY_TYPES)
            note = st.text_input("Note")
            gap = st.number_input("Next follow-up in (days)", 1, 30, 3)
            new_stage = st.selectbox("Move stage (optional)", ["(no change)"] + STAGES)
            reason = st.selectbox("If Lost: reason", LOST_REASONS)
            if st.form_submit_button("Save"):
                db.log_activity(con, lid, t, note, gap)
                if new_stage != "(no change)":
                    db.move_stage(con, lid, new_stage, reason)
                st.rerun()

elif page == "Pipeline":
    st.header("Pipeline board")
    cols = st.columns(len(OPEN_STAGES))
    for col, stage in zip(cols, OPEN_STAGES):
        sub = leads[leads["stage"] == stage]
        col.subheader(f"{stage} ({len(sub)})")
        for r in sub.sort_values("score", ascending=False).head(15).itertuples():
            col.caption(f"**{r.company}**  \n{r.segment or ''} · score {'' if pd.isna(r.score) else int(r.score)}")
    st.divider()
    won, lost = (leads["stage"] == "Won").sum(), (leads["stage"] == "Lost").sum()
    st.write(f"Won: **{won}** · Lost: **{lost}**")
    if len(leads):
        st.subheader("Update a lead")
        with st.form("move"):
            lid = lead_picker(leads, "m_pick")
            ns = st.selectbox("New stage", STAGES)
            reason = st.selectbox("If Lost: reason", LOST_REASONS)
            val = st.number_input("Deal value (INR)", 0, 100000000, 0, 5000)
            nf = st.date_input("Next follow-up", date.today() + timedelta(days=3))
            if st.form_submit_button("Update"):
                db.move_stage(con, lid, ns, reason)
                db.update_fields(con, lid, deal_value=val)
                if ns in OPEN_STAGES:
                    db.set_followup(con, lid, nf.isoformat())
                st.rerun()

elif page == "Add / import leads":
    st.header("Add or import leads")
    with st.form("add"):
        c1, c2 = st.columns(2)
        company = c1.text_input("Company *")
        contact = c2.text_input("Contact name")
        role = c1.text_input("Role")
        email = c2.text_input("Email")
        seg = c1.selectbox("Segment", ["", "Automation", "Mobile App", "MVP / Product Build", "SaaS / Platform"])
        src = c2.text_input("Source")
        val = st.number_input("Estimated deal value (INR)", 0, 100000000, 0, 5000)
        if st.form_submit_button("Add lead") and company.strip():
            db.add_lead(con, company.strip(), contact, role, email, "", src, seg, None, val)
            st.success("Added")
            st.rerun()
    st.subheader("Import CSV (e.g. leads_scored.csv from the Lead Engine)")
    f = st.file_uploader("CSV with at least a 'company' column", type="csv")
    if f is not None:
        n = db.import_scored_csv(con, pd.read_csv(f))
        st.success(f"Imported {n} new leads")

else:
    st.header("Conversion analytics")
    hist, acts = db.history_df(con), db.activities_df(con)
    if leads.empty:
        st.info("No data yet. Add leads or load the synthetic demo data from the sidebar.")
        st.stop()
    conv = A.reached_counts(leads, hist)
    fc = A.weighted_forecast(leads)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total leads", len(leads))
    k2.metric("Open pipeline (INR)", f"{fc['open_pipeline_value']:,.0f}")
    k3.metric("Weighted forecast (INR)", f"{fc['weighted_forecast']:,.0f}")
    k4.metric("Won value (INR)", f"{fc['won_value']:,.0f}")

    fig = px.funnel(conv, x="reached", y="stage", title="Funnel: leads that reached each stage")
    st.plotly_chart(fig, width="stretch")
    st.dataframe(conv, width="stretch", hide_index=True)
    w = A.weakest_stage(conv)
    if w:
        st.warning(f"Weakest step: **{w['stage']}** ({w['conv_from_prev']:.0%} conversion from the previous stage). Fix this first.")

    c1, c2 = st.columns(2)
    d = A.avg_days_in_stage(hist)
    c1.subheader("Average days in stage")
    if len(d):
        c1.plotly_chart(px.bar(d, x="stage", y="avg_days"), width="stretch")
    lr = A.lost_reasons(leads)
    c2.subheader("Why deals are lost")
    if len(lr):
        c2.plotly_chart(px.bar(lr, x="reason", y="count"), width="stretch")

    st.subheader("Weekly activity")
    wa = A.weekly_activity(acts)
    if len(wa):
        st.plotly_chart(px.bar(wa, x="week", y="count", color="type"), width="stretch")
    st.subheader("Win rate by segment")
    st.dataframe(A.segment_win_rate(leads), width="stretch", hide_index=True)
