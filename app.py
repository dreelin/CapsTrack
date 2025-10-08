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
TEAM_ID = 23  # Washington Capitals ESPN ID
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
# Scoreboard
# -----------------------------

def fetch_espn_schedule(team_id):
    url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/teams/{team_id}/schedule"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json().get("events", [])
    except requests.RequestException as e:
        st.error(f"Failed to fetch ESPN schedule: {e}")
        return []

def get_status_name(game):
    """Return status type name lowercase from competitions[0], safely."""
    try:
        return game["competitions"][0]["status"]["type"]["name"].lower()
    except (KeyError, IndexError):
        return ""

def build_game_card(game):
    try:
        comp = game["competitions"][0]
        home = comp["competitors"][0]
        away = comp["competitors"][1]

        home_team = home["team"]["displayName"]
        away_team = away["team"]["displayName"]

        home_score = home.get("score") or ""
        away_score = away.get("score") or ""

        # Status
        status_type = comp["status"]["type"]["name"].lower()
        status_id = comp["status"]["type"].get("id", 0)
        is_past = status_type == "completed"

        # Background and result
        if is_past:
            capitals_won = (
                (home_team == "Washington Capitals" and int(home_score) > int(away_score)) or
                (away_team == "Washington Capitals" and int(away_score) > int(home_score))
            )
            result_text = "W" if capitals_won else "L"
            if status_id != 1:  # id != 1 → OT
                result_text += " OT"
            bg_color = "#d4f4dd" if capitals_won else "#f8d3d3"
        else:
            result_text = ""
            bg_color = "#ffffff"

        start_dt = datetime.fromisoformat(comp.get("date", game.get("date")).replace("Z", "+00:00"))

        # Gamecast link
        gamecast_url = next(
            (link["href"] for link in game.get("links", []) if "gamecast" in link.get("rel", [])),
            "#"
        )

        html = f"""
        <a href="{gamecast_url}" target="_blank" style="text-decoration:none;color:inherit;">
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
        </a>
        """
        return html
    except Exception as e:
        st.warning(f"Error building game card: {e}")
        return "<div>Invalid game data</div>"

# Fetch schedule
games = fetch_espn_schedule(TEAM_ID)

# Split past/future
past_games = [g for g in games if get_status_name(g) == "completed"]
future_games = [g for g in games if get_status_name(g) != "completed"]

# Determine 5 cards
cards = past_games[-2:] + future_games[:3]
if len(cards) < 5:
    needed = 5 - len(cards)
    cards += future_games[3:3+needed]

st.subheader("🏒 Caps Games")
cols = st.columns(5)
for i, game in enumerate(cards[:5]):
    html_card = build_game_card(game)
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
