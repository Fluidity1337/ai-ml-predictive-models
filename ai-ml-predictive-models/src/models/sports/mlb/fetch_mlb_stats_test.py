# fetch_stats_test.py
import sys
import os
import importlib.util

# Dynamically load fetch_stats module
# Dynamically load fetch_schedule.py
module_name = "fetch_mlbstats"
file_path = Path(__file__).parent / "fetch_schedule.py"
fetch_stats = importlib.util.module_from_spec(spec)
sys.modules["fetch_stats"] = fetch_stats
spec.loader.exec_module(fetch_stats)

# Test with simulated player_id (real ID required for actual API)
try:
    pitcher_id = "608324"  # Example: Justin Verlander
    df = fetch_stats.fetch_pitcher_stats(player_id=pitcher_id, year=2025)
    print("Pitcher stats (last 3 starts):\n")
    print(df)
except Exception as e:
    print(f"Test failed: {e}")
