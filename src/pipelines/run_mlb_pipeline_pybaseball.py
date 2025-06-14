#!/usr/bin/env python3
import sys
from pathlib import Path
import logging
import json
import csv
from datetime import datetime

import requests
import pandas as pd

# ─── Optional pybaseball import for stats retrieval ──────────────────────────────
try:
    from pybaseball import batting_stats, pitching_stats, playerid_reverse_lookup
    HAS_PYBASEBALL = True
except ImportError:
    HAS_PYBASEBALL = False

# ─── Optional MLB-StatsAPI import for fallback ─────────────────────────────────
try:
    import statsapi
    HAS_STATAPI = True
except ImportError:
    HAS_STATAPI = False

# ─── Paths & Config ────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))
CONFIG_PATH = ROOT / "config.json"
with open(CONFIG_PATH) as f:
    config = json.load(f)

RAW_DATA_DIR = Path(config.get("mlb_test_output_path", "./output")).resolve()
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

# ─── Logging ───────────────────────────────────────────────────────────────────
log_file = RAW_DATA_DIR / "mlb_pipeline.log"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, mode='a', encoding='utf-8')
    ]
)
logging.info(f"Logging to console and file: {log_file}")

# ─── Season & Data Loading ─────────────────────────────────────────────────────
SEASON = datetime.now().year

if HAS_PYBASEBALL:
    logging.info(f"Loading {SEASON} pitching stats via pybaseball…")
    DF_PITCH = pitching_stats(SEASON)
    logging.debug(f"DF_PITCH shape: {DF_PITCH.shape}")
    pitch_id_cols = [c for c in DF_PITCH.columns if c.lower() in ('player_id','id','key_mlbam')]
    if pitch_id_cols:
        DF_PITCH.set_index(pitch_id_cols[0], drop=False, inplace=True)
        logging.debug(f"Indexed DF_PITCH on column: {pitch_id_cols[0]}")
    else:
        logging.warning("No MLBAM ID column found in DF_PITCH; index lookup will always fail.")
    
    logging.info(f"Loading {SEASON} batting stats via pybaseball…")
    DF_BAT = batting_stats(SEASON)
    logging.debug(f"DF_BAT shape: {DF_BAT.shape}")
    fg_id_cols = [c for c in DF_BAT.columns if c.lower() == 'idfg']
    if fg_id_cols:
        DF_BAT.set_index(fg_id_cols[0], drop=True, inplace=True)
        logging.debug(f"Indexed DF_BAT on column: {fg_id_cols[0]}")
        
        logging.info("Building MLBAM→FG crosswalk…")
        fg_ids = DF_BAT.index.unique().tolist()
        ID_MAP = playerid_reverse_lookup(player_ids=fg_ids)
        ID_MAP = ID_MAP[['key_mlbam','key_fangraphs']].dropna()
        ID_MAP.rename(columns={'key_mlbam':'mlbam_id','key_fangraphs':'fg_id'}, inplace=True)
        ID_MAP['mlbam_id'] = ID_MAP['mlbam_id'].astype(int)
        ID_MAP['fg_id']    = ID_MAP['fg_id'].astype(int)
        DF_BAT = (
            DF_BAT.reset_index()
            .merge(ID_MAP, left_on=fg_id_cols[0], right_on='fg_id', how='left')
            .set_index('mlbam_id', drop=False)
        )
        logging.debug(f"Re-indexed DF_BAT on MLBAM via crosswalk; new shape: {DF_BAT.shape}")
    else:
        logging.warning("No Fangraphs ID column found in DF_BAT; crosswalk may be empty.")
else:
    logging.warning("pybaseball not installed: skipping pybaseball data load.")
    DF_PITCH = pd.DataFrame()
    DF_BAT = pd.DataFrame()

# ─── Helper: lookup stats by player_id or Name, with detailed logging ────────────
def lookup_stats(player_id: int, player_name: str, df: pd.DataFrame) -> dict:
    pid = int(player_id)
    logging.debug(f"Looking up stats for {player_name} (ID={pid})")
    stats = {}
    attempts = {'index': False, 'name_fallback': False, 'statsapi': False}

    # pybaseball lookup
    if HAS_PYBASEBALL and not df.empty:
        try:
            row = df.loc[pid]
            attempts['index'] = True
            if isinstance(row, pd.Series):
                stats = row.dropna().to_dict()
            elif isinstance(row, pd.DataFrame) and not row.empty:
                stats = row.iloc[0].dropna().to_dict()
            if stats:
                logging.debug(f"pybaseball index lookup succeeded for {player_name} (ID={pid})")
                return stats
            else:
                logging.debug(f"pybaseball index lookup found no data for {player_name} (ID={pid})")
        except KeyError:
            logging.debug(f"pybaseball index lookup failed for {player_name} (ID={pid})")
        # Name fallback
        if 'Name' in df.columns:
            matches = df[df['Name'] == player_name]
            attempts['name_fallback'] = True
            if not matches.empty:
                stats = matches.iloc[0].dropna().to_dict()
                logging.debug(f"pybaseball name fallback lookup succeeded for {player_name} (ID={pid})")
                return stats
            else:
                logging.debug(f"pybaseball name fallback found no match for {player_name} (ID={pid})")
    else:
        logging.debug(f"Skipping pybaseball lookup for {player_name} (ID={pid})")

    # MLB-StatsAPI fallback
    if HAS_STATAPI:
        try:
            attempts['statsapi'] = True
            group = 'pitching' if df is DF_PITCH else 'hitting'
            api_data = statsapi.get('stats', {
                'stats': 'season',
                'group': group,
                'season': SEASON,
                'personIds': pid
            })
            splits = api_data.get('stats', [{}])[0].get('splits', [])
            stat = splits[0].get('stat', {}) if splits else {}
            if stat:
                logging.debug(f"MLB-StatsAPI fallback succeeded for {player_name} (ID={pid})")
                return stat
            else:
                logging.debug(f"MLB-StatsAPI fallback returned no data for {player_name} (ID={pid})")
        except Exception as e:
            logging.error(f"MLB-StatsAPI fallback failed for {player_name} (ID={pid}): {e}")
    else:
        logging.debug(f"Skipping MLB-StatsAPI fallback for {player_name} (ID={pid})")

    # Final error
    logging.error(
        f"No stats found for {player_name} (ID={pid}) after all fallbacks. Attempts: {attempts}"
    )
    return {}

# ─── Fetch schedule & boxscore ─────────────────────────────────────────────────
def fetch_mlb_schedule(date_str: str) -> list:
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}&hydrate=probablePitcher"
    r = requests.get(url); r.raise_for_status()
    dates = r.json().get("dates", [])
    return dates[0].get("games", []) if dates else []

def fetch_game_details(game: dict) -> tuple[list, list]:
    game_id = game.get("gamePk")
    if not game_id:
        return [], []
    box = requests.get(f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore")
    box.raise_for_status()
    teams_box = box.json().get("teams", {})
    pitchers, batters = [], []
    for side in ("away", "home"):
        info = game["teams"][side]
        pb = teams_box.get(side, {})
        # Probable pitcher
        prob = info.get("probablePitcher")
        if prob and (pid := prob.get("id")):
            name = prob.get("fullName")
            stats = lookup_stats(pid, name, DF_PITCH)
            pitchers.append({
                "game_id": game_id,
                "player_type": "Pitcher",
                "team": side,
                "id": pid,
                "name": name,
                "position": "P",
                "stats": stats
            })
        # First three batters
        count = 0
        for player in pb.get("players", {}).values():
            order = player.get("battingOrder")
            if not order or count >= 3:
                continue
            try:
                order = int(order)
            except ValueError:
                continue
            pid_b = player.get("person", {}).get("id")
            name_b = player.get("person", {}).get("fullName")
            stats_b = lookup_stats(pid_b, name_b, DF_BAT)
            batters.append({
                "game_id": game_id,
                "player_type": "Batter",
                "team": side,
                "id": pid_b,
                "name": name_b,
                "position": player.get("position", {}).get("abbreviation"),
                "order": order,
                "stats": stats_b
            })
            count += 1
    return pitchers, batters

# ─── Generate Daily Websheet HTML ─────────────────────────────────────────────────
def generate_html(games):
    html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\"/>
  <title>Moneyline Hacks - RFI Model</title>
  <link href=\"https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css\" rel=\"stylesheet\">
  <style>
    body {{ background-color: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
    .title-highlight {{ background: linear-gradient(to right, #34d399, #06b6d4); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
  </style>
</head>
<body class=\"p-6\">
  <div class=\"flex flex-col items-center justify-center gap-3 mb-6\">
    <img src=\"https://raw.githubusercontent.com/Fluidity1337/ai-ml-predictive-models/main/assets/img/mlh/mlh-logo-1.jpg\" alt=\"Moneyline Hacks Logo\" class=\"h-16\" />
    <h1 class=\"text-4xl font-extrabold title-highlight\">Moneyline Hacks</h1>
    <h2 class=\"text-xl text-gray-400\">Run First Inning (RFI) Model — {datetime.now().strftime('%B %d')}</h2>
    <img src=\"https://raw.githubusercontent.com/Fluidity1337/ai-ml-predictive-models/main/assets/img/mlb/mlb-logo-2.png\" alt=\"Baseball Icon\" class=\"h-10\" />
  </div>
  <div class=\"bg-gray-800 max-w-5xl mx-auto overflow-x-auto rounded-lg shadow-xl\">
    <table class=\"min-w-full text-sm text-left text-gray-300\">
        <thead class="bg-gray-700 text-gray-300 text-sm uppercase">
        <tr>
            <th class="px-4 py-3">Pitching Team</th>
            <th class="px-4 py-3">Proj. Pitcher</th>
            <th class="px-4 py-3">25 NRFI Record</th>
            <th class="px-4 py-3">Streak</th>
            <th class="px-4 py-3">Opponent</th>
            <th class="px-4 py-3">Opp. NRFI Record</th>
            <th class="px-4 py-3">Opponent Streak</th>
        </tr>
        </thead>
      <tbody>
"""
    for game in games:
        away = game["teams"]["away"]
        home = game["teams"]["home"]

        for team_type in ["away", "home"]:
            team = game["teams"][team_type]
            opp_type = "home" if team_type == "away" else "away"
            opponent = game["teams"][opp_type]

            team_name = team["team"]["name"]
            opp_name = opponent["team"]["name"]
            pitcher = team.get("probablePitcher", {}).get("fullName", "-")
            #game_id = game["gameId"]

            # Hardcoded values for now
            nrfi_record = "12-13"
            streak = "+3"
            opp_nrfi_record = "14-11"
            opp_streak = "-1"

            html += f"<tr class='hover:bg-gray-700 border-b border-gray-700'>"
            html += f"<td class='px-4 py-3'>{team_name}</td>"
            html += f"<td class='px-4 py-3'>{pitcher}</td>"
            html += f"<td class='px-4 py-3'>{nrfi_record}</td>"
            html += f"<td class='px-4 py-3 text-green-400'>{streak}</td>"
            html += f"<td class='px-4 py-3'>{opp_name}</td>"
            html += f"<td class='px-4 py-3'>{opp_nrfi_record}</td>"
            html += f"<td class='px-4 py-3 text-red-400'>{opp_streak}</td>"
            html += "</tr>\n"
            #logging.info(f"Appended table row to HTML for game {game_id} for {team_name} vs {opp_name}")
            logging.debug(f"Appended table row for game {game['gamePk']} for {team_name} vs {opp_name}")
        html += "</tbody></table></div></body></html>"
        HTML_OUTPUT_PATH.write_text(html)
    logging.info(f"Wrote to file {HTML_OUTPUT_PATH}")
    
# ─── Main pipeline ──────────────────────────────────────────────────────────────
def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    games = fetch_mlb_schedule(date_str)
    all_players = []
    for game in games:
        p_list, b_list = fetch_game_details(game)
        all_players.extend(p_list + b_list)

    # Save JSON
    json_path = RAW_DATA_DIR / "mlb_daily_summary.json"
    with open(json_path, "w") as f:
        json.dump({"date": date_str, "players": all_players}, f, indent=2)
    logging.info(f"Saved JSON summary to {json_path}")

    # Save CSV
    csv_path = RAW_DATA_DIR / "mlb_daily_summary.csv"
    with open(csv_path, "w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        header = ["game_id","player_type","team","id","name","position","order"]
        writer.writerow(header + [*all_players[0]['stats'].keys()])
        for rec in all_players:
            row = [rec.get(k) for k in header]
            stats_vals = [rec['stats'].get(k, '') for k in rec['stats'].keys()]
            writer.writerow(row + stats_vals)
    logging.info(f"Saved CSV summary to {csv_path}")

if __name__ == "__main__":
    main()
