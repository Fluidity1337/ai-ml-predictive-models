import json
from pathlib import Path


def find_config_path(filename: str = "config.json") -> Path:
    """
    Walk upwards from this file's directory to locate the given config file.
    Returns the Path to the first matching file.
    Raises FileNotFoundError if not found.
    """
    current = Path(__file__).resolve()
    for parent in (current, *current.parents):
        candidate = parent / filename
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"Could not locate {filename} in any parent directories")


def load_config(filename: str = "config.json") -> dict:
    """
    Load and parse the JSON config file from the project root (or nearest parent).

    Usage:
        from utils.config_loader import load_config
        config = load_config()
    """
    path = find_config_path(filename)
    try:
        content = path.read_text(encoding="utf-8")
        return json.loads(content)
    except Exception as e:
        raise RuntimeError(f"Failed to load config from {path}: {e}")
