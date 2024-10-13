import logging
import os
import sys
from http import HTTPStatus
from logging import StreamHandler

import requests
from dotenv import load_dotenv
from requests import RequestException
from telebot import TeleBot
from telebot.apihelper import ApiException

from exeptions import APIError, SendMessageError


load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
SOURCE = ('API_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')
ENDPOINT = 'https://api.openweathermap.org/data/2.5/weather?'


def check_tokens():
    """Проверка наличия необходимых переменных окружения."""
    missing_token = [token for token in SOURCE if not globals()[token]]
    if missing_token:
        error_token = ', '.join(missing_token)
        logging.critical(f'Отсутствуют пременные окружения: {error_token}')
        raise TypeError(f'Отсутствуют пременные окружения: {error_token}')


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        logging.debug(f'Начало отправки сообщения: {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Сообщение отправлено: {message}')
    except (ApiException, RequestException) as error:
        logging.error(f'Ошибка при отправке сообщения: {error}')
        raise SendMessageError(error)


def get_api_answer(city):
    """Получение ответа от API."""
    logging.debug(f'Начало запроса к API: {city}')
    params = {
        'q': city,
        'appid': API_TOKEN,
        'units': 'metric',
        'lang': 'ru'
    }
    try:
        response = requests.get(
            ENDPOINT,
            params=params
        )
        logging.debug('API успешно получен.')
    except RequestException as error:
        raise APIError(f'Ошибка при запросе к основному API: {error}')
    if response.status_code != HTTPStatus.OK:
        raise APIError(f'Неправильный статус: {response.status_code} '
                       f'{response.reason}')
    logging.debug(f'Ответ от API: статус {response.status_code}, тело: {response.text}')
    return response.json()


def parse_weather(data):
    """Парсинг и форматирование данных о погоде."""
    if not isinstance(data, dict):
        raise KeyError('Некорректный ответ: ожидается словарь')

    weather_info = {}
    if 'main' not in data:
        raise KeyError('Некорректный ответ: отсутствует ключ "main"')
    weather_info['temperature'] = data['main'].get('temp')
    weather_info['humidity'] = data['main'].get('humidity')

    if 'weather' not in data or len(data['weather']) == 0:
        raise KeyError('Некорректный ответ: отсутствует или пуст список "weather"')
    weather_info['condition'] = data['weather'][0].get('description')

    return weather_info


def send_welcome(message):
    """Отправляет сообщение при команде /start."""
    welcome_text = (
        "Привет! Я бот, который сообщает текущую погоду по городам.\n\n"
        "Как пользоваться ботом:\n"
        "1. Введите название города, и я отправлю вам информацию о погоде в этом городе.\n"
        "2. Убедитесь, что город введен правильно, чтобы получить корректные данные.\n\n"
        "Пример: Москва\n\n"
        "Наслаждайтесь использованием бота!"
    )
    bot.send_message(message.chat.id, welcome_text)


def main():
    """Основная логика работы бота."""
    global bot
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    processed_cities = set()
    last_update_id = None

    while True:
        try:
            updates = bot.get_updates(offset=last_update_id, timeout=5)
            for update in updates:
                last_update_id = update.update_id + 1

                if update.message:
                    city = update.message.text.strip()
                    logging.debug(f'Получено сообщение: {city}')

                    if city == '/start':
                        logging.debug('Получена команда /start')
                        send_welcome(update.message)
                        continue

                    if city.startswith('/'):
                        logging.debug(f'Игнорируем команду: {city}')
                        continue

                    processed_cities.add(city)

                    response = get_api_answer(city)
                    weather_data = parse_weather(response)

                    if weather_data:
                        weather_message = (
                            f"Текущая погода в {city}: "
                            f"Температура: {weather_data['temperature']:.2f}°C\n"
                            f"Влажность: {weather_data['humidity']}%\n"
                            f"Описание: {weather_data['condition']}\n"
                        )
                        send_message(bot, weather_message)
                        processed_cities.remove(city)
                    else:
                        send_message(bot, "Не удалось получить данные о погоде.")
        except SendMessageError as error:
            logging.error(f'Ошибка при отправке сообщения: {error}')
        except Exception as error:
            logging.error(f'Сбой в работе программы: {error}')
            send_message(bot, f'Сбой в работе программы: {error}')


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format=('%(asctime)s, %(levelname)s,'
                '%(name)s, %(pathname)s, %(message)s'),
        handlers=[StreamHandler(sys.stdout)]
    )
    main()
