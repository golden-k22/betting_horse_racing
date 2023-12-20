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
from logger import Logger


class TAB:
    def __init__(self, logger):
        self.logger = logger
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
        self.logger.print_log("Got the Login Page...")
        acc_number = self.browser.find_element(by=By.XPATH, value="//input[@data-testid='account-number-input']")
        # acc_number.send_keys("4505547")
        acc_number.send_keys("4506618")
        acc_password = self.browser.find_element(by=By.XPATH, value="//input[@data-testid='password-input']")
        # acc_password.send_keys("datsun1600")
        acc_password.send_keys("Sana730104")

        login_btn = self.browser.find_element(by=By.XPATH, value="//button[@data-testid='login-button']")
        login_btn.click()
        time.sleep(1)
        self.logger.print_log("Successfully Logged In.")

    def go_race_page(self, url, runner_no, is_fixed_bet):
        self.browser.get(url)
        self.logger.print_log("Got Race Page...")
        self.logger.print_log("You selected : ", is_fixed_bet)
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
        self.logger.print_log("Bet now clicked.")
        time.sleep(1)

        t_timezone = 'Australia/Perth'
        py_timezone = pytz.timezone(t_timezone)
        current_time = datetime.now(py_timezone)
        date_str = "{0}_{1}_{2}".format(current_time.year, '{:02d}'.format(current_time.month),
                                        '{:02d}'.format(current_time.day))
        dirpath = r'./{0}-{1}'.format(date_str, meeting)
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)

        file_name = dirpath + "/bet-{0}{1}-{2}-{3}.png".format(RaceType, RaceNo, runner_name, win_stake)
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
            if text.__contains__("${0}".format(bonus_stake)):
                item.click()
                self.logger.print_log("Bonus bet selected.")
                bet_btn = self.browser.find_element(by=By.XPATH, value="//button[@data-id='bet-now']")
                bet_btn.click()
                time.sleep(1)
                self.logger.print_log("Bet now clicked")

                t_timezone = 'Australia/Perth'
                py_timezone = pytz.timezone(t_timezone)
                current_time = datetime.now(py_timezone)
                date_str = "{0}_{1}_{2}".format(current_time.year, '{:02d}'.format(current_time.month),
                                                '{:02d}'.format(current_time.day))
                dirpath = r'./{0}-{1}'.format(date_str, meeting)
                if not os.path.exists(dirpath):
                    os.makedirs(dirpath)

                file_name = dirpath + "/bonusbet-{0}{1}-{2}-{3}.png".format(RaceType, RaceNo, runner_name, bonus_stake)
                self.browser.get_screenshot_as_file(file_name)
                self.submit()
                break
            else:
                self.logger.print_log("There is not available bonus bets of {0}".format(bonus_stake))

    def get_bonus_cnt(self):

        try:
            menu_btn = self.browser.find_element(by=By.XPATH, value="//div[@data-id='menu']")
            menu_btn.click()
            time.sleep(1)
            account_btn = self.browser.find_element(by=By.XPATH, value="//div[@menu-name='account']")
            account_btn.click()
            time.sleep(1)
            bonus_bet_btn = self.browser.find_element(by=By.XPATH, value="//tab-t[@value='myBonusBets']")
            bonus_bet_btn.click()
            time.sleep(2)
            # self.browser.get_screenshot_as_file("bonus.png")

            bonus_select_btns = self.browser.find_elements(by=By.XPATH,
                                                           value='//h2[@data-testid="bonus-bet-card-title"]')
            all_availables = 0
            bets_50 = 0
            bets_25 = 0
            bets_125 = 0
            bets_10 = 0
            for item in bonus_select_btns:
                text = item.text
                self.logger.print_log(text)
                if text.__contains__("${0}".format(50)):
                    bets_50 += 1
                    all_availables += 1
                elif text.__contains__("${0}".format(25)):
                    bets_25 += 1
                    all_availables += 1
                elif text.__contains__("${0}".format(12.5)):
                    bets_125 += 1
                    all_availables += 1
                elif text.__contains__("${0}".format(10)):
                    bets_10 += 1
                    all_availables += 1
            return all_availables, bets_50, bets_25, bets_125, bets_10
        except Exception as e:
            self.logger.print_log(e.msg)
            # self.browser.close()
        return "--", "--", "--", "--", "--"

    def submit(self):
        # pass
        submit_btn = self.browser.find_element(by=By.XPATH, value="//button[@data-id='submit-bet']")
        submit_btn.click()

    def place_bet(self, date_str, meeting, venue, RaceType, RaceNo, runner_no, win_stake, is_fixed_bet):
        try:
            self.bet_now(date_str, meeting, venue, RaceType, RaceNo, runner_no, win_stake, is_fixed_bet)
            # self.bet_bonus(date_str, meeting, venue, RaceType, RaceNo, runner_no, "50.00", is_fixed_bet)
        except NoSuchElementException as e:
            self.logger.print_log(e.msg)

    def place_bonus_bet(self, date_str, meeting, venue, RaceType, RaceNo, runner_no, win_stake, is_fixed_bet):
        try:
            self.bet_bonus(date_str, meeting, venue, RaceType, RaceNo, runner_no, win_stake, is_fixed_bet)
        except NoSuchElementException as e:
            self.logger.print_log(e.msg)

    def close_browser(self):
        try:
            self.browser.close()
            self.logger.print_log("Browser Closed.")
        except Exception as e:
            self.logger.print_log(e.msg)


if __name__ == "__main__":
    logger = Logger()
    tab_browser = TAB(logger)
    # all, bet50, bet25, bet125, bet10=tab_browser.get_bonus_cnt()
    # print_log("{0}, {1}, {2}, {3}, {4}".format(all, bet50, bet25, bet125, bet10))
    tab_browser.place_bonus_bet("2022-06-27", "PINJARRA", "PJA", "H", 6, 4, 1, "2")
    tab_browser.close_browser()
