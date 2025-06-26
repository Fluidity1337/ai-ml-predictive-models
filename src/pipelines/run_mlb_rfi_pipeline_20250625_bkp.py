# run_mlb_rfi_pipeline_with_websheets_3.py

import sys
import logging
import json
import csv
from pathlib import Path
from datetime import datetime
import requests
import pandas as pd

# Try pybaseball for season stats
try:
    from pybaseball import batting_stats, pitching_stats
    HAS_PYBASEBALL = True
except ImportError:
    HAS_PYBASEBALL = False
    logging.warning("pybaseball not available, season stats may be incomplete")

# Load config
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

FEATURES_CONFIG_PATH = Path(config["mlb_rfi_model_features_config_path"])
with open(FEATURES_CONFIG_PATH, "r", encoding="utf-8") as f:
    features_cfg = json.load(f)

ROOT = Path(config["root_path"]).resolve()
RAW_DATA_DIR = Path(config["mlb_test_output_path"]).resolve()
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Logging setup
date_now = datetime.now().strftime('%Y-%m-%d')
log_file = RAW_DATA_DIR / f"mlb_pipeline_{date_now}.log"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(), logging.FileHandler(
        log_file, mode='a', encoding='utf-8')]
)
logging.info(f"Logging to console and file: {log_file}")

# Determine date to process
date_str = sys.argv[1] if len(
    sys.argv) > 1 else datetime.now().strftime('%Y-%m-%d')
SEASON = int(date_str.split('-')[0])

# build a map of team IDs → 3-letter club codes
teams_resp = requests.get(
    f"https://statsapi.mlb.com/api/v1/teams?season={SEASON}&sportId=1"
)
teams_resp.raise_for_status()
TEAM_CODES = {
    t['id']: t.get('abbreviation') or t.get('triCode', '')
    for t in teams_resp.json().get('teams', [])
}

# Load season stats


def load_stats():
    df_pitch = pd.DataFrame()
    df_bat = pd.DataFrame()
    if HAS_PYBASEBALL:
        try:
            logging.info(f"Loading {SEASON} pitching stats via pybaseball…")
            df_pitch = pitching_stats(SEASON)
        except Exception as e:
            logging.error(f"pybaseball pitching_stats error: {e}")
        try:
            logging.info(f"Loading {SEASON} batting stats via pybaseball…")
            df_bat = batting_stats(SEASON)
        except Exception as e:
            logging.error(f"pybaseball batting_stats error: {e}")
    return df_pitch, df_bat


DF_PITCH, DF_BAT = load_stats()

WEIGHTS = features_cfg["weights"]
BOUNDS = features_cfg["bounds"]

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


def minmax_scale(x, lo, hi):
    if x is None:
        return 0.5
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def pitcher_score(stats):
    b = BOUNDS

    # helper: coerce to float, or fall back to default
    def safe(key, default):
        try:
            v = stats.get(key, None)
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    # midpoint of a bound range
    def mid(low, high):
        return (low + high) / 2

    # debug log so you can inspect what came in
    print(f"[DEBUG pitcher_score] stats = {stats!r}")

    # pull every value through safe()
    era = safe("era",            mid(*b["era"]))
    whip = safe("whip",           mid(*b["whip"]))
    so9 = safe("strikeOutsPer9Inn", 0.0) / 9.0
    bb9 = safe("baseOnBallsPer9Inn", 0.0) / 9.0
    f1era = safe("firstInningEra", mid(*b["f1_era"]))

    # build your feature scores
    scores = {
        "era":     1.0 - minmax_scale(era,   *b["era"]),
        "whip":    1.0 - minmax_scale(whip,  *b["whip"]),
        "k_rate":  minmax_scale(so9,        *b["k_rate"]),
        "bb_rate": 1.0 - minmax_scale(bb9,   *b["bb_rate"]),
        "f1_era":  1.0 - minmax_scale(f1era, *b["f1_era"]),
    }

    # average them
    return sum(scores.values()) / len(scores)


def batter_score(feats):
    b = BOUNDS
    f = {
        "obp_vs":        feats["obp_vs"],
        "hr_rate":       minmax_scale(feats["hr_rate"], *b["hr_rate"]),
        "recent_f1_obp": feats["recent_f1_obp"]
    }
    return sum(f.values()) / len(f)


# Utility functions
def get_boxscore_batters(game_id, side):
    url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore"
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
            'position': pos,
            'order': p.get('battingOrder')
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
    if pid is None:
        logging.debug(
            f"[LookupStats]  → skipping lookup for {name!r} because pid is None")
        return {}
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
            stat = splits[0].get('stat', {})

        logging.debug(f"[LookupStats]  → got {len(stat)} fields")
        return stat

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
            return splits2[0].get('stat', {})
    except Exception:
        pass
    # 3) pybaseball fallback
    if HAS_PYBASEBALL and not df.empty:
        for col in ('mlbam_id', 'player_id'):
            if col in df.columns and pid in df[col].values:
                return df[df[col] == pid].iloc[0].dropna().to_dict()
    return {}

# Main game detail fetch and scoring


def fetch_game_details(game: dict) -> tuple[list, list]:
    game_id = game.get('gamePk')
    team_stats = {'away': {}, 'home': {}}
    pitchers, batters_list = [], []

    for side in ('away', 'home'):
        # initialize default pitcher and batter scores to avoid KeyError
        game[f"{side}_pitcher_score"] = 0.0
        game[f"{side}_batter_score"] = 0.0
        info = game['teams'][side]
        team_id = info['team']['id']
        # look up the 3-letter code from our pre-fetched map
        team_abbrev = TEAM_CODES.get(team_id, '')

        # Probable Pitcher
        prob = info.get('probablePitcher')
        if prob:
            pstats = lookup_stats(
                prob['id'], prob['fullName'], df_pitch, 'pitching')
            pscore = pitcher_score(pstats)
            game[f"{side}_pitcher_score"] = pscore
            pitchers.append({
                'game_id': game_id,
                'player_type': 'pitcher',
                'team': side,
                'team_abbrev': team_abbrev,
                'id': prob['id'],
                'name': prob['fullName'],
                'position': 'P',
                'order': None,
                'stats': pstats
            })
            team_stats[side]['pitcher'] = pstats

        # Batters fallback
        lineup = get_boxscore_batters(game_id, side)
        if len(lineup) < 3:
            lineup = get_live_batters(game_id, side)
        if len(lineup) < 3:
            lineup = get_schedule_preview_batters(game, side)
        if len(lineup) < 3:
            lineup = get_roster_batters(team_id)
        if len(lineup) < 3:
            lineup = get_season_leaders()
        lineup = lineup[:3]

        feats = []
        for b in lineup:
            pid = b.get('id')
            if pid:
                bstats = lookup_stats(pid, b.get(
                    'name', ''), df_bat, 'hitting')
            else:
                logging.debug(
                    f"[fetch_game_details] no ID for {b.get('name', 'unknown')}, assigning empty stats")
                bstats = {}
            feats.append(bstats)
            batters_list.append({
                'game_id': game_id,
                'player_type': 'batter',
                'team': side,
                'team_abbrev': team_abbrev,
                'id': pid,
                'name': b.get('name'),
                'position': b.get('position'),
                'order': b.get('order'),
                'stats': bstats
            })
        team_stats[side]['batters'] = feats

        # Batter score
        bscore = 0.0
        if feats:
            obp_vs = sum(float(x.get('obp', 0)) for x in feats) / len(feats)
            hr_rate = sum(float(x.get('homeRuns', 0))
                          for x in feats) / len(feats)
            f1_obp = sum(float(x.get('firstInningOBP', 0))
                         for x in feats) / len(feats)
            bscore = batter_score(
                {'obp_vs': obp_vs, 'hr_rate': hr_rate, 'recent_f1_obp': f1_obp})
            game[f"{side}_batter_score"] = bscore

    # Compute RFI grades
    for side in ('away', 'home'):
        p = game.get(f"{side}_pitcher_score", 0.0)
        b = game.get(f"{side}_batter_score", 0.0)
        raw = WEIGHTS['pitcher'] * p + WEIGHTS['batter'] * b
        game[f"{side}_rfi_grade"] = round(raw * 10, 1)

    away_g = game.get('away_rfi_grade', 0)
    home_g = game.get('home_rfi_grade', 0)
    game['nrfi_grade'] = round((away_g + home_g) / 2, 1)

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
    for g in games:
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
    csv_path = RAW_DATA_DIR / \
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
            row += [rec.get(gk, '') for gk in grade_keys]
            row += [rec['stats'].get(sk, '') for sk in stat_keys]
            writer.writerow(row)

    logging.info(f"Saved CSV to {csv_path}")

    # ——— JSON stats summary alongside CSV ———
    json_stats_path = RAW_DATA_DIR / \
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
            "away_rfi_grade":   g["away_rfi_grade"],
            "home_rfi_grade":   g["home_rfi_grade"],
            "nrfi_grade":       g["nrfi_grade"],
        })

    # ——— CSV game summary ———
    game_csv = RAW_DATA_DIR / \
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
    game_json = RAW_DATA_DIR / \
        f"mlb_daily_game_summary_{date_str.replace('-', '')}.json"
    with open(game_json, 'w', encoding='utf-8') as gj:
        json.dump(game_summary, gj, indent=2)
    logging.info(f"Saved JSON game summary to {game_json}")
