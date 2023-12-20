import betfairlightweight
import pytz
from betfairlightweight import filters
import pandas as pd
import numpy as np
import os
import datetime

import json

# Change this certs path to wherever you're storing your certificates
with open('credentials.json') as f:
    cred = json.load(f)
    my_username = cred['username']
    my_password = cred['password']
    my_app_key = cred['app_key']


def get_today_events():
    # Filter for just horse racing
    horse_racing_filter = betfairlightweight.filters.market_filter(text_query='Horse Racing')

    # This returns a list
    horse_racing_event_type = trading.betting.list_event_types(
        filter=horse_racing_filter)[0]

    horse_racing_event_type_id = horse_racing_event_type.event_type.id

    # Define a market filter

    t_timezone = 'Australia/Perth'
    py_timezone = pytz.timezone(t_timezone)
    today = datetime.datetime.now(py_timezone).date()
    print("Current time : ", datetime.datetime.now(py_timezone))
    start = datetime.datetime(today.year, today.month, today.day, tzinfo=datetime.timezone.utc)
    end = start + datetime.timedelta(1)
    thoroughbreds_event_filter = betfairlightweight.filters.market_filter(
        event_type_ids=[horse_racing_event_type_id],
        market_countries=['AU'],
        market_start_time={
            'to': (datetime.datetime.utcnow() + datetime.timedelta(days=1)).strftime("%Y-%m-%dT%TZ")
            # 'to': end.strftime("%Y-%m-%dT%TZ")
        }
    )

    # print("Print the filter", thoroughbreds_event_filter)

    # Get a list of all thoroughbred events as objects
    aus_thoroughbred_events = trading.betting.list_events(
        filter=thoroughbreds_event_filter
    )

    # Create a DataFrame with all the events by iterating over each event object
    aus_thoroughbred_events_today = pd.DataFrame({
        'Event Name': [event_object.event.name for event_object in aus_thoroughbred_events],
        'Event ID': [event_object.event.id for event_object in aus_thoroughbred_events],
        'Event Venue': [event_object.event.venue for event_object in aus_thoroughbred_events],
        'Country Code': [event_object.event.country_code for event_object in aus_thoroughbred_events],
        'Time Zone': [event_object.event.time_zone for event_object in aus_thoroughbred_events],
        'Open Date': [event_object.event.open_date for event_object in aus_thoroughbred_events],
        'Market Count': [event_object.market_count for event_object in aus_thoroughbred_events]
    })

    print('today events---------------------------\n', aus_thoroughbred_events_today)
    return aus_thoroughbred_events_today
    # print('list of event ids',aus_thoroughbred_events_today['Event ID'].tolist())


def get_eventID_by_name(events, event_name):
    result_evt = events[events['Event Name'].astype(str).str.lower().str.contains(event_name.lower())]
    if len(result_evt['Event ID'].values) > 0:
        return result_evt['Event ID'].values[0]
    else:
        return -1


def get_market_types(eventId):
    # Define a market filter
    market_types_filter = betfairlightweight.filters.market_filter(event_ids=[eventId],
                                                                   market_type_codes=["WIN"])
    # Request market types
    market_types = trading.betting.list_market_types(
        filter=market_types_filter
    )

    # Create a DataFrame of market types
    market_types = pd.DataFrame({
        'Market Type': [market_type_object.market_type for market_type_object in market_types],
    })
    print('Market Type----------------------------- \n', market_types)
    return market_types


def get_market_catalogues(eventId):
    market_catalogue_filter = betfairlightweight.filters.market_filter(event_ids=[eventId],
                                                                       market_type_codes=["WIN"]
                                                                       )
    market_catalogues = trading.betting.list_market_catalogue(
        filter=market_catalogue_filter,
        max_results='100',
        market_projection=['RUNNER_DESCRIPTION'],
        sort='FIRST_TO_START'
    )

    # runners = [m_cat_runner.runner_name for m_cat_runner in market_catalogues[0].runners]
    # [print("==========", market_cat_object.__dict__) for market_cat_object in market_catalogues]
    # Create a DataFrame for each market catalogue

    market = pd.DataFrame({
        'Market Name': [market_cat_object.market_name for market_cat_object in market_catalogues],
        'Market ID': [market_cat_object.market_id for market_cat_object in market_catalogues],
        # 'Market Cat': [market_cat_object for market_cat_object in market_catalogues],
        # 'Total Matched': [market_cat_object.total_matched for market_cat_object in market_catalogues],
    })

    print('Market Catalogues----------------------------- \n', market)
    return market_catalogues, market


def get_market_index_by_name(market, market_name):
    result_evt = market[market['Market Name'].astype(str).str.lower().str.contains(market_name.lower())]
    if len(result_evt['Market ID'].values[0]) > 0:
        market_index = result_evt.index.values.astype(int)[0]
        market_id = result_evt['Market ID'].values[0]
        return market_index, market_id
    else:
        return -1


def process_runner_books(runner_books, market_catalogue):
    all_lay_prices = []
    all_lay_sizes = []
    all_back_prices = []
    all_back_sizes = []
    best_back_prices = []
    best_back_sizes = []
    selection_ids = []
    runners = []
    for r_index, runner_book in enumerate(runner_books):
        if runner_book.status == "ACTIVE":
            print("------------Selected Id", runner_book.selection_id)

            # print('===================runner book dict=======================', runner_book.__dict__)
            lay_prices = []
            lay_sizes = []
            back_prices = []
            back_sizes = []
            for index, lay in enumerate(runner_book.ex.available_to_lay):
                lay_prices.append(lay.price)
                lay_sizes.append(lay.size)
            all_lay_prices.append(lay_prices)
            all_lay_sizes.append(lay_sizes)

            for indexb, back in enumerate(runner_book.ex.available_to_back):
                back_prices.append(back.price)
                back_sizes.append(back.size)
            all_back_prices.append(back_prices)
            all_back_sizes.append(back_sizes)

            if len(runner_book.ex.available_to_back) > 0:
                best_back_prices.append(runner_book.ex.available_to_back[0].price)
                best_back_sizes.append(runner_book.ex.available_to_back[0].size)
            else:
                best_back_prices.append(1.01)
                best_back_sizes.append(1.01)
            selection_ids.append(runner_book.selection_id)
            runners.append(market_catalogue.runners[r_index].runner_name)

    df = pd.DataFrame({
        'Runner Name': runners,
        'Selection ID': selection_ids,
        'Lay Size': all_lay_sizes,
        'Lay Price': all_lay_prices,
        'Back Size': all_back_sizes,
        'Back Price': all_back_prices,
        'Best Back Price': best_back_prices,
        'Best Back Size': best_back_sizes,
    })
    return df


market_id = 0
trading = betfairlightweight.APIClient(username=my_username,
                                       password=my_password,
                                       app_key=my_app_key,
                                       # certs="/home/gpauser/Desktop/Scripts")
                                       certs="/home/ubuntu/test/certs")
trading.login()
today_events = get_today_events()


# def process_runner_books(self, runner_books):
#     '''
#     This function processes the runner books and returns a DataFrame with the best back/lay prices + vol for each runner
#     :param runner_books:
#     :return:
#     '''
#     best_back_prices = [runner_book.ex.available_to_back[0].price
#                         if runner_book.ex.available_to_back[0].price
#                         else 1.01
#                         for runner_book
#                         in runner_books]
#     best_back_sizes = [runner_book.ex.available_to_back[0].size
#                        if runner_book.ex.available_to_back[0].size
#                        else 1.01
#                        for runner_book
#                        in runner_books]
#
#     best_lay_prices = [runner_book.ex.available_to_lay[0].price
#                        if runner_book.ex.available_to_lay[0].price
#                        else 1000.0
#                        for runner_book
#                        in runner_books]
#     best_lay_sizes = [runner_book.ex.available_to_lay[0].size
#                       if runner_book.ex.available_to_lay[0].size
#                       else 1.01
#                       for runner_book
#                       in runner_books]
#
#     selection_ids = [runner_book.selection_id for runner_book in runner_books]
#     last_prices_traded = [runner_book.last_price_traded for runner_book in runner_books]
#     total_matched = [runner_book.total_matched for runner_book in runner_books]
#     statuses = [runner_book.status for runner_book in runner_books]
#     scratching_datetimes = [runner_book.removal_date for runner_book in runner_books]
#     adjustment_factors = [runner_book.adjustment_factor for runner_book in runner_books]
#
#     df = pd.DataFrame({
#         'Selection ID': selection_ids,
#         'Best Back Price': best_back_prices,
#         'Best Back Size': best_back_sizes,
#         'Best Lay Price': best_lay_prices,
#         'Best Lay Size': best_lay_sizes,
#         'Last Price Traded': last_prices_traded,
#         'Total Matched': total_matched,
#         'Status': statuses,
#         'Removal Date': scratching_datetimes,
#         'Adjustment Factor': adjustment_factors
#     })
#     return df

def get_market_book(market_catalogues, index, market_id):
    # Create a price filter. Get all traded and offer data
    price_filter = betfairlightweight.filters.price_projection(
        # price_data=['EX_BEST_OFFERS']
        price_data=['EX_ALL_OFFERS']
    )

    # Request market books
    market_books = trading.betting.list_market_book(
        market_ids=[market_id],
        price_projection=price_filter
    )

    # Grab the first market book from the returned list as we only requested one market
    market_book = market_books[0]
    # print("================= Market Detail =====================\n", market_book.json())
    runners_df = process_runner_books(market_book.runners, market_catalogues[index])
    print("Runner Df for Market id({0})-----------------\n".format(market_id), runners_df)
    return runners_df


def get_runner_detail(event_name, market_name):
    event_id = get_eventID_by_name(today_events, event_name)
    if event_id != -1:
        print("Event ID ===========", event_id)
        catalogues, market = get_market_catalogues(event_id)
        market_index, market_id = get_market_index_by_name(market, market_name)
        print("Market ID==========={0}- {1}".format(market_id, market_index))
        if market_id != -1:
            runners_df = get_market_book(catalogues, market_index, market_id)
            return runners_df, market_id
        else:
            # Market Id is wrong!
            return pd.DataFrame(), 0.0
    else:
        # Event id is wrong!
        return pd.DataFrame(), 0.0


def place_order(event_name, market_name, runner_name, size, price):
    result = False
    runners_df, market_id = get_runner_detail(event_name, market_name)
    if runners_df.empty:
        print("Wrong Market Name or Event Name!")
    else:
        runner = runners_df[runners_df['Runner Name'].astype(str).str.lower().str.contains(runner_name.lower())]
        if len(runner['Selection ID']) > 0:
            selected_id = runner['Selection ID'].values[0]
            # selected_id = runners_df.loc[runners_df.index[runner_no - 1], 'Selection ID']
            print("selected_id  : ", selected_id)
            # Get the favourite's price and selection id
            fav_selection_id = runners_df.loc[runners_df['Best Back Price'].idxmin(), 'Selection ID']
            fav_price = runners_df.loc[runners_df['Best Back Price'].idxmin(), 'Best Back Price']
            # fav_selection_id = runners_df.loc[runners_df['Back Price'].idxmin(), 'Selection ID']
            # fav_price = runners_df.loc[runners_df['Back Price'].idxmin(), 'Back Price']
            # print("fav_selection_id", fav_selection_id)
            # print("fav_price", fav_price)
            # Define a limit order filter
            limit_order_filter = betfairlightweight.filters.limit_order(
                size=size,
                price=price,
                persistence_type='LAPSE'
            )
            # Define an instructions filter
            instructions_filter = betfairlightweight.filters.place_instruction(
                order_type="LIMIT",
                selection_id=str(selected_id),
                side="BACK",
                limit_order=limit_order_filter,

            )
            print("instruction filters : \n", instructions_filter)
            r = json.dumps(str(instructions_filter))
            loaded_r = json.loads(r)
            print("instruction filters : \n", loaded_r)
            # Place the order
            print("market Id is : \n", market_id)
            order = trading.betting.place_orders(
                market_id=str(market_id),  # The market id we obtained from before
                customer_strategy_ref='back_the_fav',
                instructions=[instructions_filter]  # This must be a list
            )
            print("order result: \n", order.__dict__)
            if order.status == "SUCCESS":
                result = True
    return result


if __name__ == '__main__':
    today_events = get_today_events()
    # detail_runners = get_runner_detail("Gawler", "R8 1516m")
    # place_order("Gawler", "R8 1516m", "Zoustorm", 10, 10)

# event_ids = today_events['Event ID'].tolist()
# market_list = []
# for index, event_id in enumerate(event_ids):
#     market = {}
#     # get_market_types(event_id)
#     catalogues = get_market_catalogues(event_id)
#     market['marketIDs'] = catalogues['Market ID'].tolist()
#     market['marketNames'] = catalogues['Market Name'].tolist()
#     market_list.append(market)
#
# for market in market_list:
#     for index, market_id in enumerate(market['marketIDs']):
#         get_market_book(market_id)
