# run_mlb_rfi_pipeline_with_websheets_3.py

import sys
import logging
import json
import csv
from pathlib import Path
from datetime import datetime
import requests
import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

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


def lookup_stats(pid, name, df, group):
    try:
        url = f"https://statsapi.mlb.com/api/v1/people/{pid}/stats?stats=season&group={group}&season={SEASON}"
        r = requests.get(url)
        r.raise_for_status()
        splits = r.json().get('stats', [{}])[0].get('splits', [])
        if splits:
            return splits[0].get('stat', {})
    except Exception:
        pass
    if not df.empty:
        for col in ('mlbam_id', 'player_id'):
            if col in df.columns and pid in df[col].values:
                return df[df[col] == pid].iloc[0].dropna().to_dict()
    return {}


def get_boxscore_batters(game_id, side):
    try:
        data = requests.get(
            f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore").json()
        players = data['teams'][side]['players']
    except Exception:
        return []
    arr = []
    for p in players.values():
        ord = p.get('battingOrder')
        if ord and str(ord).isdigit():
            arr.append({
                'id': p['person']['id'],
                'name': p['person']['fullName'],
                'position': p.get('position', {}).get('abbreviation', ''),
                'order': int(ord)
            })
    return sorted(arr, key=lambda x: x['order'])[:3]


def fetch_schedule(date_str):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}&hydrate=teams(team,previewPlayers),probablePitcher"
    return requests.get(url).json().get("dates", [{}])[0].get("games", [])


def fetch_game_details(game):
    game_id = game.get("gamePk")
    team_stats = {"away": {}, "home": {}}
    pitchers, batters = [], []

    for side in ("away", "home"):
        info = game['teams'][side]
        team_id = info['team']['id']
        pitcher = info.get("probablePitcher")

        # ——— Pitcher ———
        if pitcher:
            pid = pitcher["id"]
            stats = lookup_stats(
                pid, pitcher["fullName"], df_pitch, 'pitching')
            pitchers.append({
                "game_id":     game_id,
                "player_type": "pitcher",
                "team":        side,
                "id":           pid,
                "name":        pitcher["fullName"],
                "position":    "P",
                "order":       None,
                "stats":       stats
            })
            team_stats[side]["pitcher"] = stats

        # ——— Batters: try boxscore, then previewPlayers ———
        lineup = get_boxscore_batters(game_id, side)
        if not lineup:
            # fall back to the schedule’s hydrated previewPlayers
            preview = info.get("previewPlayers", [])
            lineup = []
            for p in preview[:3]:
                lineup.append({
                    "id":       p['person']['id'],
                    "name":     p['person']['fullName'],
                    "position": p.get('position', {}).get('abbreviation', ''),
                    "order":    int(p.get('battingOrder', 0)) if p.get('battingOrder') else None
                })
        lineup_stats = []
        for b in lineup:
            stats = lookup_stats(b["id"], b["name"], df_bat, 'hitting')
            batters.append({
                "game_id":     game_id,
                "player_type": "batter",
                "team":        side,
                "id":           b["id"],
                "name":        b["name"],
                "position":    b["position"],
                "order":       b["order"],
                "stats":       stats
            })
            lineup_stats.append(stats)

        team_stats[side]["batters"] = lineup_stats

    # (compute pitcher_score, batter_score, attach to game, then return)

    # Compute RFI grade
    for side in ("away", "home"):
        pscore = pitcher_score(team_stats[side].get("pitcher", {}))
        bat_feats = team_stats[side].get("batters", [])
        if bat_feats:
            obp_vs = sum(float(b.get("obp", 0))
                         for b in bat_feats) / len(bat_feats)
            hr_rate = sum(float(b.get("homeRuns", 0))
                          for b in bat_feats) / len(bat_feats)
            f1_obp = sum(float(b.get("firstInningOBP", 0))
                         for b in bat_feats) / len(bat_feats)
        else:
            obp_vs = hr_rate = f1_obp = 0

        bscore = batter_score({
            "obp_vs":        obp_vs,
            "hr_rate":       hr_rate,
            "recent_f1_obp": f1_obp
        })

        game[f"{side}_pitcher_score"] = pscore
        game[f"{side}_batter_score"] = bscore
        game[f"{side}_rfi_grade"] = WEIGHTS["pitcher"] * pscore \
            + WEIGHTS["batter"] * bscore

    game["nrfi_grade"] = game["away_rfi_grade"]
    return pitchers, batters


if __name__ == '__main__':
    # allow passing a date in YYYY-MM-DD as first arg, otherwise use today
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        date_str = datetime.now().strftime('%Y-%m-%d')

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
                'rfi_grade':     g[f"{p['team']}_rfi_grade"],
                'nrfi_grade':    g["nrfi_grade"]
            })
        for b in bs:
            b.update({
                'pitcher_score': g[f"{b['team']}_pitcher_score"],
                'batter_score':  g[f"{b['team']}_batter_score"],
                'rfi_grade':     g[f"{b['team']}_rfi_grade"],
                'nrfi_grade':    g["nrfi_grade"]
            })
        all_pitchers.extend(ps)
        all_batters.extend(bs)

    # build CSV filename with the provided date
    csv_path = RAW_DATA_DIR / \
        f"mlb_combined_stats_{date_str.replace('-', '')}.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        headers = ['game_id', 'player_type', 'team',
                   'id', 'name', 'position', 'order']
        grade_keys = ['pitcher_score',
                      'batter_score', 'rfi_grade', 'nrfi_grade']
        stat_keys = sorted({k for rec in all_pitchers +
                           all_batters for k in rec['stats'].keys()})
        writer.writerow(headers + grade_keys + stat_keys)
        for rec in all_pitchers + all_batters:
            row = [rec.get(c, '') for c in headers]
            row += [rec.get(gk, '') for gk in grade_keys]
            row += [rec['stats'].get(sk, '') for sk in stat_keys]
            writer.writerow(row)

    logging.info(f"Saved CSV to {csv_path}")
