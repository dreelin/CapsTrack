import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import requests
import time
import pytz

st.set_page_config(page_title="Caps Bet Tracker", layout="wide")

st.markdown("""
<script>
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.jump-to-user-breakdown').forEach(a => {
    a.addEventListener('click', e => {
      e.preventDefault();
      const target = document.getElementById('user-breakdown');
      if (target) target.scrollIntoView({ behavior: 'smooth' });
    });
  });
});
</script>
""", unsafe_allow_html=True)

# -----------------------------
# Configuration
# -----------------------------
PASSWORD = st.secrets["password"]
TEAM_ID = 23  # Washington Capitals ESPN ID
EASTERN = pytz.timezone("US/Eastern")
USERS = {
    "Alex": 10,   # units
    "Ben": 8,
    "Chris": 12,
}

DATA_FILE = "bets.csv"

# -----------------------------
# Load/Save Data
# -----------------------------
def load_data():
    try:
        df = pd.read_csv(DATA_FILE)
    except FileNotFoundError:
        df = pd.DataFrame(columns=["date", "game", "home_team", "away_team",
                                   "legs", "odds", "amount", "result"])
    return df

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

bets = load_data()

# -----------------------------
# ESPN Schedule
# -----------------------------
def fetch_espn_schedule(team_id):
    url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/teams/{team_id}/schedule"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        events = resp.json().get("events", [])
        games = []
        for g in events:
            comp = g.get("competitions", [{}])[0]
            home = comp.get("competitors", [{}])[0]
            away = comp.get("competitors", [{}])[1]
            dt = datetime.fromisoformat(comp.get("date").replace("Z", "+00:00")).astimezone(EASTERN)
            games.append({
                "id": g.get("id"),
                "home_team": home.get("team", {}).get("displayName", ""),
                "away_team": away.get("team", {}).get("displayName", ""),
                "home_score": home.get("score", ""),
                "away_score": away.get("score", ""),
                "status_type": comp.get("status", {}).get("type", {}).get("name", "").lower(),
                "date_obj": dt,
                "date_str": dt.strftime("%-m/%-d %-I:%M %p ET"),
                "gamecast_url": next((l["href"] for l in g.get("links", [])
                                      if l.get("text") == "Gamecast" and "desktop" in l.get("rel", [])), "#"),
            })
        return games
    except Exception as e:
        st.error(f"Failed to fetch ESPN schedule: {e}")
        return []

# -----------------------------
# Scoreboard
# -----------------------------
games = fetch_espn_schedule(TEAM_ID)
past_games = [g for g in games if g["status_type"] == "completed"]
future_games = [g for g in games if g["status_type"] != "completed"]
cards = past_games[-2:] + future_games[:3]
if len(cards) < 5:
    needed = 5 - len(cards)
    cards += future_games[3:3+needed]

cols = st.columns(5)
for i, game in enumerate(cards[:5]):
    g = game
    # Background color for past games
    if g["status_type"] == "completed":
        caps_won = ((g["home_team"] == "Washington Capitals" and int(g["home_score"]) > int(g["away_score"])) or
                    (g["away_team"] == "Washington Capitals" and int(g["away_score"]) > int(g["home_score"])))
        bg_color = "#d4f4dd" if caps_won else "#f8d3d3"
        result_text = "W" if caps_won else "L"
    else:
        bg_color = "#ffffff"
        result_text = ""
    html = f"""
    <a href="{g['gamecast_url']}" target="_blank" style="text-decoration:none;color:inherit;">
    <div style="
        border-radius:10px;
        border:1px solid #ccc;
        padding:10px;
        margin:5px;
        width:250px;
        background-color:{bg_color};
        color:black;
        box-shadow:2px 2px 5px rgba(0,0,0,0.1);
    ">
        <strong>{g['date_str']} {result_text}</strong><br>
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <span>{g['away_team']}</span>
            <span>{g['away_score']}</span>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <span>{g['home_team']}</span>
            <span>{g['home_score']}</span>
        </div>
    </div>
    </a>
    """
    cols[i].markdown(html, unsafe_allow_html=True)

# -----------------------------
# Add Bet Form (working with Streamlit forms)
# -----------------------------
# Make sure session state for legs exists
if "legs_inputs" not in st.session_state:
    st.session_state.legs_inputs = ["Capitals Moneyline", "A. Ovechkin 1+ Goal"]

# Determine upcoming games for dropdown
def format_game_dropdown(games):
    options = []
    for g in games:
        try:
            comp = g["competitions"][0]
            home = comp["competitors"][0]["team"]["displayName"]
            away = comp["competitors"][1]["team"]["displayName"]
            dt = datetime.fromisoformat(comp["date"].replace("Z", "+00:00")).astimezone(EASTERN)
            options.append(f"{dt.strftime('%-m/%-d')} {away} vs {home}||{g['id']}")
        except Exception:
            continue
    options.append("Manual")
    return options

game_options = format_game_dropdown(cards)  # cards = 5 games from scoreboard
closest_upcoming_index = 2 if len(past_games) >= 2 else len(past_games)
default_game = game_options[closest_upcoming_index]

with st.expander("➕ Add New Bet", expanded=True):
    with st.form("new_bet"):
        # Game selection
        selected_game = st.selectbox("Game", options=game_options, index=game_options.index(default_game))
        manual = selected_game == "Manual"

        # Manual inputs if manual selected
        if manual:
            date = st.date_input("Date", datetime.today())
            game_text = st.text_input("Game (e.g. Caps vs Rangers)")
        else:
            date = None
            game_text = selected_game.split("||")[0]  # store the display text
            game_id = selected_game.split("||")[1]   # store the ESPN game ID

        # Dynamic legs
        new_legs = []
        for idx, val in enumerate(st.session_state.legs_inputs):
            new_val = st.text_input(f"Leg {idx+1}", value=val, key=f"leg_{idx}")
            new_legs.append(new_val)

        # Option to add a new leg
        add_leg = st.checkbox("Add another leg")
        if add_leg:
            new_legs.append("")
        st.session_state.legs_inputs = new_legs  # save back to session state

        # Odds and amount
        odds = st.number_input("Odds (American)", value=-110)
        amount = st.number_input("Amount ($)", value=69.0)

        # Result
        result = st.selectbox("Result", ["pending", "win", "loss"])

        # Password check
        pw = st.text_input("Password to save bet", type="password")

        # Submit
        submit = st.form_submit_button("Save Bet")
        if submit:
            if pw != PASSWORD:
                st.error("Incorrect password, bet not saved.")
            else:
                new_row = {
                    "date": date if manual else "",  # only manual
                    "game": game_text,
                    "game_id": game_id if not manual else "",
                    "legs": new_legs,
                    "odds": odds,
                    "amount": amount,
                    "result": result
                }
                bets = pd.concat([bets, pd.DataFrame([new_row])], ignore_index=True)
                save_data(bets)
                st.success("Bet saved!")
                # reset legs to default
                st.session_state.legs_inputs = ["Capitals Moneyline", "A. Ovechkin 1+ Goal"]



# -----------------------------
# Summary Stats
# -----------------------------
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

user_summary = []
for user, units in USERS.items():
    user_amount = total_profit / 10 * units
    user_summary.append((user, units, user_amount))

import streamlit as st

# --- Example summary values ---
wins = len(bets[bets["result"] == "win"])
losses = len(bets[bets["result"] == "loss"])
total_profit = bets["profit"].sum()

# USERS dict: username -> units
USERS = {
    "Atodd": 1,
    "Dree": 2,
    "Casey": 3,
    "Kyle": 1,
    "Nick": 1,
    "Ross": 1,
    "Saucy": 1
}

# --- Compute user summary ---
user_summary = []
for user, units in USERS.items():
    user_amount = total_profit / 10 * units
    user_summary.append((user, units, user_amount))

import streamlit as st

# -------------------
# Example summary data
# -------------------
wins = len(bets[bets["result"] == "win"])
losses = len(bets[bets["result"] == "loss"])
total_profit = bets["profit"].sum()
USERS = {"Alice": 3, "Bob": 2, "Charlie": 5}

# Compute user summary
user_summary = []
for user, units in USERS.items():
    user_amount = total_profit / 10 * units
    user_summary.append((user, units, user_amount))

# -------------------
# Session state for toggling details
# -------------------
if "show_details" not in st.session_state:
    st.session_state.show_details = False

import streamlit as st

# -------------------
# summary data
# -------------------
wins = len(bets[bets["result"] == "win"])
losses = len(bets[bets["result"] == "loss"])
total_profit = bets["profit"].sum()
USERS = {"Alice": 3, "Bob": 2, "Charlie": 5}

# Compute user summary
user_summary = []
for user, units in USERS.items():
    user_amount = total_profit / 10 * units
    user_summary.append((user, units, user_amount))

# -------------------
# Session state for toggling details
# -------------------
if "show_details" not in st.session_state:
    st.session_state.show_details = False

# -------------------
# Summary header row (H2, colored text)
# -------------------
header_color = "green" if total_profit >= 0 else "red"

col1, col2, col3 = st.columns([2,1,2])

# Left: Skeet Summary
col1.markdown(f"<h2 style='color:{header_color}; text-align:center;'>Skeet Summary</h2>", unsafe_allow_html=True)

# Middle: W-L
col2.markdown(f"<h2 style='color:{header_color}; text-align:center;'>{wins}-{losses}</h2>", unsafe_allow_html=True)

col3.markdown(f"<h2 style='color:{header_color}; text-align:center;'>"
              f"<a class='jump-to-user-breakdown' href='#user-breakdown' style='color:{header_color}; text-decoration:none;'>${total_profit:.2f}</a>"
              "</h2>", unsafe_allow_html=True)

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
# Bet History
# -----------------------------
st.subheader("📜 Bet History")
st.dataframe(bets.sort_values("date", ascending=False), use_container_width=True)

st.markdown("<div id='user-breakdown'></div>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

for name, units, user_amount in user_summary:
    color = "green" if user_amount >= 0 else "red"
    st.markdown(
        f"<div style='text-align:center'><span>{name} ({units} units): </span>"
        f"<span style='color:{color}'>${user_amount:.2f}</span></div>",
        unsafe_allow_html=True
    )
