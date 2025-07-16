#!/usr/bin/env python3
import json
import sys
from pathlib import Path
import logging
import logging.config
from utils.config_loader import load_config


def calculate_nrfi_score(values: dict, features_def: dict):
    """
    Compute weighted RFI score (0–100) from input values and feature definitions.
    Returns (score: float, had_missing_data: bool, missing_features: list[str])
    """
    score = 0.0
    had_missing_data = False
    missing_features = []

    for feat, conf in features_def.items():
        weight = conf['weight']
        bmin, bmax = conf['bounds']
        val = values.get(feat)

        if val in (None, 'NA'):
            had_missing_data = True
            missing_features.append(feat)
            continue

        try:
            val = float(val)
        except (ValueError, TypeError):
            had_missing_data = True
            missing_features.append(feat)
            continue

        clamped = max(min(val, bmax), bmin)
        norm = (clamped - bmin) / (bmax - bmin) if bmax > bmin else 0
        score += norm * weight

    return round(score * 100, 2), had_missing_data, missing_features


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <feature_values_json> or 'mock'")
        sys.exit(1)

    cfg = load_config()
    features_path = Path(cfg['models']['mlb_rfi']['feature_definitions_path'])
    with open(features_path, 'r') as fd:
        features_def = json.load(fd)

    arg = sys.argv[1]
    if arg.lower() == 'mock':
        values = {
            "xFIP": 4.0,
            "BarrelPct": 'NA',
            "f1_era": None,
            "WHIP": 1.2,
            "wRCp1st": 110,
            "wOBA3": 0.320,
            "test": True
        }
        print("Running mock test:")
        print(json.dumps(values, indent=2))
    else:
        input_path = Path(arg)
        if not input_path.exists():
            print(f"Error: file '{input_path}' not found.")
            sys.exit(1)
        with open(input_path, 'r') as fv:
            values = json.load(fv)

    score, had_missing, missing_feats = calculate_rfi_score(
        values, features_def)
    print(f"RFI score: {score}")
    print(f"Missing data: {'Yes' if had_missing else 'No'}")
    if missing_feats:
        print(f"Missing features: {', '.join(missing_feats)}")
