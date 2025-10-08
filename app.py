import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import requests
import time

st.set_page_config(page_title="Caps Bet Tracker", layout="wide")
st.title("🏒 Caps Bet Tracker")

# -----------------------------
# Configuration
# -----------------------------
PASSWORD = st.secrets["password"]
TEAM_ID = 3691  # Washington Capitals Sofascore ID
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

def fetch_games(url, retries=3, backoff=2):
    """
    Fetch games from SofaScore with retry and User-Agent.
    
    Args:
        url (str): API endpoint
        retries (int): number of retries on failure
        backoff (int): seconds to wait between retries, multiplied each retry

    Returns:
        list: list of game events (empty if failed)
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/117.0.0.0 Safari/537.36"
        )
    }

    attempt = 0
    while attempt < retries:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("events", [])
            else:
                st.warning(f"SofaScore API returned {resp.status_code} on attempt {attempt + 1}")
        except requests.RequestException as e:
            st.warning(f"SofaScore request failed on attempt {attempt + 1}: {e}")
        
        attempt += 1
        time.sleep(backoff * attempt)  # exponential backoff

    st.error("Failed to fetch games from SofaScore after multiple attempts.")
    return []

def format_game_tile(game, is_past=True):
    start_dt = datetime.fromtimestamp(game["startTimestamp"])
    away_team = game["awayTeam"]["name"]
    home_team = game["homeTeam"]["name"]
    
    away_score = game.get("awayScore", {}).get("current", "")
    home_score = game.get("homeScore", {}).get("current", "")

    # Determine result & background color
    result_text = ""
    bg_color = "#ffffff"  # default white

    if is_past:
        winner_code = game.get("winnerCode")
        status_code = game.get("status", {}).get("code", 100)
        ot_text = " OT" if status_code != 100 else ""

        # Capitals W/L
        if (winner_code == 1 and home_team == "Capitals") or (winner_code == 2 and away_team == "Capitals"):
            result_text = f"W{ot_text}"
            bg_color = "#d4f4dd"  # light green
        else:
            result_text = f"L{ot_text}"
            bg_color = "#f8d3d3"  # light red

    # Build HTML card
    html = f"""
    <div style="
        border-radius:10px;
        border:1px solid #ccc;
        padding:10px;
        margin:5px;
        width:250px;
        background-color:{bg_color};
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    ">
        <strong>{start_dt.strftime('%Y-%m-%d %H:%M')} {result_text}</strong><br>
        <div style="display:flex; justify-content:space-between;">
            <span>{away_team}</span><span>{away_score}</span>
        </div>
        <div style="display:flex; justify-content:space-between;">
            <span>{home_team}</span><span>{home_score}</span>
        </div>
    </div>
    """
    return html

# Fetch recent and upcoming games
recent_games = fetch_games(f"https://www.sofascore.com/api/v1/team/{TEAM_ID}/events/last/0")[:2]
upcoming_games = fetch_games(f"https://www.sofascore.com/api/v1/team/{TEAM_ID}/events/next/0")[:3]

st.subheader("🏒 Caps Games")
cols = st.columns(5)  # 2 recent + 3 upcoming = 5 cards

for i, game in enumerate(recent_games + upcoming_games):
    is_past = i < len(recent_games)
    html_card = format_game_tile(game, is_past)
    cols[i].markdown(html_card, unsafe_allow_html=True)



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
