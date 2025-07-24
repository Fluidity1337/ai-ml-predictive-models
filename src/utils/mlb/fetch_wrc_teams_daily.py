# --- Fetch and Store wRC+ CSV ---
import requests
from datetime import datetime

def fetch_wrc_plus(output_dir="./data/raw"):
    os.makedirs(output_dir, exist_ok=True)
    today = datetime.today().strftime("%Y-%m-%d")
    fg_url = "https://www.fangraphs.com/leaders/splits-leaderboards"
    params = {
        "splitArr": "44",
        "statType": "team",
        "statgroup": "2",
        "startDate": today,
        "endDate": today,
        "position": "B",
        "sort": "23,1",
        "csv": "1"
    }
    resp = requests.get(fg_url, params=params)
    resp.raise_for_status()
    path = os.path.join(output_dir, f"wrc_plus_{today}.csv")
    with open(path, "wb") as f:
        f.write(resp.content)
    print(f"Saved wRC+ CSV to {path}")

# To run:
#   python fetch_wrc_teams_daily.py
