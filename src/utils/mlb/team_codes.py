import requests
import logging
import json
from pathlib import Path
from utils.config_loader import load_config

logger = logging.getLogger(__name__)

# Load and validate config
cfg = load_config()
mlb_data = cfg.get("mlb_data", {})

season = mlb_data.get("season")
use_cache = mlb_data.get("use_cache", True)
cache_dir = mlb_data.get("cache_dir", ".cache")

if season is None:
    raise ValueError("Missing 'season' in mlb_data config")

cache_dir = Path(cache_dir).resolve()
cache_dir.mkdir(parents=True, exist_ok=True)
cache_path = cache_dir / f"team_codes_{season}.json"


def get_team_codes(mock_data: dict = None, disable_fallback: bool = False) -> dict:
    """
    Returns a mapping of team IDs to 3-letter abbreviations for the configured season.

    Args:
        mock_data (dict): If provided, returns this instead of calling the API.
        disable_fallback (bool): If True, do not use cached fallback.

    Returns:
        dict: { team_id: "BOS", ... }
    """
    if mock_data:
        logger.debug("[Mock] Returning mocked team codes")
        return mock_data

    url = f"https://statsapi.mlb.com/api/v1/teams?season={season}&sportId=1"

    try:
        logger.info(f"Fetching team codes from MLB API for season {season}")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()

        data = {
            t['id']: t.get('abbreviation') or t.get('triCode', '')
            for t in resp.json().get('teams', [])
        }

        if use_cache:
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                logger.info(f"✅ Saved team codes to cache at {cache_path}")
            except Exception as e:
                logger.warning(f"⚠️ Could not write cache file: {e}")

        return data

    except Exception as e:
        logger.error(f"❌ Failed to fetch team codes from API: {e}")

        if use_cache and not disable_fallback and cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                logger.info(
                    f"[Fallback] Loaded team codes from cache: {cache_path}")
                return cached
            except Exception as e2:
                logger.error(f"❌ Failed to load cached team codes: {e2}")

        raise RuntimeError(
            "Unable to retrieve team codes and no valid fallback available.")


def refresh_team_cache() -> dict:
    """
    Refresh the team code cache from live MLB API regardless of config fallback settings.

    Returns:
        dict: Freshly fetched team codes.
    """
    logger.info("🔄 Refreshing team codes cache from API")
    return get_team_codes(disable_fallback=True)


if __name__ == "__main__":
    print("=== Team Code Fetch Test ===")
    try:
        codes = get_team_codes()
        print(f"Total teams loaded: {len(codes)}")
        print(f"Sample: {list(codes.items())[:5]}")
    except Exception as e:
        print(f"ERROR: {e}")
