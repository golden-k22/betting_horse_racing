import operator
from datetime import datetime, timezone
from tkinter import ttk, messagebox

import pytz

try:
    from Tkinter import *
    from ttk import *
except ImportError:  # Python 3
    from tkinter import *
    from tkinter.ttk import *
import tkinter as tk
import threading

import json
import sched, time

TIME_BETWEEN_REQUESTS = 5
BACK_COLOR = "#66737F"
FORE_COLOR = "#cccccc"
WHITE = "white"
INPUT_WIDTH = 120
INPUT_PADX = 10
OFFSET_X = 70
INPUT_PADY = 20
OFFSET_Y = 30
DEFAULT_STAKE = 50

races = []
is_on = True


class App(tk.Tk):

    def __init__(self):
        tk.Tk.__init__(self)
        self.title("Auto Betting")
        self.geometry("900x600+500+200")
        self.resizable(0, 0)

        self.timer = None
        self.checked_races = [tk.StringVar(value='0') for _ in races]
        self.fixed_bets = [tk.StringVar(value='0') for _ in races]
        self.stake_values = [DEFAULT_STAKE for _ in races]
        self.table_y = 180
        self.CreateUI()
        self.showAllRaces()
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.periodicalFunc()
        self.protocol("WM_DELETE_WINDOW", self.on_exit)

    def on_exit(self):
        """When you click to exit, this function is called"""
        if messagebox.askyesno("Exit", "Do you want to quit the application?"):
            self.timer.cancel()

            self.destroy()

    def CreateUI(self):
        self.back_frame = tk.Frame(master=self.master, height=600, width=900, bg=BACK_COLOR)
        self.back_frame.place(x=0, y=0)
        self.label1 = tk.Label(master=self.master, text="Auto Betting", font='Helvetica 28 bold', bg=BACK_COLOR)
        self.label1.place(x=350, y=50)

        self.input_frame = tk.Frame(master=self.back_frame, height=70, width=800, bg=BACK_COLOR)
        self.input_frame.place(x=50, y=self.table_y - 80)

        self.def_stake_label = tk.Label(master=self.input_frame, text="Default Stake : ", font='Helvetica 14 bold',
                                        fg='#ffffff', bg=BACK_COLOR)
        self.def_stake_label.place(x=OFFSET_X, y=0 + INPUT_PADY)
        # style = ttk.Style(self.master)
        # style.configure('My.TEntry', padding=(20, 0, 0, 0))
        # self.def_stake_entry = ttk.Entry(master=self.input_frame, font="Helvetica 10", style='My.TEntry')
        v = StringVar(self.master, value=DEFAULT_STAKE)
        self.def_stake_entry = tk.Entry(master=self.input_frame, font="Helvetica 10", borderwidth=3, textvariable=v)
        self.def_stake_entry.place(x=OFFSET_X + INPUT_WIDTH + 25, y=3 + INPUT_PADY, width=INPUT_WIDTH, height=22)

        h_frame = tk.Frame(self.back_frame, background="#ffffff")
        h_frame.place(x=100, y=self.table_y)

        r_canvas = tk.Canvas(self.back_frame, borderwidth=0, background="#ffffff", width=700, height=350)
        r_canvas.place(x=100, y=self.table_y + 25)
        self.r_frame = tk.Frame(r_canvas, background="#ffffff")
        verticalScrollbar = tk.Scrollbar(self.back_frame, orient="vertical", command=r_canvas.yview)
        r_canvas.configure(yscrollcommand=verticalScrollbar.set)
        r_canvas.create_window((4, 4), window=self.r_frame, anchor="nw")
        verticalScrollbar.place(relx=0.887, rely=0.341, relheight=0.590, relwidth=0.013)
        self.r_frame.bind("<Configure>", lambda event, canvas=r_canvas: self.onFrameConfigure(r_canvas))
        self.display_header(h_frame)

        # no_filterBtn = tk.Button(self.back_frame, text="All Races", width=15, command=self.showAllRaces).place(x=200,
        #                                                                                                        y=570)
        # aut_filterBtn = tk.Button(self.back_frame, text="Australia Races", width=15,
        #                           command=self.showOnlyAusRaces).place(x=400,
        #                                                                y=570)
        # other_filterBtn = tk.Button(self.back_frame, text="Other Races", width=15, command=self.showOtherRaces).place(
        #     x=600, y=570)

    def onFrameConfigure(self, canvas):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def display_header(self, frame):
        no_label = tk.Label(master=frame, width=5, height=1, borderwidth=2, text="No", font='Helvetica 12',
                            bg=FORE_COLOR)
        no_label.grid(row=0, column=0, sticky="ew")
        races_label = tk.Label(master=frame, width=30, height=1, borderwidth=2, text="Races", font='Helvetica 12',
                               bg=FORE_COLOR)
        races_label.grid(row=0, column=1, sticky="ew")

        bet_label = tk.Label(master=frame, width=10, height=1, borderwidth=2, text="Bet",
                             font='Helvetica 12', bg=FORE_COLOR)
        bet_label.grid(row=0, column=2, sticky="ew")
        fixed_label = tk.Label(master=frame, width=10, height=1, borderwidth=2, text="Fixed",
                               font='Helvetica 12', bg=FORE_COLOR)
        fixed_label.grid(row=0, column=3, sticky="ew")
        tote_label = tk.Label(master=frame, width=10, height=1, borderwidth=2, text="Tote",
                              font='Helvetica 12', bg=FORE_COLOR)
        tote_label.grid(row=0, column=4, sticky="ew")
        check_label = tk.Label(master=frame, width=10, height=1, borderwidth=2, text="Stake", font='Helvetica 12',
                               bg=FORE_COLOR)
        check_label.grid(row=0, column=5, sticky="ew")

    def displayList(self, index, race_name):
        textNo = tk.Label(master=self.r_frame, width=5, height=1, borderwidth=1, text=index+1,font='Helvetica 12',
                          bg=WHITE)
        textNo.grid(row=index, column=0, sticky="ew")

        textRace = tk.Label(self.r_frame, width=30, height=1, borderwidth=1, text=race_name,font='Helvetica 12',
                            bg=WHITE)
        # textRace.bind("<Button-1>", lambda e, param=index: self.show_detail(param))
        textRace.grid(row=index, column=1, sticky="ew")

        bet_frame = tk.Frame(self.r_frame, width=10, height=1, borderwidth=1)
        bet_frame.grid(row=index, column=2)
        checkBox = tk.Checkbutton(bet_frame, width=10, text="", height=1, onvalue=1, offvalue=0,
                                  variable=self.checked_races[index])
        checkBox.bind("<Button-1>", lambda e, param=index: self.update_checkbox(param))
        checkBox.grid(row=1, column=1)

        fixed_bet_frame = tk.Frame(self.r_frame, width=10, height=1, borderwidth=1)
        fixed_bet_frame.grid(row=index, column=3)
        fixed_bet = tk.Radiobutton(fixed_bet_frame, width=10, text='', variable=self.fixed_bets[index], value=1)
        fixed_bet.bind("<Button-1>", lambda e, param=index: self.update_radiobutton(param))
        fixed_bet.grid(row=1, column=1, sticky="ew")

        tote_bet_frame = tk.Frame(self.r_frame, width=10, height=1, borderwidth=1)
        tote_bet_frame.grid(row=index, column=4)
        tote_bet = tk.Radiobutton(tote_bet_frame, width=10, text='', variable=self.fixed_bets[index], value=2)
        tote_bet.bind("<Button-1>", lambda e, param=index: self.update_radiobutton(param))
        tote_bet.grid(row=1, column=1, sticky="ew")

        sv = StringVar(value=self.stake_values[index])
        sv.trace("w", lambda name, index, mode, param=index, sv=sv: self.update_stake_entry(param, sv))
        stake_entry = tk.Entry(master=self.r_frame, font="Helvetica 10", borderwidth=3, textvariable=sv)
        stake_entry.grid(row=index, column=5, sticky="ew")

    def clearFrame(self):
        # destroy all widgets from frame
        for widget in self.r_frame.winfo_children():
            widget.destroy()

        # this will clear frame and frame will be empty
        # if you want to hide the empty panel then
        self.r_frame.pack_forget()

    def showAllRaces(self):
        if self.timer is not None:
            self.timer.cancel()
        self.clearFrame()
        for i, race in enumerate(races, start=0):

            current_time = datetime.now(timezone.utc)
            datetime_object = datetime.fromisoformat(str(race['RaceStartingTime'])[:-1] + '+00:00')
            time_difference = datetime_object - current_time
            if time_difference.total_seconds() > 0:
                if "MeetingName" in race.keys():
                    raceName = 'R{0} {1}'.format(race['RaceNo'], race['MeetingName'])
                    self.displayList(i, raceName)

    def showOnlyAusRaces(self):
        if self.timer is not None:
            self.timer.cancel()
        self.clearFrame()
        for i, race in enumerate(races, start=1):
            print(race)
            if "MeetingName" in race.keys():
                if race['Location'] in ['VIC', 'QLD', 'TAS', 'WA', 'SA', 'NT', 'ACT', 'TAS']:
                    raceName = 'R{0} {1}'.format(race['RaceNo'], race['MeetingName'])
                    self.displayList(i, raceName)

    def showOtherRaces(self):
        if self.timer is not None:
            self.timer.cancel()
        self.clearFrame()
        for i, race in enumerate(races, start=1):
            print(race)
            if "MeetingName" in race.keys():
                if race['Location'] not in ['VIC', 'QLD', 'TAS', 'WA', 'SA', 'NT', 'ACT', 'TAS']:
                    raceName = 'R{0} {1}'.format(race['RaceNo'], race['MeetingName'])
                    self.displayList(i, raceName)
    def update_checkbox(self, param):
        selectedId = param
        if self.checked_races[selectedId].get() == "0":
            self.fixed_bets[selectedId].set(1)
        elif self.checked_races[selectedId].get() == "1":
            self.fixed_bets[selectedId].set(0)
        print("checkbox selected-----------", selectedId)

    def update_radiobutton(self, param):
        selectedId = param
        if self.fixed_bets[selectedId].get() == "0":
            self.checked_races[selectedId].set(1)
        print("Radio selected-----------", selectedId)

    def update_stake_entry(self, param, s_value):
        selectedId = param
        print("Entry selected-----------", selectedId)
        self.stake_values[selectedId] = s_value.get()

    def monitor_checkbox(self):
        for index, item in enumerate(self.checked_races):
            if item.get() == "1":
                race = races[index]
                t_timezone = 'Australia/Perth'
                py_timezone = pytz.timezone(t_timezone)
                current_time = datetime.now(py_timezone)
                is_fixed_bet = self.fixed_bets[index].get()
                stack_value = self.stake_values[index]

                if int(is_fixed_bet) == 1:
                    print("is_fixed_bet")
                else:
                    print("Tote bet")
                print(stack_value)
                # print("Current time : ", current_time)

                # date_str = "{0}-{1}-{2}".format(current_time.year, '{:02d}'.format(current_time.month),
                #                                 '{:02d}'.format(current_time.day))
                # race_url = "https://api.beta.tab.com.au/v1/tab-info-service/racing/dates/{0}/meetings/{1}/{2}/races/{3}?jurisdiction=SA".format(
                #     date_str, race['RaceType'], race['VenueMnemonic'], race['RaceNo'])
                # response = requests.request("GET", race_url)
                # odd_data = response.json()
                # race_dict = {}
                # race_dict['VenueMnemonic'] = odd_data['meeting']['venueMnemonic']
                # race_dict['Location'] = odd_data['meeting']['location']
                # race_dict['MeetingName'] = odd_data['meeting']['meetingName']
                # race_dict['RaceNo'] = odd_data['raceNumber']
                # race_dict['RaceType'] = odd_data['meeting']['raceType']
                # race_dict['Distance'] = odd_data['raceDistance']
                # startTimeStr = utc_to_localtime(datetime.fromisoformat(odd_data['raceStartTime'][:-1] + '+09:30'))
                # race_dict['RaceStartingTime'] = startTimeStr
                #
                # current_time = datetime.now(timezone.utc)
                # datetime_object = datetime.fromisoformat(str(odd_data['raceStartTime'])[:-1] + '+00:00')
                # time_difference = datetime_object - current_time
                # race_dict['TimeDifference'] = '{:02d}h '.format(
                #     int(time_difference.seconds / 3600)) + '{:02d}m '.format(
                #     int((time_difference.seconds % 3600) / 60)) + '{:02d}s'.format(time_difference.seconds % 60)
                # races[index] = race_dict
                # betting_time = random.randint(30, 300)
                # if time_difference.seconds > 0 and time_difference.seconds < betting_time:
                #     print("Will bet now (left {0} seconds".format(time_difference.seconds))
            else:
                pass

    def periodicalFunc(self):
        self.monitor_checkbox()
        if self.timer is None:
            self.timer = threading.Timer(TIME_BETWEEN_REQUESTS, self.periodicalFunc, ())
        else:
            self.timer.cancel()
            self.timer = threading.Timer(TIME_BETWEEN_REQUESTS, self.periodicalFunc, ())
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


if __name__ == '__main__':
    with open('aus_races.json', 'r') as file:
        your_json = file.read().replace('\n', '')
    races = json.loads(your_json)
    App().mainloop()
