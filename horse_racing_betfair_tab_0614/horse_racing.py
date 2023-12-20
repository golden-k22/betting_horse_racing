import calendar
import json
import operator
import threading
from datetime import datetime, timedelta, timezone
from tkinter import messagebox

import pytz
import requests

import betfairapi
from tab_automator import TAB

try:
    from Tkinter import *
    from ttk import *
except ImportError:  # Python 3
    from tkinter import *
    from tkinter.ttk import *
import tkinter as tk


TIME_BETWEEN_REQUESTS = 5
BACK_COLOR = "#C0C0C0"
WHITE = "white"
INPUT_WIDTH = 120
INPUT_PADX = 10
OFFSET_X = 70
INPUT_PADY = 20
OFFSET_Y = 30

races = []


def utc_to_localtime(utc_dt):
    # get integer timestamp to avoid precision lost
    timestamp = calendar.timegm(utc_dt.timetuple())
    local_dt = datetime.fromtimestamp(timestamp)
    assert utc_dt.resolution >= timedelta(microseconds=1)
    local_dt.replace(microsecond=utc_dt.microsecond)
    return local_dt.strftime("%I:%M %p")


def requestAllRaces():
    unsorted_races = []
    init_url = 'https://api.beta.tab.com.au/v1/tab-info-service/racing/dates/today/meetings?jurisdiction=SA'
    response1 = requests.request("GET", init_url)
    meetings = response1.json()['meetings']
    for index, meeting in enumerate(meetings):
        if "_links" in meeting.keys():
            for r_index, race in enumerate(meeting['races']):
                race_dict = {}
                if (meeting['raceType'] == "H") and (
                        meeting['location'] in ['VIC', 'QLD', 'TAS', 'WA', 'SA', 'NT', 'ACT', 'NSW']):
                    race_dict['VenueMnemonic'] = meeting['venueMnemonic']
                    race_dict['Location'] = meeting['location']
                    race_dict['MeetingName'] = meeting['meetingName']
                    race_dict['RaceNo'] = race['raceNumber']
                    race_dict['RaceType'] = meeting['raceType']
                    race_dict['Distance'] = race['raceDistance']
                    startTimeStr = utc_to_localtime(datetime.fromisoformat(race['raceStartTime'][:-1] + '+09:30'))
                    race_dict['RaceStartingTime'] = race['raceStartTime']
                    race_dict['RaceStartingTimeStr'] = startTimeStr
                    unsorted_races.append(race_dict)
        else:
            pass
    races = sorted(unsorted_races, key=operator.itemgetter('RaceStartingTime'), reverse=False)
    with open('aus_races.json', 'w') as outfile:
        json.dump(races, outfile, indent=4)
    return races


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
        runnerDetail['bettingStatus'] = runner['fixedOdds']['bettingStatus']
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

    with open('runners.json', 'w') as outfile:
        json.dump(runnersDetail, outfile, indent=4)

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
            bbr = float('{:.2f}'.format((0.95 * temp_stake / stake_var) * 100))
            profit = (((back - 1) * stake_var) - ((price - 1)) * temp_stake)
            break
    return lay_size, stake, xr, bbr, profit


class App(tk.Tk):

    def __init__(self):

        tk.Tk.__init__(self)
        self.title("Horse Racing")
        self.geometry("1300x800+200+100")
        self.resizable(0, 0)

        self.timer = None
        self.selectedRaceId = 0
        self.selectedRunners = []
        self.checked_races = [tk.StringVar(value='0') for _ in races]
        self.table_y = 250
        self.CreateUI()
        self.setBonusBets()
        self.showOnlyAusRaces()
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.on_exit)

    def on_exit(self):
        """When you click to exit, this function is called"""
        if messagebox.askyesno("Exit", "Do you want to quit the application?"):
            if self.timer is not None:
                self.timer.cancel()
            self.destroy()

    def CreateUI(self):
        self.label1 = tk.Label(master=self.master, text="Betting for Horse Racing", font='Helvetica 28 bold')
        self.label1.place(x=400, y=50)

        self.input_frame = tk.Frame(master=self.master, height=150, width=1125, bg=BACK_COLOR)
        self.input_frame.place(x=100, y=self.table_y - 120)

        self.mode_label = tk.Label(master=self.input_frame, text="Mode", font='Helvetica 10', bg=BACK_COLOR)
        self.mode_label.place(x=OFFSET_X, y=0 + INPUT_PADY)
        self.mode_entry = tk.Entry(master=self.input_frame, font="Helvetica 10")
        self.mode_entry.place(x=OFFSET_X, y=OFFSET_Y + INPUT_PADY, width=INPUT_WIDTH, height=25)

        self.maxh_label = tk.Label(master=self.input_frame, text="Max Horses", font='Helvetica 10', bg=BACK_COLOR)
        self.maxh_label.place(x=OFFSET_X + INPUT_PADX + INPUT_WIDTH, y=0 + INPUT_PADY)
        self.maxh_entry = tk.Entry(master=self.input_frame, font="Helvetica 10")
        self.maxh_entry.insert(END, '0')
        self.maxh_entry.place(x=OFFSET_X + INPUT_PADX + INPUT_WIDTH, y=OFFSET_Y + INPUT_PADY, width=INPUT_WIDTH,
                              height=25)

        self.stake_label = tk.Label(master=self.input_frame, text="Stake", font='Helvetica 10', bg=BACK_COLOR)
        self.stake_label.place(x=OFFSET_X + 2 * (INPUT_PADX + INPUT_WIDTH), y=0 + INPUT_PADY)
        self.stake_entry = tk.Entry(master=self.input_frame, font="Helvetica 10")
        self.stake_entry.insert(END, '10')
        self.stake_entry.place(x=OFFSET_X + 2 * (INPUT_PADX + INPUT_WIDTH), y=OFFSET_Y + INPUT_PADY, width=INPUT_WIDTH,
                               height=25)

        self.minO_label = tk.Label(master=self.input_frame, text="Min Odds", font='Helvetica 10', bg=BACK_COLOR)
        self.minO_label.place(x=OFFSET_X + 3 * (INPUT_PADX + INPUT_WIDTH), y=0 + INPUT_PADY)
        self.minO_entry = tk.Entry(master=self.input_frame, font="Helvetica 10")
        self.minO_entry.insert(END, '0')
        self.minO_entry.place(x=OFFSET_X + 3 * (INPUT_PADX + INPUT_WIDTH), y=OFFSET_Y + INPUT_PADY, width=INPUT_WIDTH,
                              height=25)

        self.maxO_label = tk.Label(master=self.input_frame, text="Max Odds", font='Helvetica 10', bg=BACK_COLOR)
        self.maxO_label.place(x=OFFSET_X + 4 * (INPUT_PADX + INPUT_WIDTH), y=0 + INPUT_PADY)
        self.maxO_entry = tk.Entry(master=self.input_frame, font="Helvetica 10")
        self.maxO_entry.insert(END, '9999')
        self.maxO_entry.place(x=OFFSET_X + 4 * (INPUT_PADX + INPUT_WIDTH), y=OFFSET_Y + INPUT_PADY, width=INPUT_WIDTH,
                              height=25)

        self.underlay_label = tk.Label(master=self.input_frame, text="Underlay %", font='Helvetica 10', bg=BACK_COLOR)
        self.underlay_label.place(x=OFFSET_X + 5 * (INPUT_PADX + INPUT_WIDTH), y=0 + INPUT_PADY)
        self.underlay_entry = tk.Entry(master=self.input_frame, font="Helvetica 10")
        self.underlay_entry.insert(END, '0')
        self.underlay_entry.place(x=OFFSET_X + 5 * (INPUT_PADX + INPUT_WIDTH), y=OFFSET_Y + INPUT_PADY,
                                  width=INPUT_WIDTH, height=25)

        self.comDis_label = tk.Label(master=self.input_frame, text="Comm Discount %", font='Helvetica 10',
                                     bg=BACK_COLOR)
        self.comDis_label.place(x=OFFSET_X + 6 * (INPUT_PADX + INPUT_WIDTH), y=0 + INPUT_PADY)
        self.comDis_entry = tk.Entry(master=self.input_frame, font="Helvetica 10")
        self.comDis_entry.insert(END, '0')
        self.comDis_entry.place(x=OFFSET_X + 6 * (INPUT_PADX + INPUT_WIDTH), y=OFFSET_Y + INPUT_PADY, width=INPUT_WIDTH,
                                height=25)

        self.retention_label = tk.Label(master=self.input_frame, text="Retention %", font='Helvetica 10', bg=BACK_COLOR)
        self.retention_label.place(x=OFFSET_X + 7 * (INPUT_PADX + INPUT_WIDTH), y=0 + INPUT_PADY)
        self.retention_entry = tk.Entry(master=self.input_frame, font="Helvetica 10")
        self.retention_entry.insert(END, '95')
        self.retention_entry.place(x=OFFSET_X + 7 * (INPUT_PADX + INPUT_WIDTH), y=OFFSET_Y + INPUT_PADY,
                                   width=INPUT_WIDTH, height=25)

        # For Bonus Bets

        self.available_bonus_labels = tk.Label(master=self.input_frame, text="All bonus bets : ",
                                               font='Helvetica 10', bg=BACK_COLOR)
        self.available_bonus_labels.place(x=OFFSET_X + 3 * (INPUT_PADX + INPUT_WIDTH), y=40 + OFFSET_Y + INPUT_PADY)
        self.available_bonus_cnt = tk.Entry(master=self.input_frame, font="Helvetica 10")
        self.available_bonus_cnt.insert(END, '--')
        self.available_bonus_cnt.place(x=OFFSET_X + 3 * (INPUT_PADX + INPUT_WIDTH), y=60 + OFFSET_Y + INPUT_PADY,
                                       width=INPUT_WIDTH,
                                       height=25)

        self.available_50_labels = tk.Label(master=self.input_frame, text="50$ : ", font='Helvetica 10', bg=BACK_COLOR)
        self.available_50_labels.place(x=OFFSET_X + 4 * (INPUT_PADX + INPUT_WIDTH), y=40 + OFFSET_Y + INPUT_PADY)
        self.available_50_cnt = tk.Entry(master=self.input_frame, font="Helvetica 10")
        self.available_50_cnt.insert(END, '--')
        self.available_50_cnt.place(x=OFFSET_X + 4 * (INPUT_PADX + INPUT_WIDTH), y=60 + OFFSET_Y + INPUT_PADY,
                                    width=INPUT_WIDTH,
                                    height=25)

        self.available_25_labels = tk.Label(master=self.input_frame, text="$25 : ", font='Helvetica 10', bg=BACK_COLOR)
        self.available_25_labels.place(x=OFFSET_X + 5 * (INPUT_PADX + INPUT_WIDTH), y=40 + OFFSET_Y + INPUT_PADY)
        self.available_25_cnt = tk.Entry(master=self.input_frame, font="Helvetica 10")
        self.available_25_cnt.insert(END, '--')
        self.available_25_cnt.place(x=OFFSET_X + 5 * (INPUT_PADX + INPUT_WIDTH), y=60 + OFFSET_Y + INPUT_PADY,
                                    width=INPUT_WIDTH,
                                    height=25)

        self.available_125_labels = tk.Label(master=self.input_frame, text="$12.5 : ", font='Helvetica 10',
                                             bg=BACK_COLOR)
        self.available_125_labels.place(x=OFFSET_X + 6 * (INPUT_PADX + INPUT_WIDTH), y=40 + OFFSET_Y + INPUT_PADY)
        self.available_125_cnt = tk.Entry(master=self.input_frame, font="Helvetica 10")
        self.available_125_cnt.insert(END, '--')
        self.available_125_cnt.place(x=OFFSET_X + 6 * (INPUT_PADX + INPUT_WIDTH), y=60 + OFFSET_Y + INPUT_PADY,
                                     width=INPUT_WIDTH,
                                     height=25)

        self.available_10_labels = tk.Label(master=self.input_frame, text="$10 : ", font='Helvetica 10', bg=BACK_COLOR)
        self.available_10_labels.place(x=OFFSET_X + 7 * (INPUT_PADX + INPUT_WIDTH), y=40 + OFFSET_Y + INPUT_PADY)
        self.available_10_cnt = tk.Entry(master=self.input_frame, font="Helvetica 10")
        self.available_10_cnt.insert(END, '--')
        self.available_10_cnt.place(x=OFFSET_X + 7 * (INPUT_PADX + INPUT_WIDTH), y=60 + OFFSET_Y + INPUT_PADY,
                                    width=INPUT_WIDTH,
                                    height=25)

        # self.search_btn = tk.Button(master=self.input_frame, text="Search",font='Helvetica 10', width=10, command=self.search_detail)
        # self.search_btn.place(x=OFFSET_X+7*(INPUT_PADX+INPUT_WIDTH), y=OFFSET_Y + INPUT_PADY-1)

        h_frame = tk.Frame(self, background="#ffffff")
        h_frame.place(x=100, y=self.table_y + 50)

        r_canvas = tk.Canvas(self, borderwidth=0, background="#ffffff", width=450, height=400)
        r_canvas.place(x=100, y=self.table_y + 70)
        self.r_frame = tk.Frame(r_canvas, background="#ffffff")
        verticalScrollbar = tk.Scrollbar(self, orient="vertical", command=r_canvas.yview)
        r_canvas.configure(yscrollcommand=verticalScrollbar.set)
        r_canvas.create_window((4, 4), window=self.r_frame, anchor="nw")
        verticalScrollbar.place(relx=0.42, rely=0.400, relheight=0.505, relwidth=0.013)
        self.r_frame.bind("<Configure>", lambda event, canvas=r_canvas: self.onFrameConfigure(r_canvas))
        self.display_header(h_frame)

        self.label_title = tk.Label(master=self.master, text="Detail of Race", font='Helvetica 14')
        self.label_title.place(x=820, y=self.table_y + 70)
        self.label_race = tk.Label(master=self.master, text="", font='Helvetica 8')
        self.label_race.place(x=610, y=self.table_y + 120)
        self.label_start = tk.Label(master=self.master, text="", font='Helvetica 8')
        self.label_start.place(x=800, y=self.table_y + 120)
        self.label_left = tk.Label(master=self.master, text="", font='Helvetica 8')
        self.label_left.place(x=1000, y=self.table_y + 120)

        h_detail_frame = tk.Frame(self, background="#ffffff")
        h_detail_frame.place(x=600, y=self.table_y + 150)

        r_detail_canvas = tk.Canvas(self, borderwidth=0, background="#ffffff", width=560, height=300)
        r_detail_canvas.place(x=600, y=self.table_y + 170)
        self.r_detail_frame = tk.Frame(r_detail_canvas, background="#ffffff")
        r_detail_canvas.create_window((4, 4), window=self.r_detail_frame, anchor="nw")
        self.display_detail_header(h_detail_frame)

        # aut_filterBtn = tk.Button(self, text="Australia Races", width=15, command=self.showOnlyAusRaces).place(x=550,y=700)

    def onFrameConfigure(self, canvas):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def is_bonus_available(self):
        if (self.isFloat(self.stake_entry.get()) == False):
            return False
        stake_value = float(self.stake_entry.get())
        available_bet_cnt = 0
        if stake_value == 12.5:
            available_bet_cnt = self.available_125_cnt.get()
        elif stake_value == 10:
            available_bet_cnt = self.available_10_cnt.get()
        elif stake_value == 25:
            available_bet_cnt = self.available_25_cnt.get()
        elif stake_value == 50:
            available_bet_cnt = self.available_50_cnt.get()
        else:
            available_bet_cnt = 0

        if available_bet_cnt == "--":
            return False
        else:
            if int(available_bet_cnt) > 0:
                return True
            else:
                return False

    def setBonusBets(self):

        self.available_bonus_cnt.config(state='normal')
        self.available_50_cnt.config(state='normal')
        self.available_25_cnt.config(state='normal')
        self.available_125_cnt.config(state='normal')
        self.available_10_cnt.config(state='normal')

        self.available_bonus_cnt.delete(0, 'end')
        self.available_50_cnt.delete(0, 'end')
        self.available_25_cnt.delete(0, 'end')
        self.available_125_cnt.delete(0, 'end')
        self.available_10_cnt.delete(0, 'end')
        all_bets, bet_50, bet_25, bet_125, bet_10 = tab_browser.get_bonus_cnt()
        self.available_bonus_cnt.insert(END, all_bets)
        self.available_50_cnt.insert(END, bet_50)
        self.available_25_cnt.insert(END, bet_25)
        self.available_125_cnt.insert(END, bet_125)
        self.available_10_cnt.insert(END, bet_10)

        self.available_bonus_cnt.config(state='readonly')
        self.available_50_cnt.config(state='readonly')
        self.available_25_cnt.config(state='readonly')
        self.available_125_cnt.config(state='readonly')
        self.available_10_cnt.config(state='readonly')

    def display_header(self, frame):

        no_label = tk.Label(master=frame, width=3, height=1, borderwidth=1, text="No", font='Helvetica 10',
                            bg=WHITE)
        no_label.grid(row=0, column=0, sticky="ew")
        races_label = tk.Label(master=frame, width=24, height=1, borderwidth=1, text="Races", font='Helvetica 10',
                               bg=WHITE)
        races_label.grid(row=0, column=1, sticky="ew")
        start_time_label = tk.Label(master=frame, width=11, height=1, borderwidth=1, text="Start Time",
                                    font='Helvetica 10', bg=WHITE)
        start_time_label.grid(row=0, column=2, sticky="ew")
        left_time_label = tk.Label(master=frame, width=12, height=1, borderwidth=1, text="Left Time",
                                   font='Helvetica 10', bg=WHITE)
        left_time_label.grid(row=0, column=3, sticky="ew")
        check_label = tk.Label(master=frame, width=5, height=1, borderwidth=1, text="Status", font='Helvetica 10',
                               bg=WHITE)
        check_label.grid(row=0, column=4, sticky="ew")

    def displayList(self, index, race_name, start_time, left_time):
        textNo = tk.Label(master=self.r_frame, width=3, height=1, borderwidth=1, text=index, font='Helvetica 10',
                          bg=WHITE)
        textNo.grid(row=index, column=0, sticky="ew")
        textNo.bind("<Button-1>", lambda e, param=index: self.show_detail(param))

        textRace = tk.Label(self.r_frame, width=24, height=1, borderwidth=1, text=race_name, font='Helvetica 10',
                            bg=WHITE)
        textRace.bind("<Button-1>", lambda e, param=index: self.show_detail(param))
        textRace.grid(row=index, column=1, sticky="ew")

        textStartTime = tk.Label(self.r_frame, width=11, height=1, borderwidth=1, text=start_time, font='Helvetica 10',
                                 bg=WHITE)
        textStartTime.bind("<Button-1>", lambda e, param=index: self.show_detail(param))
        textStartTime.grid(row=index, column=2, sticky="ew")

        textLeftTime = tk.Label(self.r_frame, width=12, height=1, borderwidth=1, text=left_time, font='Helvetica 10',
                                bg=WHITE)
        textLeftTime.bind("<Button-1>", lambda e, param=index: self.show_detail(param))
        textLeftTime.grid(row=index, column=3, sticky="ew")

        checkBox = tk.Checkbutton(self.r_frame, text="", height=1, borderwidth=1, onvalue=1, offvalue=0,
                                  font='Helvetica 10',
                                  variable=self.checked_races[index])
        # checkBox.grid(row=index, column=4)

    def display_detail_header(self, frame):

        no_label = tk.Label(master=frame, width=3, height=1, borderwidth=1, text="No", font='Helvetica 10', bg=WHITE)
        no_label.grid(row=0, column=0, sticky="ew")
        horse_label = tk.Label(master=frame, width=24, height=1, borderwidth=1, text="Horse", font='Helvetica 10',
                               bg=WHITE)
        horse_label.grid(row=0, column=1, sticky="ew")
        back_label = tk.Label(master=frame, width=7, height=1, borderwidth=1, text="Back",
                              font='Helvetica 10', bg=WHITE)
        back_label.grid(row=0, column=2, sticky="ew")
        lay_label = tk.Label(master=frame, width=7, height=1, borderwidth=1, text="Lay",
                             font='Helvetica 10', bg=WHITE)
        lay_label.grid(row=0, column=3, sticky="ew")
        stake_label = tk.Label(master=frame, width=7, height=1, borderwidth=1, text="Stake", font='Helvetica 10',
                               bg=WHITE)
        stake_label.grid(row=0, column=4, sticky="ew")
        xr_label = tk.Label(master=frame, width=7, height=1, borderwidth=1, text="BBr", font='Helvetica 10',
                            bg=WHITE)
        xr_label.grid(row=0, column=5, sticky="ew")
        action_label = tk.Label(master=frame, width=20, height=1, borderwidth=1, text="Action", font='Helvetica 10',
                                bg=WHITE)
        action_label.grid(row=0, column=6, sticky="ew")

    def displayDetailList(self, index, horse_name, back, lay, stake, bbr):
        textNo = tk.Label(master=self.r_detail_frame, width=3, height=1, borderwidth=1, text=index, font='Helvetica 10',
                          bg=WHITE)
        textNo.grid(row=index, column=0, sticky="ew")
        # textNo.bind("<Button-1>", lambda e, param=index: self.show_detail(param))

        textHorse = tk.Label(self.r_detail_frame, width=24, height=1, borderwidth=1, text=horse_name,
                             font='Helvetica 10',
                             bg=WHITE)
        textHorse.grid(row=index, column=1, sticky="ew")
        textBack = tk.Label(self.r_detail_frame, width=7, height=1, borderwidth=1, text=back, font='Helvetica 10',
                            bg=WHITE)
        textBack.grid(row=index, column=2, sticky="ew")
        textLay = tk.Label(self.r_detail_frame, width=7, height=1, borderwidth=1, text=lay, font='Helvetica 10',
                           bg=WHITE)
        textLay.grid(row=index, column=3, sticky="ew")
        textStake = tk.Label(self.r_detail_frame, width=7, height=1, borderwidth=1, text=stake, font='Helvetica 10',
                             bg=WHITE)
        textStake.grid(row=index, column=4, sticky="ew")
        textXr = tk.Label(self.r_detail_frame, width=7, height=1, borderwidth=1, text="{0}%".format(bbr),
                          font='Helvetica 10',
                          bg=WHITE)
        textXr.grid(row=index, column=5, sticky="ew")

        actionBtn = tk.Button(self.r_detail_frame, text="Bet", width=12)
        if self.isFloat(stake) == False or self.is_bonus_available() == False:
            actionBtn['state'] = DISABLED
        else:
            actionBtn.bind("<Button-1>", lambda e, param=index: self.bet(param))
        actionBtn.grid(row=index, column=6, sticky="ew")

    def clearFrame(self):
        # destroy all widgets from frame
        for widget in self.r_frame.winfo_children():
            widget.destroy()

        # this will clear frame and frame will be empty
        # if you want to hide the empty panel then
        self.r_frame.pack_forget()

    def clearDetailFrame(self):
        # destroy all widgets from frame
        for widget in self.r_detail_frame.winfo_children():
            widget.destroy()

        # this will clear frame and frame will be empty
        # if you want to hide the empty panel then
        self.r_detail_frame.pack_forget()

    def bet(self, param):
        print("----------- bet now -------------{0}- {1}".format(self.selectedRaceId, param))
        runners = sorted(self.selectedRunners, key=operator.itemgetter('BBr'), reverse=True)
        race = races[self.selectedRaceId]
        print(race)
        runner = runners[param]
        print(runner)

        t_timezone = 'Australia/Perth'
        py_timezone = pytz.timezone(t_timezone)
        current_time = datetime.now(py_timezone)
        date_str = "{0}-{1}-{2}".format(current_time.year, '{:02d}'.format(current_time.month),
                                        '{:02d}'.format(current_time.day))
        meeting_str = race['MeetingName']
        venue_str = race['VenueMnemonic']
        race_type = race['RaceType']
        race_no = race['RaceNo']
        runner_no = runner['RunnerNo']
        is_fixed_bet = 1

        if self.isDigit(self.stake_entry):
            stake_val = int(self.stake_entry.get())
            race_name_key = "R" + str(race["RaceNo"]) + " " + str(race["Distance"]) + "m"
            runnerStake = float(runner['Stake'])
            runnerLay = float(runner['Lay'])
            betfair_result = betfairapi.place_order(race['MeetingName'], race_name_key, runner_no, runnerStake,
                                                    runnerLay)
            if betfair_result:
                print("Successed in putting bet in betfair api...")
                tab_browser.place_bonus_bet(date_str, meeting_str, venue_str, race_type, race_no, runner_no, stake_val,
                                            is_fixed_bet)
                self.setBonusBets()

            else:
                print("Failed in putting bet in betfair api...")
        else:
            print("please input stake for tab betting.")

    def showOnlyAusRaces(self):
        if self.timer is not None:
            self.timer.cancel()
        self.label_race.config(text="")
        self.label_start.config(text='')
        self.label_left.config(text='')
        self.clearDetailFrame()
        self.clearFrame()
        for i, race in enumerate(races, start=0):
            current_time = datetime.now(timezone.utc)
            datetime_object = datetime.fromisoformat(str(race['RaceStartingTime'])[:-1] + '+00:00')
            time_difference = datetime_object - current_time
            if time_difference.total_seconds() >= 0:
                time_diff_str = '{:02d}h '.format(
                    int(time_difference.total_seconds() / 3600)) + '{:02d}m '.format(
                    int((time_difference.total_seconds() % 3600) / 60)) + '{:02d}s'.format(
                    int(time_difference.total_seconds() % 60))
            else:
                time_diff_str = '-{:02d}h '.format(
                    int(time_difference.total_seconds() / (-3600))) + \
                                '{:02d}m '.format(int((time_difference.total_seconds() % (-3600)) / (-60))) + \
                                '{:02d}s'.format(int(time_difference.total_seconds() % (-60)) * (-1))
            # if time_difference.total_seconds() > 0:
            if "MeetingName" in race.keys():
                if race['Location'] in ['VIC', 'QLD', 'TAS', 'WA', 'SA', 'NT', 'ACT', 'TAS']:
                    raceName = '{0}{1} {2}'.format(race['RaceType'], race['RaceNo'], race['MeetingName'])
                    self.displayList(i, raceName, race['RaceStartingTimeStr'], time_diff_str)

    def show_detail(self, param):
        self.selectedRaceId = param
        self.periodicalFunc(self.selectedRaceId)

    # def monitor_checkbox(self):
    #     for index, item in enumerate(self.checked_races):
    #         if item.get() == "1":
    #             race = races[index]
    #             t_timezone = 'Australia/Perth'
    #             py_timezone = pytz.timezone(t_timezone)
    #             current_time = datetime.now(py_timezone)
    #             print("Current time : ", current_time)
    #
    #             date_str = "{0}-{1}-{2}".format(current_time.year, '{:02d}'.format(current_time.month),
    #                                             '{:02d}'.format(current_time.day))
    #             race_url = "https://api.beta.tab.com.au/v1/tab-info-service/racing/dates/{0}/meetings/{1}/{2}/races/{3}?jurisdiction=SA".format(
    #                 date_str, race['RaceType'], race['VenueMnemonic'], race['RaceNo'])
    #             response = requests.request("GET", race_url)
    #             odd_data = response.json()
    #             race_dict = {}
    #             race_dict['VenueMnemonic'] = odd_data['meeting']['venueMnemonic']
    #             race_dict['Location'] = odd_data['meeting']['location']
    #             race_dict['MeetingName'] = odd_data['meeting']['meetingName']
    #             race_dict['RaceNo'] = odd_data['raceNumber']
    #             race_dict['RaceType'] = odd_data['meeting']['raceType']
    #             race_dict['Distance'] = odd_data['raceDistance']
    #             startTimeStr = utc_to_localtime(datetime.fromisoformat(odd_data['raceStartTime'][:-1] + '+09:30'))
    #             race_dict['RaceStartingTime'] = startTimeStr
    #
    #             current_time = datetime.now(timezone.utc)
    #             datetime_object = datetime.fromisoformat(str(odd_data['raceStartTime'])[:-1] + '+00:00')
    #             time_difference = datetime_object - current_time
    #             race_dict['TimeDifference'] = '{:02d}h '.format(
    #                 int(time_difference.seconds / 3600)) + '{:02d}m '.format(
    #                 int((time_difference.seconds % 3600) / 60)) + '{:02d}s'.format(time_difference.seconds % 60)
    #             races[index] = race_dict
    #             betting_time = random.randint(30, 300)
    #             if time_difference.seconds > 0 and time_difference.seconds < betting_time:
    #                 print("Will bet now (left {0} seconds".format(time_difference.seconds))
    #                 t_timezone = 'Australia/Perth'
    #                 py_timezone = pytz.timezone(t_timezone)
    #                 current_time = datetime.now(py_timezone)
    #                 date_str = "{0}-{1}-{2}".format(current_time.year, '{:02d}'.format(current_time.month),
    #                                                 '{:02d}'.format(current_time.day))
    #                 meeting = race_dict['MeetingName']
    #                 venue = race_dict['VenueMnemonic']
    #                 RaceType = race_dict['RaceType']
    #                 RaceNo = race_dict['RaceNo']
    #
    #                 if self.isDigit(self.stake_entry):
    #                     stake_val = int(self.stake_entry.get())
    #                 else:
    #                     stake_val = 0
    #                 runners = requestRaceDetails(race_dict, stake_val)
    #                 runners = sorted(runners, key=operator.itemgetter('ReturnWin'), reverse=False)
    #                 runner_no = runners[0]['RunnerNo']
    #
    #                 tab_browser.place_bet(date_str, meeting, venue, RaceType, RaceNo, runner_no, BET_WIN_STAKE)

    def periodicalFunc(self, selectedId):
        # self.monitor_checkbox()
        self.showOnlyAusRaces()
        # print("you clicked on", races[selectedId])
        raceName = 'R{0} {1}'.format(races[selectedId]['RaceNo'], races[selectedId]['MeetingName'])
        self.label_race.config(text=raceName)
        self.label_start.config(text=races[selectedId]['RaceStartingTimeStr'])

        current_time = datetime.now(timezone.utc)
        datetime_object = datetime.fromisoformat(str(races[selectedId]['RaceStartingTime'])[:-1] + '+00:00')
        time_difference = datetime_object - current_time
        if time_difference.total_seconds() >= 0:
            time_diff_str = '{:02d}h '.format(
                int(time_difference.total_seconds() / 3600)) + '{:02d}m '.format(
                int((time_difference.total_seconds() % 3600) / 60)) + '{:02d}s'.format(
                int(time_difference.total_seconds() % 60))
        else:
            time_diff_str = '-{:02d}h '.format(
                int(time_difference.total_seconds() / (-3600))) + \
                            '{:02d}m '.format(int((time_difference.total_seconds() % (-3600)) / (-60))) + \
                            '{:02d}s'.format(int(time_difference.total_seconds() % (-60)) * (-1))

        self.label_left.config(text=time_diff_str)

        if self.isDigit(self.stake_entry):
            stake_val = int(self.stake_entry.get())
        else:
            stake_val = 0
        runners = requestRaceDetails(races[selectedId], stake_val)
        self.selectedRunners = runners
        runners = sorted(runners, key=operator.itemgetter('BBr'), reverse=True)
        self.clearDetailFrame()
        max_horse = 0
        if self.isDigit(self.maxh_entry):
            max_horse = int(self.maxh_entry.get())
        # if max_horse > 0:
        #     print("Sorting...")
        #     runners = sorted(runners, key=operator.itemgetter('BBr'), reverse=True)
        runners_displayed = 0
        for i, runner in enumerate(runners, start=0):
            if (runner['bettingStatus'] == "Open"):
                if "RunnerName" in runner.keys():
                    is_available = 1
                    if self.isDigit(self.maxO_entry):
                        max_odds = int(self.maxO_entry.get())
                        if int(runner['ReturnWin']) >= max_odds:
                            is_available = 0
                    if self.isDigit(self.minO_entry):
                        min_odds = int(self.minO_entry.get())
                        if int(runner['ReturnWin']) < min_odds:
                            is_available = 0
                    if is_available == 1:
                        if max_horse == 0:
                            self.displayDetailList(i, runner['RunnerName'], runner['ReturnWin'],
                                                   runner['Lay'], runner['Stake'], runner['BBr'])
                        elif max_horse != 0 and runners_displayed < max_horse:
                            self.displayDetailList(i, runner['RunnerName'], runner['ReturnWin'],
                                                   runner['Lay'], runner['Stake'], runner['BBr'])
                            runners_displayed += 1

        if self.timer is None:
            self.timer = threading.Timer(TIME_BETWEEN_REQUESTS, self.periodicalFunc, (selectedId,))
        else:
            self.timer.cancel()
            self.timer = threading.Timer(TIME_BETWEEN_REQUESTS, self.periodicalFunc, (selectedId,))
        self.timer.start()

    def search_detail(self):
        print("Button clicked.")

    def isDigit(self, entry):
        try:
            i = int(entry.get())
            return True
        except ValueError:
            # Handle the exception
            print('Please enter an integer')
            return False

    def isFloat(self, value):
        try:
            i = float(value)
            return True
        except ValueError:
            # Handle the exception
            print('Please enter an float')
            return False


if __name__ == '__main__':
    races = requestAllRaces()
    requestRaceDetails(races[-1], 10)
    # tab_browser = TAB()
    # App().mainloop()
