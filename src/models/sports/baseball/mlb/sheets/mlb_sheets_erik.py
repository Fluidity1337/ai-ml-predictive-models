import requests
from datetime import date
import pandas as pd
from bs4 import BeautifulSoup

# Add streaks, use ranks or averages for highlighting.
# for output, name the file nogames.pdf

# https://www.foxsports.com/mlb/injuries is a good injuries list
# https://www.foxsports.com/mlb/schedule?date=2025-03-31 a good, easy one for just the games, but no pitcher info
# https://www.mlb.com/schedule this one is definitely the best, has starting pitchers too
# rotowire might have the best: https://www.rotowire.com/baseball/daily-lineups.php
# ^^^^ this one shows pitcher and expected lineup, batter handedness, pitcher handedness, betting lines, and whether it's a domed stadium
# 
# the stats are going to be really hard, and may need to cross-reference. can NOT put all batters from every team, it's ridiculous
# check which batters the sportsbooks list and use that to determine. maybe it's season's at-bats #, slash, etc.
# 
# baseball reference for sched is easy and basic: https://www.baseball-reference.com/leagues/MLB-schedule.shtml#today
# https://www.baseball-reference.com/previews/2025/LAN202503310.shtml
# Each game has a "preview", and following that link summarizes team stats and has AMAZING pitcher stats
# That same fucking page has team's batters vs other team's starting pitcher...this is incredible
# lastly, it gives you batter and pitcher stats for each team. will still need advanced stats, but that is a damn good start
# 
# Doink is outstanding, but hard to scrape - https://doinksports.com/research/mlb
# MLB is pretty great for basic/adv stats - https://www.mlb.com/stats/2024?split=i01&playerPool=ALL_CURRENT&position=P
# 
# Statcast is best place to get the crazy data, just have to figure out columns: https://baseballsavant.mlb.com/leaderboard/custom?year=2024&type=pitcher&filter=&min=q&selections=pa%2Ck_percent%2Cbb_percent%2Cwoba%2Cxwoba%2Csweet_spot_percent%2Cbarrel_batted_rate%2Chard_hit_percent%2Cavg_best_speed%2Cavg_hyper_speed%2Cwhiff_percent%2Cswing_percent&chart=false&x=pa&y=pa&r=no&chartType=beeswarm&sort=xwoba&sortDir=asc
# IF needed, transition to 

# Statistics:
# Slugging Percentage (SLG) - because total bases is a component of it divided by at-bats; higher = more extra-base hits, highlight by top/bottom %
# Isolated Power (ISO) - extra-base hit ability = SLG - BA
# Batting Average (BA) - 
# OPS (On-Base Plus Slugging) - 
# TB/G - Just avg total bases per game
# H/AB - Hits per at-bat
# LHP vs RHP, home vs away, day vs night, etc.
# FOR MATCHUPS:
# Pitcher WHIP (higher = more baserunners)
# Pitcher HR/9 (susceptibility to extra-base hits)
# SLG Allowed (how hard pitcher gets hit)
# BABIP? (BA on balls in play) - low means fewer hits allowed; really a measure for luck (> .400 = inflated and < .200 deflated)
# Ballpark Factor
# Weather Factor
# 
# Need to factor in how many pitches thrown in L2-3 days, pitchers/inning/etc
# 
# 
# 
# wRC+ (how good a hitter is, higher is better, 100 is league avg)
# OPS+ (how good a hitter is, higher is better, 100 is league avg)
# ERA+ (how good a pitcher is, higher is better, 100 is league avg)
# ERA- (how good a pitcher is, lower is better, 100 is avg, calc'd diff from ERA)
# /9 tells you how good compared to other pitchers b/c they pitch diff number of innings
# K/9 (over 10 is pretty good, less than 9 has trouble finishing hitters off)
# BB/9 (over 3.5 is a lot, under 2 very good)
# If K/9 is 3x BB/9, they're doing really well even with high BB/9 or low K/9
# K% = K/9 but shows vs # of batters instead of # innings (20% avg, < 15% bad, 25% elite)
# BB% = Avg 8, >9 bad, <7.5 very good
# Modern Slash lines are AVG/OBP/SLG/OPS
# 
# 

today = date.today().strftime('%A, %B %-d, %Y')
# have to use selenium for baseball-reference, look at it later
url = 'https://www.rotowire.com/baseball/daily-lineups.php'
# need to get headers
resp = requests.get(url)
# add check to make sure the banner at the top says the actual date (<div class="page-title__secondary">Starting MLB lineups for March 31, 2025</div>)
soup = BeautifulSoup(resp.text, 'html.parser')
lineups = [l for l in soup.find_all('div', class_='lineup') if 'is-mlb' in l['class'] and 'is-tools' not in l['class']]
games = []

# will obviously need to think this through better, this is sloppy
# can really use class=is-visit and get all of that at once
for lineup in lineups:
	make_home_lineup_var = ''
	make_away_lineup_var = ''
	# this can get pitcher W-L ERA - class=lineup__player-highlight-stats
	data = {
		'time': lineup.find('div', class_='lineup__time').text,
		'home_team': lineup.find('div', class_='is-home').text.strip(),
		'away_team': lineup.find('div', class_='is-visit').text.strip(),
		'home_pitcher': lineup.find_all('div', class_='lineup__player-highlight-name')[1].select('a')[0].text,
		'away_pitcher': lineup.find_all('div', class_='lineup__player-highlight-name')[0].select('a')[0].text,
		'home_batters': lineup.find_all('li', class_=),
		'away_batters': ,
	}

[p.select_one('a')['title'] for p in lineup.find_all('li', class_='lineup__player')]









# global variable assignment
endpoints = ['leaguedashplayerstats', 'leaguedashteamstats', 'scheduleleaguev2']
session = requests.Session()
session.headers = nba_stats_headers
base_url = 'https://stats.nba.com/stats/'
schedule = None
injuries = None
data_dict = {}

# function here for gathering data - might not even need pandas
def get_data(url, query_dict={}, req_headers=api_header_dict):
    # add in req_headers = {}; will auto-use api_header_dict for any that match url.startswith(base_url)
    ####################################################
    # if url in endpoints, use base_url
    ####################################################
    if url.startswith(base_url):
        response = session.get(base_url + endpoint, params=query_dict, headers=req_headers)
    else:
        response = requests.get(url, params=query_dict, headers=req_headers)
    response.raise_for_status()
    # possibly add a comparison here to do json.loads and compare them before returning response.json()
    return response.json()

def get_schedule():
    date_str = date.today().strftime('%m/%d/%Y %H:%M:%S')
    params = {
        'LeagueID': '00',
        'Season': '2024-25'
    }
    sched_data = get_data('scheduleleaguev2', query_dict=params)
    game_days = sched_data['leagueSchedule']['gameDates']
    # it could be better to just do startswith in the list comprehension, or do date_str in games['gameDate']
    # might be better as for loop, depends on error handling and likelihood of failure
    # re method ended up working too, I just think it's not as clear, but may be better as comprehension
    # give filter a try, see if it works better: https://stackoverflow.com/questions/69912399/json-python-search-for-value-in-dict-based-on-another-value-in-same-dict-list
    # also add re as a backup method
    games_today = next(
        games['games']
        for games in game_days
        if games['gameDate'] == date_str
    )
    return {
        teams[game['homeTeam']['teamTricode']]: {
            'location': 'home'
            'opponent': game['awayTeam']['teamTricode']
        }
        teams[game['awayTeam']['teamTricode']]: {
            'location': 'away'
            'opponent': game['homeTeam']['teamTricode']
        }
        for game in games_today
    }

def get_injuries():
    injuries_api = 'https://www.rotowire.com/basketball/tables/injury-report.php?team=ALL&pos=ALL'
    injury_data = get_data(injuries_api)
    # need to test for name consistency like AJ/A.J., hyphenated names, Jr./II, etc.
    return {
        player['player']:player['team']
        for player in injury_data
        if 'Out' in player['status']
    }
