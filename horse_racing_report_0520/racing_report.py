import json
import operator

import requests
import calendar
from datetime import datetime, timedelta, timezone
import pytz
import threading

import betfairapi

STAKE_VARIABLE_1 = 12.5
STAKE_VARIABLE_2 = 25
STAKE_VARIABLE_3 = 50
TIME_BETWEEN_REQUESTS = 5


# races = []


def utc_to_localtime(utc_dt):
    # get integer timestamp to avoid precision lost
    timestamp = calendar.timegm(utc_dt.timetuple())
    local_dt = datetime.fromtimestamp(timestamp)
    assert utc_dt.resolution >= timedelta(microseconds=1)
    local_dt.replace(microsecond=utc_dt.microsecond)
    return local_dt.strftime("%I:%M %p")


def requestAllRaces():
    races = []
    init_url = 'https://api.beta.tab.com.au/v1/tab-info-service/racing/dates/today/meetings?jurisdiction=SA'
    response1 = requests.request("GET", init_url)
    meetings = response1.json()['meetings']
    for index, meeting in enumerate(meetings):
        if "_links" in meeting.keys():
            for index, race in enumerate(meeting['races']):
                race_dict = {}
                if (meeting['raceType'] == "R") and (
                        meeting['location'] in ['VIC', 'QLD', 'TAS', 'WA', 'SA', 'NT', 'ACT', 'NSW']):
                    race_dict['VenueMnemonic'] = meeting['venueMnemonic']
                    race_dict['Location'] = meeting['location']
                    race_dict['MeetingName'] = meeting['meetingName']
                    race_dict['RaceNo'] = race['raceNumber']
                    race_dict['RaceType'] = meeting['raceType']
                    race_dict['Distance'] = race['raceDistance']
                    race_dict['RaceName'] = race['raceName']
                    # startTimeStr = utc_to_localtime(datetime.fromisoformat(race['raceStartTime'][:-1] + '+09:30'))
                    race_dict['RaceStartingTime'] = race['raceStartTime']
                    race_dict['Status'] = race['raceStatus']

                    current_time = datetime.now(timezone.utc)
                    datetime_object = datetime.fromisoformat(str(race['raceStartTime'])[:-1] + '+00:00')
                    time_difference = datetime_object - current_time
                    race_dict['TimeDifference'] = '{:02d}h '.format(
                        int(time_difference.seconds / 3600)) + '{:02d}m '.format(
                        int((time_difference.seconds % 3600) / 60)) + '{:02d}s'.format(time_difference.seconds % 60)
                    races.append(race_dict)
        else:
            pass
    sorted_races = sorted(races, key=operator.itemgetter('RaceStartingTime'), reverse=False)
    # with open('races.json', 'w') as outfile:
    #     json.dump(sorted_races, outfile, indent=4)
    return sorted_races


def requestRaceDetails(race, stake_val):
    t_timezone = 'Australia/Perth'
    py_timezone = pytz.timezone(t_timezone)
    current_time = datetime.now(py_timezone)
    print("Current time : ", current_time)

    date_str = "{0}-{1}-{2}".format(current_time.year, '{:02d}'.format(current_time.month),
                                    '{:02d}'.format(current_time.day))
    race_url = "https://api.beta.tab.com.au/v1/tab-info-service/racing/dates/{0}/meetings/{1}/{2}/races/{3}?jurisdiction=SA".format(
        date_str, race['RaceType'], race['VenueMnemonic'], race['RaceNo'])
    response = requests.request("GET", race_url)
    odd_data = response.json()

    runnersDetail = []
    for index, runner in enumerate(odd_data['runners']):
        if (runner['fixedOdds']['bettingStatus'] == "Open"):
            runnerDetail = {}
            runnerDetail['RunnerNo'] = runner['runnerNumber']
            runnerDetail['RunnerName'] = runner['runnerName']
            runnerDetail['ReturnWin'] = runner['fixedOdds']['returnWin']
            runnerDetail['Lay'] = "n/a"
            runnerDetail['Stake'] = "n/a"
            # runnerDetail['Xr'] = 0
            runnerDetail['BBr'] = 0
            runnerDetail['Profit'] = 0
            runnerDetail['Stake_Variable'] = stake_val
            runnersDetail.append(runnerDetail)

    race_name_key = "R" + str(race["RaceNo"]) + " " + str(race["Distance"]) + "m"
    runners_lay, market_id = betfairapi.get_runner_detail(race['MeetingName'], race_name_key)
    if runners_lay.empty:
        print("Wrong Market Name or Event Name!")
    else:
        for index, runner in enumerate(runnersDetail):
            if runners_lay['Lay Size'].count() - 1 > index:
                back = runner['ReturnWin']
                lays = runners_lay.iloc[index]
                lay, stake, xr, bbr, profit = calc_stake(stake_val, back, lays)
                runner["Lay"] = lay
                runner['Stake'] = stake
                runner['BBr'] = bbr
                runner['Profit'] = profit

    # with open('out2.json', 'w') as outfile:
    #     json.dump(runnersDetail, outfile, indent=4)

    return runnersDetail


def calc_stake(stake_var, back, lays):
    lay_size = "n/a"
    stake = "n/a"
    xr = 0
    bbr = 0
    profit = 0
    lay_prices = lays['Lay Price']
    print("lays : ", lays)
    l_size = 0
    for l_index, price in enumerate(lay_prices):
        temp_stake = ((back - 1) / (price - 0.05)) * stake_var
        l_size = l_size + lays['Lay Size'][l_index]
        if temp_stake <= l_size:
            print("Selected Lay price : ", price)
            lay_size = "{:.2f}".format(price)
            stake = "{:.2f}".format(temp_stake)
            xr = float("{:.2f}".format(temp_stake * 0.95))
            bbr = (0.95 * temp_stake / stake_var) * 100
            profit = (((back - 1) * stake_var) - ((price - 1)) * temp_stake)
            break
    return lay_size, stake, xr, bbr, profit


def print_report(races, xr_list, file_name):
    f = open(file_name, "w")
    for index, i_race in enumerate(races):
        for stake_index in range(3):
            # Track: XXX Race 1: max Xr 70 % available for 25 seconds
            track_str = "Track: {0} ({1}) ".format(i_race['VenueMnemonic'],
                                                   xr_list[3 * index + stake_index]['Stake_Variable'])
            race_str = "--- Race {0}: ".format(i_race['RaceNo'])
            max_xr_percent = xr_list[3 * index + stake_index]['MAX']
            max_xr_sec = xr_list[3 * index + stake_index]['DURATION']
            max_xr_str = "max BBr {0}% available for {1} seconds".format(max_xr_percent, max_xr_sec)
            str_for_test = '  Horse No: {0}, Lay: {1}, Stake: {2}, Back: {3}, Profit: {4}'.format(
                xr_list[3 * index + stake_index]["RunnerNo"], xr_list[3 * index + stake_index]["Lay"],
                xr_list[3 * index + stake_index]["Stake"], xr_list[3 * index + stake_index]["Back"],
                xr_list[3 * index + stake_index]["Profit"], )
            report_str = track_str + race_str + max_xr_str + str_for_test
            print(report_str)
            f.write(report_str + "\n")
    f.close()


def get_max_bbr_percent(runners):
    runner = None
    runners = sorted(runners, key=operator.itemgetter('BBr'), reverse=True)
    if len(runners) > 0:
        if runners[0]['BBr'] > 0:
            # max_xr_percent = '{:.2f}'.format(runners[0]['BBr'])
            runner = runners[0]
    return runner


def update_xr_report(races, xr_list):
    for index, i_race in enumerate(races):
        cur_time = datetime.now(timezone.utc)
        # race_start_time = datetime.fromisoformat(i_race['RaceStartingTime'][:-1] + '+00:00')
        # if race_start_time > cur_time:
        if i_race['Status'] == "Normal":
            print("-------------------------- Available ----------------------------------")
            runnersList = [requestRaceDetails(i_race, STAKE_VARIABLE_1),
                           requestRaceDetails(i_race, STAKE_VARIABLE_2),
                           requestRaceDetails(i_race, STAKE_VARIABLE_3)]
            for stake_index, runners in enumerate(runnersList):
                runner = get_max_bbr_percent(runners)
                race_xr = {'MAX': 0, 'FROM': datetime.now(timezone.utc), 'DURATION': 0, "RunnerNo": 0, "Lay": 0,
                           'Stake': 0, 'Back': 0, 'Profit': 0, 'Stake_Variable': 0}
                if runner is not None:
                    race_xr['MAX'] = '{:.2f}'.format(runner['BBr'])
                    race_xr['FROM'] = cur_time
                    race_xr['DURATION'] = 0
                    race_xr["RunnerNo"] = runner['RunnerNo']
                    race_xr["Lay"] = runner['Lay']
                    race_xr['Stake'] = runner['Stake']
                    race_xr['Back'] = runner['ReturnWin']
                    race_xr['Profit'] = '{:.2f}'.format(runner['Profit'])
                    race_xr['Stake_Variable'] = runner['Stake_Variable']

                if float(race_xr['MAX']) > float(xr_list[3 * index + stake_index]['MAX']):
                    print("Max changed.")
                    xr_list[3 * index + stake_index] = race_xr
                elif float(race_xr['MAX']) == float(xr_list[3 * index + stake_index]['MAX']):
                    xr_list[3 * index + stake_index]['DURATION'] = (
                            cur_time - xr_list[3 * index + stake_index]['FROM']).seconds
                else:
                    print("Bellow of MAX")
                    xr_list[3 * index + stake_index]['FROM'] = cur_time
            break
    return xr_list


def periodical_func(timer=None):
    races = requestAllRaces()
    xr_list = update_xr_report(races, xr_list_prev)
    t_timezone = 'Australia/Perth'
    py_timezone = pytz.timezone(t_timezone)
    today_date_str = datetime.now(py_timezone).date()
    print_report(races, xr_list, "report {0}.txt".format(today_date_str))
    if timer is None:
        timer = threading.Timer(TIME_BETWEEN_REQUESTS, periodical_func, (timer,))
    else:
        timer.cancel()
        timer = threading.Timer(TIME_BETWEEN_REQUESTS, periodical_func, (timer,))
    timer.start()


if __name__ == '__main__':
    all_races = requestAllRaces()
    # races = [{
    #     "VenueMnemonic": "KYN",
    #     "Location": "VIC",
    #     "MeetingName": "KYNETON",
    #     "RaceNo": 1,
    #     "RaceType": "R",
    #     "Distance": 1112,
    #     "RaceName": "BET365 ODDS DRIFT PROTECTOR F&M MAIDEN",
    #     "RaceStartingTime": "2022-05-09T02:30:00.000Z",
    #     "TimeDifference": "02h 27m 45s"
    # }]
    timer = None
    xr_list_prev = [
        {'MAX': 0, 'FROM': datetime.now(timezone.utc), 'DURATION': 0, "RunnerNo": 0, "Lay": 0, 'Stake': 0,
         'Back': 0, 'Profit': 0, 'Stake_Variable': 0} for _ in range(len(all_races) * 3)]

    periodical_func(timer)
