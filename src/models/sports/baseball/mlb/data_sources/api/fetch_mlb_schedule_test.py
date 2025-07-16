from datetime import date
import importlib.util
import sys
from pathlib import Path

# Dynamically load fetch_mlb_schedule.py
module_name = "fetch_mlb_schedule"
file_path = Path(__file__).parent / "fetch_mlb_schedule.py"

spec = importlib.util.spec_from_file_location(module_name, file_path)
fetch_mlb_schedule = importlib.util.module_from_spec(spec)
sys.modules[module_name] = fetch_mlb_schedule
spec.loader.exec_module(fetch_mlb_schedule)

# Run the fetch_schedule function
schedule_df = fetch_mlb_schedule.fetch_mlb_schedule()

# Display result
print(schedule_df)

# Optional: Run test on a specific date (e.g., June 3, 2025)
test_date = date(2025, 6, 30)
schedule_df_test = fetch_mlb_schedule.fetch_mlb_schedule(test_date)
print("\nFiltered for test date:")
print(schedule_df_test)
