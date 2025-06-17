#!/usr/bin/env python3
import sys
import logging
import json
from pathlib import Path
from datetime import datetime

# Load config.json from project root of this script
CONFIG_PATH = Path(__file__).resolve().parents[6] / "config.json"
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    config = json.load(f)

# Define absolute project root from config
ROOT = Path(config["root_path"]).resolve()

# Raw data directory, relative to ROOT if not absolute
RAW_DATA_DIR = Path(config.get("mlb_test_output_path", "./output")).resolve()
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

date_suffix = datetime.now().strftime("%Y%m%d")
JSON_FILENAME = config.get(
    "json_filename", f"mlb_daily_summary_{date_suffix}.json")
HTML_FILENAME = config.get(
    "html_filename", f"mlb_mlh_rfi_websheet_{date_suffix}.html")

JSON_PATH = RAW_DATA_DIR / JSON_FILENAME
HTML_PATH = RAW_DATA_DIR / HTML_FILENAME

# Logging setup
date_now = datetime.now().strftime("%Y-%m-%d")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logging.info(f"Project root: {ROOT}")
logging.info(f"Raw data dir: {RAW_DATA_DIR}")
logging.info(f"JSON path: {JSON_PATH} (exists={JSON_PATH.exists()})")
logging.info(f"HTML path: {HTML_PATH}")


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
        games = data.get('games', [])
        logging.info(f"Loaded {len(games)} games from JSON")
        logging.debug(f"Games data: {games}")
        return games

    def format_time(self, iso: str) -> str:
        try:
            dt = datetime.fromisoformat(iso.replace('Z', ''))
            return dt.strftime('%-I:%M %p ET')
        except Exception:
            logging.debug(f"Failed to parse time '{iso}'")
            return iso or '-'

    def generate(self):
        games = self.load_data()
        if not games:
            logging.warning("No games data; HTML will be blank.")
        html = f"""<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset='UTF-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1.0'/>
  <title>Moneyline Hacks - RFI Model</title>
  <link href='https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css' rel='stylesheet'>
  <style>
    body {{ background-color:#0f172a; color:#e2e8f0; font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
    .title-highlight {{ background:linear-gradient(to right,#34d399,#06b6d4); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
    table {{ border-collapse: collapse; width:100%; }}
    th, td {{ border: 1px solid #fff; padding: 0.5rem; }}
  </style>
</head>
<body class='p-6'>
  <div class='text-center mb-6'>
    <h1 class='text-4xl font-extrabold title-highlight'>Moneyline Hacks</h1>
    <p class='text-gray-400'>Run First Inning (RFI) Model — {datetime.now().strftime('%B %d')}</p>
  </div>
  <div class='overflow-auto max-w-5xl mx-auto'>
    <table class='min-w-full text-gray-300 text-sm'>
      <thead class='bg-gray-700 uppercase'>
        <tr>
          <th>Game Time</th>
          <th>Pitching Team</th>
          <th>Proj. Pitcher</th>
          <th>Opponent</th>
          <th>Team Grade</th>
          <th>NRFI Grade</th>
          <th>Recommendation</th>
        </tr>
      </thead>
      <tbody>
"""
        for game in games:
            time_str = self.format_time(game.get('gameDate', ''))
            away = game['teams']['away']
            home = game['teams']['home']
            tg, ng, rec = '0.0', '0.0', 'TBD'
            logging.debug(f"Rendering game {game.get('gamePk')} at {time_str}")
            html += (
                f"<tr>"
                f"<td rowspan='2'>{time_str}</td>"
                f"<td>{away['team']['name']}</td>"
                f"<td>{away.get('probablePitcher', {{}}).get('fullName','-')}</td>"
                f"<td>{home['team']['name']}</td>"
                f"<td>{tg}</td>"
                f"<td>{ng}</td>"
                f"<td>{rec}</td>"
                f"</tr>\n"
            )
            html += (
                f"<tr>"
                f"<td>{home['team']['name']}</td>"
                f"<td>{home.get('probablePitcher', {{}}).get('fullName','-')}</td>"
                f"<td>{away['team']['name']}</td>"
                f"<td>{tg}</td>"
                f"<td>{ng}</td>"
                f"<td>{rec}</td>"
                f"</tr>\n"
            )
        html += """
      </tbody>
    </table>
  </div>
</body>
</html>
"""
        self.output_path.write_text(html)
        logging.info(f"Wrote HTML to {self.output_path}")


if __name__ == '__main__':
    generator = BaseballRfiHtmlGenerator(JSON_PATH, HTML_PATH)
    generator.generate()
