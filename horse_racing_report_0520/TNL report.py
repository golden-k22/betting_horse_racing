import json
import operator
import time

import requests
import calendar
from datetime import datetime, timedelta, timezone
import threading

FROM_DATE = "2022-04-03"
TO_DATE = "2022-05-07"
MIN_ODDS = 12.5
MAX_ODDS = 25
TIME_BETWEEN_REQUESTS = 10
history_meetings = []


def utc_to_localtime(utc_dt):
    # get integer timestamp to avoid precision lost
    timestamp = calendar.timegm(utc_dt.timetuple())
    local_dt = datetime.fromtimestamp(timestamp)
    assert utc_dt.resolution >= timedelta(microseconds=1)
    local_dt.replace(microsecond=utc_dt.microsecond)
    return local_dt.strftime("%I:%M %p")


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


def getWinRunner(url):
    # print(url)
    runners = requestRunners(url)
    winNo = 0
    winName = ''
    winOdds = 0.0
    for index, runner in enumerate(runners):
        if "bettingStatus" in runner['fixedOdds'].keys():
            if runner['fixedOdds']['bettingStatus'] == 'Winner':
                winNo = runner['runnerNumber']
                winName = runner['runnerName']
                winOdds = runner['fixedOdds']['returnWin']
                break
    return winNo, winName, winOdds


def requestAllRaces(date_str):
    tracks = []
    url = "https://api.beta.tab.com.au/v1/historical-results-service/SA/racing/{0}".format(date_str)
    meetings = requestMeetings(url)
    for index, meeting in enumerate(meetings):
        if (meeting['raceType'] == "R") and (
                meeting['location'] in ['VIC', 'QLD', 'TAS', 'WA', 'SA', 'NT', 'ACT', 'NSW']):
            track = {'meetingName': meeting['meetingName'], 'venue': meeting['venueMnemonic'], 'races': []}
            for r_index, race in enumerate(meeting['races']):
                if race['raceStatus'] == "Paying":
                    winNo, winName, winOdds = getWinRunner(race['_links']['self'])
                    race_dict = {'raceName': race['raceName'],
                                 'raceNumber': race['raceNumber'],
                                 'winRunnerNo': winNo,
                                 'winRunnerName': winName,
                                 'winOdds': winOdds}
                    if winOdds != 0.0:
                        track['races'].append(race_dict)
            tracks.append(track)

    # sorted_races = sorted(races, key=operator.itemgetter('RaceStartingTime'), reverse=False)
    # with open('tracks.json', 'w') as outfile:
    #     json.dump(tracks, outfile, indent=4)
    print("=============================End {0}=============================".format(date_str))
    return tracks


def set_history_data(meetingName, venue, total_race_cnt, matched_race_cnt):
    isExist = False
    selectedMeeting={}
    for index, meeting in enumerate(history_meetings):
        print("Duplicated meeting. ************** " , meetingName)
        if meeting['meetingName'] == meetingName and meeting['venue'] == venue:
            selectedMeeting['meetingName'] = meetingName
            selectedMeeting['venue'] = venue
            selectedMeeting['total_race_cnt'] = meeting['total_race_cnt'] + total_race_cnt
            selectedMeeting['matched_race_cnt'] = meeting['matched_race_cnt'] + matched_race_cnt
            history_meetings[index]=selectedMeeting
            isExist = True
            break
    if isExist==False:
        selectedMeeting['meetingName'] = meetingName
        selectedMeeting['venue'] = venue
        selectedMeeting['total_race_cnt'] = total_race_cnt
        selectedMeeting['matched_race_cnt'] = matched_race_cnt
        history_meetings.append(selectedMeeting)
    return selectedMeeting


def print_report(meetings, from_date_str, to_date_str, file_name, history_file_name):
    f = open(file_name, "a")
    hf = open(history_file_name, "w")
    f.write("\nDates : {0} to {1}\n".format(from_date_str, to_date_str))
    f.write("Min Odds : {0} , Max Odds : {1}\n\n".format(MIN_ODDS, MAX_ODDS))
    for index, meeting in enumerate(meetings):
        total_race_cnt = len(meeting['races'])
        if total_race_cnt > 0:
            matched_race_cnt = 0
            for r_index, race in enumerate(meeting['races']):
                race_str = "Track: {0}({1})  Race {2} Winners odds : {3}".format(
                    meeting['meetingName'], meeting['venue'], race['raceNumber'], race['winOdds'])
                f.write(race_str + "\n")
                if race['winOdds'] > MIN_ODDS and race['winOdds'] < MAX_ODDS:
                    matched_race_cnt += 1
            percent = 100 * matched_race_cnt / total_race_cnt
            percent_str = "{:.2f}".format(percent)
            track_str = "Track: {0}({1})  Total Races : {2}, Winners within odds : {3}, Winner within odds {4} %".format(
                meeting['meetingName'], meeting['venue'], total_race_cnt, matched_race_cnt, percent_str)
            # print(track_str)
            history_meeting = set_history_data(meeting['meetingName'], meeting['venue'], total_race_cnt,
                                               matched_race_cnt)
            f.write(track_str + "\n")

        else:
            track_str = "Track: {0}({1}) There is no races available.".format(meeting['meetingName'], meeting['venue'])
            # print(track_str)
            f.write(track_str + "\n")
    for history_meeting in history_meetings:
        percent = 100 * history_meeting['matched_race_cnt'] / history_meeting['total_race_cnt']
        percent_str = "{:.2f}".format(percent)
        history_str = "History Track: {0}({1})  Total Races : {2}, Winners within odds : {3}, Winner within odds {4} %".format(
            history_meeting['meetingName'], history_meeting['venue'], history_meeting['total_race_cnt'],
            history_meeting['matched_race_cnt'], percent_str)
        hf.write(history_str + "\n")
    f.close()
    hf.close()

if __name__ == '__main__':
    today = datetime.now()
    from_date = datetime.strptime(FROM_DATE, '%Y-%m-%d')
    to_date = datetime.strptime(TO_DATE, '%Y-%m-%d')
    next_date = from_date

    while next_date <= to_date:
        meetings = requestAllRaces(str(next_date.date()))
        print_report(meetings, str(next_date.date()), str(next_date.date()),
                     "TNL Report from {0}.txt".format(str(from_date.date())),
                     "Historical TNL Report from {0}.txt".format(str(from_date.date())))
        next_date = next_date + timedelta(1)
