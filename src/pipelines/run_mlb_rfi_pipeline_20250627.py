# run_mlb_rfi_pipeline_with_websheets_3.py

import sys
import logging
import logging.config
from datetime import datetime
from pathlib import Path
import requests
import pandas as pd
from utils.config_loader import load_config
from utils.helpers import RatingCalculator, FeatureConfigLoader
from src.utils.mlb.team_codes import get_team_codes

TEAM_CODES = get_team_codes()

# Load config
cfg = load_config()
# print("[DEBUG] Loaded config:", cfg)
logging.config.dictConfig(cfg["logging"])

features_path = cfg["models"]["mlb_rfi"]["feature_definitions_path"]
features_cfg = FeatureConfigLoader.load_features_config(features_path)

logging.info("Features config keys: %s", list(features_cfg.keys()))

weights = {k: v["weight"] for k, v in features_cfg.items() if "weight" in v}
bounds = {k: v["bounds"] for k, v in features_cfg.items() if "bounds" in v}

# Optionally load pybaseball data
try:
    from pybaseball import pitching_stats, batting_stats
    SEASON = int(datetime.now().year)
    df_pitch = pitching_stats(SEASON)
    df_bat = batting_stats(SEASON)
except Exception as e:
    logging.warning("Pybaseball not available or errored: %s", e)
    df_pitch = pd.DataFrame()
    df_bat = pd.DataFrame()

raw_data_dir = Path(cfg["mlb_data"]["raw"])
raw_data_dir.mkdir(parents=True, exist_ok=True)

"""
# Logging setup
date_now = datetime.now().strftime('%Y-%m-%d')
log_file = raw_data_dir / f"mlb_pipeline_{date_now}.log"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(), logging.FileHandler(
        log_file, mode='a', encoding='utf-8')]
)
logging.info(f"Logging to console and file: {log_file}")
"""

# Determine date to process
date_str = sys.argv[1] if len(
    sys.argv) > 1 else datetime.now().strftime('%Y-%m-%d')
SEASON = int(date_str.split('-')[0])


# Load season stats


def load_stats():
    df_pitch = pd.DataFrame()
    df_bat = pd.DataFrame()
    if HAS_PYBASEBALL:
        try:
            logging.info(f"Loading {SEASON} pitching stats via pybaseball…")
            df_pitch = pitching_stats(SEASON)
            # ——— DEBUG: what columns did we actually get? ———
            logging.info("pybaseball.pitching_stats columns: %s",
                         df_pitch.columns.tolist())
            if 'xFIP' not in df_pitch.columns and 'xfip' not in df_pitch.columns:
                logging.warning(
                    "⚠️ No xFIP column found in pybaseball output!")
        except Exception as e:
            logging.error(f"pybaseball pitching_stats error: {e}")
        try:
            logging.info(f"Loading {SEASON} batting stats via pybaseball…")
            df_bat = batting_stats(SEASON)
        except Exception as e:
            logging.error(f"pybaseball batting_stats error: {e}")
    return df_pitch, df_bat


DF_PITCH, DF_BAT = load_stats()


# Utility functions
def get_boxscore_batters(game_id, side, preview: bool = False):
    """
    Fetch the boxscore lineup. If preview=True, use ?mode=preview.
    """
    suffix = "?mode=preview" if preview else ""
    url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore{suffix}"
    data = requests.get(url).json()
    lineup = []
    team_data = data.get('teams', {}).get(side, {})
    players_info = team_data.get('players', {})
    for pid in team_data.get('batters', []):
        key = f"ID{pid}"
        player = players_info.get(key, {})
        person = player.get('person', {})
        pos = player.get('position', {}).get('code')
        lineup.append({
            'id': person.get('id'),
            'name': person.get('fullName'),
            'position': pos,
            'order': None
        })
    return lineup


def get_live_batters(game_id, side):
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live"
    data = requests.get(url).json()
    lineup = []
    box = data.get('liveData', {}).get(
        'boxscore', {}).get('teams', {}).get(side, {})
    players_info = box.get('players', {})
    for pid in box.get('batters', []):
        key = f"ID{pid}"
        player = players_info.get(key, {})
        person = player.get('person', {})
        pos = player.get('position', {}).get('code')
        lineup.append({
            'id': person.get('id'),
            'name': person.get('fullName'),
            'position': pos,
            'order': None
        })
    return lineup


def get_schedule_preview_batters(game, side):
    preview = game.get('teams', {}).get(side, {}).get('previewPlayers', [])
    sorted_preview = sorted(
        preview, key=lambda p: int(p.get('battingOrder') or 0))
    lineup = []
    for p in preview:
        person = p.get('person', {})
        pos = None
        position_info = p.get('position')
        if isinstance(position_info, dict):
            pos = position_info.get('code')
        else:
            pos = position_info
        lineup.append({
            'id': person.get('id'),
            'name': person.get('fullName'),
            'position': p.get('position', {}).get('abbreviation', ''),
            'order': p.get('battingOrder', 0)
        })
    return lineup


def get_roster_batters(team_id):
    url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster"
    data = requests.get(url).json()
    lineup = []
    for m in data.get('roster', []):
        person = m.get('person', {})
        pos = m.get('position', {}).get('code')
        lineup.append({
            'id': person.get('id'),
            'name': person.get('fullName'),
            'position': pos,
            'order': None
        })
    return lineup


def get_season_leaders():
    if df_bat.empty:
        return []
    top = df_bat.nlargest(3, 'atBats')
    lineup = []
    for _, row in top.iterrows():
        lineup.append({
            'id': row.get('playerId'),
            'name': row.get('Name'),
            'position': row.get('Pos'),
            'order': None
        })
    return lineup


def get_schedule_preview_batters(game: dict, side: str) -> list:
    pp = game['teams'][side].get('previewPlayers', [])
    bat = []
    for p in pp[:3]:
        bat.append({
            'id': p['person']['id'],
            'name': p['person']['fullName'],
            'position': p.get('position', {}).get('abbreviation', ''),
            'order': int(p.get('battingOrder', 0))
        })
    return bat


def fetch_schedule(date_str):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}&hydrate=teams(team,previewPlayers),probablePitcher"
    return requests.get(url).json().get("dates", [{}])[0].get("games", [])


def lookup_stats(pid: int, name: str, df: pd.DataFrame, group: str) -> dict:
    # 0) Initialize empty dict up front
    stat: dict = {}
    if pid is None:
        logging.debug(
            f"[LookupStats]  → skipping lookup for {name!r} because pid is None")
        return stat
    logging.debug(f"[LookupStats] {group.upper()} for {name} (ID={pid})…")

    # 1) Primary statsapi GET
    try:
        url = f"https://statsapi.mlb.com/api/v1/people/{pid}/stats?stats=season&group={group}&season={SEASON}"
        res = requests.get(url)
        res.raise_for_status()
        stats_list = res.json().get('stats', [])
        if stats_list and isinstance(stats_list, list):
            splits = stats_list[0].get('splits', [])
        else:
            splits = []
        if splits:
            stat = splits[0].get('stat', {}) or {}
            logging.debug(f"[LookupStats]  → API returned {len(stat)} fields")
        else:
            logging.debug(f"[LookupStats]  → API returned no splits")

    except Exception:
        logging.debug(
            f"[LookupStats]  → Primary API failed for {name}", exc_info=True)
    # 2) Hydrated people endpoint
    try:
        url2 = (f"https://statsapi.mlb.com/api/v1/people/{pid}"
                f"?hydrate=stats(group={group},type=season,season={SEASON})")
        res2 = requests.get(url2)
        res2.raise_for_status()
        ppl = res2.json().get('people', [])
        if ppl and isinstance(ppl, list):
            splits2 = ppl[0].get('stats', [{}])[0].get('splits', [])
        else:
            splits2 = []
        if splits2:
            stat = splits2[0].get('stat', {}) or {}
            logging.debug(
                f"[LookupStats]  → hydrated API returned {len(stat)} fields")
    except Exception:
        pass
    # 3) pybaseball fallback - Merge in pybaseball season-level stats (FIP, xFIP, etc.) by player name
    if HAS_PYBASEBALL and not df.empty:
        try:
            # pybaseball declares hitters/pitchers in a 'Name' column
            row = df[df['Name'] == name]
            if not row.empty:
                pyb = row.iloc[0].dropna().to_dict()
                stat.update(pyb)
                logging.debug(
                    f"[LookupStats]  → merged {len(pyb)} pybaseball fields")
        except Exception:
            logging.debug(
                f"[LookupStats]  → pybaseball merge failed for {name}", exc_info=True)

    return stat

# Main game detail fetch and scoring


def fetch_game_details(game, df_pitch, df_bat, features_cfg):
    game_id = game["gamePk"]
    probables = game.get("probablePitchers", {})
    lineups = game.get("previewBattingOrders", {})

    rating_calculator = RatingCalculator(features_cfg)
    pitchers = []
    batters_list = []

    for side in ("away", "home"):
        prob = probables.get(side)
        lineup = lineups.get(side, [])
        game[f"{side}_pitcher_score"] = None
        game[f"{side}_batter_score"] = None

        # --- Pitcher Score ---
        if prob:
            pstats = lookup_stats(
                prob['id'], prob['fullName'], df_pitch, "pitching")
            pscore = rating_calculator.compute_score(pstats)
            game[f"{side}_pitcher_score"] = pscore

            pitchers.append({
                "game_id": game_id,
                "side": side,
                "id": prob["id"],
                "name": prob["fullName"],
                "team": game[f"{side}Team"]["team"]["abbreviation"],
                "score": pscore
            })

        # --- Batter Score ---
        batter_stats = []
        for b in lineup:
            pid = b.get("id")
            bstats = lookup_stats(pid, b.get("name", ""),
                                  df_bat, "hitting") if pid else {}
            batter_stats.append(bstats)

            batters_list.append({
                "game_id": game_id,
                "side": side,
                "id": pid,
                "name": b.get("name", ""),
                "team": game[f"{side}Team"]["team"]["abbreviation"],
            })

        # Aggregate top-of-lineup hitter stats and score
        if batter_stats:
            avg_batter_features = {}
            for k in set().union(*[bs.keys() for bs in batter_stats]):
                try:
                    values = [float(bs[k]) for bs in batter_stats if k in bs]
                    avg_batter_features[k] = sum(values) / len(values)
                except Exception:
                    continue

            bscore = rating_calculator.compute_score(avg_batter_features)
            game[f"{side}_batter_score"] = bscore

    return pitchers, batters_list


if __name__ == '__main__':
    # allow passing a date in YYYY-MM-DD as first arg, otherwise use today
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        # date_str = datetime.now().strftime('%Y-%m-%d')
        date_str = "2025-06-26"

    # validate format (simple check)
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        logging.error("Date must be in YYYY-MM-DD format, got %r", date_str)
        sys.exit(1)

    games = fetch_schedule(date_str)

    all_pitchers, all_batters = [], []
    # for g in games:
    g = games[0]

    ps, bs = fetch_game_details(g)
    # attach the game-level grades onto each record
    for p in ps:
        p.update({
            'pitcher_score': g[f"{p['team']}_pitcher_score"],
            'batter_score':  g[f"{p['team']}_batter_score"],
            'away_rfi_grade': g['away_rfi_grade'],
            'home_rfi_grade': g['home_rfi_grade'],
            'nrfi_grade':     g['nrfi_grade']
        })
    for b in bs:
        b.update({
            'pitcher_score': g[f"{b['team']}_pitcher_score"],
            'batter_score':  g[f"{b['team']}_batter_score"],
            'away_rfi_grade': g['away_rfi_grade'],
            'home_rfi_grade': g['home_rfi_grade'],
            'nrfi_grade':     g['nrfi_grade']
        })
    all_pitchers.extend(ps)
    all_batters.extend(bs)

    # build CSV filename with the provided date
    csv_path = raw_data_dir / \
        f"mlb_combined_stats_{date_str.replace('-', '')}.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        headers = ['game_id', 'player_type', 'team', 'team_abbrev',
                   'id', 'name', 'position', 'order']
        grade_keys = ['pitcher_score',
                      'batter_score', 'away_rfi_grade', 'home_rfi_grade', 'nrfi_grade']
        stat_keys = sorted({k for rec in all_pitchers +
                           all_batters for k in rec['stats'].keys()})
        writer.writerow(headers + grade_keys + stat_keys)
        for rec in all_pitchers + all_batters:
            row = [rec.get(c, '') for c in headers]
            row += [rec.get(gk, 'NA') for gk in grade_keys]
            row += [rec['stats'].get(sk, 'NA') for sk in stat_keys]
            writer.writerow(row)

    logging.info(f"Saved CSV to {csv_path}")

    # ——— JSON stats summary alongside CSV ———
    json_stats_path = raw_data_dir / \
        f"mlb_daily_stats_summary_{date_str.replace('-', '')}.json"
    with open(json_stats_path, 'w', encoding='utf-8') as jf:
        json.dump(all_pitchers + all_batters, jf, indent=2)
    logging.info(f"Saved JSON stats summary to {json_stats_path}")

    # ——— Build a per‐game summary ———
    game_summary = []
    for g in games:
        away_team = g["teams"]["away"]["team"]["name"]
        home_team = g["teams"]["home"]["team"]["name"]
        away_abbrev = TEAM_CODES.get(
            g["teams"]["away"]["team"]["id"],
            ""
        )
        home_abbrev = TEAM_CODES.get(
            g["teams"]["home"]["team"]["id"],
            ""
        )
        away_pitch = g["teams"]["away"].get(
            "probablePitcher", {}).get("fullName", "")
        home_pitch = g["teams"]["home"].get(
            "probablePitcher", {}).get("fullName", "")

        # first 3 batters we just collected:
        # bs is the per‐game batters list returned by fetch_game_details()
        away_bats = [b['name'] for b in bs if b['team'] == "away"]
        home_bats = [b['name'] for b in bs if b['team'] == "home"]

        game_summary.append({
            "game_id":          g["gamePk"],
            "game_datetime":    g["gameDate"],
            "away_team":        away_team,
            "away_abbrev":      away_abbrev,
            "home_team":        home_team,
            "home_abbrev":      home_abbrev,
            "away_pitcher":     away_pitch,
            "home_pitcher":     home_pitch,
            "away_batters":     away_bats,
            "home_batters":     home_bats,
            "away_rfi_grade":   g.get("away_rfi_grade"),
            "home_rfi_grade":   g.get("home_rfi_grade"),
            "nrfi_grade":       g.get("nrfi_grade")
        })

    # ——— CSV game summary ———
    game_csv = raw_data_dir / \
        f"mlb_daily_game_summary_{date_str.replace('-', '')}.csv"
    with open(game_csv, 'w', newline='', encoding='utf-8') as gf:
        writer = csv.writer(gf)
        writer.writerow([
            "game_id", "game_datetime", "away_team", "away_abbrev", "home_team", "home_abbrev",
            "away_pitcher", "home_pitcher",
            "away_batters", "home_batters",
            "away_rfi_grade", "home_rfi_grade", "nrfi_grade"
        ])
        for r in game_summary:
            writer.writerow([
                r["game_id"], r["game_datetime"], r["away_team"], r["away_abbrev"], r["home_team"], r["home_abbrev"],
                r["away_pitcher"], r["home_pitcher"],
                ";".join(r["away_batters"]), ";".join(r["home_batters"]),
                r["away_rfi_grade"], r["home_rfi_grade"], r["nrfi_grade"],
            ])
    logging.info(f"Saved CSV game summary to {game_csv}")

    # ——— JSON game summary ———
    game_json = raw_data_dir / \
        f"mlb_daily_game_summary_{date_str.replace('-', '')}.json"
    with open(game_json, 'w', encoding='utf-8') as gj:
        json.dump(game_summary, gj, indent=2)
    logging.info(f"Saved JSON game summary to {game_json}")
