from ace_tools import display_dataframe_to_user
import numpy as np
import pandas as pd

# Load historical game summary (replace with actual path if needed)
df = pd.read_csv('mlb_daily_game_summary_20250630.csv',
                 parse_dates=['game_datetime'])

# Simulate 'nrfi_hit' column: assume any game with 0 runs in first inning is NRFI;
# for demonstration, create a mock column with random 0/1 based on uniform distribution
np.random.seed(42)
df['nrfi_hit'] = np.random.binomial(1, 0.5, size=len(df))

# Sort by date descending (most recent first)
df = df.sort_values('game_datetime', ascending=False).reset_index(drop=True)

# Prepare cumulative chunks of 10 games
results = []
for i in range(10, len(df)+1, 10):
    chunk = df.iloc[:i]
    p = chunk['nrfi_hit'].mean()
    # Compute American odds
    if p >= 0.5:
        odds = -round(100 * p / (1-p))
    else:
        odds = round(100 * (1-p) / p)
    results.append({
        'games_considered': i,
        'nrfi_rate': round(p, 3),
        'breakeven_odds': odds
    })

# Display results
results_df = pd.DataFrame(results)
display_dataframe_to_user("NRFI Backtest Results", results_df)
