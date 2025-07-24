
import os
import sqlite3
from utils.config_loader import load_config

def ensure_db_dir(db_path):
    dir_path = os.path.dirname(db_path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)

def connect_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def create_schema(cur):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS teams (
        team_id INTEGER PRIMARY KEY AUTOINCREMENT,
        mlb_id INTEGER UNIQUE NOT NULL,
        name TEXT NOT NULL,
        abbreviation TEXT NOT NULL
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS players (
        player_id INTEGER PRIMARY KEY AUTOINCREMENT,
        mlb_id INTEGER UNIQUE NOT NULL,
        first_name TEXT,
        last_name TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS games (
        game_id INTEGER PRIMARY KEY AUTOINCREMENT,
        mlb_game_id INTEGER UNIQUE NOT NULL,
        game_date DATE,
        home_team_id INTEGER REFERENCES teams(team_id),
        away_team_id INTEGER REFERENCES teams(team_id)
    );
    """)

def insert_example_data(cur):
    cur.execute("INSERT OR IGNORE INTO teams (mlb_id, name, abbreviation) VALUES (1, 'Sample Team', 'ST')")
    cur.execute("INSERT OR IGNORE INTO players (mlb_id, first_name, last_name) VALUES (100, 'John', 'Doe')")

def main():
    config = load_config()
    try:
        root_path = config["root_path"]
        print(f"[DEBUG] root_path (auto-detected): {root_path}")
    except KeyError:
        import sys
        import importlib.util
        config_loader_path = os.path.join(os.path.dirname(__file__), '..', 'utils', 'config_loader.py')
        spec = importlib.util.spec_from_file_location("config_loader", os.path.abspath(config_loader_path))
        config_loader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_loader)
        root_path = str(config_loader.find_project_root())
        print(f"[WARN] root_path not found in config, auto-detected: {root_path}")
    # Get db path from mlb_data.data_lake_filepath in config.yaml
    mlb_data = config.get("mlb_data", {})
    #print(f"[DEBUG] mlb_data section from config: {mlb_data}")
    db_path_config = mlb_data.get("data_lake_filepath")
    if not db_path_config:
        db_path_config = mlb_data.get("data_lake_path")
    if not db_path_config:
        raise ValueError("'mlb_data.data_lake_filepath' or 'mlb_data.data_lake_path' must be set in config.yaml for database path resolution.")
    # If db_path_config is absolute, use as is; else resolve relative to project_root
    if os.path.isabs(db_path_config):
        resolved_db_path = os.path.normpath(db_path_config)
    else:
        resolved_db_path = os.path.normpath(os.path.abspath(os.path.join(root_path, db_path_config)))
    print(f"[DEBUG] root_path: {root_path}")
    print(f"[DEBUG] db_path: {resolved_db_path}")
    if not resolved_db_path:
        raise ValueError("'data_lake_path' not set in config.yaml and default could not be determined.")
    # Prevent DB from being created inside any 'src' directory
    db_path_norm = os.path.normpath(resolved_db_path).lower()
    src_norm = os.path.normpath(os.path.join(root_path, 'src')).lower()
    if db_path_norm.startswith(src_norm):
        raise ValueError(f"Database path {resolved_db_path} is inside a 'src' directory. Please set 'root_path' or 'data_lake_path' in config.yaml to a location outside 'src'.")
    ensure_db_dir(resolved_db_path)
    if os.path.exists(resolved_db_path):
        print(f"[INFO] Database already exists at {resolved_db_path}. Connecting...")
    else:
        print(f"[INFO] Database does not exist. Creating new database at {resolved_db_path}.")
    conn = connect_db(resolved_db_path)
    cur = conn.cursor()
    create_schema(cur)
    insert_example_data(cur)
    conn.commit()
    conn.close()
    if os.path.exists(resolved_db_path):
        print(f"[SUCCESS] Database is ready at {resolved_db_path}")
    else:
        print(f"[ERROR] Database was not created at {resolved_db_path}")

if __name__ == "__main__":
    main()

