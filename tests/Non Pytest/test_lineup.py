import sys
import logging
from datetime import datetime

# make sure these come from your pipeline module
from pipelines.run_mlb_rfi_pipeline_20250625 import fetch_schedule, TEAM_CODES, get_schedule_preview_batters

# configure logging if not already done
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


def test_dodgers_preview(date_str: str):
    """
    Logs the first three Dodgers hitters on the given date.
    """
    games = fetch_schedule(date_str)
    for g in games:
        for side in ("away", "home"):
            team_id = g["teams"][side]["team"]["id"]
            if TEAM_CODES.get(team_id) == "LAD":
                hitters = get_schedule_preview_batters(g, side)
                logging.info(
                    "Dodgers (%s) first 3 hitters on %s:", side, date_str)
                for h in hitters:
                    logging.info("  Spot %s: %s", h["order"], h["name"])
                return hitters
    logging.warning("No Dodgers game found on %s", date_str)
    return []


if __name__ == "__main__":
    # allow passing a date; default to today if none given
    date_str = sys.argv[1] if len(
        sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    # for your specific case you could also hard-code:
    date_str = "2025-06-26"
    hitters = test_dodgers_preview(date_str)
    if hitters:
        print(f"Retrieved {len(hitters)} hitters for LAD on {date_str}.")
