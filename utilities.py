import json
from collections import defaultdict
import pandas as pd
import requests
from telebot import types
from settings import DATABASE_URL
import psycopg2

START, ADDRESS, PHOTO_CONFIRMATION, PHOTO, LOCATION, LOCATION_CONFIRMATION, END, LIST_CONF, LIST = range(9)
USER_STATE = defaultdict(lambda: START)

def get_distances(locations, api_key):
    print(locations)
    print(list(range(1, len(locations)+1)))
    if len(locations) < 2:
        return []
    body = {"locations": locations,
        "destinations":list(range(1, len(locations))),"metrics":["distance"],
        "resolve_locations":"true","sources":[0],"units":"m"}
    print(body)
    headers = {
        'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
        'Authorization': api_key,
        'Content-Type': 'application/json; charset=utf-8'
    }
    call = requests.post('https://api.openrouteservice.org/v2/matrix/foot-walking', json=body, headers=headers)
    print(call.text)
    return json.loads(call.text)['distances'][0]

def execute_pgsql(sql):
    with psycopg2.connect(DATABASE_URL) as connection:
        connection.autocommit=True
        with connection.cursor() as cur:
            cur.execute(sql)


def create_messages_table():
    sql_create = """
            CREATE TABLE IF NOT EXISTS public.bot_messages
        (
            id serial primary key not null,
            "user" bigint,
            message text COLLATE pg_catalog."default"
        )
        TABLESPACE pg_default;
        ALTER TABLE public.bot_messages
            OWNER to postgres;"""
    execute_pgsql(sql_create)


def insert_message(user_id, message):
    address = message['name']
    try:
        photo = message['photo']
    except KeyError:
        photo = None
        #print('no photo')
    try:
        latitude = message['location'][0]
        longitude = message['location'][1]
    except KeyError:
        latitude = None
        longitude = None
        #print('no location')
    sql_insert = f"""
        INSERT INTO public.bot_messages(
        "user", address, photo, latitude, longitude)
        VALUES ({user_id}, '{address}', 
        {'NULL' if photo is None else photo}, 
        {'NULL' if latitude is None else latitude}, 
        {'NULL' if longitude is None else longitude});"""
    execute_pgsql(sql_insert)

def select_messages(user_id):
    sql_select = f'''SELECT * FROM public.bot_messages 
        WHERE "user" = {user_id}
        ORDER BY id DESC;'''
    with psycopg2.connect(DATABASE_URL) as connection:
        return pd.read_sql(con=connection, sql=sql_select, index_col="id")

def delete_messages(user_id):
    sql_delete = f'DELETE FROM public.bot_messages WHERE "user"={user_id}'
    execute_pgsql(sql_delete)


def get_state(message):
    return USER_STATE[message.chat.id]
def update_state(message, state):
    USER_STATE[message.chat.id] = state
    
    
def create_keyboard_1():
    #keyboard = types.InlineKeyboardMarkup(row_width=2)
    #buttons = [types.InlineKeyboardButton(text='Да', callback_data="0", request_location=True),
    #           types.InlineKeyboardButton(text='Нет', callback_data="1")]
    #keyboard.add(*buttons)
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    button = types.KeyboardButton(text='Отправить геолокацию',request_location=True)
    button2 = types.KeyboardButton(text='Нет')
    markup.add(button, button2)
    return markup #keyboard
    
def create_keyboard_2():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(text='Да', callback_data="0"),
               types.InlineKeyboardButton(text='Нет', callback_data="1")]
    keyboard.add(*buttons)
    return keyboard
        
PRODUCTS = defaultdict(lambda: {})
def get_product(user_id):
    return PRODUCTS[user_id]
def update_product(user_id, key, value):
    PRODUCTS[user_id][key] = value
