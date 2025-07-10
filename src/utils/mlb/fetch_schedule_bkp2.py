from requests.exceptions import HTTPError
from unittest.mock import patch
import unittest
import requests
import logging
from datetime import datetime
import argparse
import yaml
import os
import json

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
file_handler = logging.FileHandler('fetch_schedule.log')
file_handler.setLevel(logging.DEBUG)

logger.addHandler(console_handler)
logger.addHandler(file_handler)


def fetch_schedule(date_str: str) -> list:
    """
    Fetch MLB schedule for a given date.
    Returns a tuple (games_list, raw_json).
    """
    url = (
        f"https://statsapi.mlb.com/api/v1/schedule?"
        f"sportId=1&date={date_str}"
    )
    try:
        response = requests.get(url)
        logger.debug(f"Received response status: {response.status_code}")
        response.raise_for_status()
        raw = response.json()
    except Exception as e:
        logger.error(f"Error fetching schedule: {e}", exc_info=True)
        print(f"Error fetching schedule: {e}")
        return [], {}

    dates = raw.get("dates", [])
    if not dates:
        logger.info(f"No games found for date: {date_str}")
        return [], raw

    games = dates[0].get("games", [])
    logger.debug(f"Found {len(games)} games for date: {date_str}")
    print(f"Fetched {len(games)} games for {date_str}")
    # return games, raw
    return games


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch MLB schedule or run tests.")
    parser.add_argument(
        "date",
        nargs="?",
        default=datetime.today().strftime("%Y-%m-%d"),
        help="Date in YYYY-MM-DD format"
    )
    parser.add_argument(
        "--save-json",
        action="store_true",
        help="Save raw JSON to the directory configured in config.yaml under [mlb_data][game_schedule]"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run unit tests"
    )
    args = parser.parse_args()

    if args.test:
        unittest.main(argv=[__file__])
    else:
        # games, raw = fetch_schedule(args.date)
        games = fetch_schedule(args.date)
        if args.save_json:
            try:
                with open("config.yaml") as f:
                    cfg = yaml.safe_load(f)
                out_dir = cfg["mlb_data"]["game_schedule"]
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, f"schedule_{args.date}.json")
                with open(out_path, "w") as jf:
                    json.dump(raw, jf, indent=2)
                logger.info(f"Saved raw schedule JSON to {out_path}")
                print(f"🚀 Saved raw JSON to {out_path}")
            except Exception as e:
                logger.error(f"Error saving JSON: {e}", exc_info=True)
                print(f"Error saving JSON: {e}")
        print(games)
