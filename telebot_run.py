import telebot
from telebot import types
from collections import defaultdict
import psycopg2
from psycopg2 import extras
from psycopg2.extensions import AsIs
import os
import pandas as pd
import json
import requests

port=os.environ.get('PORT', 5000)

DATABASE_URL = os.environ.get("DATABASE_URL", f"postgres://postgres:qazxswedc@127.0.0.1:5432/test")
print(DATABASE_URL)

token = '1550103906:AAGk_4LIoxERAPtRzXlhV3DwQMdzrbWRYbE' # os.getenv("TOKEN")
bot = telebot.TeleBot(token)
#API_KEY = 'AIzaSyAZ8MdA36TrX5nBH-BiK0H-D-FtZxXYS8k' # os.getenv("API_KEY")
API_KEY = '5b3ce3597851110001cf6248cd8544fc87f24ee9b2b419d7a4a8743a' # os.getenv("API_KEY")

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

    
@bot.message_handler(commands=['list'])
def handle_message0(message):
    keyboard = create_keyboard_2()
    bot.send_message(message.chat.id, text='''Использовать геолокацию? 
    При использовании геолокации 
    будут показаны ближайшие 
    запомненные места в радиусе 
    500 метров.''', reply_markup=keyboard)
    update_state(message, LIST_CONF)

@bot.callback_query_handler(func=lambda callback_query: get_state(callback_query.message) == LIST_CONF)
def handle_list(callback_query):
    try:
        message = callback_query.message
        text = callback_query.data
        if '0' in text.lower():
            keyboard = create_keyboard_1()
            bot.send_message(message.chat.id, text=f'Жду геолокацию', reply_markup=keyboard)
            update_state(message, LIST)
        else:
            df = select_messages(message.chat.id)[:10]
            if len(df) == 0:
                bot.send_message(message.chat.id, text='Данных ещё нет, для добавления введите команду: /add')
            else:
                bot.send_message(message.chat.id, text='Список последних запомненных мест:')
                for index, row in df.iterrows():
                    if not row["photo"] is None:
                        bot.send_photo(message.chat.id, row["photo"], caption=row["address"])
                    else:
                        bot.send_message(message.chat.id, text=row["address"])
            update_state(message, START)
    except:
        update_state(message, START)


@bot.message_handler(content_types=['location'],func=lambda message: get_state(message) == LIST)
def handle_confirmation22(message):
    try:
        update_state(message, START)
        df = select_messages(message.chat.id)[:10]
        tdf = df[df['latitude'].notna()]
        if len(tdf) == 0:
            bot.send_message(message.chat.id, text='Данных с геолокацией не найдено')
            bot.send_message(message.chat.id, text='Список последних запомненных мест:')
            for index, row in df.iterrows():
                if not row["photo"] is None:
                    bot.send_photo(message.chat.id, row["photo"], caption=row["address"])
                else:
                    bot.send_message(message.chat.id, text=row["address"])
        else:
            dist = get_distances(locations=[[message.location.longitude, message.location.latitude]]+\
                                 [[row[0], row[1]] for index, row in tdf[['longitude', 'latitude']].iterrows()],
                                 api_key=API_KEY)
            if len(dist) > 0:
                dist_2 = [i for i in dist if i <= 500]
                if len(dist_2) > 0:
                    bot.send_message(message.chat.id, text='Список ближайших мест:')
                    for (index, row), d in zip(tdf.iterrows(), dist):
                        if d < 500:
                            if not row["photo"] is None:
                                bot.send_photo(message.chat.id, row["photo"], caption=row["address"]+', '+str(d)+' метров')
                            else:
                                bot.send_message(message.chat.id, text=row["address"]+', '+str(d)+' метров')
                else:
                    bot.send_message(message.chat.id, text='Сохранённых мест в радиусе 500 метров не найдено, последние сохранённые места c локацией:')
                    for (index, row), d in zip(tdf.iterrows(), dist):
                        if not row["photo"] is None:
                            bot.send_photo(message.chat.id, row["photo"], caption=row["address"]+', '++str(d)+' метров')
                        else:
                            bot.send_message(message.chat.id, text=row["address"])
                    tdf = df[df['latitude'].isna()]
                    bot.send_message(message.chat.id, text='Последние сохранённые места без локации:')
                    for index, row in tdf.iterrows():
                        if not row["photo"] is None:
                            bot.send_photo(message.chat.id, row["photo"], caption=row["address"])
                        else:
                            bot.send_message(message.chat.id, text=row["address"])
    except:
        update_state(message, START)


@bot.message_handler(commands=['reset'])
def handle_message1(message):
    try:
        delete_messages(message.chat.id)
        bot.send_message(message.chat.id, text='Все данные удалены!')
    except:
        update_state(message, START)

@bot.message_handler(commands=['add'])
@bot.message_handler(func=lambda message: get_state(message) == START)
def handle_message2(message):
    try:
        bot.send_message(message.chat.id, text='Напиши адрес')
        update_state(message, ADDRESS)
    except:
        update_state(message, START)

@bot.message_handler(func=lambda message: get_state(message) == ADDRESS)
def handle_address(message):
    try:
        update_product(message.chat.id, 'name', message.text)
        product = get_product(message.chat.id)
        keyboard = create_keyboard_2()
        bot.send_message(message.chat.id, text=f'Добавить фото?', reply_markup=keyboard)
        update_state(message, PHOTO_CONFIRMATION)
    except:
        update_state(message, START)

@bot.callback_query_handler(func=lambda callback_query: get_state(callback_query.message) == PHOTO_CONFIRMATION)
def handle_photo(callback_query):
    try:
        message = callback_query.message
        text = callback_query.data
        if '0' in text.lower():
            update_state(message, PHOTO)
            bot.answer_callback_query(callback_query.id, text=f'Жду фото')
            #bot.send_message(message.chat.id, text=f'Жду фото')
        else:
            product = get_product(message.chat.id)
            keyboard = create_keyboard_2()
            #bot.answer_callback_query(callback_query.id, text=f'Добавить локацию?', reply_markup=keyboard)
            bot.send_message(message.chat.id, text=f'Добавить геолокацию? Если добавить геолокацию, можно будет запросить ближайшие места', reply_markup=keyboard)
            update_state(message, LOCATION_CONFIRMATION)
    except:
        update_state(message, START)


@bot.message_handler(content_types=['photo'], func=lambda message: get_state(message) == PHOTO)
def handle_confirmation(message):
    try:
        fileID = message.photo[-1].file_id
        file_info = bot.get_file(fileID)
        downloaded_file = bot.download_file(file_info.file_path)
        print(type(downloaded_file))
        print(len(downloaded_file))
        binary = psycopg2.Binary(downloaded_file)
        update_product(message.chat.id, 'photo', binary)

        bot.send_message(message.chat.id, text=f'Фото принято')
        product = get_product(message.chat.id)
        keyboard = create_keyboard_2()
        bot.send_message(message.chat.id, text=f'Добавить геолокацию?', reply_markup=keyboard)
        update_state(message, LOCATION_CONFIRMATION)
    except:
        update_state(message, START)
    

@bot.callback_query_handler(func=lambda callback_query: get_state(callback_query.message) == LOCATION_CONFIRMATION)
def handle_location(callback_query):
    try:
        message = callback_query.message
        text = callback_query.data
        if '0' in text.lower():
            update_state(message, LOCATION)
            keyboard = create_keyboard_1()
            bot.send_message(message.chat.id, text=f'Жду геолокацию', reply_markup=keyboard)
        else:
            product = get_product(message.chat.id)
            keyboard = create_keyboard_2()
            #bot.answer_callback_query(callback_query.id, text=f'Подтвердите добавление места:', reply_markup=keyboard)
            bot.send_message(message.chat.id, text=f'Подтвердите добавление места:', reply_markup=keyboard)
            update_state(message, END)
    except:
        update_state(message, START)

@bot.message_handler(content_types=['location'],func=lambda message: get_state(message) == LOCATION)
def handle_confirmation2(message):
    try:
        print(message.text)
        if message.text != "Нет":
            update_product(message.chat.id, 'location', (message.location.latitude, message.location.longitude))

        product = get_product(message.chat.id)
        keyboard = create_keyboard_2()
        bot.send_message(message.chat.id, text=f'Подтвердите добавление места:', reply_markup=keyboard)
        update_state(message, END)
    except:
        update_state(message, START)


@bot.callback_query_handler(func=lambda callback_query: get_state(callback_query.message) == END)
def handle_confirmation3(callback_query):
    try:
        message = callback_query.message
        text = callback_query.data
        if '0' in text.lower():
            product = get_product(message.chat.id)
            insert_message(message.chat.id, product)
            #bot.answer_callback_query(callback_query.id, text=f'Запомнили:')
            bot.send_message(message.chat.id, text=f'Добавили адрес: {product["name"]}')
        update_state(message, START)
    except:
        update_state(message, START)

if __name__ == "__main__":
    bot.polling()
