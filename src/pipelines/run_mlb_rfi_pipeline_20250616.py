#!/usr/bin/env python3
from datetime import datetime as _dt
import sys
import logging
import json
import csv
from pathlib import Path
import requests
import pandas as pd

# ─── Setup logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# ─── Load main config once ─────────────────────────────────────────────────
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"
if not CONFIG_PATH.exists():
    logging.error(f"config.json not found at {CONFIG_PATH}")
    sys.exit(1)

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

# ─── Load features (weights & bounds) config ───────────────────────────────
FEATURES_CFG_PATH = Path(config["mlb_rfi_model_features_config_path"])
if not FEATURES_CFG_PATH.exists():
    logging.error(f"Features config not found at {FEATURES_CFG_PATH}")
    sys.exit(1)

with open(FEATURES_CFG_PATH, "r", encoding="utf-8") as f:
    features_cfg = json.load(f)

WEIGHTS = features_cfg["weights"]
BOUNDS = features_cfg["bounds"]

# ─── Define paths & filenames ──────────────────────────────────────────────
ROOT = Path(config["root_path"]).resolve()
RAW_DATA_DIR = Path(config["mlb_raw_data_path"]).resolve()
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

date_str = _dt.now().strftime("%Y-%m-%d")
date_suffix = date_str.replace("-", "")

JSON_INPUT = RAW_DATA_DIR / f"mlb_daily_summary_{date_suffix}.json"
JSON_OUTPUT = RAW_DATA_DIR / \
    f"mlb_daily_summary_{date_suffix}.json"  # enriched
CSV_OUTPUT = RAW_DATA_DIR / f"mlb_daily_summary_{date_suffix}.csv"
HTML_OUTPUT = RAW_DATA_DIR / f"mlb_mlh_rfi_websheet_{date_suffix}.html"

# ─── Optional: load season stats via pybaseball ──────────────────────────────
SEASON = int(_dt.now().strftime("%Y"))
DF_PITCH, DF_BAT = pd.DataFrame(), pd.DataFrame()
try:
    from pybaseball import pitching_stats, batting_stats
    logging.info(f"Loading {SEASON} season stats via pybaseball")
    DF_PITCH = pitching_stats(SEASON)
    DF_BAT = batting_stats(SEASON)
except ImportError:
    logging.warning("pybaseball unavailable; continuing without it")
except Exception as e:
    logging.error(f"pybaseball load error: {e}")

# ─── Helpers: feature scaling & scoring ─────────────────────────────────────


def minmax_scale(x, lo, hi):
    """
    Clamp x to [lo,hi], scale into [0,1].
    If x is non‐numeric or None, returns 0.5 (neutral).
    """
    try:
        x_val = float(x)
    except (TypeError, ValueError):
        return 0.5
    # avoid division by zero just in case
    span = hi - lo if hi != lo else 1.0
    return max(0.0, min(1.0, (x_val - lo) / span))


def pitcher_score(stats: dict) -> float:
    b = BOUNDS
    feats = {
        "era":    1 - minmax_scale(stats.get("era"),                 *b["era"]),
        "whip":   1 - minmax_scale(stats.get("whip"),                *b["whip"]),
        "k_rate": minmax_scale(stats.get("strikeOutsPer9Inn", 0)/9,  *b["k_rate"]),
        "bb_rate": 1 - minmax_scale(stats.get("baseOnBallsPer9Inn", 0)/9, *b["bb_rate"]),
        "f1_era": 1 - minmax_scale(stats.get("firstInningEra"),      *b["f1_era"]),
    }
    return sum(feats.values()) / len(feats)


def batter_score(feats: dict) -> float:
    b = BOUNDS
    buckets = {
        "obp_vs":        feats.get("obp_vs", 0),
        "hr_rate":       minmax_scale(feats.get("hr_rate", 0), *b["hr_rate"]),
        "recent_f1_obp": feats.get("recent_f1_obp", 0),
    }
    return sum(buckets.values()) / len(buckets)


def compute_nrfi_score(p_stats, b_feats, park=0.5, weather=0.5, team_pct=0.5, opp_pct=0.5):
    """Combine all four buckets with configured weights."""
    p = pitcher_score(p_stats)
    b = batter_score(b_feats)
    pk = (park + weather) / 2
    tm = (team_pct + opp_pct) / 2
    w = WEIGHTS
    return w["pitcher"]*p + w["batter"]*b + w["park"]*pk + w["team"]*tm

# ─── Fetch & parse functions (unchanged) ──────────────────────────────────


def fetch_schedule(date_str: str) -> list:
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}&hydrate=probablePitcher"
    r = requests.get(url)
    if r.status_code != 200:
        logging.error(f"Failed to fetch schedule for {date_str}")
        return []
    return r.json().get("dates", [{}])[0].get("games", [])


def fetch_boxscore(game_id: int) -> dict:
    base = f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore"
    r = requests.get(base)
    if r.status_code == 200:
        return r.json()
    logging.info(f"No live boxscore for {game_id}, trying preview")
    r2 = requests.get(f"{base}?mode=preview")
    return r2.json() if r2.status_code == 200 else {}


def fetch_player_stats(pid: int) -> dict:
    # 1) MLB statsapi
    url = f"https://statsapi.mlb.com/api/v1/people/{pid}/stats?stats=season&group=pitching"
    try:
        r = requests.get(url)
        r.raise_for_status()
        splits = r.json().get("stats", [{}])[0].get("splits", [])
        if splits:
            return splits[0].get("stat", {})
    except:
        pass
    # 2) Fallback to hydrated people endpoint
    try:
        url2 = f"https://statsapi.mlb.com/api/v1/people/{pid}?hydrate=stats(group=pitching,type=season,season={SEASON})"
        r2 = requests.get(url2)
        r2.raise_for_status()
        ppl = r2.json().get("people", [{}])[0]
        splits = ppl.get("stats", [{}])[0].get("splits", [])
        if splits:
            return splits[0].get("stat", {})
    except:
        pass
    # 3) pybaseball fallback
    if not DF_PITCH.empty and pid in DF_PITCH.get("player_id", []):
        return DF_PITCH[DF_PITCH["player_id"] == pid].iloc[0].dropna().to_dict()
    return {}


def parse_game_data(game: dict, box: dict) -> tuple[list, list]:
    pitchers, batters = [], []
    gid = game["gamePk"]
    for side in ("away", "home"):
        team = game["teams"][side]
        prob = team.get("probablePitcher")
        if prob:
            stats = fetch_player_stats(prob["id"])
            pitchers.append({
                "game_id": gid, "team": side,
                "id": prob["id"], "name": prob["fullName"],
                "stats": stats
            })
        else:
            logging.warning(f"No probable pitcher for {side} in game {gid}")
        players = box.get("teams", {}).get(side, {}).get("players", {})
        lineup = []
        for pid, pdat in players.items():
            ord = pdat.get("battingOrder")
            if ord and str(ord).isdigit() and int(ord) <= 300:
                st = pdat.get("stats", {}).get("batting", {})
                lineup.append({
                    "game_id": gid, "team": side,
                    "id": pdat["person"]["id"],
                    "name": pdat["person"]["fullName"],
                    "position": pdat.get("position", {}).get("abbreviation", ""),
                    "order":   int(ord),
                    "stats": {
                        "obp":           st.get("obp"),
                        "homeRuns":      st.get("homeRuns"),
                        "firstInningOBP": st.get("firstInningOBP")
                    }
                })
        line = sorted(lineup, key=lambda x: x["order"])[:3]
        batters.extend(line)
    return pitchers, batters

# ─── HTML generator (unchanged) ─────────────────────────────────────────────


def generate_html(games: list):
    """
    Builds a Tailwind‐styled websheet grouped by game (two rows each),
    center-aligned, CamelCase headers, with your color bands.
    """
    # … your existing generate_html implementation …
    pass  # <— keep your implementation here


# ─── Main pipeline ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.info(f"Starting pipeline for {date_str}")

    # 1) Fetch schedule
    games = fetch_schedule(date_str)
    if not games:
        logging.warning("No games found; exiting.")
        sys.exit(0)

    # 2) Fetch details
    allp, allb = [], []
    for game in games:
        ps, bs = parse_game_data(game, fetch_boxscore(game["gamePk"]))
        if not ps:
            logging.warning(f"No pitchers for game {game['gamePk']}")
        if not bs:
            logging.warning(f"No batters for game {game['gamePk']}")
        allp.extend(ps)
        allb.extend(bs)

    # 3) Enrich each game with scores & grades
    for game in games:
        for side in ("away", "home"):
            stats = next((p["stats"] for p in allp
                          if p["game_id"] == game["gamePk"] and p["team"] == side),
                         {})
            psc = pitcher_score(stats)

            lineup = [b["stats"] for b in allb
                      if b["game_id"] == game["gamePk"] and b["team"] == side]
            if lineup:
                # coerce None to 0.0, cast strings to float if necessary
                vals_obp = [(float(b["obp"]) if b.get("obp")
                             is not None else 0.0) for b in lineup]
                vals_hr = [(float(b["homeRuns"]) if b.get("homeRuns")
                            is not None else 0.0) for b in lineup]
                vals_f1 = [(float(b["firstInningOBP"]) if b.get("firstInningOBP") is not None else 0.0)
                           for b in lineup]

                obp_vs = sum(vals_obp) / len(vals_obp)
                hr_rate = sum(vals_hr) / len(vals_hr)
                recent_f1_obp = sum(vals_f1) / len(vals_f1)

                feats = {
                    "obp_vs":        obp_vs,
                    "hr_rate":       hr_rate,
                    "recent_f1_obp": recent_f1_obp
                }
            else:
                feats = {"obp_vs": 0.0, "hr_rate": 0.0, "recent_f1_obp": 0.0}

            bsc = batter_score(
                {"obp_vs": obp_vs, "hr_rate": hr_rate, "recent_f1_obp": recent_f1_obp})

            # store
            game[f"{side}_pitcher_score"] = psc
            game[f"{side}_batter_score"] = bsc
            game[f"{side}_rfi_grade"] = WEIGHTS["pitcher"] * \
                psc + WEIGHTS["batter"]*bsc

        # game-level NRFI uses away side’s first-inning odds
        game["nrfi_grade"] = game["away_rfi_grade"]

    # 4) Write enriched JSON
    with open(JSON_OUTPUT, "w", encoding="utf-8") as f:
        json.dump({"date": date_str, "games": games}, f, indent=2)
    logging.info(f"Saved enriched JSON to {JSON_OUTPUT}")

    # 5) Write enriched CSV
    headers = [
        "Date", "GameID", "GameTime",
        "AwayTeam", "AwayPitcher", "AwayPitcherScore", "AwayBatterScore", "AwayRFIGrade",
        "HomeTeam", "HomePitcher", "HomePitcherScore", "HomeBatterScore", "HomeRFIGrade",
        "NRFIGrade"
    ]
    with open(CSV_OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for g in games:
            iso = g.get("gameDate", "")
            try:
                tm = _dt.fromisoformat(iso.replace("Z", ""))
                tm_str = tm.strftime("%I:%M %p ET").lstrip("0")
            except:
                tm_str = "-"
            w.writerow([
                date_str,
                g["gamePk"],
                tm_str,
                g["teams"]["away"]["team"]["name"],
                g["teams"]["away"].get(
                    "probablePitcher", {}).get("fullName", "-"),
                g["away_pitcher_score"],
                g["away_batter_score"],
                g["away_rfi_grade"],
                g["teams"]["home"]["team"]["name"],
                g["teams"]["home"].get(
                    "probablePitcher", {}).get("fullName", "-"),
                g["home_pitcher_score"],
                g["home_batter_score"],
                g["home_rfi_grade"],
                g["nrfi_grade"],
            ])
    logging.info(f"Saved enriched CSV to {CSV_OUTPUT}")

    # 6) Generate HTML
    generate_html(games)
    logging.info(f"HTML websheet written to {HTML_OUTPUT}")
