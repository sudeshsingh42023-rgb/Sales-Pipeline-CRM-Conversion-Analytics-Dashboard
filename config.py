"""Edit stages, probabilities and cadence here."""
STAGES = ["Lead", "Contacted", "Replied", "Call Booked", "Proposal", "Won", "Lost"]
FUNNEL = ["Lead", "Contacted", "Replied", "Call Booked", "Proposal", "Won"]   # progression order
OPEN_STAGES = ["Lead", "Contacted", "Replied", "Call Booked", "Proposal"]
# Probability of closing, used for the weighted forecast. Adjust once you have real win data.
STAGE_PROB = {"Lead": 0.02, "Contacted": 0.05, "Replied": 0.15, "Call Booked": 0.30, "Proposal": 0.55}
FOLLOWUP_GAP_DAYS = 3          # default days until next follow-up after an activity
STALE_DAYS = 7                 # open deal with no activity this long = stale
ACTIVITY_TYPES = ["Email", "LinkedIn", "Call", "WhatsApp", "Meeting", "Note"]
LOST_REASONS = ["No response", "No budget", "Chose competitor", "Built in-house", "Bad timing", "Not a fit", "Other"]
DB_PATH = "data/crm.db"
