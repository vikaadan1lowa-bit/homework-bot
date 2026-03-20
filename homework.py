import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot


load_dotenv()


logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)

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
    tokens = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    ]
    try:
        return all(tokens)
    except Exception:
        return False


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот отправил сообщение "{message}"')
    except Exception as error:
        logging.error(f'Сбой при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except Exception as error:
        logging.error(f'Ошибка запроса к API: {error}')
    if response.status_code != HTTPStatus.OK:
        raise Exception(f'API вернул {response.status_code}')
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    try:
        homeworks = response['homeworks']
        current_date = response['current_date']
    except KeyError as error:
        raise KeyError(error)
    if not isinstance(homeworks, list):
        raise TypeError('"homeworks" не является списком')
    return homeworks, current_date


def parse_status(homework):
    """Извлекает статус конкретной домашней работы."""
    try:
        name = homework['homework_name']
    except KeyError:
        raise KeyError('В ответе API отсутствует ключ "homework_name"')

    status = homework.get('status')
    try:
        verdict = HOMEWORK_VERDICTS[status]
    except KeyError:
        raise KeyError(f'Неизвестный статус домашней работы: {status}')

    return f'Изменился статус проверки работы "{name}": {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствуют необходимые токены!')
        return
    bot = TeleBot(TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks, timestamp = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                logging.debug('Новых домашних работ нет.')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            try:
                send_message(bot, message)
            except Exception:
                logging.error(
                    'Не удалось отправить сообщение об ошибке в Telegram.'
                )
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
