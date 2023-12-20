import json
import time

import requests
from datetime import datetime, timedelta
import pandas as pd

FROM_DATE = "2022-06-28"
TO_DATE = "2022-07-30"

NUMBER_OF_POSITION = 4

TIME_BETWEEN_REQUESTS = 10
MEETING_FILTER=["ROSEHILL","CAULFIELD","MORPHETTVILLE", "FLEMINGTON", "RANDWICK","SUNSHINE" "COAST"]

def requestMeetings(url):
    isException = True
    meetings = []
    while isException:
        try:
            response = requests.request("GET", url, headers={'Content-Type': 'application/json'})
            meetings = response.json()['meetings']
            isException = False
        except Exception as e:
            print("Wait... Request again now: ")
            isException = True
            time.sleep(TIME_BETWEEN_REQUESTS)
    return meetings


def requestRunners(url):
    isException = True
    runners = []
    while isException:
        try:
            response = requests.request("GET", url, headers={'Content-Type': 'application/json'})
            runners = response.json()['runners']
            isException = False
        except Exception as e:
            print("Wait... Request again now: ")
            isException = True
            time.sleep(TIME_BETWEEN_REQUESTS)
    return runners


def getWinRunner(meeting, race):
    runners = requestRunners(race['_links']['self'])

    cols = ['meetingName', 'meetingDate', 'venue', 'race_type', 'link', 'raceNumber', 'raceName', 'runnerNumber',
            'runnerName', 'winOdds', 'Fav', 'finishedPosition']
    runner_lst = []

    for index, runner in enumerate(runners):
        runnerName = runner['runnerName']
        runnerNo = runner['runnerNumber']
        position = runner['finishingPosition']
        if "bettingStatus" in runner['fixedOdds'].keys():
            if runner['fixedOdds']['bettingStatus'] == "Winner" or runner['fixedOdds']['bettingStatus'] == "Loser" or \
                    runner['fixedOdds']['bettingStatus'] == "Placing":
                winOdds = runner['fixedOdds']['returnWin']
                runner_track = [meeting['meetingName'], meeting['meetingDate'], meeting['venueMnemonic'],
                                meeting['raceType'],
                                race['_links']['self'], race['raceNumber'], race['raceName'],
                                runnerNo, runnerName, winOdds, "", position]
                runner_lst.append(runner_track)
    runners_df = pd.DataFrame(runner_lst, columns=cols)
    runners_df.loc[runners_df['finishedPosition'] == 0, 'finishedPosition'] = 10

    # Get favorite runner.
    fav_runner_df = runners_df.copy().sort_values(['raceName', 'winOdds'], ascending=[True, True]).groupby(
        'raceName').head(1)
    fav_runner_df.iloc[0, fav_runner_df.columns.get_loc('Fav')] = "Fav"

    runners_df = runners_df.sort_values(['raceName', 'finishedPosition'], ascending=[True, True]).groupby(
        'raceName').head(NUMBER_OF_POSITION)

    result_df = pd.concat([fav_runner_df, runners_df], axis=0)

    return result_df


def requestAllRaces(date_str):
    url = "https://api.beta.tab.com.au/v1/historical-results-service/SA/racing/{0}".format(date_str)
    meetings = requestMeetings(url)

    cols = ['meetingName', 'meetingDate', 'venue', 'race_type', 'link', 'raceNumber', 'raceName', 'runnerNumber',
            'runnerName', 'winOdds', 'Fav', 'finishedPosition']
    runners_df = pd.DataFrame([], columns=cols)

    for index, meeting in enumerate(meetings):
        if (meeting['raceType'] == "R") and (
                meeting['location'] in ['VIC', 'QLD', 'TAS', 'WA', 'SA', 'NT', 'ACT', 'NSW'])\
                and meeting['meetingName'] in MEETING_FILTER:
            for r_index, race in enumerate(meeting['races']):

                if race['raceStatus'] == "Paying":
                    runners = getWinRunner(meeting, race, )
                    runners_df = pd.concat([runners_df, runners], axis=0)

    print("=============================End {0}=============================".format(date_str))
    return runners_df


def get_saturday(date):
    weekday = date.weekday()
    if weekday == 6:
        delta = 6
    else:
        delta = 5 - weekday
    saturday = date + timedelta(delta)
    return saturday


def get_win_percent(meeting_df):
    total_cnt = (meeting_df['Fav'] == 'Fav').sum()
    top1_win_cnt = (meeting_df['finishedPosition'] == 1).sum()
    top2_win_cnt = (meeting_df['finishedPosition'] == 2).sum()
    top3_win_cnt = (meeting_df['finishedPosition'] == 3).sum()
    top4_win_cnt = (meeting_df['finishedPosition'] == 4).sum()
    top1_win_percent = 100 * top1_win_cnt / total_cnt
    top2_win_percent = 100 * (top1_win_cnt+top2_win_cnt) / total_cnt
    top3_win_percent = 100 * (top1_win_cnt+top2_win_cnt+top3_win_cnt) / total_cnt
    top4_win_percent = 100 * (top1_win_cnt+top2_win_cnt+top3_win_cnt+top4_win_cnt) / total_cnt
    print("Favorite finished Top 1st {0} %".format(format(top1_win_percent, ".2f")))
    print("Favorite finished Top 2st {0} %".format(format(top2_win_percent, ".2f")))
    print("Favorite finished Top 3st {0} %".format(format(top3_win_percent, ".2f")))
    print("Favorite finished Top 4st {0} %".format(format(top4_win_percent, ".2f")))


def get_runners_in_date_range():
    from_date = datetime.strptime(FROM_DATE, '%Y-%m-%d')
    to_date = datetime.strptime(TO_DATE, '%Y-%m-%d')
    next_date = get_saturday(from_date)

    cols = ['meetingName', 'meetingDate', 'venue', 'race_type', 'link', 'raceNumber', 'raceName', 'runnerNumber',
            'runnerName', 'winOdds', 'Fav', 'finishedPosition']
    runners_in_scope = pd.DataFrame([], columns=cols)
    while next_date <= to_date:
        print("Getting runners data of {0} (Saturday)".format(next_date))
        runners_df = requestAllRaces(str(next_date.date()))
        runners_in_scope = pd.concat([runners_in_scope, runners_df], axis=0)
        next_date = next_date + timedelta(7)
    runners_in_scope.to_csv("runners_df.csv", encoding='utf-8', index=False)
    return runners_in_scope


if __name__ == '__main__':
    all_runners_df = get_runners_in_date_range()
    fav_runners_df=all_runners_df.loc[all_runners_df["Fav"]=="Fav"]
    get_win_percent(fav_runners_df)
