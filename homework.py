import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot
from telebot.apihelper import ApiException
from requests.exceptions import RequestException


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = (
        'PRACTICUM_TOKEN',
        'TELEGRAM_TOKEN',
        'TELEGRAM_CHAT_ID'
    )
    missing_tokens = [
        token for token in tokens
        if not globals().get(token)
    ]
    if missing_tokens:
        message = (
            f'Отсутствуют переменные окружения: '
            f'{", ".join(missing_tokens)}'
        )
        logging.critical(message)
        raise ValueError(message)
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    logging.debug(f'Отправка сообщения: "{message}"')
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logging.debug(f'Бот отправил сообщение "{message}"')


class APIRequestError(Exception):
    """Ошибка запроса к API Практикума."""

    pass


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    logging.debug(f'Отправка запроса на {ENDPOINT} с параметрами {payload}')
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.RequestException as error:
        raise ConnectionError(f'Ошибка запроса к API: {error}')
    if response.status_code != HTTPStatus.OK:
        raise APIRequestError(f'API вернул {response.status_code}')
    logging.debug(f'Ответ получен успешно: {response.status_code}')
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    logging.debug('Начинаем проверку ответа API')
    if not isinstance(response, dict):
        raise TypeError(f'Ответ API не словарь, а {type(response)}')
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ "homeworks" в ответе API')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            f'"homeworks" не является списком, получен {type(homeworks)}'
        )
    logging.debug('Проверка ответа API успешно завершена')
    return homeworks


def parse_status(homework):
    """Извлекает статус конкретной домашней работы."""
    logging.debug('Начнем извлекать статус конкретной домашней работы')
    missing_keys = []
    if 'homework_name' not in homework:
        missing_keys.append('homework_name')
    if 'status' not in homework:
        missing_keys.append('status')
    if missing_keys:
        raise KeyError(
            f'В ответе API отсутствуют ключи: {", ".join(missing_keys)}'
        )
    name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Неизвестный статус домашней работы: {status}')
    verdict = HOMEWORK_VERDICTS[status]
    logging.debug('Статус конкретной домашней работы успешно извлечен')
    return f'Изменился статус проверки работы "{name}": {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствуют необходимые токены!')
        return
    bot = TeleBot(TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = None
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logging.debug('Новых домашних работ нет.')
                continue
            message = parse_status(homeworks[0])
            if message != last_message:
                send_message(bot, message)
                last_message = message
            if 'current_date' in response:
                timestamp = response['current_date']
        except (RequestException, ApiException) as error:
            logging.exception(f'Сбой при работе с внешними сервисами: {error}')
        except Exception as error:
            logging.exception(f'Сбой в работе программы: {error}')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('program.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    main()
