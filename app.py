import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import requests
import time
import pytz

st.set_page_config(page_title="Caps Bet Tracker", layout="wide")

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

        # Convert date to ET and format
        dt_utc = datetime.fromisoformat(comp.get("date", game.get("date")).replace("Z", "+00:00"))
        dt_et = dt_utc.astimezone(EASTERN)
        dt_str = dt_et.strftime("%-m/%-d %-I:%M %p ET")

        # Gamecast link
        gamecast_url = "#"
        for link in game.get("links", []):
            if link.get("text") == "Gamecast" and "desktop" in link.get("rel", []):
                gamecast_url = link["href"]
                break

        # Capitals logo fixed
        caps_logo = "https://a.espncdn.com/guid/cbe677ee-361e-91b4-5cae-6c4c30044743/logos/secondary_logo_on_primary_color.png"

        # Other team logo (away or home)
        def get_team_logo(team):
            if team["team"]["displayName"] == "Washington Capitals":
                return caps_logo
            logos = team["team"].get("logos", [])
            if logos:
                return logos[0].get("href", "")
            return ""  # fallback

        home_logo = get_team_logo(home)
        away_logo = get_team_logo(away)

        # HTML with logos on left side
        html = f"""
        <a href="{gamecast_url}" target="_blank" style="text-decoration:none;color:inherit;">
        <div style="
            border-radius:10px;
            border:1px solid #ccc;
            padding:10px;
            margin:5px;
            width:250px;
            background-color:{bg_color};
            color:black;
            box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
        ">
            <strong>{dt_str} {result_text}</strong><br>
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div style='display:flex; align-items:center;'>
                    <img src='{away_logo}' alt='' width='24' height='24' style='margin-right:5px;'/>
                    <span>{away_team}</span>
                </div>
                <span>{away_score}</span>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div style='display:flex; align-items:center;'>
                    <img src='{home_logo}' alt='' width='24' height='24' style='margin-right:5px;'/>
                    <span>{home_team}</span>
                </div>
                <span>{home_score}</span>
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

# -------------------
# Summary header row (H2, colored text)
# -------------------
header_color = "green" if total_profit >= 0 else "red"

col1, col2, col3 = st.columns([2,1,2])

# Left: Skeet Summary
col1.markdown(f"<h2 style='color:{header_color}; text-align:center;'>Skeet Summary</h2>", unsafe_allow_html=True)

# Middle: W-L
col2.markdown(f"<h2 style='color:{header_color}; text-align:center;'>{wins}-{losses}</h2>", unsafe_allow_html=True)

# Right: Amount acts as toggle (styled clickable amount text, no navigation)
with col3:
    # Wrapper div to scope styles
    st.markdown("<div class='amount-block'>", unsafe_allow_html=True)
    if st.button(f"${total_profit:.2f}", key="amount_toggle"):
        st.session_state.show_details = not st.session_state.get("show_details", False)
    st.markdown("</div>", unsafe_allow_html=True)
    # Scoped CSS so only this button looks like plain heading text
    st.markdown(f"""
    <style>
    .amount-block button {{
        all: unset !important; /* strip all default styles */
        color:{header_color} !important;
        font-size:2rem !important;
        font-weight:700 !important;
        line-height:1 !important;
        cursor:pointer !important;
        display:inline-block !important;
        padding:0 !important;
        margin:0 !important;
    }}
    .amount-block button:focus {{outline:none !important;}}
    .amount-block button:hover {{text-decoration:underline;}}
    /* Remove any container styling Streamlit might add */
    .amount-block button div, .amount-block button span {{all: unset !important;}}
    </style>
    <div style='font-size:10px; margin-top:2px; color:#888;'>(click amount for details)</div>
    """, unsafe_allow_html=True)

# -------------------
# User breakdown (conditional)
# -------------------
if st.session_state.show_details:
    st.write("")  # spacing
    st.markdown("<hr>", unsafe_allow_html=True)

    for name, units, user_amount in user_summary:
        color = "green" if user_amount >= 0 else "red"
        st.markdown(
            f"<div style='text-align:center'><span>{name} ({units} units): </span>"
            f"<span style='color:{color}'>${user_amount:.2f}</span></div>",
            unsafe_allow_html=True
        )

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
