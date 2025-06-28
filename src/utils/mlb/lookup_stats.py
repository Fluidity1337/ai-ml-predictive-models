import logging
import pandas as pd
import requests

try:
    import pybaseball
    HAS_PYBASEBALL = True
except ImportError:
    HAS_PYBASEBALL = False

if not HAS_PYBASEBALL:
    raise ImportError(
        "This script requires pybaseball. Please install it with `pip install pybaseball`.")


def lookup_stats(pid: int, name: str, df: pd.DataFrame, group: str, season: str = "2025") -> dict:
    # 0) Initialize empty dict up front
    stat: dict = {}
    if pid is None:
        logging.debug(
            f"[LookupStats]  → skipping lookup for {name!r} because pid is None")
        return stat
    logging.debug(f"[LookupStats] {group.upper()} for {name} (ID={pid})…")

    # 1) Primary statsapi GET
    try:
        url = f"https://statsapi.mlb.com/api/v1/people/{pid}/stats?stats=season&group={group}&season={season}"
        res = requests.get(url)
        res.raise_for_status()
        stats_list = res.json().get('stats', [])
        if stats_list and isinstance(stats_list, list):
            splits = stats_list[0].get('splits', [])
        else:
            splits = []
        if splits:
            stat = splits[0].get('stat', {}) or {}
            logging.debug(f"[LookupStats]  → API returned {len(stat)} fields")
        else:
            logging.debug("[LookupStats]  → API returned no splits")

    except Exception:
        logging.debug(
            f"[LookupStats]  → Primary API failed for {name}", exc_info=True)
    # 2) Hydrated people endpoint
    try:
        url2 = (f"https://statsapi.mlb.com/api/v1/people/{pid}"
                f"?hydrate=stats(group={group},type=season,season={season})")
        res2 = requests.get(url2)
        res2.raise_for_status()
        ppl = res2.json().get('people', [])
        if ppl and isinstance(ppl, list):
            splits2 = ppl[0].get('stats', [{}])[0].get('splits', [])
        else:
            splits2 = []
        if splits2:
            stat = splits2[0].get('stat', {}) or {}
            logging.debug(
                f"[LookupStats]  → hydrated API returned {len(stat)} fields")
    except Exception:
        pass
    # 3) pybaseball fallback - Merge in pybaseball season-level stats (FIP, xFIP, etc.) by player name
    if HAS_PYBASEBALL and not df.empty:
        try:
            # pybaseball declares hitters/pitchers in a 'Name' column
            row = df[df['Name'] == name]
            if not row.empty:
                pyb = row.iloc[0].dropna().to_dict()
                stat.update(pyb)
                logging.debug(
                    f"[LookupStats]  → merged {len(pyb)} pybaseball fields")
        except Exception:
            logging.debug(
                f"[LookupStats]  → pybaseball merge failed for {name}", exc_info=True)

    stat["season"] = season
    # logging.debug(f"[LookupStats]  → returning keys: {list(stat.keys())}")
    return stat


if __name__ == "__main__":
    import logging
    import pandas as pd

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s — %(levelname)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Example: Mitch Keller (ID=656605)
    test_pid = 656605
    test_name = "Mitch Keller"
    test_group = "pitching"
    test_season = "2025"

    # Create empty DataFrame with Name column (pybaseball fallback)
    df_test = pd.DataFrame(columns=["Name"])

    result = lookup_stats(test_pid, test_name, df_test,
                          test_group, test_season)
    print("\n[Unit Test] Stats returned:\n")
    for k, v in result.items():
        print(f"{k}: {v}")
