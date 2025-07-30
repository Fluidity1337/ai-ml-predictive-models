#!/usr/bin/env python3
"""
Calibrate raw NRFI model scores to well-calibrated probabilities using logistic regression,
then inject calibrated probabilities into JSON summaries, writing results to an output directory.

REQUIRED:
  -i, --input-dir   Directory containing input JSON files.
  -d, --output-dir  Directory to output calibrated JSON files.

OPTIONAL:
  -p, --pattern     Filename pattern to match (default: mlb_daily_game_summary_*_augmented.json)
  -s, --score-col   Raw score column name (default: game_nrfi_score)
  -t, --target-col  Boolean column: True if there was a run in 1st inning (default: first_inning_run)
  --example         Show usage examples and exit.
  --start-date      Start date (YYYYMMDD) to process (inclusive, default: today)
  --end-date        End date (YYYYMMDD) to process (inclusive, default: today)

USAGE EXAMPLES:
  # Calibrate NRFI scores for all augmented summaries in a directory
  python -m src.models.sports.baseball.mlb.calibrate_nrfi_scores -i data/baseball/mlb/interim/game_summaries -p "mlb_daily_game_summary_*_augmented.json" -d data/baseball/mlb/processed/game_summaries

  # Use custom score/target columns
  python -m src.models.sports.baseball.mlb.calibrate_nrfi_scores -i data/baseball/mlb/interim/game_summaries -p "mlb_daily_game_summary_*_augmented.json" -d data/baseball/mlb/processed/game_summaries -s my_score_col -t my_target_col


NOTES:
- This script is designed for file-based workflows but is structured to allow future scaling to database (DB) backends.
- To support DB, refactor load_data and output logic to use DB queries/inserts instead of file I/O.
"""

import os
import glob
import json
import argparse
import math
import pandas as pd

# Try sklearn; fallback to numpy-based logistic fit
try:
    from sklearn.linear_model import LogisticRegression
    HAVE_SK = True
except ImportError:
    HAVE_SK = False
    import numpy as _np

# Load data from JSON files matching pattern in input_dir
def load_data(input_dir, pattern):
    files = glob.glob(os.path.join(input_dir, pattern))
    if not files:
        raise FileNotFoundError(
            f"No files found matching: {pattern} in {input_dir}")
    records = []
    for fp in files:
        with open(fp) as f:
            records.extend(json.load(f))
    return pd.DataFrame(records)


def fit_with_sklearn(df, score_col, target_col):
    X = df[[score_col]].values
    y = (~df[target_col]).astype(int).values
    model = LogisticRegression(solver='lbfgs')
    model.fit(X, y)
    return model.intercept_[0], model.coef_[0][0]


def fit_with_numpy(df, score_col, target_col):
    # Manual Newton-Raphson for logistic
    X_raw = df[score_col].values
    y = (~df[target_col]).astype(int).values
    X0 = _np.vstack([_np.ones_like(X_raw), X_raw]).T
    w = _np.zeros(2)
    def _sigmoid(z): return 1 / (1 + _np.exp(-z))
    for _ in range(10):
        z = X0.dot(w)
        p = _sigmoid(z)
        grad = X0.T.dot(y - p)
        W = _np.diag(p * (1 - p))
        H = -(X0.T.dot(W).dot(X0))
        w -= _np.linalg.inv(H).dot(grad)
    return w[0], w[1]


def compute_calibrated_prob(intercept, coef, score):
    # Apply logistic calibration so that higher raw score -> higher NRFI probability by inverting the original model output.
    # original logit: intercept + coef*score
    z = intercept + coef * score
    raw_p = 1 / (1 + math.exp(-z))
    # invert so higher score -> higher probability
    return 1 - raw_p


def main():

    import datetime
    parser = argparse.ArgumentParser(
        description="""
Calibrate NRFI scores and output updated JSONs.

REQUIRED:
  -i, --input-dir   Directory containing input JSON files.
  -d, --output-dir  Directory to output calibrated JSON files.

OPTIONAL:
  -p, --pattern     Filename pattern to match (default: mlb_daily_game_summary_*_augmented.json)
  -s, --score-col   Raw score column name (default: game_nrfi_score)
  -t, --target-col  Boolean column: True if there was a run in 1st inning (default: first_inning_run)
  --start-date      Start date (YYYYMMDD) to process (inclusive, default: today)
  --end-date        End date (YYYYMMDD) to process (inclusive, default: today)
  --example         Show usage examples and exit.
        """
    )
    parser.add_argument('-i', '--input-dir', required=True, help='[REQUIRED] Directory containing input JSON files')
    parser.add_argument('-d', '--output-dir', required=True, help='[REQUIRED] Directory to output calibrated JSON files')
    parser.add_argument('-p', '--pattern', default='mlb_daily_game_summary_*_augmented.json', help='Filename pattern to match (default: mlb_daily_game_summary_*_augmented.json)')
    parser.add_argument('-s', '--score-col', default='game_nrfi_score', help='Raw score column name (default: game_nrfi_score)')
    parser.add_argument('-t', '--target-col', default='first_inning_run', help='Boolean column: True if there was a run in 1st inning (default: first_inning_run)')
    parser.add_argument('--start-date', type=str, default=None, help='Start date (YYYYMMDD) to process (inclusive, default: today)')
    parser.add_argument('--end-date', type=str, default=None, help='End date (YYYYMMDD) to process (inclusive, default: today)')
    parser.add_argument('--example', action='store_true', help='Show usage examples and exit.')
    args = parser.parse_args()
    if args.example:
        print("""
USAGE EXAMPLES:
  # Calibrate NRFI scores for today's games (default)
  python -m src.models.sports.baseball.mlb.calibrate_nrfi_scores -i data/baseball/mlb/interim/game_summaries -d data/baseball/mlb/processed/game_summaries

  # Calibrate for a specific date
  python -m src.models.sports.baseball.mlb.calibrate_nrfi_scores -i data/baseball/mlb/interim/game_summaries -d data/baseball/mlb/processed/game_summaries --start-date 20250725 --end-date 20250725

  # Calibrate for a date range
  python -m src.models.sports.baseball.mlb.calibrate_nrfi_scores -i data/baseball/mlb/interim/game_summaries -d data/baseball/mlb/processed/game_summaries --start-date 20250720 --end-date 20250725

  # Use custom score/target columns
  python -m src.models.sports.baseball.mlb.calibrate_nrfi_scores -i data/baseball/mlb/interim/game_summaries -d data/baseball/mlb/processed/game_summaries -s my_score_col -t my_target_col
        """)
        return
    if not args.input_dir or not args.output_dir:
        parser.error('Both -i/--input-dir and -d/--output-dir are required.')

    # Date filtering logic
    def parse_date_from_filename(filename):
        # Expects format: mlb_daily_game_summary_YYYYMMDD_*.json
        import re
        m = re.search(r'(\d{8})', filename)
        return m.group(1) if m else None

    today_str = datetime.datetime.today().strftime('%Y%m%d')
    start_date = args.start_date or today_str
    end_date = args.end_date or today_str

    # Find files matching pattern and filter by date
    input_files = [f for f in glob.glob(os.path.join(args.input_dir, args.pattern))
                  if start_date <= (parse_date_from_filename(os.path.basename(f)) or '') <= end_date]
    if not input_files:
        raise FileNotFoundError(f"No files found in {args.input_dir} matching {args.pattern} for date(s) {start_date} to {end_date}")

    # Load data for calibration
    records = []
    for fp in input_files:
        with open(fp) as f:
            records.extend(json.load(f))
    df = pd.DataFrame(records)
    print("Loaded columns:", df.columns.tolist())
    for col in [args.score_col, args.target_col]:
        if col not in df.columns:
            raise KeyError(
                f"Required column '{col}' not found; available: {df.columns.tolist()}")

    # Fit logistic calibration
    if HAVE_SK:
        intercept, coef = fit_with_sklearn(df, args.score_col, args.target_col)
    else:
        intercept, coef = fit_with_numpy(df, args.score_col, args.target_col)
    print(
        f"Calibration parameters: intercept={intercept:.4f}, coef={coef:.4f}")

    # Save calibration parameters
    params = {'intercept': intercept,
              'coef': coef, 'score_col': args.score_col}
    os.makedirs(args.output_dir, exist_ok=True)
    params_path = os.path.join(args.output_dir, 'nrfi_calibration_params.json')
    with open(params_path, 'w') as pf:
        json.dump(params, pf, indent=2)
    print(f"Saved calibration params to {params_path}")

    # Apply calibrated probabilities and write outputs
    for inp in input_files:
        with open(inp) as f:
            games = json.load(f)
        for game in games:
            score = game.get(args.score_col)
            if isinstance(score, (int, float)):
                game['calibrated_p_nrfi'] = compute_calibrated_prob(
                    intercept, coef, score)
        out_path = os.path.join(args.output_dir, os.path.basename(inp))
        with open(out_path, 'w') as f:
            json.dump(games, f, indent=2)
        print(f"Wrote updated file: {out_path}")


if __name__ == '__main__':
    main()
