import robin_stocks.robinhood as r
import time
import discord
from discord.ext import commands, tasks
import json
import pandas as pd
import requests
import decimal

try:
    intents = discord.Intents.default()
    intents.members = True
    client = commands.Bot(command_prefix = '.', case_insensitive=True,  intents=intents)
except:
    client = commands.Bot(command_prefix = '.', case_insensitive=True)


look_up = {'01': 'January', '02': 'Febuary', '03': 'March', '04': 'April', '05': 'May',
            '06': 'June', '07': 'July', '08': 'August', '09': 'September', '10': 'October', '11': 'November', '12': 'December'}


with open("config.json", "r") as keys_file:
    keys = json.load(keys_file)
    server_id = keys['server_id']
    channel_id = keys['channel_id']
    user = keys['user']
    password = keys['password']
    username = keys['alert_name']
    CREDS = keys['bot_token']

login = r.login(user,password,expiresIn=86400)


def get_holdings():
    my_stocks = r.build_holdings()
    my_options = r.options.get_open_option_positions()
    dicts = []
    for option in my_options:
        link = option['option']
        value = requests.get(link).json()
        option.update(value)
        dicts.append(option)
    for option_position in dicts:
        underlying = option_position['chain_symbol']
        strike = option_position['strike_price']
        expiration = option_position['expiration_date']
        contract_type = option_position['type']
        quantity = option_position['quantity']
        average_price = option_position['average_price']
        mark = ((float(option_position['min_ticks']['above_tick']) + float(option_position['min_ticks']['above_tick']))/2)*100
        month = expiration.split("-")[1]
        day = expiration.split("-")[2]
        year = expiration.split("-")[0]
        symbol = underlying + "_"+month+day+year[2:]+contract_type[0].upper()+format_number(strike)
        name = look_up[month] + " " + day + " " + year + " " + format_number(strike) + " " + contract_type
        my_stocks[symbol] = {"type":"option", "quantity":quantity, "average_buy_price":average_price,"name":name, "equity":mark}
    return my_stocks

def format_number(num):
    try:
        dec = decimal.Decimal(num)
    except:
        return 'bad'
    tup = dec.as_tuple()
    delta = len(tup.digits) + tup.exponent
    digits = ''.join(str(d) for d in tup.digits)
    if delta <= 0:
        zeros = abs(tup.exponent) - len(tup.digits)
        val = '0.' + ('0'*zeros) + digits
    else:
        val = digits[:delta] + ('0'*tup.exponent) + '.' + digits[delta:]
    val = val.rstrip('0')
    if val[-1] == '.':
        val = val[:-1]
    if tup.sign:
        return '-' + val
    return val

def handle_sell(symbol, previous):
    quantity = float(previous['quantity'])
    side = "sold"
    quantity = str(round(quantity, 2))
    fill_price = previous['equity']
    security_type = previous['type']
    name = previous['name']
    order_str = username+" "+side+" "+str(quantity)+" "+name+" (**"+symbol+"**). Filled @ "+str(fill_price) + " Security Type: " + security_type.upper()
    return order_str

def handle_add_sub(symbol, order, previous):
    total_quantity = float(order['quantity'])
    old_quantity = float(previous['quantity'])
    print(total_quantity)
    change = total_quantity-old_quantity
    if change > 0:
        side = "bought"
    else:
        side = "sold"
    average_price = order['average_buy_price']
    fill_price = order['equity']
    security_type = order['type']
    name = order['name']
    order_str = username+" "+side+" "+str(change)+" "+name+" (**"+symbol+"**). Filled @ "+str(fill_price) + ", New Average: "+str(average_price)+" Security Type: " + security_type.upper()
    return order_str

def handle_buy(symbol, order):
    quantity = float(order['quantity'])
    side = "bought"
    quantity = str(round(quantity, 2))
    average_price = order['average_buy_price']
    security_type = order['type']
    name = order['name']
    order_str = username+" "+side+" "+str(quantity)+" "+name+" (**"+symbol+"**). Filled @ "+str(average_price) + " Security Type: " + security_type.upper()
    return order_str

def compare_holdings(old, new):
    old_keys = old.keys()
    new_keys = new.keys()
    for key in new_keys:
        if key not in old_keys:
            return handle_buy(key, new[key])
        new_quantity = new[key]['quantity']
        old_quantity = old[key]['quantity']
        if new_quantity != old_quantity:
            return handle_add_sub(key, new[key], old[key])
    for key in old_keys:
        if key not in new_keys:
            return handle_sell(key, old[key])
    return False

@client.event
async def on_ready():
    positions = get_holdings()
    with open('positions.json', 'w') as fp:
        json.dump(positions, fp)
    print("Robinhood bot is ready")

@tasks.loop(seconds = 3) # repeat after every 10 seconds
async def robinhood_loop():
    if client.is_ready():
        with open('positions.json', 'r') as fp:
            old_positions = json.load(fp)
        new_positions = get_holdings()
        server = client.get_guild(server_id)
        channel = server.get_channel(channel_id)
        updates = compare_holdings(old_positions, new_positions)
        if updates:
            await channel.send(updates)
        with open('positions.json', 'w') as fp:
            json.dump(new_positions, fp)

robinhood_loop.start()

client.run(DEV_BOT_TOKEN)