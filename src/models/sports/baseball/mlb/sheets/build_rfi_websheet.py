import sys
import logging
import logging.config
import json
from pathlib import Path
from datetime import datetime as _dt
from zoneinfo import ZoneInfo

from pyparsing import col
from utils.config_loader import load_config

cfg = load_config()
# 🛠️ Ensure the logging directory exists BEFORE using the config
log_path = Path(cfg["logging"]["handlers"]["file"]["filename"])
log_path.parent.mkdir(parents=True, exist_ok=True)
logging.config.dictConfig(cfg["logging"])


raw_data_dir = Path(cfg["mlb_data"]["test_output"])

# Raw data directory, relative to ROOT if not absolute
raw_data_dir.mkdir(parents=True, exist_ok=True)

# Determine JSON and HTML filenames
# JSON_PATH must be defined before deriving date_suffix
JSON_FILENAME = cfg.get(
    # "json_filename", f"mlb_daily_game_summary_{_dt.now().strftime('%Y%m%d')}.json"
    "json_filename", "mlb_daily_game_summary_20250701.json"
)
JSON_PATH = raw_data_dir / JSON_FILENAME
HTML_FILENAME = cfg.get(
    "html_filename", f"mlb_mlh_rfi_websheet_{JSON_PATH.stem.split('_')[-1]}.html"
)
HTML_PATH = raw_data_dir / HTML_FILENAME

# Derive title_date from JSON filename suffix
date_suffix = JSON_PATH.stem.split('_')[-1]
try:
    title_date = _dt.strptime(date_suffix, '%Y%m%d').strftime('%B %d, %Y')
except Exception as e:
    logging.error(f"Error parsing date_suffix '{date_suffix}': {e}")
    title_date = date_suffix

logging.info(f"Raw data dir: {raw_data_dir}")
logging.info(f"JSON path: {JSON_PATH} (exists={JSON_PATH.exists()})")
logging.info(f"HTML path: {HTML_PATH}")
logging.info(f"Title date: {title_date}")

# Color thresholds

# Utility functions


def grade_color(score):
    try:
        s = float(score)
        if s <= 20:
            return 'bg-de4545 text-white'
        if s < 4:
            return 'bg-red-300 text-black'
        if s >= 50:
            return 'bg-green-600 text-white'
        return 'bg-gray-600 text-white'
    except:
        return ''

# Letter grade helper


def letter_grade(score):
    try:
        s = float(score)
        # if s >= 98: return 'A+'
        # if s >= 94: return 'A'
        # if s >= 90: return 'A-'
        # if s >= 85: return 'B+'
        # if s >= 80: return 'B'
        # if s >= 75: return 'B-'
        # if s >= 70: return 'C+'
        # if s >= 65: return 'C'
        # if s >= 60: return 'C-'
        # if s >= 55: return 'D+'
        # if s >= 50: return 'D'
        # if s >= 45: return 'D-'
        if s >= 50:
            return 'A'
        if s >= 40:
            return 'B'
        if s >= 30:
            return 'C'
        if s >= 20:
            return 'D'
        if s >= 10:
            return 'F'
        return 'F'
    except:
        return ''
# Recommendation logic


def recommendation_from_grade(grade):
    # map letter grade to recommendation
    mapping = {
        'A+': 'NRFI', 'A': 'NRFI', 'A-': 'NRFI',
        'B+': 'Lean NRFI', 'B': 'Lean NRFI', 'B-': 'Lean NRFI',
        'C+': 'TBD', 'C': 'TBD', 'C-': 'TBD',
        'D+': 'Lean YRFI', 'D': 'Lean YRFI', 'D-': 'Lean YRFI',
        'F': 'YRFI'
    }
    return mapping.get(grade, 'TBD')


# Icon mapping for grades
icon_map = {
    'A+': '✅', 'A': '✅', 'A-': '✅',
    'B+': '⚠️', 'B': '⚠️', 'B-': '⚠️',
    'C+': '❌', 'C': '❌', 'C-': '❌',
    'D+': '❌', 'D': '❌', 'D-': '❌',
    'F': '❌'
}


def recommendation(nrfi):
    try:
        s = float(nrfi)
        if s <= 20:
            return 'YRFI'

        # if s < 4:
        #    return 'Lean YRFI'

        # if s <= 6:
        #    return 'No Bet'
        if s > 50:
            return 'NRFI'
        return 'TBD'
    except:  # noqa: E722
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
  <title>Moneyline Hacks - NRFI Model</title>
  <link href='https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css' rel='stylesheet'>
  <style>
    /* global box-sizing */
    *, *::before, *::after {{ box-sizing: border-box; }}
    /* reset margins */
    html, body {{ margin: 0; padding: 0; }}
    body {{
      background-color: #0f172a;
      color: #e2e8f0;
      font-family: 'Segoe UI', sans-serif;
      padding: 1.5rem;
    }}
    .title-highlight {{
      background: linear-gradient(to right, #34d399, #06b6d4);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}

    /* custom class for s<=20 */
    .bg-de4545 {{ background-color: #db5a5a !important; }}
    /* wrapper provides uniform white border */
    .table-wrapper {{ 
      display: inline-block; 
      max-width: 100%; 
      overflow-x: auto; 
      border: 1px solid #fff; 
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background-color: #0f172a; /* table background behind cells */
      border: 1px solid #fff;     /* uniform outer border */
    }}
    th, td {{
      border: 1px solid #fff;
      padding: 0.5rem;
      text-align: center;
    }}
    .overflow-auto.max-w-5xl.mx-auto {{
    box-sizing: border-box; 
    }}
  </style>
</head>
<body class='p-6'>
  <div class='flex flex-col items-center justify-center gap-3 mb-6'>
    <!-- First line: logo and title -->
    <div class='flex items-center gap-4'>
      <img
        src='https://raw.githubusercontent.com/Fluidity1337/ai-ml-predictive-models/main/assets/img/mlh/mlh-logo-1.jpg'
        alt='Moneyline Hacks Logo'
        class='h-16'/>
      <h1 class='text-4xl font-extrabold title-highlight'>Moneyline Hacks</h1>
    </div>
    <!-- Second line: date and second logo -->
    <div class='flex items-center gap-4'>
      <h2 class='text-xl text-gray-400'>No Run First Inning Model — {title_date}</h2>
      <img
        src='https://raw.githubusercontent.com/Fluidity1337/ai-ml-predictive-models/main/assets/img/mlb/mlb-logo-2.png'
        alt='Baseball Icon'
        class='h-10'/>
    </div>
  </div>
  <div class='overflow-auto max-w-5xl mx-auto'>
    <table class='min-w-full text-gray-300 text-sm'>
      <thead class='bg-gray-900 text-gray-100 uppercase text-xs'>
        <tr>
          <th class='px-4 py-2'>MLB Matchup</th>
          <th class='px-4 py-2'>Start Time</th>
          <th class='px-4 py-2'>SP Name</th>
          <th class='px-4 py-2'>SP xFIP (L30D)</th>
          <th class='px-4 py-2'>xFIP Score (0-100)</th>          
          <th class='px-4 py-2'>SP Barrel% (L30D)</th>        
          <th class='px-4 py-2'>Top 3 Hitters Avg wOBA (L14D)</th>          
          <th class='px-4 py-2'>Team 1st Inning wRC+ (Season)</th>
          <th class='px-4 py-2'>Team RFI Grade (0-100)</th>
          <th class='px-4 py-2'>Grade</th>        
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

            away_team = game.get('away_team', 'N/A')
            home_team = game.get('home_team', 'N/A')
            away_abbrev = game.get('away_team_abbrev', 'N/A')
            home_abbrev = game.get('home_team_abbrev', 'N/A')
            away_pitcher = game.get('away_pitcher', 'N/A')
            home_pitcher = game.get('home_pitcher', 'N/A')

            # xFIP
            # Round pitcher xFIP to two decimal places if numeric, else fallback
            raw_away_xfip = game.get('away_pitcher_recent_xfip')
            away_pitcher_recent_xfip = f"{raw_away_xfip:.2f}" if isinstance(
                raw_away_xfip, (int, float)) else 'N/A'
            raw_home_xfip = game.get('home_pitcher_recent_xfip')
            home_pitcher_recent_xfip = f"{raw_home_xfip:.2f}" if isinstance(
                raw_home_xfip, (int, float)) else 'N/A'

            # xFIP Score
            raw_away_xfip_score = game.get('away_pitcher_recent_xfip_score')
            away_pitcher_recent_xfip_score = f"{raw_away_xfip_score:.2f}" if isinstance(
                raw_away_xfip_score, (int, float)) else 'N/A'
            raw_home_xfip_score = game.get('home_pitcher_recent_xfip_score')
            home_pitcher_recent_xfip_score = f"{raw_home_xfip_score:.2f}" if isinstance(
                raw_home_xfip_score, (int, float)) else 'N/A'

            # Barrel %
            raw_away_barrel_pct = game.get('away_pitcher_recent_barrel_pct')
            away_pitcher_recent_barrel_pct = f"{raw_away_barrel_pct:.2f}" if isinstance(
                raw_away_barrel_pct, (int, float)) else 'N/A'
            raw_home_barrel_pct = game.get('home_pitcher_recent_barrel_pct')
            home_pitcher_recent_barrel_pct = f"{raw_home_barrel_pct:.2f}" if isinstance(
                raw_home_barrel_pct, (int, float)) else 'N/A'

            # Barrel % Score
            raw_away_barrel_pct_score = game.get(
                'away_pitcher_recent_barrel_pct_score')
            away_pitcher_recent_barrel_pct_score = f"{raw_away_barrel_pct_score:.2f}" if isinstance(
                raw_away_barrel_pct_score, (int, float)) else 'N/A'
            raw_home_barrel_pct_score = game.get(
                'home_pitcher_recent_barrel_pct')
            home_pitcher_recent_barrel_pct_score = f"{raw_home_barrel_pct_score:.2f}" if isinstance(
                raw_home_barrel_pct_score, (int, float)) else 'N/A'

            # wRC+ 1st Inning
            raw_away_team_wrc_plus_1st_inn = game.get(
                'away_team_wrc_plus_1st_inn')
            away_team_season_wrc_plus_1st_inn = f"{raw_away_team_wrc_plus_1st_inn:.2f}" if isinstance(
                raw_away_team_wrc_plus_1st_inn, (int, float)) else 'N/A'
            raw_home_team_wrc_plus_1st_inn = game.get(
                'home_team_wrc_plus_1st_inn')
            home_team_season_wrc_plus_1st_inn = f"{raw_home_team_wrc_plus_1st_inn:.2f}" if isinstance(
                raw_home_team_wrc_plus_1st_inn, (int, float)) else 'N/A'

            # wOBA3
            raw_away_team_woba3 = game.get('away_team_woba3')
            away_team_recent_woba3 = f"{raw_away_team_woba3:.2f}" if isinstance(
                raw_away_team_woba3, (int, float)) else 'N/A'
            raw_home_team_woba3 = game.get('home_team_woba3')
            home_team_recent_woba3 = f"{raw_home_team_woba3:.2f}" if isinstance(
                raw_home_team_woba3, (int, float)) else 'N/A'

            # Team RFI
            raw_away_team_rfi_score = game.get('away_team_score')
            away_team_nrfi_score = f"{raw_away_team_rfi_score:.2f}" if isinstance(
                raw_away_team_rfi_score, (int, float)) else 'N/A'
            raw_home_team_rfi_score = game.get('home_team_score')
            home_team_nrfi_score = f"{raw_home_team_rfi_score:.2f}" if isinstance(
                raw_home_team_rfi_score, (int, float)) else 'N/A'

            game_nrfi_score = game.get('game_nrfi_score', '')
            # rec = recommendation(game_nrfi_score)
            score = game.get('game_nrfi_score', 0)
            grade = letter_grade(score)
            rec = recommendation_from_grade(grade)
            color_cls = grade_color(score)

            # Away row (lighter gray on left 5 cols, lighter gray on RHS spans)
            html += (
                "<tr>"
                f"<td class='px-4 py-2 bg-gray-700' rowspan='2'>{away_abbrev} @{home_abbrev}</td>"
                f"<td class='px-4 py-2 bg-gray-700' rowspan='2'>{game_time}</td>"
                f"<td class='px-4 py-2 bg-gray-700'>{away_pitcher} ({away_abbrev})</td>"
                f"<td class='px-4 py-2 bg-gray-700'>{away_pitcher_recent_xfip}</td>"
                f"<td class='px-4 py-2 bg-gray-700'>{away_pitcher_recent_xfip_score}</td>"
                f"<td class='px-4 py-2 bg-gray-700'>{away_pitcher_recent_barrel_pct}%</td>"
                # f"<td class='px-4 py-2 bg-gray-700'>{away_pitcher_recent_barrel_pct_score}</td>"
                f"<td class='px-4 py-2 bg-gray-700'>{away_team_recent_woba3}</td>"
                f"<td class='px-4 py-2 bg-gray-700'>{away_team_season_wrc_plus_1st_inn}</td>"
                f"<td class='px-4 py-2 bg-gray-700'>{away_team_nrfi_score}</td>"
                f"<td class='{color_cls}' rowspan='2'>{grade}</td>"
                f"<td class='{color_cls}' rowspan='2'>{icon_map.get(grade, '')} {rec}</td>"
                "</tr>\n"
            )

            # Home row (darker gray on left 5 cols, lighter gray on RHS already spanned)
            html += (
                "<tr>"
                f"<td class='px-4 py-2 bg-gray-800'>{home_pitcher} ({home_abbrev})</td>"
                f"<td class='px-4 py-2 bg-gray-800'>{home_pitcher_recent_xfip}</td>"
                f"<td class='px-4 py-2 bg-gray-800'>{home_pitcher_recent_xfip_score}</td>"
                f"<td class='px-4 py-2 bg-gray-800'>{home_pitcher_recent_barrel_pct}%</td>"
                # f"<td class='px-4 py-2 bg-gray-800'>{home_pitcher_recent_barrel_pct_score}</td>"
                f"<td class='px-4 py-2 bg-gray-800'>{home_team_recent_woba3}</td>"
                f"<td class='px-4 py-2 bg-gray-800'>{home_team_season_wrc_plus_1st_inn}</td>"
                f"<td class='px-4 py-2 bg-gray-800'>{home_team_nrfi_score}</td>"
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
