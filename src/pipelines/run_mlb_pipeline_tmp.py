import sys
from pathlib import Path
import requests
from datetime import datetime
import json
import csv
import logging

# Configure logging (ISO timestamps)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")

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

    box_url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore"
    logging.debug("Boxscore URL: %s", box_url)
    res = requests.get(box_url)
    res.raise_for_status()
    teams_box = res.json().get("teams", {})

    season = datetime.now().year
    pitchers, batters = [], []

    for team_type in ["home", "away"]:
        team_info = game["teams"][team_type]
        team_box = teams_box.get(team_type, {})

        # --- Pitcher ---
        prob = team_info.get("probablePitcher")
        if prob and prob.get("id"):
            pid = prob["id"]
            raw = fetch_player_season_stats(pid, season, group="pitching")

            stats_p = {
                "era": raw.get("era"),
                "fip": raw.get("fip"),
                "xFIP": raw.get("xFip"),
                "whip": raw.get("whip"),
                "k_per_9": raw.get("strikeOutsPer9Inn"),
                "bb_per_9": raw.get("baseOnBallsPer9Inn"),
                "hr_per_9": raw.get("homeRunsPer9Inn"),
                "swinging_strike_pct": raw.get("swingingStrikePct"),
                "opponent_avg": raw.get("opponentBattingAverage"),
                "first_inning_era": raw.get("firstInningEra"),
            }
            pitchers.append({
                "name": prob.get("fullName"),
                "id": pid,
                "team": team_type,
                "stats": stats_p
            })
            game["teams"][team_type]["pitcherStats"] = stats_p

        # --- Batters (first 3 in order) ---
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

            raw_b = fetch_player_season_stats(pid_b, season, group="hitting")
            stats_b = {
                "avg": raw_b.get("avg"),
                "obp": raw_b.get("obp"),
                "slg": raw_b.get("slg"),
                "ops": raw_b.get("ops"),
                "iso": raw_b.get("iso"),
                "woba": raw_b.get("woba"),
                "wrc_plus": raw_b.get("wrcPlus"),
                "k_pct": raw_b.get("strikeOutRate"),
                "bb_pct": raw_b.get("baseOnBallsPercent"),
                "hard_hit_pct": raw_b.get("hardHitPct"),
                "barrel_pct": raw_b.get("barrelPct"),
                "first_inning_obp": raw_b.get("firstInningOBP"),
                "first_inning_ops": raw_b.get("firstInningOPS"),
            }

            batters.append({
                "name": player_data["person"].get("fullName"),
                "id": pid_b,
                "team": team_type,
                "order": order,
                "position": player_data.get("position", {}).get("abbreviation"),
                "stats": stats_b
            })
            count += 1

        game["teams"][team_type]["batterStats"] = [b for b in batters if b["team"] == team_type][:3]

    return pitchers, batters


def generate_html(games):
    # (unchanged — still builds your Tailwind table)
    ...


if __name__ == "__main__":
    date_str = datetime.now().strftime("%Y-%m-%d")
    logging.info("Fetching MLB Schedule")
    games = fetch_mlb_schedule(date_str)
    logging.info(f"Fetched {len(games)} games.")

    all_pitchers, all_batters = [], []
    logging.info("Fetching Details for Each Game")
    for game in games:
        gid = game.get("gamePk")
        p_list, b_list = fetch_game_details(game)
        for p in p_list:
            p["game_id"] = gid
            all_pitchers.append(p)
        for b in b_list:
            b["game_id"] = gid
            all_batters.append(b)

    # --- JSON Output (contains full stats dicts) ---
    json_path = RAW_DATA_DIR / "mlb_daily_summary.json"
    with open(json_path, "w") as f:
        json.dump({
            "date": date_str,
            "games": games,
            "pitchers": all_pitchers,
            "batters": all_batters
        }, f, indent=2)
    logging.info(f"Saved combined summary to {json_path}")

    # --- CSV Output (flat table with all metrics) ---
    csv_path = RAW_DATA_DIR / "mlb_daily_summary.csv"
    with open(csv_path, "w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Game ID","Player Type","Team","Name","Position",
            # Pitcher metrics
            "ERA","FIP","xFIP","WHIP","K/9","BB/9","HR/9",
            "Swinging Strike %","Opponent Avg","1st Inning ERA",
            # Batter metrics
            "AVG","OBP","SLG","OPS","ISO","wOBA","wRC+",
            "K%","BB%","Hard Hit %","Barrel %",
            "1st Inning OBP","1st Inning OPS",
        ])

        for p in all_pitchers:
            s = p["stats"]
            writer.writerow([
                p["game_id"], "Pitcher", p["team"], p["name"], "P",
                s.get("era"), s.get("fip"), s.get("xFIP"), s.get("whip"),
                s.get("k_per_9"), s.get("bb_per_9"), s.get("hr_per_9"),
                s.get("swinging_strike_pct"), s.get("opponent_avg"),
                s.get("first_inning_era"),
                # blanks for batter columns
                *[""] * 12
            ])

        for b in all_batters:
            s = b["stats"]
            writer.writerow([
                b["game_id"], "Batter", b["team"], b["name"], b["position"],
                # blanks for pitcher columns
                *[""] * 11,
                s.get("avg"), s.get("obp"), s.get("slg"), s.get("ops"),
                s.get("iso"), s.get("woba"), s.get("wrc_plus"),
                s.get("k_pct"), s.get("bb_pct"),
                s.get("hard_hit_pct"), s.get("barrel_pct"),
                s.get("first_inning_obp"), s.get("first_inning_ops"),
            ])

    logging.info(f"Saved CSV summary to {csv_path}")
