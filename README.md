# Sports Predictive Models 🧠⚾🏀

A collection of machine learning models designed to make sports predictions, starting with MLB Run First Inning (RFI) predictions.

---

## 📂 Project Structure


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