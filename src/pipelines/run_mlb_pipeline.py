import sys
from pathlib import Path
import requests
from datetime import datetime
import json
import csv
import os
import logging

# Configure logging
datefmt = '%Y-%m-%d %H:%M:%S'
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt=datefmt)

# Allow project-root imports
sys.path.append(str(Path(__file__).resolve().parents[2]))

# Load config
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"
with open(CONFIG_PATH) as f:
    config = json.load(f)

RAW_DATA_DIR = Path(config.get("mlb_test_output_path", "./output")).resolve()
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
HTML_OUTPUT_PATH = CONFIG_PATH.parent / "index.html"


def fetch_mlb_schedule(date_str):
    """Fetch MLB schedule for a given date."""
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}&hydrate=probablePitcher"
    logging.debug("Schedule URL: %s", url)
    res = requests.get(url)
    res.raise_for_status()
    dates = res.json().get("dates", [])
    return dates[0].get("games", []) if dates else []


def fetch_player_season_stats(player_id, season, group="pitching"):
    """Fetch season-long stats for a player, pitching or hitting."""
    pid = str(player_id).lstrip("ID")
    if not pid.isdigit():
        logging.warning("Invalid player_id %s", player_id)
        return {}
    url = f"https://statsapi.mlb.com/api/v1/people/{pid}/stats?stats=season&group={group}&season={season}"
    logging.debug("Stats URL (%s) for player %s: %s", group, pid, url)
    res = requests.get(url)
    if res.status_code != 200:
        logging.warning("Failed stats fetch (%s) for %s: %s", group, pid, res.status_code)
        return {}
    splits = res.json().get("stats", [{}])[0].get("splits", [])
    stat = splits[0].get("stat", {}) if splits else {}
    logging.debug("Stats fetched for %s ID %s: %s", group, pid, stat)
    return stat


def fetch_game_details(game):
    """Fetch season stats for probable pitcher and first 3 batters via battingOrder."""
    game_id = game.get("gamePk")
    if not game_id:
        return [], []

    # Fetch boxscore once
    box_url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore"
    logging.debug("Boxscore URL: %s", box_url)
    res = requests.get(box_url)
    res.raise_for_status()
    teams_box = res.json().get("teams", {})

    season = datetime.now().year
    pitchers = []
    batters = []

    for team_type in ["home", "away"]:
        team_info = game["teams"][team_type]
        team_box = teams_box.get(team_type, {})

        # Probable pitcher
        prob = team_info.get("probablePitcher")
        if prob and prob.get("id"):
            pid = prob["id"]
            stats_p = fetch_player_season_stats(pid, season, group="pitching")
            pitchers.append({
                "name": prob.get("fullName"), "id": pid,
                "team": team_type, "stats": stats_p
            })
            game["teams"][team_type]["pitcherStats"] = stats_p

        # First 3 batters by battingOrder
        count = 0
        for player_key, player_data in team_box.get("players", {}).items():
            order = player_data.get("battingOrder")
            if not order or count >= 3:
                continue
            try:
                order = int(order)
            except ValueError:
                continue
            pid_b = player_data.get("person", {}).get("id")
            if not pid_b:
                continue
            stats_b = fetch_player_season_stats(pid_b, season, group="hitting")
            rec = {
                "name": player_data["person"].get("fullName"),
                "id": pid_b,
                "team": team_type,
                "order": order,
                "position": player_data.get("position", {}).get("abbreviation"),
                "stats": stats_b
            }
            batters.append(rec)
            count += 1
        # attach collected batters
        game["teams"][team_type]["batterStats"] = [b for b in batters if b["team"] == team_type][:3]

    logging.debug("Fetched %d pitchers and %d batters for game %s", len(pitchers), len(batters), game_id)
    return pitchers, batters

def get_first_three_batters_live_feed(game_id):
    """Fetch and return the first three batters for both home and away teams using the GUMBO live feed."""
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    box = data.get("liveData", {}) \
               .get("boxscore", {}) \
               .get("teams", {})

    result = {}
    for side in ["away", "home"]:
        team_box = box.get(side, {})
        batter_ids = team_box.get("batters", [])[:3]
        players = team_box.get("players", {})
        batters = []
        for bid in batter_ids:
            key = f"ID{bid}"
            entry = players.get(key, {})
            person = entry.get("person", {})
            name = person.get("fullName", "Unknown")
            position = entry.get("position", {}).get("abbreviation", "")
            batters.append({"id": bid, "name": name, "position": position})
        result[side] = batters
    return result

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

if __name__ == "__main__":
    date_str = datetime.now().strftime("%Y-%m-%d")
    logging.info("Fetching MLB Schedule")
    games = fetch_mlb_schedule(date_str)
    logging.info(f"Fetched {len(games)} games.")

    all_pitchers, all_batters = [], []
    logging.info("Fetching Details for Each Game")
    for game in games:
        game_id = game.get("gamePk")
        if not game_id:
            continue
        p_list, b_list = fetch_game_details(game)
        for p in p_list:
            p["game_id"] = game_id
            all_pitchers.append(p)
        for b in b_list:
            b["game_id"] = game_id
            all_batters.append(b)

    if len(sys.argv) < 2:
        print("Usage: python run_mlb_pipeline.py <game_id>")
        sys.exit(1)

    game_id = sys.argv[1]
    try:
        batters = get_first_three_batters_live_feed(game_id)
    except requests.HTTPError as e:
        print(f"Error fetching live feed for game {game_id}: {e}")
        sys.exit(1)

    for side in ["away", "home"]:
        print(f"{side.capitalize()} batters for game {game_id}:")
        if not batters.get(side):
            print("  No batters available (lineup not posted yet)")
        for b in batters.get(side, []):
            print(f"  {b['id']}: {b['name']} ({b['position']})")
        
    # Save JSON summary
    json_path = RAW_DATA_DIR / "mlb_daily_summary.json"
    with open(json_path, "w") as f:
        json.dump({"date": date_str, "games": games, "pitchers": all_pitchers, "batters": all_batters}, f, indent=2)
    logging.info(f"Saved combined summary to {json_path}")

    # Save CSV summary
    csv_path = RAW_DATA_DIR / "mlb_daily_summary.csv"
    with open(csv_path, "w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Game ID","Player Type","Team","Name","Position","ERA","WHIP","K/9","BB/9","1st Inning ERA","AVG","HR","OPS"])
        for p in all_pitchers:
            writer.writerow([p["game_id"],"Pitcher",p["team"],p["name"],"P",p["stats"].get("era"),p["stats"].get("whip"),p["stats"].get("strikeOutsPer9Inn"),p["stats"].get("baseOnBallsPer9Inn"),p["stats"].get("firstInningEra"),"","",""])
        for b in all_batters:
            writer.writerow([b["game_id"],"Batter",b["team"],b["name"],b["position"],"","","","","",b["stats"].get("avg"),b["stats"].get("homeRuns"),b["stats"].get("ops")])
    logging.info(f"Saved CSV summary to {csv_path}")

    generate_html(games)
