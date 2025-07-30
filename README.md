### Calibrate NRFI Scores (logistic regression)

Calibrate raw NRFI model scores to well-calibrated probabilities using logistic regression, then inject calibrated probabilities into JSON summaries, writing results to an output directory.

**Required:**
- `-i`, `--input-dir`: Directory containing input JSON files
- `-d`, `--output-dir`: Directory to output calibrated JSON files

**Optional:**
- `-p`, `--pattern`: Filename pattern to match (default: mlb_daily_game_summary_*_augmented.json)
- `-s`, `--score-col`: Raw score column name (default: game_nrfi_score)
- `-t`, `--target-col`: Boolean column: True if there was a run in 1st inning (default: first_inning_run)
- `--example`: Show usage examples and exit

**Usage examples:**

```bash
# Calibrate NRFI scores for all augmented summaries in a directory
python -m src.models.sports.baseball.mlb.calibrate_nrfi_scores -i data/baseball/mlb/interim/game_summaries -p "mlb_daily_game_summary_*_augmented.json" -d data/baseball/mlb/processed/game_summaries

# Use custom score/target columns
python -m src.models.sports.baseball.mlb.calibrate_nrfi_scores -i data/baseball/mlb/interim/game_summaries -p "mlb_daily_game_summary_*_augmented.json" -d data/baseball/mlb/processed/game_summaries -s my_score_col -t my_target_col
```

**Note:**
- This script is designed for file-based workflows but is structured to allow future scaling to database (DB) backends. To support DB, refactor load_data and output logic to use DB queries/inserts instead of file I/O.

### Fetch wRC+ CSV from Fangraphs

Fetch and store wRC+ CSV for a given date from Fangraphs, using config-driven paths.

**Required:**
- `--output_dir`: Output directory for CSV (default: from config)
- `--date`: Date in YYYY-MM-DD format (default: today)
- `--fg_url`: Fangraphs URL (default: from config)

**Usage examples:**

```bash
# Fetch today's wRC+ CSV to default location
python -m src.utils.mlb.fetch_wrc_teams_daily

# Fetch for a specific date and output directory
python -m src.utils.mlb.fetch_wrc_teams_daily --output_dir data/baseball/mlb/raw --date 2025-07-24
```

**Note:**
- This script is designed for file-based workflows but is structured to allow future scaling to database (DB) backends. To support DB, refactor fetch_wrc_plus and output logic to use DB queries/inserts instead of file I/O.
### Augment MLB Game Summaries (first-inning run data)

Augment only the files for a specific date, date range, or season. By default, skips files if the augmented output already exists unless you use `--force`.

**Required:**
- `-i`, `--input-dir`: Directory containing input JSON files
- `-d`, `--output-dir`: Directory to output augmented JSON files

**Optional:**
- `-p`, `--pattern`: Filename pattern to match (default: mlb_daily_game_summary_*.json)
- `--start-date`: Start date (YYYYMMDD) to process (inclusive)
- `--end-date`: End date (YYYYMMDD) to process (inclusive)
- `--season`: Season year (YYYY) to process (e.g., 2025)
- `--force`: Overwrite existing augmented files
- `--example`: Show usage examples and exit

**Usage examples:**

```bash
# Augment a single date
python -m src.utils.mlb.augment_game_summaries -i data/baseball/mlb/raw -d data/baseball/mlb/interim/game_summaries --start-date 20250724 --end-date 20250724

# Augment a date range
python -m src.utils.mlb.augment_game_summaries -i data/baseball/mlb/raw -d data/baseball/mlb/interim/game_summaries --start-date 20250720 --end-date 20250725

# Augment all files for a season, overwriting existing
python -m src.utils.mlb.augment_game_summaries -i data/baseball/mlb/raw -d data/baseball/mlb/interim/game_summaries --season 2025 --force
```

**Note:**
- This script is designed for file-based workflows but is structured to allow future scaling to database (DB) backends. To support DB, refactor augment_game_summaries and output logic to use DB queries/inserts instead of file I/O.
# Sports Predictive Models 🧠⚾🏀

A collection of machine learning models designed to make sports predictions, starting with MLB Run First Inning (RFI) predictions.

---

## 📂 Project Structure
Good Software Practices reference - utils\mlb\fetch_wrc_teams_daily.py

## Getting Started

### 1. Create & activate a virtual environment  
```bash
python3 -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

Install Dependencies
pip install --upgrade pip
pip install .[tests]

poetry install

## Usage

**Fetch today’s schedule** (defaults to today’s date):  
```bash
python fetch_schedule.py

Fetch for a specific date:
python fetch_schedule.py 2025-07-02

Save raw JSON into your configured directory:
python fetch_schedule.py 2025-07-02 --save-json

Run the unit tests:
python fetch_schedule.py --test


1) wRC+ Fangraphs
https://www.fangraphs.com/leaders/splits-leaderboards?splitArr=44&splitArrPitch=&autoPt=false&splitTeams=false&statType=team&statgroup=2&startDate=2025-03-01&endDate=2025-11-01&players=&filter=&groupBy=season&wxTemperature=&wxPressure=&wxAirDensity=&wxElevation=&wxWindSpeed=&position=B&sort=23,1

2) wOBA - advanced_team_stats.py - refresh
python advanced_team_stats.py --force --quiet

python -m src.pipelines.run_mlb_rfi_pipeline 2025-07-22
python src/utils/mlb/augment_game_summaries.py -i data/baseball/mlb/raw -o data/baseball/mlb/interim/game_summaries
python src/models/sports/baseball/mlb/calibrate_nrfi_scores.py -i data/baseball/mlb/interim/game_summaries -p "mlb_daily_game_summary_*_augmented.json" -d data/baseball/mlb/processed/game_summaries

python src/renderers/build_rfi_websheet.py