# Sales Pipeline CRM & Conversion Analytics Dashboard

A lightweight CRM built with Python, SQLite and Streamlit that keeps an outbound sales pipeline organised,
enforces follow-up discipline, and shows where deals leak out of the funnel.
Built for a software-sales workflow (Business Growth Intern, Isocode) and designed to take its leads from the
companion **B2B Lead Discovery & Outreach Engine** project.

> **Status of the data:** the "Load SYNTHETIC demo data" button creates fake leads only so you can see the dashboard.
> Use your real pipeline before quoting any number on a resume.

## The problem
Spreadsheets and memory fail in outbound sales: follow-ups get forgotten, nobody knows which stage is the
bottleneck, and forecasts are guesses. This tool answers three questions every day:
1. **Who do I need to contact today?** (action queue)
2. **Where is my pipeline leaking?** (funnel conversion, time in stage, loss reasons)
3. **How much revenue is realistically coming?** (stage-weighted forecast)

## Features
| Area | What it does |
|---|---|
| Stages | Lead → Contacted → Replied → Call Booked → Proposal → Won / Lost (editable in `crm/config.py`) |
| Today's queue | Open leads due or overdue for follow-up, or stale (no contact in 7+ days), most overdue first |
| Auto follow-ups | Logging an email/call/LinkedIn/WhatsApp/meeting automatically schedules the next follow-up (default 3 days) |
| Pipeline board | Kanban-style view per open stage; update stage, deal value and next follow-up |
| Lost reasons | Mandatory-style reason picker when a deal is lost |
| Import | Upload `leads_scored.csv` from the Lead Engine (or any CSV with a `company` column) |
| Funnel analytics | Leads that reached each stage and stage-to-stage conversion (skipped stages are handled correctly) |
| Weakest-step alert | Flags the funnel step with the lowest conversion (needs 5+ leads at the previous stage) |
| Time in stage | Average days leads spend in each stage, computed from stage history |
| Forecast | Open pipeline value, probability-weighted forecast, won value |
| Activity | Weekly activity count by channel; win rate by segment |

## Quick start
```bash
pip install -r requirements.txt
streamlit run app.py
```
Then click **Load SYNTHETIC demo data** in the sidebar to explore, or add/import your real leads.
The database is a single SQLite file at `data/crm.db` (delete it to reset).

Run the tests: `python -m pytest -q`

## How the numbers are computed
- **Reached stage:** a lead counts as having reached a stage if it ever entered that stage *or any later one*.
  Conversion = reached(stage) / reached(previous stage).
- **Time in stage:** difference between consecutive stage-change timestamps; open leads use "now" for their current stage.
- **Weighted forecast:** deal value × stage probability (`STAGE_PROB` in `crm/config.py`). The defaults are assumptions:
  replace them with your own win rates once you have closed deals.
- **Queue:** open leads where `next_followup <= today` or days since last contact >= `STALE_DAYS`.

## Using it for real (before putting results on your resume)
1. Import your real prospects (from the Lead Engine's `data/leads_scored.csv`, or add them manually).
2. Log every touch the same day you do it. The queue and analytics only work if the data is honest.
3. After 3-4 weeks, open **Analytics**, find the weakest stage, change one thing (subject line, call script, offer),
   and compare conversion before and after. That before/after is your strongest resume bullet.

## Resume bullets (replace the brackets with your real numbers)
- Built a sales pipeline CRM (Python, SQLite, Streamlit) with 6 deal stages, automated follow-up scheduling and a
  daily action queue; achieved **[X]%** of follow-ups within 48 hours across **[N]** leads.
- Created a conversion analytics dashboard (funnel, time-in-stage, loss reasons, weighted forecast) that identified
  **[stage]** as the main bottleneck; revising **[message/script]** lifted conversion from **[X]%** to **[Y]%**.

## Project structure
```
app.py                 Streamlit UI (queue, pipeline, add/import, analytics)
crm/config.py          stages, probabilities, cadence, reasons
crm/db.py              SQLite layer, follow-up scheduling, queue
crm/analytics.py       funnel, time-in-stage, forecast, activity, win rate
crm/seed.py            SYNTHETIC demo data generator
tests/test_core.py     unit tests
data/                  crm.db is created here
```

## Limitations and ideas
- Single user, local SQLite. For a team, move to Postgres and add login.
- Stage probabilities are assumptions until you have real closed deals.
- Ideas: email/calendar sync, Slack or WhatsApp reminders, deal-size history, cohort analysis by source,
  logistic-regression lead scoring from won/lost outcomes, export to CSV/Google Sheets.
