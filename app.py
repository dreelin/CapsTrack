import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import requests
import time
import pytz
from streamlit_cookies_manager import EncryptedCookieManager
import ast


st.set_page_config(page_title="Caps Bet Tracker", layout="wide", initial_sidebar_state="collapsed")

hide_streamlit_style = """
    <style>
    /* Hide hamburger menu */
    #MainMenu {visibility: hidden;}
    /* Hide footer */
    footer {visibility: hidden;}
    /* Optional: hide header bar */
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.markdown("""
    <style>
    .css-18e3th9 {padding-top: 0rem;}   /* Main container top padding */
    .css-1d391kg {padding-top: 0rem;}   /* Older versions may need this */
    </style>
""", unsafe_allow_html=True)


st.markdown("""
<style>
/* Collapse only top-level st-emotion-cache elements that are empty or contain just style blocks */
[class^="st-emotion-cache-"] > :empty {
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: hidden !important;
}

/* Remove main container top padding */
.css-18e3th9 {padding-top: 0rem !important;}
.css-1d391kg {padding-top: 0rem !important;}

/* Hide Streamlit default menu, header, footer */
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


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
COOKIE_SECRET = st.secrets["cookie_secret"]

TEAM_ID = 23  # Washington Capitals ESPN ID
EASTERN = pytz.timezone("US/Eastern")
USERS = {
    "Atodd": 1,
    "Dree": 2,
    "Casey": 3,
    "Kyle": 1,
    "Nick": 1,
    "Ross": 1,
    "Saucy": 1
}

DATA_FILE = "bets.csv"

cookies = EncryptedCookieManager(
    prefix="capstrack_",
    password=st.secrets.get("cookie_secret", COOKIE_SECRET)
)

if not cookies.ready():
    st.stop()

# -----------------------------
# Load/Save Data
# -----------------------------
def load_data():
    try:
        df = pd.read_csv(DATA_FILE)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
    except FileNotFoundError:
        df = pd.DataFrame(columns=["date", "game", "home_team", "away_team",
                                   "legs", "odds", "amount", "result", "profit"])
    return df


def save_data(df):
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df.to_csv(DATA_FILE, index=False)

bets = load_data()

if "auth" not in st.session_state:
    st.session_state.auth = cookies.get("auth") == "ok"

if not st.session_state.auth:
    pw = st.text_input("Password", type="password")
    if pw == PASSWORD:
        st.session_state.auth = True
        cookies["auth"] = "ok"
        cookies.save()
        st.success("Authenticated! Reloading...")
        st.rerun()
    st.stop()

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





# -------------------
# summary data
# -------------------
wins = len(bets[bets["result"] == "win"])
losses = len(bets[bets["result"] == "loss"])
total_profit = bets["profit"].sum()


# Compute user summary
user_summary = []
for user, units in USERS.items():
    user_amount = total_profit / 10 * units
    user_summary.append((user, units, user_amount))


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
st.subheader("Profit Chart")

if not bets.empty:
    # Drop bets without a date
    bets_sorted = bets.dropna(subset=["date"]).copy()

    # Ensure 'date' is datetime
    bets_sorted["date"] = pd.to_datetime(bets_sorted["date"])

    # Group by date (ignore time) and sum profit per day
    daily_profit = bets_sorted.groupby(bets_sorted["date"].dt.date)["profit"].sum().reset_index()

    # Compute cumulative profit
    daily_profit["cumulative_profit"] = daily_profit["profit"].cumsum()

    # Format date as mm/dd for x-axis
    daily_profit["date_str"] = daily_profit["date"].apply(lambda d: d.strftime("%m/%d"))

    # Plot
    st.line_chart(daily_profit.set_index("date_str")["cumulative_profit"])
else:
    st.info("No bets yet — add some to see the bankroll chart!")


# -----------------------------
# Add Bet Form (fixed)
# -----------------------------
if "legs_inputs" not in st.session_state:
    st.session_state.legs_inputs = ["Capitals Moneyline", "A. Ovechkin 1+ Goal"]

# Determine upcoming games for dropdown
def format_game_dropdown(games):
    options = []
    for g in games:
        options.append(f"{g['date_str']} {g['away_team']} vs {g['home_team']}")
    options.append("Manual")
    return options

game_options = format_game_dropdown(cards)
closest_upcoming_index = 2 if len(past_games) >= 2 else len(past_games)
default_game = game_options[closest_upcoming_index]

with st.expander("Add Bet", expanded=False):
    with st.form("new_bet"):
        # ---------------------
        # Determine default game properly
        # ---------------------
        upcoming_games = [g for g in cards if g["status_type"] != "completed"]
        if upcoming_games:
            nearest_game = upcoming_games[0]
            nearest_game_text = f"{nearest_game['date_str']} {nearest_game['away_team']} vs {nearest_game['home_team']}"
        else:
            nearest_game_text = "Manual"

        # Format dropdown options (without showing ID)
        game_options = [f"{g['date_str']} {g['away_team']} vs {g['home_team']}" for g in cards] + ["Manual"]

        # ---------------------
        # Columns: Dropdown first
        # ---------------------
        col_game, col_date, col_name = st.columns([2,1,2])
        with col_game:
            selected_game = st.selectbox("Game", options=game_options, index=game_options.index(nearest_game_text))
        manual = selected_game == "Manual"

        with col_date:
            manual_date = st.date_input("Date", datetime.today())
        with col_name:
            manual_name = st.text_input("Game Name", "")

        # ---------------------
        # Odds / Amount / Result
        # ---------------------
        col_odds, col_amount, col_result = st.columns([1,1,1])
        with col_odds:
            odds = st.number_input("Odds (American)", value=-110)
        with col_amount:
            amount = st.number_input("Amount ($)", value=69.0)
        with col_result:
            result = st.selectbox("Result", ["pending", "win", "loss"])



        # ---------------------
        # Legs
        # ---------------------
        legs_text = st.text_area("Legs (one per line)", value="Capitals Moneyline\nA. Ovechkin 1+ Goal", height=100)

        # ---------------------
        # Submit
        # ---------------------
        submit = st.form_submit_button("Save Bet")
        if submit:
            if not st.session_state.get("auth"):
                st.error("You are not authorized to save bets. Please log in first.")
            else:
                # Determine game data
                if manual:
                    if not manual_name or not manual_date:
                        st.error("Manual game requires both Date and Game Name")
                        st.stop()
                    game_text = manual_name
                    game_date = manual_date
                    game_id = ""
                else:
                    # Find selected game in cards
                    game_data = next((g for g in cards
                                      if f"{g['date_str']} {g['away_team']} vs {g['home_team']}" == selected_game), None)
                    if not game_data:
                        st.error("Selected game not found")
                        st.stop()
                    game_text = f"{game_data['away_team']} vs {game_data['home_team']}"
                    game_date = game_data["date_obj"].date()
                    game_id = game_data["id"]

                # Process legs
                legs_list = [l.strip() for l in legs_text.split("\n") if l.strip()]

                profit = 0
                if result == "win":
                    profit = amount * (100 / abs(odds)) if odds < 0 else amount * (odds / 100)
                elif result == "loss":
                    profit = -amount

                # Save
                new_row = {
                    "date": game_date,
                    "game": game_text,
                    "game_id": game_id,
                    "legs": legs_list,
                    "odds": odds,
                    "amount": amount,
                    "result": result,
                    "profit": profit

                }
                bets = pd.concat([bets, pd.DataFrame([new_row])], ignore_index=True)
                save_data(bets)
                st.success("Bet saved!")

# -----------------------------
# Bet History
# -----------------------------
st.subheader("Bet History")

def parse_legs(x):
    if isinstance(x, list):
        return x
    try:
        # Try to parse string representation of list
        parsed = ast.literal_eval(x)
        if isinstance(parsed, list):
            return parsed
        return [str(parsed)]
    except Exception:
        # Fallback: split by comma
        return [s.strip() for s in str(x).split(",")]

bets_display = bets.copy()
bets_display["legs"] = bets_display["legs"].apply(parse_legs)

# Format date and profit
bets_display["date_str"] = bets_display["date"].apply(lambda d: d.strftime("%m/%d/%Y") if pd.notnull(d) else "")
bets_display["profit_str"] = bets_display["profit"].apply(lambda p: f"${p:.2f}")

# Header row
header_cols = st.columns([1, 3, 3, 1, 1, 1, 1, 1])
header_titles = ["Date", "Game", "Legs", "Odds", "Amount", "Result", "Profit", "Settle Bet"]
for col, title in zip(header_cols, header_titles):
    col.markdown(f"**{title}**", unsafe_allow_html=True)

# Build table manually
for i, row in bets_display.sort_values("date", ascending=False).iterrows():
    cols = st.columns([1, 3, 3, 1, 1, 1, 1, 1])  # Adjust widths
    
    # Date
    cols[0].markdown(row["date_str"])
    
    # Game
    cols[1].markdown(row["game"])
    
    # Legs as pills (colored for readability)
    legs_html = ""
    for l in row["legs"]:
        legs_html += f"<span style='display:inline-block; padding:2px 8px; border-radius:12px; background:#2563eb; color:white; margin:2px; font-size:12px'>{l}</span>"
    cols[2].markdown(legs_html, unsafe_allow_html=True)
    
    # Odds, amount, result, profit
    cols[3].markdown(row["odds"])
    cols[4].markdown(row["amount"])
    cols[5].markdown(row["result"])
    color = "green" if row["profit"] > 0 else "red" if row["profit"] < 0 else "gray"
    cols[6].markdown(f"<span style='color:{color}'>{row["profit_str"]}</span>", unsafe_allow_html=True)
    
    # Settle Bet buttons
    if row["result"] == "pending" and st.session_state.auth:
        settle_col = cols[7]
        btn_cols = settle_col.columns([1,1,1])
        
        # Win button
        if btn_cols[0].button("W", key=f"win_{i}"):
            bets.at[i, "result"] = "win"
            profit = bets.at[i, "amount"] * (100 / abs(bets.at[i, "odds"])) if bets.at[i, "odds"] < 0 else bets.at[i, "amount"] * (bets.at[i, "odds"] / 100)
            bets.at[i, "profit"] = round(profit,2)
            save_data(bets)
            st.rerun()

        # Loss button
        if btn_cols[1].button("L", key=f"loss_{i}"):
            bets.at[i, "result"] = "loss"
            bets.at[i, "profit"] = -bets.at[i, "amount"]
            save_data(bets)
            st.rerun()
        
        # Void button
        if btn_cols[2].button("V", key=f"void_{i}"):
            bets.at[i, "result"] = "void"
            bets.at[i, "profit"] = 0
            save_data(bets)
            st.rerun()

st.markdown("<div id='user-breakdown'></div>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

for name, units, user_amount in user_summary:
    color = "green" if user_amount >= 0 else "red"
    st.markdown(
        f"<div style='text-align:center'><span>{name} ({units} units): </span>"
        f"<span style='color:{color}'>${user_amount:.2f}</span></div>",
        unsafe_allow_html=True
    ) 
