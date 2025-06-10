import requests
from datetime import date
import pandas as pd

# IMPORTANT: Figure out how to trim data for players - may need to factor in games played as % and/or usage; this is why there's value in doing Last X games
#     Min. 5 games played?
# Add notes at the bottom for a type of glossary, depending if PDF can do it?
# Add streaks, use ranks or averages for highlighting.
# for output, name the file nogames.pdf

#make sure to mask headers
nba_stats_headers = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'en-US,en;q=0.5',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Host': 'stats.nba.com',
    'Referer': 'https://stats.nba.com/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:72.0) Gecko/20100101 Firefox/72.0',
    'x-nba-stats-origin': 'stats',
    'x-nba-stats-token': 'true',
}
player_stats_params = {
    'ActiveRoster': '',
    'College': '',
    'Conference': '',
    'Country': '',
    'DateFrom': '',
    'DateTo': '',
    'Division': '',
    'DraftPick': '',
    'DraftYear': '',
    'GameScope': '',
    'GameSegment': '',
    'GameSubtype': '',
    'Height': '',
    'ISTRound': '',
    'LastNGames': '0',
    'LeagueID': '00',
    'Location': '',
    'MeasureType': 'Base',
    'Month': '0',
    'OpponentTeamID': '0',
    'Outcome': '',
    'PaceAdjust': 'N',
    'Period': '0',
    'PerMode': 'PerGame',
    'PlayerExperience': '',
    'PlayerPosition': '',
    'PlusMinus': 'N',
    'PORound': '0',
    'Rank': 'N',
    'Season': '2024-25',
    'SeasonSegment': '',
    'SeasonType': 'Regular Season',
    'ShotClockRange': '',
    'StarterBench': '',
    'TeamID': '0',
    'TwoWay': '',
    'VsConference': '',
    'VsDivision': '',
    'Weight': ''
}
team_stats_params = {
    'Conference': '',
    'DateFrom': '',
    'DateTo': '',
    'Division': '',
    'GameScope': '',
    'GameSegment': '',
    'GameSubtype': '',
    'ISTRound': '',
    'LastNGames': '0',
    'LeagueID': '00',
    'Location': '',
    'MeasureType': 'Base',
    'Month': '0',
    'OpponentTeamID': '0',
    'Outcome': '',
    'PaceAdjust': 'N',
    'Period': '0',
    'PerMode': 'PerGame',
    'PlayerExperience': '',
    'PlayerPosition': '',
    'PlusMinus': 'N',
    'PORound': '0',
    'Rank': 'N',
    'Season': '2024-25',
    'SeasonSegment': '',
    'SeasonType': 'Regular Season',
    'ShotClockRange': '',
    'StarterBench': '',
    'TeamID': '0',
    'TwoWay': '',
    'VsConference': '',
    'VsDivision': ''
}

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

'''
Player Stats Needed:        

1Q Player:
    PPG (Top 3):    Regular
    USG             Advanced
    3PA             Regular
    +/-             Regular
1Q Team:
    PPG             Regular
    OPP Allow PPG   Opponent
    PACE            Advanced
    EFG             Advanced
    OFFRTG          Advanced
    OPP DEFRTG      Opponent
    TOV             Advanced
    FTA/FGA         Regular
1Q Trends:
    B2B Trend       I can at least add whether they're on a B2B
    Home/Away       This one is a pain...but I guess I can grab it by player id/team id. leave it for later
    ATS Record      Do this later
    Foul trend      PFD for trend of drawing fouls. If it's for specific refs...not gonna happen

Player Pts 1Q O/U                   PPG, EFG, TS%, 3PA (3P%), FTA, (location factor [if on team for > 5 games if possible]), USG, +/-, Pace, ATS, OFF EFF, DEF EFF
Player 1H doesn't really exist      
Team Pts 1Q O/U                     
Team Pts 1H O/U                     
Player PRA O/U                      
*** Add flame icon if player is hot, which requires large differential b/w L10/season and L3
*** Add in PIE metric
*** For PRA: https://www.bettingpros.com/nba/props/over-under-trends/points-assists-rebounds/
*** Styling + columns = https://www.threads.net/@jimmysportpicks099/post/DHB--e2iUmD/media

Teams: [Top 5/10 in both off and def eff], ATS disclaimer (Top 5/10 in both off and def eff), 
Hot could be L3 shooting avgs are > than 120%; maybe for teams, 


1Q Player: PPG, USG, 3PA, +/-, EFG, FTA, Home/Away, ATS, Usage, Pace, TS%
1Q Team: PPG, OPP Allowed PPG, 3PA, PACE, EFG, OFFRTG, OPP DEFRTG, TOV, FTA, FTA/FGA, OPP TO vs PTS OFF TO?, 

Find score differentials, shooting percentages, defensive efficiency.
How to incorporate injuries? - eventually factor in defensive +/- if opp player is injured/out !!! Check out DIFF% & Player PTS DIFF
Home court advantage is pretty important
Offensive vs defensive efficiency scores show if they capitalize on opportunities
Figure out how to mark hot teams > would need to be a combo of last 5-10 games scoring differentials, shooting %s, and tempo/pace
IMPORTANT: it's seeming like for Teams, it's better to pull all the data I need, and it can be applied to opponent stats in player sheets
Get current average line if possible - nba has an endpoint for that
+/- is a team's point differential
net rating is (off rtg - def rtg) is +/- adjusted per 100 possessions
PIE is the nba-generated advanced stat combines real box stats - huge indicator of win/loss
Four factors could be the goat - keep researching: https://www.sportsgamblingpodcast.com/2020/04/20/nba-most-valuable-statistic/
Fastbreak efficiency?
Add minutes played?
Since good defenses can limit players, add columns for that; compare paces
Explain pace: https://www.sportsbettingdime.com/guides/how-to/nba-pace-factor/#:~:text=That's%20what%20Pace%20Factor%20is,in%20total%20(both%20sides).
1Q/1H betting stats: https://www.oddsshark.com/nba/1st-quarter-1st-half-betting
Incorporate L5 and/or L5 home/L5 away
Another pace article: https://www.covers.com/forum/nba-betting-22/overunder-formulas-103297843
Over vs under as teams
Pace vs L5???
https://www.reddit.com/r/sportsbook/comments/67hj5n/math_and_nba_betting_what_ive_been_doing_for_two/

Pretty good shit:
TS% factors in 3s counting for more than 2s and free throws: https://www.reddit.com/r/nba/comments/1j5l0z/basic_advanced_stats_guide/
REB% adjusts for pace and maybe minutes > explain with link above
Additional shooting stats to show shooting vs layups/dunks/rim stuff: https://www.nba.com/stats/players/shooting
TOV% adjusts for minutes/pace

    Depending on how complicated this gets, I can always get teams/players for the day, their ids, and use individual calls
    ANOTHER IDEA! If I just get reg and adv for each team, I don't have to do the opponent one. Maybe have to defense though.
'''

def get_stats(teams):
    # get all defensive ratings stats for each team playing today
    # check out all of the neat stats/organization on https://www.basketball-reference.com/leagues/NBA_2025.html
    # especially need strength of schedule

    # RESUME FOR REAL: Make list of all actual stats I need and determine what they're in. Remember, OPP stuff can be gotten for each team.
    # Like if LAL vs DEN, each has basic def stats, so don't have to call opponent tab

    if type == 'player':
        # do something (determine endpoint)
    elif type == 'team':
        # do something (determine endpoint)
    else:
        # throw error, or is this a valid case?

'''
1. Get today's games
2. Get injured players on teams for today's game
3. If player averages 15+ minutes over last 20 games, keep in injury report
4. Call get_stats a lot, and end up with a dict like this: {
    ''
}

Name/Team/Location/Opp satisfied by any sheets + schedule
Player: Min/Game, 









'''


'''
# RESUME: I've got a full list of headers, and really only need two endpoints; it's time to just add the logic. If there are improvements, make them later, because HTML is going to be a fucking bitch.
#         I think I should make a giant dict with the headers included in each request. It'll make it easier to find the obscure ones. Maybe not though, not really necessary.
#         Logic for specific stuff aside, data accumulation/presentation/html should be a separate file because it'll apply to everything.
'''

    # can also use list of k:v pairs like tuples maybe; gonna have to use dict comprehension to handle the args; filter out players with like 3 GP
    # Look, just get the basic fucking stats. Then you can work on the calculations for who is hot
    # might end up wanting to focus on home vs away, but can add it later
    # IMPORTANT: might be easier to focus on players and use different endpoints to just get all stats for a player/team
    # IMPORTANT (MAYBE): I feel like only last 20-25 games matter, not full season; use L15 or L20 as a benchmark
    # original returns, when specific to a game, should have an available_flag column which says if they played or not
    # when I do streaking, will have to pull games for specific dates, pull 1Q pts, and see. that, or I can use gambling streak (just beating the lines)
# Replace all _PCT with %
# Merge all M>A>_PCT so like 3P would be % (Made/Attempts)


def main():
    schedule = get_schedule()
    injuries = [player for player,team in get_injuries() if team in sched]

    # get data and figure out how to combine it all
    # search downloaded library to examine headers

notes = '''
# 1H - GameSegment=First+Half
#   Add FastBreak points later (it's on Misc page; Scoring page has %PTS OFF FB PTS)
#   Player: only include top 3 players per team
#   Player: Assist-to-turnover ratio (on advanced)
#   Player: True Shooting % [why vs efg%] (on advanced)
#   Player: 1H Foul Rate for early foul trouble (on regular - PF) --- should we put context on it, like for minutes/usage/etc.
# PRA - PRA Avg (over 10 games), Home vs Away (on basic, Location=Home|Location=Road), usg, min/game, fga, efficiency (separate TS and eFG),
#       Rebound Opportunities (REB CHANCE & REB CHANCE %), Potential Assists (https://www.nba.com/stats/players/passing endpoint: POT_AST), L5 PRA Trend
#       Extras = Specific opp def rtg, opp reb allowed/rank, opp ast allowed/rank, Opp PFD (fouls drawn) per game
# Choose either L5 or L10 to pull, no reason to do both

# IMPORTANT: Figure out how to trim data for players - may need to factor in games played as % and/or usage; this is why there's value in doing Last X games
#     Min. 5 games played?

'''

'''
####################################################################
# 
# jstats = json_set['leagueSchedule']['gameDates'] <<< not all endpoints return same json format
# resp = r.get(games_api, params=params, headers=api_header_dict)
# Make it flexible with the dates and API URLs so I don't have to update it next season
# Odds > when loading nba.com/schedule, do dev tools > Network > odds_todaysGames.json
# 
# MAIN SECTION BELOW
####################################################################

sched_json = requests.get(schedule_endpoint)
nba_sched = json.loads(sched_json.text)
l1 = nba_sched.leagueSchedule # returns object
l2 = nba_sched.gameDates # returns array of objects
l3 = nba_sched.gameDate
'''