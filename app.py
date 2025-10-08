import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import requests

st.set_page_config(page_title="Caps Bet Tracker", layout="wide")
st.title("🏒 Caps Bet Tracker")

# -----------------------------
# Configuration
# -----------------------------
PASSWORD = "secret123"
USERS = {
    "Alex": 10,   # units
    "Ben": 8,
    "Chris": 12,
}

DATA_FILE = "bets.csv"

# -----------------------------
# Load data
# -----------------------------
def load_data():
    try:
        df = pd.read_csv(DATA_FILE)
    except FileNotFoundError:
        df = pd.DataFrame(columns=["date", "game", "legs", "odds", "amount", "result"])
    return df

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

bets = load_data()

# -----------------------------
# Password Gate for Editing
# -----------------------------
if "auth" not in st.session_state:
    st.session_state["auth"] = False

if not st.session_state["auth"]:
    pw = st.text_input("Enter password to enable editing", type="password")
    if pw == PASSWORD:
        st.session_state["auth"] = True
        st.experimental_rerun()

# -----------------------------
# Add Bet Form
# -----------------------------
if st.session_state["auth"]:
    with st.expander("➕ Add New Bet"):
        with st.form("new_bet"):
            date = st.date_input("Date", datetime.today())
            game = st.text_input("Game (e.g. Caps vs Rangers)")
            legs = st.text_area("Legs (e.g. Caps ML, Ovechkin to score)")
            odds = st.number_input("Odds (American)", value=-110)
            amount = st.number_input("Amount ($)", value=10.0)
            result = st.selectbox("Result", ["pending", "win", "loss"])
            submit = st.form_submit_button("Save Bet")
            if submit:
                new_row = {
                    "date": date,
                    "game": game,
                    "legs": legs,
                    "odds": odds,
                    "amount": amount,
                    "result": result,
                }
                bets = pd.concat([bets, pd.DataFrame([new_row])], ignore_index=True)
                save_data(bets)
                st.success("Bet saved!")

# -----------------------------
# Summary Stats
# -----------------------------
st.subheader("📊 Summary")

total_bets = len(bets)
wins = len(bets[bets["result"] == "win"])
losses = len(bets[bets["result"] == "loss"])

# Calculate profit/loss
def calc_profit(row):
    if row["result"] == "win":
        if row["odds"] > 0:
            return row["amount"] * (row["odds"] / 100)
        else:
            return row["amount"] * (100 / abs(row["odds"]))
    elif row["result"] == "loss":
        return -row["amount"]
    return 0

bets["profit"] = bets.apply(calc_profit, axis=1)
total_profit = bets["profit"].sum()

summary_df = pd.DataFrame({
    "Metric": ["Total Bets", "Record (W-L)", "Total Profit/Loss ($)"],
    "Value": [total_bets, f"{wins}-{losses}", f"${total_profit:.2f}"],
})

st.table(summary_df)

# -----------------------------
# User Breakdown (Units)
# -----------------------------
st.subheader("👥 User Performance")

unit_value = bets["amount"].mean() / 10 if not bets.empty else 1
user_data = []
for user, units in USERS.items():
    user_profit = total_profit * (units / sum(USERS.values()))
    user_data.append({"User": user, "Units": units, "Profit/Loss ($)": f"${user_profit:.2f}"})

user_df = pd.DataFrame(user_data)
st.table(user_df)

# -----------------------------
# Bankroll Chart
# -----------------------------
st.subheader("💰 Bankroll Growth")

if not bets.empty:
    bets_sorted = bets.sort_values("date")
    bets_sorted["cumulative_profit"] = bets_sorted["profit"].cumsum()
    st.line_chart(bets_sorted.set_index("date")["cumulative_profit"])
else:
    st.info("No bets yet — add some to see the bankroll chart!")

# -----------------------------
# Upcoming and Recent Games (Stub)
# -----------------------------
st.subheader("🗓️ Caps Schedule")

col1, col2 = st.columns(2)
with col1:
    st.markdown("### Upcoming Games")
    st.write("(Coming soon — Sofascore API integration)")

with col2:
    st.markdown("### Recent Games")
    st.write("(Coming soon — Sofascore API integration)")

# -----------------------------
# Bet History
# -----------------------------
st.subheader("📜 Bet History")
st.dataframe(bets.sort_values("date", ascending=False), use_container_width=True)
