#!/usr/bin/env python3
from datetime import datetime as _dt
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

# Load configuration


def load_config():
    config_path = Path.cwd() / 'config.json'
    if not config_path.exists():
        logging.error(f"config.json not found at {config_path}")
        sys.exit(1)
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


config = load_config()

# Define paths
ROOT = Path(config['root_path']).resolve()
RAW_DATA_DIR = Path(config['mlb_test_output_path']).resolve()
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

date_suffix = _dt.now().strftime('%Y%m%d')
JSON_PATH = RAW_DATA_DIR / f"mlb_daily_summary_{date_suffix}.json"
HTML_PATH = RAW_DATA_DIR / f"mlb_mlh_rfi_websheet_{date_suffix}.html"
CSV_PATH = RAW_DATA_DIR / f"mlb_daily_summary_{date_suffix}.csv"
# Generate HTML report


def generate_html(games):
    """
    Generate the HTML websheet: two rows per game, shared Game Time cell,
    CamelCase headers, center-aligned, with a borderless Vs column.
    """
    html = f"""<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset='UTF-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1.0'/>
  <title>Moneyline Hacks - RFI Model</title>
  <link href='https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css' rel='stylesheet'>
  <style>
    body {{ background-color:#0f172a; color:#e2e8f0; font-family:'Segoe UI',sans-serif; }}
    .title-highlight {{ background:linear-gradient(to right,#34d399,#06b6d4);
                       -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
    table {{ border-collapse: collapse; width:100%; }}
    th, td {{ padding:0.5rem; text-align:center; }}
    th, td:not(.borderless) {{ border:1px solid #fff; }}
  </style>
</head>
<body class='p-6'>
  <div class='text-center mb-6'>
    <h1 class='text-4xl font-extrabold title-highlight'>Moneyline Hacks</h1>
    <p class='text-gray-400'>Run First Inning (RFI) Model — {_dt.now().strftime('%B %d')}</p>
  </div>
  <div class='overflow-auto max-w-5xl mx-auto'>
    <table class='min-w-full text-gray-300 text-sm'>
      <thead class='bg-gray-900 text-gray-100 uppercase text-xs'>
        <tr>
          <th class='px-4 py-2'>Game Time</th>
          <th class='px-4 py-2'>Pitching Team</th>
          <th class='px-4 py-2'>Projected Starter</th>
          <th class='px-4 py-2 borderless'>Vs</th>
          <th class='px-4 py-2'>Team To NRFI</th>
          <th class='px-4 py-2'>Team Grade</th>
          <th class='px-4 py-2'>NRFI Grade</th>
          <th class='px-4 py-2'>Recommendation</th>
        </tr>
      </thead>
      <tbody>
"""
    for game in games:
        # format the game time
        iso = game.get('gameDate', '')
        if iso:
            try:
                dt = _dt.fromisoformat(iso.replace('Z', ''))
                time_str = dt.strftime('%I:%M %p ET').lstrip('0')
            except:
                time_str = '-'
        else:
            time_str = '-'

        away = game['teams']['away']
        home = game['teams']['home']

        # dummy placeholders
        tg_away = "0.0"
        tg_home = "0.0"
        nrfi_grade = "TBD"
        rec = "TBD"

        # Away row (lighter gray on left 5 cols, lighter gray on RHS spans)
        html += (
            "<tr>"
            f"<td class='px-4 py-2 bg-gray-700' rowspan='2'>{time_str}</td>"
            f"<td class='px-4 py-2 bg-gray-700'>{away['team']['name']}</td>"
            f"<td class='px-4 py-2 bg-gray-700'>{away.get('probablePitcher',{{}}).get('fullName','-')}</td>"
            f"<td class='px-4 py-2 bg-gray-700 borderless'>vs</td>"
            f"<td class='px-4 py-2 bg-gray-700'>{home['team']['name']}</td>"
            f"<td class='px-4 py-2 bg-gray-700'>{tg_away}</td>"
            f"<td class='px-4 py-2 bg-gray-700' rowspan='2'>{nrfi_grade}</td>"
            f"<td class='px-4 py-2 bg-gray-700' rowspan='2'>{rec}</td>"
            "</tr>\n"
        )

        # Home row (darker gray on left 5 cols, lighter gray on RHS already spanned)
        html += (
            "<tr>"
            f"<td class='px-4 py-2 bg-gray-800'>{home['team']['name']}</td>"
            f"<td class='px-4 py-2 bg-gray-800'>{home.get('probablePitcher',{{}}).get('fullName','-')}</td>"
            f"<td class='px-4 py-2 bg-gray-800 borderless'>vs</td>"
            f"<td class='px-4 py-2 bg-gray-800'>{away['team']['name']}</td>"
            f"<td class='px-4 py-2 bg-gray-800'>{tg_home}</td>"
            "</tr>\n"
        )

    html += (
        "      </tbody>\n"
        "    </table>\n"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
    )
    HTML_PATH.write_text(html)
    logging.info(f"Wrote HTML to {HTML_PATH}")


# Fetch game details with fallbacks


def fetch_game_details(game):
    # existing logic...
    pass


if __name__ == '__main__':
    # Example: load games from JSON and generate HTML
    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        games = data.get('games', [])
    except Exception as e:
        logging.error(f"Failed to load games JSON: {e}")
        sys.exit(1)
    generate_html(games)
