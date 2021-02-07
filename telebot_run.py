import psycopg2
import telebot
from settings import TOKEN, API_KEY
from utilities import *


bot = telebot.TeleBot(TOKEN)
    
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
                    if row["photo"] is not None:
                        bot.send_photo(message.chat.id, row["photo"], caption=row["address"])
                    else:
                        bot.send_message(message.chat.id, text=row["address"])
            update_state(message, START)
    except Exception as e:
        print(e)
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
                if row["photo"] is not None:
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
    except Exception as e:
        print(e)
        update_state(message, START)


@bot.message_handler(commands=['reset'])
def handle_message1(message):
    try:
        delete_messages(message.chat.id)
        bot.send_message(message.chat.id, text='Все данные удалены!')
    except Exception as e:
        print(e)
        update_state(message, START)

@bot.message_handler(commands=['add'])
@bot.message_handler(func=lambda message: get_state(message) == START)
def handle_message2(message):
    try:
        bot.send_message(message.chat.id, text='Напиши адрес')
        update_state(message, ADDRESS)
    except Exception as e:
        print(e)
        update_state(message, START)

@bot.message_handler(func=lambda message: get_state(message) == ADDRESS)
def handle_address(message):
    try:
        update_product(message.chat.id, 'name', message.text)
        product = get_product(message.chat.id)
        keyboard = create_keyboard_2()
        bot.send_message(message.chat.id, text=f'Добавить фото?', reply_markup=keyboard)
        update_state(message, PHOTO_CONFIRMATION)
    except Exception as e:
        print(e)
        update_state(message, START)

@bot.callback_query_handler(func=lambda callback_query: get_state(callback_query.message) == PHOTO_CONFIRMATION)
def handle_photo(callback_query):
    message = callback_query.message
    text = callback_query.data
    try:
        if '0' in text.lower():
            update_state(message, PHOTO)
            bot.answer_callback_query(callback_query.id, text=f'Жду фото')
        else:
            keyboard = create_keyboard_2()
            bot.send_message(message.chat.id, text=f'Добавить геолокацию? Если добавить геолокацию, можно будет запросить ближайшие места', reply_markup=keyboard)
            update_state(message, LOCATION_CONFIRMATION)
    except Exception as e:
        print(e)
        update_state(message, START)


@bot.message_handler(content_types=['photo'], func=lambda message: get_state(message) == PHOTO)
def handle_confirmation(message):
    try:
        fileID = message.photo[-1].file_id
        file_info = bot.get_file(fileID)
        downloaded_file = bot.download_file(file_info.file_path)
        binary = psycopg2.Binary(downloaded_file)
        update_product(message.chat.id, 'photo', binary)

        bot.send_message(message.chat.id, text=f'Фото принято')
        keyboard = create_keyboard_2()
        bot.send_message(message.chat.id, text=f'Добавить геолокацию?', reply_markup=keyboard)
        update_state(message, LOCATION_CONFIRMATION)
    except Exception as e:
        print(e)
        update_state(message, START)
    

@bot.callback_query_handler(func=lambda callback_query: get_state(callback_query.message) == LOCATION_CONFIRMATION)
def handle_location(callback_query):
    message = callback_query.message
    text = callback_query.data
    try:
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
    except Exception as e:
        print(e)
        update_state(message, START)

@bot.message_handler(content_types=['location'],func=lambda message: get_state(message) == LOCATION)
def handle_confirmation2(message):
    try:
        if message.text != "Нет":
            update_product(message.chat.id, 'location', (message.location.latitude, message.location.longitude))

        product = get_product(message.chat.id)
        keyboard = create_keyboard_2()
        bot.send_message(message.chat.id, text=f'Подтвердите добавление места:', reply_markup=keyboard)
        update_state(message, END)
    except Exception as e:
        print(e)
        update_state(message, START)


@bot.callback_query_handler(func=lambda callback_query: get_state(callback_query.message) == END)
def handle_confirmation3(callback_query):
    message = callback_query.message
    text = callback_query.data
    try:
        if '0' in text.lower():
            product = get_product(message.chat.id)
            insert_message(message.chat.id, product)
            #bot.answer_callback_query(callback_query.id, text=f'Запомнили:')
            bot.send_message(message.chat.id, text=f'Добавили адрес: {product["name"]}')
        update_state(message, START)
    except Exception as e:
        print(e)
        update_state(message, START)

if __name__ == "__main__":
    bot.polling()
