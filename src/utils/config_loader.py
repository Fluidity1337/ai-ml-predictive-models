import json
import yaml
import warnings
from pathlib import Path

# Suppress FutureWarnings globally for pybaseball
warnings.filterwarnings("ignore", category=FutureWarning, module="pybaseball")


def find_config_path(filename: str = "config/config.yaml") -> Path:
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


def load_config(filename: str = "config/config.yaml") -> dict:
    """
    Load and parse the YAML or JSON config file from the project root (or nearest parent).

    Usage:
        from src.utils.config_loader import load_config
        config = load_config()
    """
    path = find_config_path(filename)
    try:
        content = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(content)
        elif path.suffix == ".json":
            return json.loads(content)
        else:
            # attempt YAML first, then JSON
            try:
                return yaml.safe_load(content)
            except Exception:
                return json.loads(content)
    except Exception as e:
        raise RuntimeError(f"Failed to load config from {path}: {e}")
