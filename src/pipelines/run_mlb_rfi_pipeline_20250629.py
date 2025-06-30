# run_mlb_rfi_pipeline_with_websheets_3.py

import sys
import csv
import json
import logging
import logging.config
from datetime import datetime
from pathlib import Path
import requests
import pandas as pd
from utils.mlb.fetch_game_details import fetch_game_details
from utils.mlb.fetch_advanced_stats_for_pitcher import PitcherAdvancedStats
from utils.config_loader import load_config
from utils.helpers import RatingCalculator, FeatureConfigLoader
from utils.mlb.team_codes import get_team_codes

cfg = load_config()
logging.config.dictConfig(cfg["logging"])

# Try pybaseball for season stats
try:
    from pybaseball import batting_stats, pitching_stats
    HAS_PYBASEBALL = True
except ImportError:
    HAS_PYBASEBALL = False
    logging.warning("pybaseball not available, season stats may be incomplete")


# Determine date to process
date_str = sys.argv[1] if len(
    sys.argv) > 1 else datetime.now().strftime('%Y-%m-%d')
SEASON = int(date_str.split('-')[0])

# Get base cache path from config and inject season into filename
cache_template = cfg["mlb_data"].get(
    "team_abbrev_cds_cache_path", ".cache/team_codes_{season}.json")
cache_file = Path(cache_template.format(season=SEASON))

if cache_file.exists():
    logging.info("📦 Loading team codes from cache: %s", cache_file)
    with open(cache_file, "r", encoding="utf-8") as f:
        team_codes = json.load(f)
else:
    logging.info("📡 Fetching team codes from MLB API for season %d", SEASON)
    team_codes = get_team_codes(SEASON)  # Your custom function
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(team_codes, f, indent=2)
    logging.info("✅ Saved team codes to cache at %s", cache_file)


# logging.debug("🔁 Forcing refresh? %s", force_refresh)
# logging.debug("📦 Cache file exists? %s", cache_file.exists())
# logging.debug("📦 Cache file path: %s", cache_file)

TEAM_CODES = get_team_codes()

features_path = cfg["models"]["mlb_rfi"]["feature_definitions_path"]
features_cfg = FeatureConfigLoader.load_features_config(features_path)

logging.info("Features config keys: %s", list(features_cfg.keys()))

weights = {k: v["weight"] for k, v in features_cfg.items() if "weight" in v}
bounds = {k: v["bounds"] for k, v in features_cfg.items() if "bounds" in v}

# Optionally load pybaseball data
"""
try:
    from pybaseball import pitching_stats, batting_stats
    SEASON = int(datetime.now().year)
    df_pitch = pitching_stats(SEASON)
    # df_bat = batting_stats(SEASON)
except Exception as e:
    logging.warning("Pybaseball not available or errored: %s", e)
    df_pitch = pd.DataFrame()
    # df_bat = pd.DataFrame()
"""

raw_data_dir = Path(cfg["mlb_data"]["raw"])
raw_data_dir.mkdir(parents=True, exist_ok=True)

# Load season stats


def load_stats():
    df_pitch = pd.DataFrame()
    # df_bat = pd.DataFrame()
    if HAS_PYBASEBALL:
        try:
            logging.info(f"Loading {SEASON} pitching stats via pybaseball…")
            df_pitch = pitching_stats(SEASON)
            # ——— DEBUG: what columns did we actually get? ———
            # logging.info("pybaseball.pitching_stats columns: %s",
            #             df_pitch.columns.tolist())
            if 'xFIP' not in df_pitch.columns and 'xfip' not in df_pitch.columns:
                logging.warning(
                    "⚠️ No xFIP column found in pybaseball output!")
        except Exception as e:
            logging.error(f"pybaseball pitching_stats error: {e}")
        try:
            logging.info(f"Loading {SEASON} batting stats via pybaseball…")
            # df_bat = batting_stats(SEASON)
        except Exception as e:
            logging.error(f"pybaseball batting_stats error: {e}")
    return df_pitch  # , df_bat


DF_PITCH = load_stats()
# DF_PITCH = []

# Utility functions


def fetch_schedule(date_str):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}&hydrate=teams(team,previewPlayers),probablePitcher"
    return requests.get(url).json().get("dates", [{}])[0].get("games", [])


if __name__ == '__main__':
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        date_str = "2025-06-30"

    try:
        datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        logging.error("Date must be in YYYY-MM-DD format, got %r", date_str)
        sys.exit(1)

    games = fetch_schedule(date_str)
    logging.info("Loaded %d games", len(games))

    all_pitchers = []
    for g in games:
        ps = fetch_game_details(g, DF_PITCH, features_cfg, SEASON)

        for p in ps:
            stats = p.setdefault("stats", {})
            # Flatten recent_avgs from calculated_stats
            calculated = p.get("calculated_stats", {})
            recent = calculated.get("recent_avgs", {})
            stats["recent_xFIP"] = recent.get("avg_xFIP", "NA")
            stats["recent_xFIP_score"] = recent.get("avg_xFIP_score", "NA")
            stats["recent_Barrel%"] = recent.get("avg_Barrel%", "NA")
            stats["recent_Barrel%_score"] = recent.get(
                "avg_Barrel%_score", "NA")

        all_pitchers.extend(ps)

    csv_path = raw_data_dir / \
        f"mlb_combined_stats_{date_str.replace('-', '')}.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        headers = ['game_id', 'player_type', 'team', 'team_abbrev', 'side',
                   'id', 'name', 'position', 'order']
        stat_keys = sorted({
            k for rec in all_pitchers for k in rec.get('stats', {})
        })
        writer.writerow(headers + stat_keys)
        for rec in all_pitchers:
            row = [rec.get(c, 'NA') for c in headers]
            row += [rec['stats'].get(sk, 'NA') for sk in stat_keys]
            writer.writerow(row)

    logging.info(f"Saved CSV to {csv_path}")

    json_stats_path = raw_data_dir / \
        f"mlb_daily_stats_summary_{date_str.replace('-', '')}.json"
    with open(json_stats_path, 'w', encoding='utf-8') as jf:
        json.dump(all_pitchers, jf, indent=2)
    logging.info(f"Saved JSON stats summary to {json_stats_path}")

    game_summary = []
    for g in games:
        away_team = g["teams"]["away"]["team"]["name"]
        home_team = g["teams"]["home"]["team"]["name"]
        away_abbrev = TEAM_CODES.get(g["teams"]["away"]["team"]["id"], "")
        home_abbrev = TEAM_CODES.get(g["teams"]["home"]["team"]["id"], "")
        away_pitch = g["teams"]["away"].get(
            "probablePitcher", {}).get("fullName", "")
        home_pitch = g["teams"]["home"].get(
            "probablePitcher", {}).get("fullName", "")

        # Look up pitcher stats
        home_pitcher_stats = next((p.get("stats", {}) for p in all_pitchers if p.get(
            "name") == home_pitch and p.get("side") == "home"), {})
        away_pitcher_stats = next((p.get("stats", {}) for p in all_pitchers if p.get(
            "name") == away_pitch and p.get("side") == "away"), {})

        game_summary.append({
            "game_id": g["gamePk"],
            "game_datetime": g["gameDate"],
            "away_team": away_team,
            "away_abbrev": away_abbrev,
            "home_team": home_team,
            "home_abbrev": home_abbrev,
            "away_pitcher": away_pitch,
            "home_pitcher": home_pitch,
            "nrfi_grade": g.get("nrfi_grade"),
            "home_pitcher_recent_xFIP": home_pitcher_stats.get("recent_xFIP", "NA"),
            "home_pitcher_recent_xFIP_score": home_pitcher_stats.get("recent_xFIP_score", "NA"),
            "away_pitcher_recent_barrel%": away_pitcher_stats.get("recent_Barrel%", "NA"),
            "away_pitcher_recent_barrel%_score": away_pitcher_stats.get("recent_Barrel%_score", "NA")
        })

    game_csv = raw_data_dir / \
        f"mlb_daily_game_summary_{date_str.replace('-', '')}.csv"
    with open(game_csv, 'w', newline='', encoding='utf-8') as gf:
        writer = csv.writer(gf)
        writer.writerow([
            "game_id", "game_datetime",
            "away_team", "away_abbrev",
            "home_team", "home_abbrev",
            "away_pitcher", "home_pitcher", "nrfi_grade",
            "home_pitcher_recent_xFIP", "home_pitcher_recent_xFIP_score",
            "away_pitcher_recent_barrel%", "away_pitcher_recent_barrel%_score"
        ])
        for r in game_summary:
            writer.writerow([
                r["game_id"], r["game_datetime"], r["away_team"], r["away_abbrev"],
                r["home_team"], r["home_abbrev"], r["away_pitcher"],
                r["home_pitcher"], r["nrfi_grade"],
                r["home_pitcher_recent_xFIP"], r["home_pitcher_recent_xFIP_score"],
                r["away_pitcher_recent_barrel%"], r["away_pitcher_recent_barrel%_score"]
            ])
    logging.info(f"Saved CSV game summary to {game_csv}")

    game_json = raw_data_dir / \
        f"mlb_daily_game_summary_{date_str.replace('-', '')}.json"
    with open(game_json, 'w', encoding='utf-8') as gj:
        json.dump(game_summary, gj, indent=2)
    logging.info(f"Saved JSON game summary to {game_json}")
