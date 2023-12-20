import os
import time
from datetime import datetime

import pytz
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options


class TAB:
    def __init__(self):
        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--save-page-as-mhtml')
        self.chrome_options.add_argument("--window-size=1920x1080")
        self.browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()),
                                        options=self.chrome_options)  # for ubuntu server
        self.browser.delete_all_cookies()
        self.login_tab_site()

    def login_tab_site(self):
        login_url = "https://www.tab.com.au/login"
        self.browser.get(login_url)
        print("Got the Login Page...")
        acc_number = self.browser.find_element(by=By.XPATH, value="//input[@data-testid='account-number-input']")
        acc_number.send_keys("4505547")
        acc_password = self.browser.find_element(by=By.XPATH, value="//input[@data-testid='password-input']")
        acc_password.send_keys("datsun1600")

        login_btn = self.browser.find_element(by=By.XPATH, value="//button[@data-testid='login-button']")
        login_btn.click()
        time.sleep(1)
        print("Successfully Logged In.")

    def go_race_page(self, url, runner_no, is_fixed_bet):
        self.browser.get(url)
        print("Got Race Page...")
        print("You selected : ", is_fixed_bet)
        if int(is_fixed_bet) == 1:
            runner_row = self.browser.find_element(by=By.XPATH, value="//div[@id='runner-number-{0}']//div["
                                                                      "@data-test-fixed-odds-win-price]".format(
                runner_no))
        else:
            runner_row = self.browser.find_element(by=By.XPATH, value="//div[@id='runner-number-{0}']//div["
                                                                      "@data-test-parimutuel-win-price]".format(
                runner_no))

        runner_name = self.browser.find_element(by=By.XPATH, value="//div[@id='runner-number-{0}']//div["
                                                                   "@class='runner-name']".format(runner_no)).text

        runner_row.click()
        return runner_name

    def bet_now(self, date_str, meeting, venue, RaceType, RaceNo, runner_no, win_stake, is_fixed_bet):

        race_url = "https://www.tab.com.au/racing/{0}/{1}/{2}/{3}/{4}".format(date_str, meeting, venue, RaceType,
                                                                              RaceNo)  # racing/today/MeetingName/Venue/RaceType/RaceNo
        runner_name = self.go_race_page(race_url, runner_no, is_fixed_bet)
        stake_input = self.browser.find_element(by=By.XPATH, value="//input[@data-id='bet-stake']")
        stake_input.send_keys(win_stake)
        bet_btn = self.browser.find_element(by=By.XPATH, value="//button[@data-id='bet-now']")
        bet_btn.click()
        print("Bet now clicked.")
        time.sleep(1)

        t_timezone = 'Australia/Perth'
        py_timezone = pytz.timezone(t_timezone)
        current_time = datetime.now(py_timezone)
        date_str = "{0}_{1}_{2}".format(current_time.year, '{:02d}'.format(current_time.month),
                                        '{:02d}'.format(current_time.day))
        dirpath = r'./{0}-{1}'.format(date_str, meeting)
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)

        file_name = dirpath+"/bet-{0}{1}-{2}-{3}.png".format(RaceType, RaceNo, runner_name, win_stake)
        self.browser.get_screenshot_as_file(file_name)
        self.submit()

    def bet_bonus(self, date_str, meeting, venue, RaceType, RaceNo, runner_no, bonus_stake, is_fixed_bet):
        race_url = "https://www.tab.com.au/racing/{0}/{1}/{2}/{3}/{4}".format(date_str, meeting, venue, RaceType,
                                                                              RaceNo)  # racing/today/MeetingName/Venue/RaceType/RaceNo
        runner_name = self.go_race_page(race_url, runner_no, is_fixed_bet)
        bonus_btn = self.browser.find_element(by=By.XPATH, value="//button[@data-test-bonus-bets-button]")
        bonus_btn.click()
        bonus_select_btns = self.browser.find_elements(by=By.XPATH, value="//li[@data-test-bonus-bet]")
        for item in bonus_select_btns:
            text = item.text
            if text.__contains__("${0} Bonus Bet".format(bonus_stake)):
                print(text)
                item.click()
                print("Bonus bet selected.")
                bet_btn = self.browser.find_element(by=By.XPATH, value="//button[@data-id='bet-now']")
                bet_btn.click()
                time.sleep(1)
                print("Bet now clicked")
                break

        t_timezone = 'Australia/Perth'
        py_timezone = pytz.timezone(t_timezone)
        current_time = datetime.now(py_timezone)
        date_str = "{0}_{1}_{2}".format(current_time.year, '{:02d}'.format(current_time.month),
                                        '{:02d}'.format(current_time.day))
        dirpath = r'./{0}-{1}'.format(date_str, meeting)
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)

        file_name = dirpath+"/bonusbet-{0}{1}-{2}-{3}.png".format(RaceType, RaceNo, runner_name, bonus_stake)
        self.browser.get_screenshot_as_file(file_name)
        self.submit()

    def submit(self):
        submit_btn = self.browser.find_element(by=By.XPATH, value="//button[@data-id='submit-bet']")
        submit_btn.click()

    def place_bet(self, date_str, meeting, venue, RaceType, RaceNo, runner_no, win_stake, is_fixed_bet):
        try:
            self.bet_now(date_str, meeting, venue, RaceType, RaceNo, runner_no, win_stake, is_fixed_bet)
            # self.bet_bonus(date_str, meeting, venue, RaceType, RaceNo, runner_no, "50.00", is_fixed_bet)
        except NoSuchElementException as e:
            print(e.msg)

    def close_browser(self):
        try:
            self.browser.close()
            print("Browser Closed.")
        except Exception as e:
            print(e.msg)


if __name__ == "__main__":
    tab_browser = TAB()
    # tab_browser.place_bet("2022-06-06", "BALLARAT", "BAL", "R", 1, 3, 1, "1")