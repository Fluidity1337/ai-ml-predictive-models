import pandas as pd
import json


class RatingCalculator:
    """
    Calculates ratings (0–100) for various metrics using min-max scaling.
    """

    def __init__(self, features_cfg):
        self.features_cfg = features_cfg

    def minmax_scale(self, value, feature_name, reverse=True):
        bounds = self.features_cfg[feature_name]["bounds"]
        min_value, max_value = bounds
        if pd.isna(value):
            return 50.0  # Neutral midpoint
        scaled = (value - min_value) / (max_value - min_value)
        scaled = max(0.0, min(1.0, scaled))
        return round((1 - scaled) * 100 if reverse else scaled * 100, 1)

# REMOVE BELOW


class FeatureConfigLoader:
    """
    Loads and provides access to the features configuration.
    """
    @staticmethod
    def load_features_config(features_path):
        with open(features_path, "r", encoding="utf-8") as f:
            return json.load(f)
