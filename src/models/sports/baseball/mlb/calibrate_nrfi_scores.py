import glob
import json
import pandas as pd
from sklearn.linear_model import LogisticRegression
import ace_tools as tools

# Load all augmented JSON files
file_paths = glob.glob('/mnt/data/mlb_daily_game_summary_*_augmented.json')
records = []
for fp in file_paths:
    with open(fp, 'r') as f:
        records.extend(json.load(f))

# Build DataFrame
df = pd.DataFrame(records)
# Prepare features and target: NRFI = no run in first inning
df = df[['game_nrfi_score', 'first_inning_run']].dropna()
df['nrfi'] = (~df['first_inning_run']).astype(int)

X = df[['game_nrfi_score']]
y = df['nrfi']

# Fit logistic regression for calibration
model = LogisticRegression(solver='lbfgs')
model.fit(X, y)

# Add calibrated probabilities
df['calibrated_p_nrfi'] = model.predict_proba(X)[:, 1]

# Display model parameters and a sample of calibrated probabilities
print("Logistic calibration parameters:")
print(f"  Intercept: {model.intercept_[0]:.4f}")
print(f"  Coefficient: {model.coef_[0][0]:.4f}\n")

tools.display_dataframe_to_user(
    "Sample Calibrated NRFI Probabilities",
    df[['game_nrfi_score', 'nrfi', 'calibrated_p_nrfi']].head(10)
)
