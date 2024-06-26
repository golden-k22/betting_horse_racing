import json

import pandas as pd
import numpy as np
import requests
from datetime import date, timedelta
import os
import re
import tarfile
import zipfile
import bz2
import glob
import logging
from unittest.mock import patch
from typing import List, Set, Dict, Tuple, Optional
from itertools import zip_longest
import plotly.express as px

import betfairlightweight
from betfairlightweight import StreamListener
from betfairlightweight.resources.bettingresources import (
    PriceSize,
    MarketBook
)

# %config IPCompleter.greedy=True

#### --------------------------
#### FUNCTIONS
#### --------------------------

# Function to return Pandas DF of hub ratings for a particular date
def getHubRatings(dte):

    # Substitute the date into the URL
    url = 'https://betfair-data-supplier-prod.herokuapp.com/api/widgets/kash-ratings-model/datasets?date={}presenter=RatingsPresenter&json=true'.format(dte)

    # Convert the response into JSON
    responseJson = requests.get(url).json()
    with open('bet_hub.json', 'w') as outfile:
        json.dump(responseJson, outfile, indent=4)



# rounding to 2 decimal places or returning '' if blank
def as_str(v) -> str:
    return '%.2f' % v if type(v) is float else v if type(v) is str else ''

# splitting race name and returning the parts
def split_anz_horse_market_name(market_name: str) -> (str, str, str):
    # return race no, length, race type
    # input sample: R6 1400m Grp1
    parts = market_name.split(' ')
    race_no = parts[0] # return example R6
    race_len = parts[1] # return example 1400m
    race_type = parts[2].lower() # return example grp1, trot, pace

    return (race_no, race_len, race_type)

# creating a flag that is True when markets are australian thoroughbreds
def filter_market(market: MarketBook) -> bool:
    d = market.market_definition
    return (d.country_code == 'AU'
        and d.market_type == 'WIN'
        and (c := split_anz_horse_market_name(d.name)[2]) != 'trot' and c != 'pace')

# loading from tar and extracting files
def load_markets(file_path):
    # for file_path in file_paths:
        print(file_path)
        if os.path.isdir(file_path):
            for path in glob.iglob(file_path + '**/**/*.bz2', recursive=True):
                f = bz2.BZ2File(path, 'rb')
                yield f
                f.close()
        elif os.path.isfile(file_path):
            ext = os.path.splitext(file_path)[1]
            # iterate through a tar archive
            if ext == '.tar':
                with tarfile.TarFile(file_path) as archive:
                    for file in archive:
                        yield bz2.open(archive.extractfile(file))
            # or a zip archive
            elif ext == '.zip':
                with zipfile.ZipFile(file_path) as archive:
                    for file in archive.namelist():
                        yield bz2.open(archive.open(file))

        return None

# Extract Components From Generated Stream
def extract_components_from_stream(stream):

    with patch("builtins.open", lambda f, _: f):

        # Will return 3 market books t-3mins marketbook, the last preplay marketbook and the final market book
        evaluate_market = None
        prev_market = None
        postplay_market = None
        preplay_market = None
        t3m_market = None

        gen = stream.get_generator()

        for market_books in gen():

            for market_book in market_books:

                # If markets don't meet filter return None's
                if evaluate_market is None and ((evaluate_market := filter_market(market_book)) == False):
                    return (None, None, None, None)

                # final market view before market goes in play
                if prev_market is not None and prev_market.inplay != market_book.inplay:
                    preplay_market = market_book

                # final market view before market goes is closed for settlement
                if prev_market is not None and prev_market.status == "OPEN" and market_book.status != prev_market.status:
                    postplay_market = market_book

                # Calculate Seconds Till Scheduled Market Start Time
                seconds_to_start = (market_book.market_definition.market_time - market_book.publish_time).total_seconds()

                # Market at 3 mins before scheduled off
                if t3m_market is None and seconds_to_start < 3*60:
                    t3m_market = market_book

                # update reference to previous market
                prev_market = market_book

        # If market didn't go inplay
        if postplay_market is not None and preplay_market is None:
            preplay_market = postplay_market

        return (t3m_market, preplay_market, postplay_market, prev_market) # Final market is last prev_market

def run_stream_parsing():

    # Run Pipeline
    with open("./outputs/tho-odds.csv", "w+") as output:

        # Write Column Headers To File
        output.write("market_id,event_date,country,track,market_name,selection_id,selection_name,result,bsp,ltp,matched_volume,atb_ladder_3m,atl_ladder_3m\n")

        for file_obj in load_markets("Jun"):

            # Instantiate a "stream" object
            stream = trading.streaming.create_historical_generator_stream(
                file_path=file_obj,
                listener=listener,
            )

            # Extract key components according to the custom function above (outputs 4 objects)
            (t3m_market, preplay_market, postplay_market, final_market) = extract_components_from_stream(stream)

            # If no price data for market don't write to file
            if postplay_market is None:
                continue;

            # Runner metadata and key fields available from final market book
            runner_data = [
                {
                    'selection_id': r.selection_id,
                    'selection_name': next((rd.name for rd in final_market.market_definition.runners if rd.selection_id == r.selection_id), None),
                    'selection_status': r.status,
                    'sp': r.sp.actual_sp
                }
                for r in final_market.runners
            ]

            # Last Traded Price
            # _____________________

            # From the last marketbook before inplay or close
            ltp = [runner.last_price_traded for runner in preplay_market.runners]

            # Total Matched Volume
            # _____________________

            # Calculates the traded volume across all traded price points for each selection
            def ladder_traded_volume(ladder):
                return(sum([rung.size for rung in ladder]))

            selection_traded_volume = [ ladder_traded_volume(runner.ex.traded_volume) for runner in postplay_market.runners ]

            # Top 3 Ladder
            # ______________________

            # Extracts the top 3 price / stakes in available orders on both back and lay sides. Returns python dictionaries

            def top_3_ladder(availableLadder):
                out = {}
                price = []
                volume = []
                if len(availableLadder) == 0:
                    return(out)
                else:
                    for rung in availableLadder[0:3]:
                        price.append(rung.price)
                        volume.append(rung.size)
                    out["price"] = price
                    out["volume"] = volume
                    return(out)

            # Sometimes t-3 mins market book is empty
            try:
                atb_ladder_3m = [ top_3_ladder(runner.ex.available_to_back) for runner in t3m_market.runners]
                atl_ladder_3m = [ top_3_ladder(runner.ex.available_to_lay) for runner in t3m_market.runners]
            except:
                atb_ladder_3m = {}
                atl_ladder_3m = {}

            # Writing To CSV
            # ______________________

            for (runnerMeta, ltp, selection_traded_volume, atb_ladder_3m, atl_ladder_3m) in zip(runner_data, ltp, selection_traded_volume, atb_ladder_3m, atl_ladder_3m):

                if runnerMeta['selection_status'] != 'REMOVED':

                    output.write(
                        "{},{},{},{},{},{},{},{},{},{},{},{},{} \n".format(
                            str(final_market.market_id),
                            final_market.market_definition.market_time,
                            final_market.market_definition.country_code,
                            final_market.market_definition.venue,
                            final_market.market_definition.name,
                            runnerMeta['selection_id'],
                            runnerMeta['selection_name'],
                            runnerMeta['selection_status'],
                            runnerMeta['sp'],
                            ltp,
                            selection_traded_volume,
                            '"' + str(atb_ladder_3m) + '"', # Forcing the dictionaries to strings so we don't run into issues loading the csvs with the dictionary commas
                            '"' + str(atl_ladder_3m) + '"'
                        )
                    )



def get_win_times(horse_no, horse_df):
    total_cnt=horse_df['win'].count()
    win_cnt=(horse_df['win'] == 1).sum()
    win_percent=100*win_cnt/total_cnt
    print("Horse {0} - total count : {1}, win count : {2}, winning rate : {3} %".format(horse_no, total_cnt, win_cnt, format(win_percent,".2f")))


#### --------------------------
#### EXECUTION
#### --------------------------



with open('credentials.json') as f:
    cred = json.load(f)
    my_username = cred['username']
    my_password = cred['password']
    my_app_key = cred['app_key']
# create trading instance (don't need username/password)
trading = betfairlightweight.APIClient(username=my_username,
                                       password=my_password,
                                       app_key=my_app_key,
                                       # certs="/home/gpauser/Desktop/Scripts")
                                       certs="/home/ubuntu/betfair/certs")

# create listener
listener = StreamListener(max_latency=None)

# This will execute the files (it took me ~2 hours for 2 months of data)
run_stream_parsing()

# Load in odds file we created above
bfOdds = pd.read_csv("./outputs/tho-odds.csv", dtype={'market_id': object, 'selection_id': object, 'atb_ladder_3m': object, 'atl_ladder_3m': object})

# Convert dictionary columns
import ast
bfOdds['atb_ladder_3m'] = [ast.literal_eval(x) for x in bfOdds['atb_ladder_3m']]
bfOdds['atl_ladder_3m'] = [ast.literal_eval(x) for x in bfOdds['atl_ladder_3m']]

# Convert LTP to Numeric
bfOdds['ltp'] = pd.to_numeric(bfOdds['ltp'], errors='coerce')

# Filter after 18th Feb
bfOdds = bfOdds.query('event_date >= "2021-02-18"')

rawDF = bfOdds

# Join and clean up columns
df = (
    rawDF
    # Extra Best Back + Lay 3 mins before of
    .assign(best_back_3m = lambda x: [np.nan if d.get('price') is None else d.get('price')[0] for d in x['atb_ladder_3m']])
    .assign(best_lay_3m = lambda x: [np.nan if d.get('price') is None else d.get('price')[0] for d in x['atl_ladder_3m']])
    # Coalesce LTP to BSP (about 60 rows)
    .assign(ltp = lambda x: np.where(x["ltp"].isnull(), x["bsp"], x["ltp"]))
    # Add a binary win / loss column
    .assign(win=lambda x: np.where(x['result'] == "WINNER", 1, 0))
    # Extra columns
    # .assign(model_prob=lambda x: 1 / x['model_odds'])
    # Reorder Columns
    .reindex(columns = ['event_date', 'track', 'race_number', 'market_id', 'market_name', 'selection_id', 'bsp', 'ltp','best_back_3m','best_lay_3m','atb_ladder_3m', 'atl_ladder_3m','result','win'])

)

# sorted_df=df.sort_values(['event_date','market_id', 'best_back_3m'], ascending=[True,True, True])
#
# grouped_df=sorted_df.groupby(['market_id'], sort=False)['best_back_3m'].min()

first_horse_df= df.sort_values(['market_id','best_back_3m'], ascending=[True, True]).groupby('market_id').nth(0)
second_horse_df= df.sort_values(['market_id','best_back_3m'], ascending=[True, True]).groupby('market_id').nth(1)
third_horse_df= df.sort_values(['market_id','best_back_3m'], ascending=[True, True]).groupby('market_id').nth(2)
forth_horse_df= df.sort_values(['market_id','best_back_3m'], ascending=[True, True]).groupby('market_id').nth(3)
fifth_horse_df= df.sort_values(['market_id','best_back_3m'], ascending=[True, True]).groupby('market_id').nth(4)
sixth_horse_df= df.sort_values(['market_id','best_back_3m'], ascending=[True, True]).groupby('market_id').nth(5)

get_win_times(1, first_horse_df)
get_win_times(2, second_horse_df)
get_win_times(3, third_horse_df)
get_win_times(4, forth_horse_df)
get_win_times(5, fifth_horse_df)
get_win_times(6, sixth_horse_df)

first_horse_df.to_csv("bfOdds.csv", encoding='utf-8')
