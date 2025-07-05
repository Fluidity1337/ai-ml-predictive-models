# run_mlb_rfi_pipeline_with_websheets_3.py

import sys
import csv
import json
import logging
import logging.config
from datetime import datetime, timedelta
from pathlib import Path
import requests
import pandas as pd
from utils.mlb.fetch_schedule import fetch_schedule
from utils.mlb.fetch_game_details import fetch_game_details
from utils.mlb.fetch_advanced_stats_for_pitcher import PitcherAdvancedStats
from utils.config_loader import load_config
from utils.helpers import RatingCalculator, FeatureConfigLoader
from utils.mlb.team_codes import get_team_codes
from utils.mlb.calculate_nrfi_score import calculate_nrfi_score

cfg = load_config()
logging.config.dictConfig(cfg["logging"])
features_path = Path(cfg['models']['mlb_rfi']['feature_definitions_path'])
with open(features_path) as fd:
    features_def = json.load(fd)

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


def normalize_team_name(name):
    return name.replace(".", "").replace("  ", " ").strip().lower()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        date_str = "2025-07-03"

    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        logging.error("Date must be in YYYY-MM-DD format, got %r", date_str)
        sys.exit(1)

    # right after validating date_str
    start_dt = (dt - timedelta(days=30)).strftime('%Y-%m-%d')
    end_dt = date_str

    games = fetch_schedule(date_str)
    logging.info("Loaded %d games", len(games))

    # Load wOBA split data
    woba3_path = Path(
        "F:/Dropbox/1_Work/Development/GitHub/Fluidity1337/ai-ml-predictive-models/data/baseball/mlb/processed/team_woba3_splits_combined.json")
    with open(woba3_path, 'r', encoding='utf-8') as wf:
        woba_data = json.load(wf)
        woba_split = woba_data.get("splits", {}).get("14d", {})

    # Load wRC+ 1st inning data from FanGraphs
    wrclike_path = Path(
        "F:/Dropbox/1_Work/Development/GitHub/Fluidity1337/ai-ml-predictive-models/data/baseball/mlb/raw/fangraphs/splits_1st_inning_2025_20250629.csv")
    try:
        wrclike_df = pd.read_csv(wrclike_path)
        wrclike_map = {
            str(row["Tm"]).strip().upper(): row["wRC+"]
            for _, row in wrclike_df.iterrows()
        }
    except Exception as e:
        logging.error(f"❌ Failed to load wRC+ 1st inning CSV: {e}")
        wrclike_map = {}

    # Aggregate pitcher stats for 4th game only (index 3)
    all_pitchers = []
    # g = games[3]
    for g in games:
        pitchers = fetch_game_details(g, DF_PITCH, features_cfg, SEASON)
        for p in pitchers:
            stats = p.setdefault('stats', {})
            calc = p.setdefault('calculated_stats', {})
            recent = calc.get('recent_avgs', {})
            # Flatten recent averages
            stats['recent_xfip'] = recent.get('avg_xfip', 'NA')
            stats['recent_xfip_score'] = recent.get('avg_xfip_score', 'NA')
            stats['recent_barrel_pct'] = recent.get('avg_barrel_pct', 'NA')
            stats['recent_barrel_pct_score'] = recent.get(
                'avg_barrel_pct_score', 'NA')
            # Compute first-inning metrics via PitcherAdvancedStats
            pas = PitcherAdvancedStats(
                p.get('id'),
                start=(dt - timedelta(days=30)).date(),
                end=dt.date()
            )
            pas.analyze()
            stats['recent_f1_era'] = pas.f1_era()
            stats['recent_f1_whip'] = pas.f1_whip()
            all_pitchers.append(p)

    # Write CSV of combined stats
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

    game_summary = []
    for g in games:
        away = g['teams']['away']
        home = g['teams']['home']
        away_team = g["teams"]["away"]["team"]["name"]
        home_team = g["teams"]["home"]["team"]["name"]
        away_abbrev = TEAM_CODES.get(g["teams"]["away"]["team"]["id"], "")
        home_abbrev = TEAM_CODES.get(g["teams"]["home"]["team"]["id"], "")
        away_pitch = g["teams"]["away"].get(
            "probablePitcher", {}).get("fullName", "")
        home_pitch = g["teams"]["home"].get(
            "probablePitcher", {}).get("fullName", "")
        away_stats = next((rec['stats'] for rec in all_pitchers
                           if rec['name'] == away_pitch and rec['side'] == 'away'), {})
        home_stats = next((rec['stats'] for rec in all_pitchers
                           if rec['name'] == home_pitch and rec['side'] == 'home'), {})

        # Look up pitcher stats
        home_pitcher_stats = next((p.get("stats", {}) for p in all_pitchers if p.get(
            "name") == home_pitch and p.get("side") == "home"), {})
        away_pitcher_stats = next((p.get("stats", {}) for p in all_pitchers if p.get(
            "name") == away_pitch and p.get("side") == "away"), {})

        # Lookup opponent wOBA using team abbrev
        opp_woba_home = woba_split.get(away_abbrev.capitalize(), "NA")
        opp_woba_away = woba_split.get(home_abbrev.capitalize(), "NA")

        # Lookup wRC+ 1st inning by full team name
        TEAM_ABBREV_MAP = {
            "AZ": "ARI", "SF": "SFG", "KC": "KCR", "TB": "TBR", "NY": "NYY",
            "SD": "SDP", "CWS": "CHW", "WSH": "WSN", "CHC": "CHC", "OAK": "OAK",
            "LAA": "LAA", "LAD": "LAD", "MIA": "MIA", "BOS": "BOS", "PHI": "PHI",
            "PIT": "PIT", "CLE": "CLE", "CIN": "CIN", "SEA": "SEA", "BAL": "BAL",
            "TEX": "TEX", "TOR": "TOR", "MIN": "MIN", "HOU": "HOU", "DET": "DET",
            "ATL": "ATL", "STL": "STL", "NYM": "NYM", "NYY": "NYY", "SFG": "SFG"
        }
        home_wrclike = wrclike_map.get(TEAM_ABBREV_MAP.get(
            home_abbrev.upper(), home_abbrev.upper()), "NA")
        away_wrclike = wrclike_map.get(TEAM_ABBREV_MAP.get(
            away_abbrev.upper(), away_abbrev.upper()), "NA")

        # compute team-level RFI scores
        # away team features
        away_nrfi_features_vals = {
            "xFIP": away_stats.get('recent_xfip', 'NA'),
            "BarrelPct": away_stats.get('recent_barrel_pct', 'NA'),
            "f1_era": away_stats.get('f1_era', 'NA'),
            "WHIP": away_stats.get('f1_whip', 'NA'),
            "wRCp1st": away_wrclike,
            "wOBA3": opp_woba_away
        }
        _away_nrfi_score_resp = calculate_nrfi_score(
            away_nrfi_features_vals, features_def)
        away_nrfi_score = _away_nrfi_score_resp[0] if isinstance(
            _away_nrfi_score_resp, tuple) else _away_nrfi_score_resp

        # home team features
        home_nrfi_features_vals = {
            "xFIP": home_stats.get('recent_xfip', 'NA'),
            "BarrelPct": home_stats.get('recent_barrel_pct', 'NA'),
            "f1_era": home_stats.get('f1_era', 'NA'),
            "WHIP": home_stats.get('f1_whip', 'NA'),
            "wRCp1st": home_wrclike,
            "wOBA3": opp_woba_home,
        }
        _home_nrfi_score_resp = calculate_nrfi_score(
            home_nrfi_features_vals, features_def)
        home_nrfi_score = _home_nrfi_score_resp[0] if isinstance(
            _home_nrfi_score_resp, tuple) else _home_nrfi_score_resp

        # game-level average
        game_nrfi_score = round((away_nrfi_score + home_nrfi_score) / 2, 2)

        game_summary.append({
            'game_id':               g['gamePk'],
            'game_datetime':         g['gameDate'],
            'away_team':             away['team']['name'],
            'home_team':             home['team']['name'],
            'away_team_abbrev':      away_abbrev,
            'home_team_abbrev':      home_abbrev,
            'away_pitcher':          away_pitch,
            'home_pitcher':          home_pitch,
            'home_pitcher_recent_f1_era':  home_stats.get('recent_f1_era', 'NA'),
            'home_pitcher_recent_f1_whip': home_stats.get('recent_f1_whip', 'NA'),
            'away_pitcher_recent_f1_era':  away_stats.get('recent_f1_era', 'NA'),
            'away_pitcher_recent_f1_whip': away_stats.get('recent_f1_whip', 'NA'),
            "nrfi_grade": g.get("nrfi_grade"),
            "home_pitcher_recent_xfip": home_pitcher_stats.get("recent_xfip", "NA"),
            "home_pitcher_recent_xfip_score": home_pitcher_stats.get("recent_xfip_score", "NA"),
            "away_pitcher_recent_xfip": away_pitcher_stats.get("recent_xfip", "NA"),
            "away_pitcher_recent_xfip_score": away_pitcher_stats.get("recent_xfip_score", "NA"),
            "home_pitcher_recent_barrel_pct": home_pitcher_stats.get("recent_barrel_pct", "NA"),
            "home_pitcher_recent_barrel_pct_score": home_pitcher_stats.get("recent_barrel_pct_score", "NA"),
            "away_pitcher_recent_barrel_pct": away_pitcher_stats.get("recent_barrel_pct", "NA"),
            "away_pitcher_recent_barrel_pct_score": away_pitcher_stats.get("recent_barrel_pct_score", "NA"),
            "home_team_woba3": opp_woba_home,
            "away_team_woba3": opp_woba_away,
            "home_team_wrc_plus_1st_inn": home_wrclike,
            "away_team_wrc_plus_1st_inn": away_wrclike,
            'away_team_score': away_nrfi_score,
            'home_team_score': home_nrfi_score,
            'game_nrfi_score': game_nrfi_score
        })

    # Write game summary CSV/JSON
    summary_csv = raw_data_dir / \
        f"mlb_daily_game_summary_{date_str.replace('-','')}.csv"
    pd.DataFrame(game_summary).to_csv(summary_csv, index=False)
    logging.info(f"Saved summary CSV to {summary_csv}")
    summary_json = raw_data_dir / \
        f"mlb_daily_game_summary_{date_str.replace('-','')}.json"
    with open(summary_json, 'w', encoding='utf-8') as gj:
        json.dump(game_summary, gj, indent=2)
    logging.info(f"Saved summary JSON to {summary_json}")
