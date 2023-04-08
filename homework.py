import http
import logging
import os
import sys
import time
from urllib.error import HTTPError

import requests
import telegram
from dotenv import load_dotenv

from exceptions import TokenNotExistException

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

format = '%(asctime)s [%(levelname)s] %(message)s %(funcName)s(%(lineno)d)'
logging.basicConfig(
    format=format,
    filename='bot_homework.log',
    filemode='w',
    level=logging.DEBUG,
    encoding='utf-8')

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(format)
handler.setFormatter(formatter)


def check_tokens():
    """Проверка наличия переменных окружения."""
    tokens = (PRACTICUM_TOKEN,
              TELEGRAM_TOKEN,
              TELEGRAM_CHAT_ID,
              )

    for token in tokens:
        if token is None:
            logger.critical(f'Нет переменной окружения: {token}')
            raise TokenNotExistException(f'{token} отсутствует')
    return True


def send_message(bot, message):
    """Отправка сообщения в чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logger.error(f'Сообщение не отправленно: {error}')

    logger.debug('Сообщение успешно отправленно')


def get_api_answer(timestamp):
    """Получение ответа по API."""
    payload = {'from_date': timestamp}

    try:
        logging.info('Запрос к API')
        response = requests.get(ENDPOINT,
                                headers=HEADERS,
                                params=payload)

        if response.status_code != http.HTTPStatus.OK:
            logging.error(
                f'Получен некоректный ответ API: {response.status_code}')
            raise HTTPError(
                f'Получен некоректный ответ API: {response.status_code}')
        response = response.json()
        return response

    except Exception as error:
        logging.error(f'Ошибка при запросе к основному API: {error}')
        raise HTTPError(
            f'Получен некоректный ответ API: {response.status_code}')


def check_response(response):
    """Проверка полученного ответа на соответствие."""
    if type(response) is not dict:
        raise TypeError('В ответе API пришел не словарь')

    if 'homeworks' not in response:
        raise KeyError('В словаре нет ключа homeworks')

    if type(response['homeworks']) is not list:
        raise TypeError('Значение по ключу homeworks не является списком')

    if response['homeworks'] == []:
        return {}
    else:
        if response['homeworks'][0]['status']:
            pass
        else:
            logging.error('У домашней работы отсутствует статус')

    return response.get('homeworks')[0]


def parse_status(homework):
    """Получение статуса домашней работы."""
    if 'status' and 'homework_name' in homework:
        status_homework = homework.get('status')
        homework_name = homework.get('homework_name')

        if status_homework not in HOMEWORK_VERDICTS.keys():
            logging.error('Неожиданный статус домашней работы')
            raise ValueError(
                'Значение status_homework нет в словаре возможных статусов')

        verdict = HOMEWORK_VERDICTS[status_homework]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'

    elif homework != {}:
        raise KeyError('в ответе API домашки нет ключа homework_name')
    elif homework == {}:
        logging.debug('Новый статус домашней работы отсутствует')


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    previous_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            response_homework = check_response(response)

            if response_homework:
                message = parse_status(response_homework)

            if message != previous_message:
                send_message(bot, message)
                previous_message = message
            else:
                logging.debug('В ответе нет новых статусов.')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'

            if message != previous_message:
                send_message(bot, message)
                previous_message = message
                logger.error(message)

        time.sleep(RETRY_PERIOD)
        timestamp = int(time.time() - RETRY_PERIOD)


if __name__ == '__main__':
    main()
