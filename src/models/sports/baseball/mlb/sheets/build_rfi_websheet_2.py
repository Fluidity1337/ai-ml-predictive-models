#!/usr/bin/env python3
import sys
import logging
import json
from pathlib import Path
from datetime import datetime as _dt

# Load config.json from project root of this script
CONFIG_PATH = Path(__file__).resolve().parents[6] / "config.json"
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    config = json.load(f)

# Define absolute project root from config
ROOT = Path(config["root_path"]).resolve()

# Raw data directory, relative to ROOT if not absolute
RAW_DATA_DIR = Path(config.get("mlb_test_output_path", "./output")).resolve()
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

JSON_FILENAME = config.get(
    "json_filename", f"mlb_daily_game_summary_{date_suffix}.json")
HTML_FILENAME = config.get(
    "html_filename", f"mlb_mlh_rfi_websheet_{date_suffix}.html")

JSON_PATH = RAW_DATA_DIR / JSON_FILENAME
HTML_PATH = RAW_DATA_DIR / HTML_FILENAME

date_now = _dt.now().strftime("%Y-%m-%d")
date_suffix = JSON_PATH.stem.split('_')[-1]  # derive from filename
try:
    title_date = date_now.strptime(date_suffix, '%Y%m%d').strftime('%B %d, %Y')
except Exception:
    title_date = date_suffix

# Logging setup
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
        # JSON is a list of game summaries
        games = data if isinstance(data, list) else data.get('games', [])
        logging.info(f"Loaded {len(games)} games from JSON")
        logging.debug(f"Sample record: {games[0] if games else None}")
        return games

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
    body {{ background-color:#0f172a; color:#e2e8f0; font-family:'Segoe UI', sans-serif; }}
    .title-highlight {{ background:linear-gradient(to right,#34d399,#06b6d4); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
    table {{ border-collapse: collapse; width:100%; }}
    th, td {{ border: 1px solid #fff; padding: 0.5rem; }}
  </style>
</head>
<body class='p-6'>
  <div class=\"flex flex-col items-center justify-center gap-3 mb-6\">
    <img src=\"https://raw.githubusercontent.com/Fluidity1337/ai-ml-predictive-models/main/assets/img/mlh/mlh-logo-1.jpg\" alt=\"Moneyline Hacks Logo\" class=\"h-16\" />
    <h1 class=\"text-4xl font-extrabold title-highlight\">Moneyline Hacks</h1>
    <h2 class=\"text-xl text-gray-400\">Run First Inning (RFI) Model — {_dt.now().strftime('%B %d')}</h2>
    <img src=\"https://raw.githubusercontent.com/Fluidity1337/ai-ml-predictive-models/main/assets/img/mlb/mlb-logo-2.png\" alt=\"Baseball Icon\" class=\"h-10\" />
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
        # Render each flat summary dict
        for game in games:
            logging.debug(f"Processing record: {game}")
            iso = game.get('gameDate')
            logging.debug(f"Raw gameDate: {iso}")
            # format the game time
            if iso:
                try:
                    dt = _dt.fromisoformat(iso.replace('Z', ''))
                    date_time = dt.strftime(
                        '%b %d, %Y %I:%M %p ET').replace(' 0', ' ')
                except Exception as e:
                    logging.error(f"Error parsing iso '{iso}': {e}")
                    date_time = f"PARSE_ERR ({iso})"
            else:
                logging.warning("Missing gameDate for record")
                date_time = f"MISSING ({game.get('game_id')})"

            away_team = game.get('away_team', '-')
            home_team = game.get('home_team', '-')
            away_pitch = game.get('away_pitcher', '-')
            home_pitch = game.get('home_pitcher', '-')
            away_grade = game.get('away_rfi_grade', '-')
            home_grade = game.get('home_rfi_grade', '-')
            nrfi = game.get('nrfi_grade', '-')
            rec = "TBD"

            logging.debug(
                f"Rendering game {game.get('game_id')}: {away_team} vs {home_team}")
            # Away row (lighter gray on left 5 cols, lighter gray on RHS spans)
            html += (
                "<tr>"
                f"<td class='px-4 py-2 bg-gray-700' rowspan='2'>{date_time}</td>"
                f"<td class='px-4 py-2 bg-gray-700'>{away_team}</td>"
                f"<td class='px-4 py-2 bg-gray-700'>{away_pitch}</td>"
                f"<td class='px-4 py-2 bg-gray-700'>vs</td>"
                f"<td class='px-4 py-2 bg-gray-700'>{home_team}</td>"
                f"<td class='px-4 py-2 bg-gray-700'>{away_grade}</td>"
                f"<td class='px-4 py-2 bg-gray-700' rowspan='2'>{nrfi}</td>"
                f"<td class='px-4 py-2 bg-gray-700' rowspan='2'>{rec}</td>"
                "</tr>\n"
            )

            # Home row (darker gray on left 5 cols, lighter gray on RHS already spanned)
            html += (
                "<tr>"
                f"<td class='px-4 py-2 bg-gray-800'>{home_team}</td>"
                f"<td class='px-4 py-2 bg-gray-800'>{home_pitch}</td>"
                f"<td class='px-4 py-2 bg-gray-800'>vs</td>"
                f"<td class='px-4 py-2 bg-gray-800'>{away_team}</td>"
                f"<td class='px-4 py-2 bg-gray-800'>{home_grade}</td>"
                "</tr>\n"
            )

        html += """
      </tbody>
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
