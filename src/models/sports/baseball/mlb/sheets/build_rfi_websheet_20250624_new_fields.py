#!/usr/bin/env python3
import sys
import logging
import json
from pathlib import Path
from datetime import datetime as _dt
from zoneinfo import ZoneInfo

# Load config.json from project root of this script
CONFIG_PATH = Path(__file__).resolve().parents[6] / "config.json"
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    config = json.load(f)

# Define absolute project root from config
ROOT = Path(config["root_path"]).resolve()

# Raw data directory, relative to ROOT if not absolute
RAW_DATA_DIR = Path(config.get("mlb_test_output_path", "./output")).resolve()
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Determine JSON and HTML filenames
# JSON_PATH must be defined before deriving date_suffix
JSON_FILENAME = config.get(
    # "json_filename", f"mlb_daily_game_summary_{_dt.now().strftime('%Y%m%d')}.json"
    "json_filename", f"mlb_daily_game_summary_20250625.json"
)
JSON_PATH = RAW_DATA_DIR / JSON_FILENAME
HTML_FILENAME = config.get(
    "html_filename", f"mlb_mlh_rfi_websheet_{JSON_PATH.stem.split('_')[-1]}.html"
)
HTML_PATH = RAW_DATA_DIR / HTML_FILENAME

# Derive title_date from JSON filename suffix
date_suffix = JSON_PATH.stem.split('_')[-1]
try:
    title_date = _dt.strptime(date_suffix, '%Y%m%d').strftime('%B %d, %Y')
except Exception as e:
    logging.error(f"Error parsing date_suffix '{date_suffix}': {e}")
    title_date = date_suffix

# Logging setup
date_now = _dt.now().strftime("%Y-%m-%d")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logging.info(f"Project root: {ROOT}")
logging.info(f"Raw data dir: {RAW_DATA_DIR}")
logging.info(f"JSON path: {JSON_PATH} (exists={JSON_PATH.exists()})")
logging.info(f"HTML path: {HTML_PATH}")
logging.info(f"Title date: {title_date}")

# Color thresholds


def grade_color(score):
    try:
        s = float(score)
        """
        if s <= 3:
            return 'bg-red-600 text-white'
        if s < 4:
            return 'bg-red-300 text-black'
        """
        if s <= 6:
            return 'bg-gray-500 text-white'
        if s < 7:
            return 'bg-green-300 text-black'
        return 'bg-green-600 text-white'
    except:
        return ''

# Recommendation logic


def recommendation(nrfi):
    try:
        s = float(nrfi)
        """
        if s <= 3:
            return 'YRFI'
        if s < 4:
            return 'Lean YRFI'
        """
        if s <= 6:
            return 'No Bet'
        if s < 7:
            return 'Lean NRFI'
        return 'NRFI'
    except:
        return 'TBD'


class BaseballRfiHtmlGenerator:
    def __init__(self, json_path: Path, output_path: Path):
        self.json_path = Path(json_path)
        self.output_path = Path(output_path)

    def load_data(self):
        logging.debug(f"Attempting to load JSON data from {self.json_path}")
        if not self.json_path.exists():
            logging.error(f"JSON file not found: {self.json_path}")
            return []
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            logging.error(f"Error reading JSON: {e}")
            return []
        # JSON is expected to be a list of game summaries
        games = data if isinstance(data, list) else data.get('games', [])
        logging.info(f"Loaded {len(games)} games from JSON")
        if games:
            logging.debug(f"First record sample: {games[0]}")
        return games

    def generate(self):
        games = self.load_data()
        if not games:
            logging.warning("No games data; HTML will be blank.")
        # Build HTML header
        html = f"""<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset='UTF-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1.0'/>
  <title>Moneyline Hacks - RFI Model</title>
  <link href='https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css' rel='stylesheet'>
  <style>
    body {{ background-color:#0f172a; color:#e2e8f0; font-family:'Segoe UI', sans-serif; }}
    .title-highlight {{ background:linear-gradient(to right,#34d399,#06b6d4); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
    table {{ border-collapse: collapse; width:100%; }}
    th, td {{ border: 1px solid #fff; padding: 0.5rem; text-align: center; }}
  </style>
</head>
<body class='p-6'>
  <div class='text-center mb-6'>
    <h1 class='text-4xl font-extrabold title-highlight'>Moneyline Hacks</h1>
    <p class='text-gray-400'>Run First Inning (RFI) Model — {title_date}</p>
  </div>
  <div class='overflow-auto max-w-5xl mx-auto'>
    <table class='min-w-full text-gray-300 text-sm'>
      <thead class='bg-gray-900 text-gray-100 uppercase text-xs'>
        <tr>
          <th class='px-4 py-2'>MLB Matchup</th>
          <th class='px-4 py-2'>Start Time</th>
          <th class='px-4 py-2'>SP Name</th>
          <th class='px-4 py-2'>SP xFIP (L30D)</th>
          <th class='px-4 py-2 borderless'>SP Barrel% (L30D)</th>
          <th class='px-4 py-2'>Team 1st Inning wRC+</th>
          <th class='px-4 py-2'>Top 3 Hitters Avg wOBA</th>
          <th class='px-4 py-2'>Team RFI Grade (0-5)</th>
          <th class='px-4 py-2'>NRFI Grade (0-100)</th>
          <th class='px-4 py-2'>Recommendation</th>
        </tr>
      </thead>
      <tbody>
"""
        # Render each game summary
        for game in games:
            logging.debug(f"Processing record: {game}")
            # Extract and parse time; JSON uses 'game_datetime' key
            iso = game.get('game_datetime') or game.get('gameDate')
            if iso:
                try:
                    # 1) turn the trailing “Z” into an explicit UTC offset
                    if iso.endswith('Z'):
                        utc_dt = _dt.fromisoformat(iso.replace('Z', '+00:00'))
                    else:
                        utc_dt = _dt.fromisoformat(iso)
                    # 2) convert to Eastern Time
                    et_dt = utc_dt.astimezone(ZoneInfo('America/New_York'))
                    # 3) format as h:mm AM/PM ET
                    game_time = et_dt.strftime(
                        '%I:%M %p ET').lstrip('0').replace(' 0', ' ')
                except Exception as e:
                    logging.error(f"Error parsing timestamp '{iso}': {e}")
                    game_time = 'TBD'

            else:
                logging.warning(
                    f"Missing timestamp for game_id {game.get('game_id')}")
                game_time = 'TBD'

            away_team = game.get('away_team', '-')
            home_team = game.get('home_team', '-')
            away_abbrev = game.get('away_abbrev', '-')
            home_abbrev = game.get('home_abbrev', '-')
            away_pitcher = game.get('away_pitcher', '-')
            home_pitcher = game.get('home_pitcher', '-')
            away_team_rfi_score = game.get('away_rfi_grade', '')
            home_team_rfi_score = game.get('home_rfi_grade', '')
            nrfi = game.get('nrfi_grade', '')
            rec = recommendation(nrfi)

            # Away row (lighter gray on left 5 cols, lighter gray on RHS spans)
            html += (
                "<tr>"
                f"<td class='px-4 py-2 bg-gray-700' rowspan='2'>{away_abbrev} @{home_abbrev}</td>"
                f"<td class='px-4 py-2 bg-gray-700' rowspan='2'>{game_time}</td>"
                f"<td class='px-4 py-2 bg-gray-700'>{away_pitcher} ({away_abbrev})</td>"
                f"<td class='px-4 py-2 bg-gray-700'>TBD</td>"
                f"<td class='px-4 py-2 bg-gray-700'>TBD</td>"
                f"<td class='px-4 py-2 bg-gray-700'>TBD</td>"
                f"<td class='px-4 py-2 bg-gray-700'>TBD</td>"
                f"<td class='px-4 py-2 bg-gray-700'>{away_team_rfi_score}</td>"
                f"<td class='px-4 py-2 bg-gray-700' rowspan='2'>{nrfi}</td>"
                f"<td class='{grade_color(nrfi)}' rowspan='2'>{rec}</td>"
                "</tr>\n"
            )

            # Home row (darker gray on left 5 cols, lighter gray on RHS already spanned)
            html += (
                "<tr>"
                f"<td class='px-4 py-2 bg-gray-800'>{home_pitcher} ({home_abbrev})</td>"
                f"<td class='px-4 py-2 bg-gray-800'>TBD</td>"
                f"<td class='px-4 py-2 bg-gray-800'>TBD</td>"
                f"<td class='px-4 py-2 bg-gray-800'>TBD</td>"
                f"<td class='px-4 py-2 bg-gray-800'>TBD</td>"
                f"<td class='px-4 py-2 bg-gray-800'>{home_team_rfi_score}</td>"
                "</tr>\n"
            )

        # Close HTML
        html += """      </tbody>
    </table>
  </div>
</body>
</html>
"""
        self.output_path.write_text(html, encoding='utf-8')
        logging.info(f"Wrote HTML to {self.output_path}")


if __name__ == '__main__':
    generator = BaseballRfiHtmlGenerator(JSON_PATH, HTML_PATH)
    generator.generate()
