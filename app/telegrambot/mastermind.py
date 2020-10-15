import json
import logging
import os
from datetime import datetime
from typing import Dict

import requests
import transliterate
from bs4 import BeautifulSoup
from transliterate.exceptions import LanguageDetectionError

from app.data import emoji_conditions
from app.data.localization import hints, info, ph_info
from app.telegrambot.models import User

CUR_PATH = os.path.realpath(__file__)
BASE_DIR = os.path.dirname(os.path.dirname(CUR_PATH))
DATA_DIR = os.path.join(BASE_DIR, 'data')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

logging.basicConfig(filename='log.log', level=logging.DEBUG)
logger = logging.getLogger()


def get_day_part(ts, sunset):  # timestamp in Unix time
    if isinstance(ts, int):
        msg_time = datetime.fromtimestamp(ts).strftime('%H:%M').replace(':', '.')
    else:
        msg_time = ts
    sunset = sunset.replace(':', '.')
    if float(msg_time) > float(sunset):
        return 'night'
    else:
        return 'day'


def get_condition(cond, day_part):
    """"return emoji from the dictionary"""
    daylight_time = ['morning', 'day', 'утром', 'днём']

    if day_part.lower() not in daylight_time:
        try:
            condition = emoji_conditions.cond_emoji_night[cond.lower()]
            return condition.title()
        except KeyError as e:
            logger.warning(f'Condition has not been found\n{e}')
            try:
                translated = emoji_conditions.cond_trans_reversed[cond.lower()]
                condition = emoji_conditions.cond_emoji_night[translated.lower()]
                return condition.title()
            except KeyError as e:
                logger.warning(f'Condition has not been found\n{e}')

    try:
        condition = emoji_conditions.cond_emoji[cond.lower()]
    except KeyError as e:
        logger.warning(f'Condition has not been found\n{e}')
        try:
            translated = emoji_conditions.cond_trans_reversed[cond.lower()]
            condition = emoji_conditions.cond_emoji[translated.lower()]
        except KeyError as e:
            logger.warning(f'Condition has not been found\n{e}')
            return ''
    return condition.title()


def get_start(first_name, lang):
    """returns greeting and a short navigate information"""
    text = hints['start msg1'][lang] + first_name + hints['start msg2'][lang]
    return text


def get_response(city_name, lang, timestamp):
    """basic function"""

    transliterated_city = transliterate_name(city_name)

    try:
        weather_info = get_weather_info(transliterated_city, lang)
    except AttributeError as e:
        logger.error(f'Wrong city name\n{e}')
        return info[lang][0]
    else:
        weather_rest_info = get_extended_info(transliterated_city, 'today', lang)  # type: Dict

    daypart_message = ''
    for i in range(1, 5):
        daypart_info = weather_rest_info["part" + str(i)]  # type: Dict[str, str]
        daypart = daypart_info["weather_daypart"]
        daypart_temp = daypart_info["weather_daypart_temp"]
        daypart_cond = daypart_info["weather_daypart_condition"]
        daypart_cond_emoji = get_condition(daypart_cond, daypart)

        wind_speed_and_direction = daypart_info["wind_speed_and_direction"]
        if wind_speed_and_direction != info[lang][7]:
            wind_speed_and_direction =  wind_speed_and_direction.split(', ')[0]

        daypart_message += f'{daypart.title()}: {daypart_temp}; {info[lang][2]}: {wind_speed_and_direction} ' \
                           f'{daypart_cond_emoji}\n\n'

    header = weather_info["header"]
    temp = weather_info["temperature"]
    wind_speed_and_direction = weather_info["wind_speed_and_direction"]
    humidity = weather_info["humidity"]
    cond = weather_info["condition"]
    feels_like = weather_info["feels_like"]
    daylight_hours = weather_info["daylight_hours"]
    sunrise = weather_info["sunrise"]
    sunset = weather_info["sunset"]

    day_time = get_day_part(timestamp, sunset)
    weather_cond = get_condition(cond, day_time)

    message_part1 = f'<i>{header}</i>\n\n' \
                    f'<b>{info[lang][1]}: {temp}°; {info[lang][3]}: {feels_like}\n' \
                    f'{info[lang][2]}: {wind_speed_and_direction}; {ph_info["humidity"][lang]}: {humidity}\n' \
                    f'{cond} {weather_cond}</b> \n\n'

    message_part2 = f'{info[lang][4]}: {daylight_hours}\n' \
                    f'{info[lang][5]}: {sunrise} - {sunset}\n'

    response_message = message_part1 + daypart_message + message_part2

    return response_message


def get_weather_info(city_name, lang):
    """return the current weather info"""
    if lang == 'ru':
        source = requests.get('https://yandex.ru/pogoda/' + city_name)
    else:
        source = requests.get('https://yandex.com/pogoda/' + city_name)

    soup = BeautifulSoup(source.content, 'html.parser')
    weather_soup = soup.find('div', attrs={'class': 'fact'})

    header = weather_soup.find('div', attrs={'class': 'header-title'})
    header = header.find('h1', attrs={'class': 'title'}).text

    temperature = weather_soup.find('div', attrs={'class': 'fact__temp-wrap'})
    temperature = temperature.find(attrs={'class': 'temp__value'}).text

    wind_speed_and_direction = weather_soup.find('div', attrs={'class': 'fact__props'})
    try:
        wind_speed = wind_speed_and_direction.find('span', attrs={'class': 'wind-speed'}).text  # wind speed
        wind_direction = wind_speed_and_direction.find('span', attrs={'class': 'fact__unit'}).text  # wind unit, direct
        wind_speed_and_direction = f"{wind_speed} {wind_direction}"
    except AttributeError as e:
        logger.warning(f'No wind\n{repr(e)}')
        wind_speed_and_direction = info[lang][7]

    humidity = weather_soup.find('div', attrs={'class': 'fact__humidity'})
    humidity = humidity.find('div', attrs={'class': 'term__value'}).text  # humidity percentage

    condition = weather_soup.find('div', attrs={
        'class': 'link__condition'}).text  # condition comment (clear, windy etc.)

    feels_like = weather_soup.find('div', attrs={'class': 'term__value'})
    feels_like = feels_like.find('div', attrs={'class': 'temp'}).text  # feels like temperature

    daylight_soup = soup.find('div', attrs={'class': 'sun-card__info'})
    daylight_hours = daylight_soup.find('div', attrs={
        'class': 'sun-card__day-duration-value'}).text  # daylight duration
    sunrise = daylight_soup.find('div', attrs={'class': 'sun-card__sunrise-sunset-info_value_rise-time'}).text[-5:]
    sunset = daylight_soup.find('div', attrs={'class': 'sun-card__sunrise-sunset-info_value_set-time'}).text[-5:]

    response_message = {
        'header': header,
        'temperature': temperature,
        'wind_speed_and_direction': wind_speed_and_direction,
        'humidity': humidity,
        'condition': condition,
        'feels_like': feels_like,
        'daylight_hours': daylight_hours,
        'sunrise': sunrise,
        'sunset': sunset,
    }
    return response_message


def get_next_day(city_name, lang, phenomenon_info=False):
    """get tomorrow's weather info"""
    transliterated_city = transliterate_name(city_name)
    extended_info = get_extended_info(transliterated_city, 'tomorrow', lang)  # type: Dict
    if phenomenon_info:
        response_dict = {}
        daypart = 1
        for weather_val in extended_info.values():
            daypart_temp = weather_val["weather_daypart_temp"]
            daypart_condition = weather_val["weather_daypart_condition"]
            daypart_wind = weather_val["wind_speed_and_direction"].split(info[lang][10])[0].strip()
            daypart_humidity = weather_val["weather_daypart_humidity"]

            temp_daypart_dict = {
                'daypart_temp': daypart_temp,
                'daypart_condition': daypart_condition,
                'daypart_wind': daypart_wind,
                'daypart_humidity': daypart_humidity,
            }
            response_dict['part' + str(daypart)] = temp_daypart_dict
            daypart += 1
            if daypart > 4:
                break
        return response_dict

    response_message = f'<i>{extended_info["weather_city"]} {info[lang][6]} {extended_info["weather_date"]}</i>\n\n'
    for num in range(1, 5):
        daypart_info = extended_info["part" + str(num)]  # type: Dict[str, str]
        cond = daypart_info["weather_daypart_condition"]
        weather_daypart = daypart_info["weather_daypart"]
        daypart_temp = daypart_info["weather_daypart_temp"]
        wind_speed_and_direction = daypart_info["wind_speed_and_direction"]
        response_message += f'<b>{weather_daypart.title()}</b>, {daypart_temp} ' \
                            f'{info[lang][2]}: {wind_speed_and_direction}' \
                            f'\n{cond} {get_condition(cond, weather_daypart)}\n\n'

    return response_message


def get_next_week(city, lang):
    """get next 7 day's weather info"""
    transliterated_city = transliterate_name(city)
    extended_info = get_extended_info(transliterated_city, 'week', lang)
    response_message = ''
    weather_city = extended_info['weather_city']
    try:
        for day in extended_info.values():
            day_info_message = ''
            for day_part in day.values():
                try:
                    weather_daypart = day_part['weather_daypart'].title()
                    weather_daypart_temp = day_part['weather_daypart_temp']
                    weather_daypart_condition = day_part['weather_daypart_condition']
                    wind_speed_and_direction = day_part['wind_speed_and_direction']
                    weather_cond = get_condition(weather_daypart_condition, weather_daypart)
                    day_info_message += f'{weather_daypart}: {weather_daypart_temp}; ' \
                                        f' {wind_speed_and_direction} {weather_cond}\n'
                except TypeError as e:
                    logger.info(f'End of the day\n{repr(e)}')
                    day_info_message = f'\n<i><b>{day_part}</b></i>\n{day_info_message}'  # date + weather info
            response_message += day_info_message
    except AttributeError as e:
        logger.info(f'End of the week\n{e}')

    response_message = f'<i>{weather_city}. {info[lang][8]}</i>\n{response_message}'

    return response_message


# daily info
def get_daily(city_name, lang):
    transliterated_city = transliterate_name(city_name)
    extended_info = get_extended_info(transliterated_city, 'daily', lang)
    response_message = f'{extended_info["part1"]["weather_daypart"]},\n' \
                       f'{extended_info["part1"]["weather_daypart_temp"]},\n' \
                       f'{extended_info["part1"]["weather_daypart_condition"]},\n' \
                       f'{extended_info["part1"]["weather_daypart_wind"]},\n' \
                       f'{extended_info["part1"]["weather_daypart_direction"]},\n'
    return response_message


# handle get_extended_info func
def get_day_info(weather_rows, unit, lang):
    daypart_dict = dict()
    row_count = 0
    for row in weather_rows:
        weather_daypart = row.find('div', attrs={'class': 'weather-table__daypart'}).text
        weather_daypart_temp = row.find('div', attrs={'class': 'weather-table__temp'}).text
        weather_daypart_humidity = row.find('td', attrs={
            'class': 'weather-table__body-cell weather-table__body-cell_type_humidity'}).text
        weather_daypart_condition = row.find('td', attrs={'class': 'weather-table__body-cell_type_condition'}).text
        try:
            weather_daypart_wind = row.find('span', attrs={'class': 'weather-table__wind'}).text
            weather_unit = unit
            weather_daypart_direction = row.find('abbr', attrs={'class': 'icon-abbr'}).text
            wind_speed_and_direction = f'{weather_daypart_wind} {weather_unit}, {weather_daypart_direction}'
        except AttributeError as e:
            logger.warning(f'No wind\n{repr(e)}')
            wind_speed_and_direction = info[lang][7]

        temp_daypart_dict = {
            'weather_daypart': weather_daypart,
            'weather_daypart_temp': weather_daypart_temp,
            'weather_daypart_humidity': weather_daypart_humidity,
            'weather_daypart_condition': weather_daypart_condition,
            'wind_speed_and_direction': wind_speed_and_direction,
        }
        row_count += 1
        daypart_dict['part' + str(row_count)] = temp_daypart_dict
    return daypart_dict


# handle 'daily', 'tomorrow', 'today', 'for a week' buttons
def get_extended_info(city_name, command, lang):
    """return the extended weather info of the current day for daily cast"""
    if lang == 'ru':
        source = requests.get('https://yandex.ru/pogoda/' + city_name + '/details')
    else:
        source = requests.get('https://yandex.com/pogoda/' + city_name + '/details')

    soup = BeautifulSoup(source.content, 'html.parser')
    weather_unit = info[lang][10]

    if command == 'daily':  # button daily
        weather_table = soup.find('div', attrs={'class': 'card'})
    elif command == 'tomorrow':  # button tomorrow
        weather_table = soup.find_all('div', attrs={'class': 'card'})[2]
    elif command == 'today':
        weather_table = soup.find_all('div', attrs={'class': 'card'})[0]
    else:  # button for a week
        days_dict = dict()
        day_count = 0

        weather_city = soup.find('h1', attrs={'class': 'title title_level_1 header-title__title'}).text
        weather_city = weather_city.split()[-1]

        weather_tables = soup.find_all('div', attrs={'class': 'card'})[2:]
        for day in weather_tables:
            if day_count >= 7:  # output 7 days for the button 'for a week'
                break
            weather_day = day.find('strong', attrs={'class': 'forecast-details__day-number'}).text
            weather_month = day.find('span', attrs={'class': 'forecast-details__day-month'}).text
            weather_date = f'{weather_day} {weather_month}'
            weather_rows = day.find_all('tr', attrs={'class': 'weather-table__row'})
            day_count += 1

            daypart_dict = get_day_info(weather_rows, weather_unit, lang)
            daypart_dict['weather_date'] = weather_date
            days_dict['day' + str(day_count)] = daypart_dict

        days_dict['weather_city'] = weather_city
        return days_dict

    weather_city = soup.find('h1', attrs={'class': 'title title_level_1 header-title__title'}).text
    weather_city = weather_city.split()[-1]
    weather_day = weather_table.find('strong', attrs={'class': 'forecast-details__day-number'}).text
    weather_month = weather_table.find('span', attrs={'class': 'forecast-details__day-month'}).text
    weather_date = f'{weather_day} {weather_month}'
    weather_rows = weather_table.find_all('tr', attrs={'class': 'weather-table__row'})

    daypart_dict = get_day_info(weather_rows, weather_unit, lang)
    daypart_dict['weather_city'] = weather_city
    daypart_dict['weather_date'] = weather_date

    return daypart_dict


# def get_help(lang):
#     """returns commands list"""
#     text = hints['help intro'][lang]
#     return text


def get_cities_data(city):
    """return the cities_db dictionary"""
    with open(os.path.join(DATA_DIR, 'cities_db.json'), 'r', encoding='utf-8') as f:
        cities_data = json.load(f)
    content = cities_data[city]
    return content


def transliterate_name(city_to_translit):
    """transliterate a city name in case the name is not in the cities_db"""
    try:
        city = get_cities_data(city_to_translit.title())
    except KeyError as e:
        logger.warning(f'There is no such a city in the db {repr(e)}')
    else:
        return city

    try:
        new_name = transliterate.translit(city_to_translit, reversed=True)  # ru -> en
        if 'х' in city_to_translit.lower():  # 'х'(rus) -> 'kh'
            new_name = new_name.lower().replace('h', 'kh')
    except LanguageDetectionError as e:
        logger.warning(f'The name of the city is not in Russian. ({e})')
        new_name = city_to_translit
    return new_name


def get_user_data(message):
    chat_id = message.chat.id
    user = User.query.filter_by(chat_id=chat_id).first()
    username = message.from_user.first_name
    try:
        lang = user.language
    except AttributeError as e:
        logger.warning(e)
        lang = message.from_user.language_code
    try:
        city_name = user.city_name
    except AttributeError as e:
        logger.warning(e)
        city_name = None

    data_dict = {'user': user, 'username': username, 'city_name': city_name, 'chat_id': chat_id, 'lang': lang}
    return data_dict


if __name__ == '__main__':
    # print(get_daily('маха'))
    # print(get_response('Питер'))
    # get_scrap()
    # get_next_day('moscow')
    # get_condition('snow')
    pass
