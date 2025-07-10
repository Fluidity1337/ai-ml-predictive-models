#!/usr/bin/env python3
"""
Calibrate raw NRFI model scores to well-calibrated probabilities using logistic regression,
then inject calibrated probabilities into JSON summaries, writing results to an output directory.

Usage:
  python calibrate_nrfi_scores.py \
    -i data/baseball/mlb/interim/game_summaries \
    -p "mlb_daily_game_summary_*_augmented.json" \
    -d data/baseball/mlb/processed/game_summaries
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
    return 1 / (1 + math.exp(-(intercept + coef * score)))


def main():
    parser = argparse.ArgumentParser(
        description="Calibrate NRFI scores and output updated JSONs.")
    parser.add_argument(
        '-i', '--input-dir', required=True,
        help='Directory containing augmented JSON summaries'
    )
    parser.add_argument(
        '-p', '--pattern', default='mlb_daily_game_summary_*_augmented.json',
        help='Filename pattern for input JSON files'
    )
    parser.add_argument(
        '-s', '--score-col', default='game_nrfi_score',
        help='Raw score column name'
    )
    parser.add_argument(
        '-t', '--target-col', default='first_inning_run',
        help='Boolean column: True if there was a run in 1st inning'
    )
    parser.add_argument(
        '-d', '--output-dir', required=True,
        help='Directory where updated JSONs will be written'
    )
    args = parser.parse_args()

    # Load data for calibration
    df = load_data(args.input_dir, args.pattern)
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
    params_path = os.path.join(args.output_dir, 'nrfi_calibration_params.json')
    os.makedirs(args.output_dir, exist_ok=True)
    with open(params_path, 'w') as pf:
        json.dump(params, pf, indent=2)
    print(f"Saved calibration params to {params_path}")

    # Apply calibrated probabilities and write outputs
    input_files = glob.glob(os.path.join(args.input_dir, args.pattern))
    for inp in input_files:
        with open(inp) as f:
            games = json.load(f)
        for game in games:
            score = game.get(args.score_col)
            if score is not None:
                game['calibrated_p_nrfi'] = compute_calibrated_prob(
                    intercept, coef, score)
        # Write updated JSON to output directory
        out_path = os.path.join(args.output_dir, os.path.basename(inp))
        with open(out_path, 'w') as f:
            json.dump(games, f, indent=2)
        print(f"Wrote updated file: {out_path}")


if __name__ == '__main__':
    main()
