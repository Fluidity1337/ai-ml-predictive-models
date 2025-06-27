
import logging
import argparse
import math
import sys
import logging
from datetime import datetime, timedelta
from pybaseball import statcast_pitcher, pitching_stats_range

# logging config (DEBUG for dev; switch to INFO/WARNING in production)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s — %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


def first_inning_xfip_last_30(
    pitcher_id: int,
    days: int = 30,
    lg_hr_fb: float = 0.105,
    fip_constant: float = 3.10
) -> float:
    """
    Compute 1st-inning xFIP over the last `days` days, falling back to
    overall xFIP if no 1st-inning data is available.
    """
    logging.info(
        "Calculating 1st-inning xFIP for %s over last %d days", pitcher_id, days)
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)
    sd, ed = start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
    logging.debug("Date range: %s → %s", sd, ed)

    # 1) Try Statcast first-inning split
    try:
        df = statcast_pitcher(sd, ed, pitcher_id)
        logging.debug("Fetched %d pitches for %s", len(df), pitcher_id)
    except Exception:
        logging.exception(
            "Statcast fetch failed for %s, falling back", pitcher_id)
        return _fallback_overall_xfip(pitcher_id, sd, ed, fip_constant)

    df1 = df[df["inning"] == 1]
    logging.debug("  → %d first-inning pitches", len(df1))
    if df1.empty:
        logging.warning(
            "No 1st-inning data for %s—using overall xFIP", pitcher_id)
        return _fallback_overall_xfip(pitcher_id, sd, ed, fip_constant)

    # count events
    hr = df1["events"].eq("home_run").sum()
    bb = df1["events"].isin(["walk", "intent_walk"]).sum()
    hbp = df1["events"].eq("hit_by_pitch").sum()
    k = df1["events"].eq("strikeout").sum()
    fb = df1[(df1["launch_speed"].notna()) & (
        df1["launch_angle"] > 15)].shape[0]
    outs = df1["outs_when_up"].sum()
    ip = outs / 3.0
    logging.debug(
        "Events: HR=%d, BB=%d, HBP=%d, K=%d, FB=%d → IP=%.2f", hr, bb, hbp, k, fb, ip)

    # compute xFIP
    hr_exp = fb * lg_hr_fb
    xfip1 = (13*hr_exp + 3*(bb + hbp) - 2*k) / ip + fip_constant
    logging.info("1st-inning xFIP for %s = %.2f", pitcher_id, xfip1)
    return xfip1


def _fallback_overall_xfip(
    pitcher_id: int,
    start_date: str,
    end_date: str,
    fip_constant: float
) -> float:
    """
    Fetch overall pitching stats for the same window via pitching_stats_range
    and return xFIP if available.
    """
    try:
        ps = pitching_stats_range(start_date, end_date)
        logging.debug("Fetched overall pitching stats (%d rows)", len(ps))
        row = ps.loc[ps['ID'] == pitcher_id]
        if not row.empty and 'xFIP' in row:
            xfip = float(row.at[row.index[0], 'xFIP'])
            logging.info("Fallback overall xFIP for %s = %.2f",
                         pitcher_id, xfip)
            return xfip
        else:
            logging.error("No overall xFIP found for %s in range %s–%s",
                          pitcher_id, start_date, end_date)
    except Exception:
        logging.exception(
            "Failed to fetch overall pitching stats for %s", pitcher_id)

    # As last resort, return NaN so downstream can detect missing
    return float('nan')


def main():
    parser = argparse.ArgumentParser(
        description="Compute first-inning xFIP over the past N days for a given pitcher"
    )
    parser.add_argument(
        "pitcher_id", type=int,
        help="MLBAM pitcher ID (e.g. 605141 for Gerrit Cole)"
    )
    parser.add_argument(
        "--days", type=int, default=30,
        help="Lookback window in days (default: 30)"
    )
    args = parser.parse_args()

    try:
        xfip = first_inning_xfip_last_30(
            pitcher_id=args.pitcher_id,
            days=args.days
        )
        if xfip is None or math.isnan(xfip):
            logging.warning(
                "xFIP unavailable for pitcher %s over last %d days",
                args.pitcher_id, args.days
            )
            sys.exit(1)
        else:
            logging.info(
                "First-inning xFIP for %s over last %d days: %.2f",
                args.pitcher_id, args.days, xfip
            )
    except Exception:
        logging.exception("Failed to compute first-inning xFIP")
        sys.exit(2)


if __name__ == "__main__":
    # configure logging at the very last moment
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s — %(levelname)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    main()
