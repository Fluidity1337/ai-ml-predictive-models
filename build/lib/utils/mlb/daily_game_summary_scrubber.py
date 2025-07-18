#!/usr/bin/env python3
"""
daily_game_summary_scrubber.py

Reads an MLB daily game summary JSON, adds 'home_team_abbrev' and 'away_team_abbrev'
to each record based on a config file, and writes out a new JSON.
"""

import json
import logging
import logging.config
from utils.config_loader import load_config
import os
import sys

# -----------------------------------------------------------------------------
# Configure logging
# -----------------------------------------------------------------------------
cfg = load_config()
logging.config.dictConfig(cfg["logging"])

# -----------------------------------------------------------------------------
# Load team‐abbrev mapping from external config (JSON)
# -----------------------------------------------------------------------------
TEAM_ABBREVS_CONFIG_PATH = os.getenv(
    "ABBREV_CONFIG", "config/mlb_team_abbrevs.json")

try:
    with open(TEAM_ABBREVS_CONFIG_PATH) as cfg:
        cfg_data = json.load(cfg)
        TEAM_ABBREVS = cfg_data["team_abbreviations"]
    logging.info(
        f"Loaded {len(TEAM_ABBREVS)} team abbreviations from {TEAM_ABBREVS_CONFIG_PATH}")
except Exception as e:
    logging.error(f"Error loading config '{TEAM_ABBREVS_CONFIG_PATH}': {e}")
    sys.exit(1)


def load_json(path):
    """Load JSON file from disk."""
    with open(path, 'r') as f:
        return json.load(f)


def save_json(data, path):
    """Save data as pretty‐printed JSON."""
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    logging.info(f"Wrote output to {path}")


def add_abbrevs(records):
    """Inject abbrev fields into each game record."""
    for rec in records:
        away = rec.get("away_team", "")
        home = rec.get("home_team", "")

        # Lookup abbreviations; default to empty string if missing
        rec["away_team_abbrev"] = TEAM_ABBREVS.get(away, "")
        rec["home_team_abbrev"] = TEAM_ABBREVS.get(home, "")
    return records


def main():
    if len(sys.argv) != 3:
        logging.error(
            "Usage: python add_abbrevs.py <input.json> <output.json>")
        sys.exit(1)

    input_path, output_path = sys.argv[1], sys.argv[2]

    logging.info(f"Loading games from {input_path}")
    games = load_json(input_path)

    logging.info("Adding team abbreviations...")
    games = add_abbrevs(games)

    save_json(games, output_path)
    logging.info(f"Processed {len(games)} records.")


if __name__ == "__main__":
    main()
