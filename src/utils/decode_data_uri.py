#!/usr/bin/env python3
import sys
import urllib.parse
from io import StringIO
import pandas as pd


def main():
    if len(sys.argv) != 2:
        print("Usage: python decode_data_uri.py '<data_uri>'")
        sys.exit(1)
    data_uri = sys.argv[1]
    try:
        _, encoded = data_uri.split(",", 1)
    except ValueError:
        print("Error: Invalid Data URI.")
        sys.exit(1)
    # Percent-decode the CSV text
    csv_text = urllib.parse.unquote(encoded)
    # Read into a pandas DataFrame
    df = pd.read_csv(StringIO(csv_text))
    # Print preview and save full CSV
    print("Decoded CSV preview:\n")
    print(df.head().to_string(index=False))
    out_path = "decoded_output.csv"
    df.to_csv(out_path, index=False)
    print(f"\nFull decoded data saved to '{out_path}'")


if __name__ == "__main__":
    main()
