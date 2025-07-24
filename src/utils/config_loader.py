import json
import yaml
import warnings
from pathlib import Path

# Suppress FutureWarnings globally for pybaseball
warnings.filterwarnings("ignore", category=FutureWarning, module="pybaseball")

def find_project_root(markers=(".git", "pyproject.toml", "requirements.txt")) -> Path:
    """
    Walk upwards from this file's directory to locate a project root marker.
    Returns the Path to the project root directory.
    Raises FileNotFoundError if not found.
    """
    current = Path(__file__).resolve().parent
    for parent in (current, *current.parents):
        for marker in markers:
            if (parent / marker).exists():
                return parent
    raise FileNotFoundError(f"Could not locate project root using markers: {markers}")

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
    print(f"[DEBUG] Loading config from: {path}")
    try:
        content = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            config = yaml.safe_load(content)
        elif path.suffix == ".json":
            config = json.loads(content)
        else:
            # attempt YAML first, then JSON
            try:
                config = yaml.safe_load(content)
            except Exception:
                config = json.loads(content)

        # Force root_path to always be the detected project root
        try:
            project_root = str(find_project_root())
            config["root_path"] = project_root
            print(f"[DEBUG] Forced root_path to project root: {project_root}")
        except Exception as e:
            print(f"[WARN] Could not auto-detect project root: {e}")
        return config
    except Exception as e:
        raise RuntimeError(f"Failed to load config from {path}: {e}")
