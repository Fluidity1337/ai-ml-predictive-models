import json
import pandas as pd
from pandas import json_normalize

# Utility: Save JSON to file
def save_as_json(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

# Utility: Flatten JSON and save as CSV
def json_to_flat_csv(json_data, path):
    df = json_normalize(json_data)
    df.to_csv(path, index=False)
    return df

# Demonstration: Sample conversion
sample_json = [
    {
        "game_id": "123",
        "pitcher": {
            "id": "999",
            "name": "Justin Verlander"
        },
        "stats": {
            "IP": 6,
            "H": 4,
            "BB": 1
        }
    },
    {
        "game_id": "124",
        "pitcher": {
            "id": "998",
            "name": "Max Scherzer"
        },
        "stats": {
            "IP": 7,
            "H": 3,
            "BB": 2
        }
    }
]

# Save as JSON
json_path = "/mnt/data/sample_pitchers.json"
csv_path = "/mnt/data/sample_pitchers_flat.csv"

save_as_json(sample_json, json_path)

# Flatten and save as CSV
flat_df = json_to_flat_csv(sample_json, csv_path)

import ace_tools as tools; tools.display_dataframe_to_user(name="Flattened Pitcher Stats", dataframe=flat_df)
