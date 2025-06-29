#!/usr/bin/env python3
"""
fangraphs_scraper.py

Fetches every team’s first-inning wRC+ (wRCp1st) from a FanGraphs CSV Data URI
and decodes it into a pandas DataFrame.

Usage:
  1. In your browser, click the CSV export button on the Splits Leaderboards
     (1st Inning, Team) to copy the generated data URI (data:application/csv;...).
  2. Run this script passing that URI:
       python fangraphs_scraper.py '<data_uri>'

Dependencies:
  - Python packages: pandas
"""

import sys
import urllib.parse
from io import StringIO
import pandas as pd


def decode_data_uri(data_uri: str) -> pd.DataFrame:
    """
    Decodes a CSV Data URI into a pandas DataFrame.
    Expects format 'data:application/csv;charset=utf-8,<percent-encoded-csv>'.
    Returns the parsed DataFrame.
    """
    try:
        prefix, encoded = data_uri.split(',', 1)
    except ValueError:
        raise ValueError("Invalid Data URI: missing comma separator")
    # Percent-decode
    csv_text = urllib.parse.unquote(encoded)
    # Load into pandas
    return pd.read_csv(StringIO(csv_text))


def main():
    if len(sys.argv) != 2:
        print("Usage: python fangraphs_scraper.py '<data_uri>'")
        sys.exit(1)

    data_uri = sys.argv[1]
    try:
        df = decode_data_uri(data_uri)
    except Exception as e:
        print(f"Error decoding Data URI: {e}", file=sys.stderr)
        sys.exit(1)

    # Ensure correct columns exist
    if 'Tm' not in df.columns and 'Team' in df.columns:
        df.rename(columns={'Team': 'Tm'}, inplace=True)
    df = df.rename(columns=lambda c: c.strip())

    # Select only team code and wRC+
    if 'Tm' not in df.columns or 'wRC+' not in df.columns:
        print("Decoded CSV does not contain required 'Tm' and 'wRC+' columns.")
        sys.exit(1)
    team_wrcp1st = df[['Tm', 'wRC+']]

    # Output results
    print("First-inning wRC+ for each team:\n")
    print(team_wrcp1st.to_string(index=False))
    # Optionally save
    team_wrcp1st.to_csv('wrcp1st_by_team.csv', index=False)
    print("\nSaved to 'wrcp1st_by_team.csv'")


if __name__ == '__main__':
    main()
