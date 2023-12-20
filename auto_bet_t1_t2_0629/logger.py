import os
from datetime import datetime, timezone

import pytz


class Logger:
    def __init__(self):
        self.py_timezone = pytz.timezone('Australia/Perth')
        self.log_file = self.initialize()

    def initialize(self):
        current_time = datetime.now(self.py_timezone)
        date_str = current_time.strftime('%m-%d-%Y')
        timeStr = current_time.strftime("%H-%M-%S")
        DirPath = './logs/' + date_str

        if not os.path.exists(DirPath):
            os.makedirs(DirPath)
        filePath=DirPath + "/log-{0}.txt".format(timeStr)
        return filePath

    def print_log(self, text1, text2=""):
        print(text1, text2)
        f = open(self.log_file, "a")
        current_time = datetime.now(self.py_timezone)
        timestamp = current_time.strftime('%Y-%m-%m %H:%M:%S:%f')
        f.write("{0} : {1}{2}\n".format(timestamp, text1, text2))
        f.close()
