import os
import re
import random
from aiogram import Bot, Dispatcher, executor, types
from dotenv import load_dotenv
from loguru import logger
from google_client import GoogleAPIClient
from google import genai
from google.genai import types as gai_types
import datetime
import requests
import numpy as np

logger.add('bot/logs/bot.log', format='{time:DD-MM-YY HH:mm:ss} - {level} - {message}', level='INFO', rotation='1 week', compression='zip')

load_dotenv()
TOKEN = os.getenv('TOKEN')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
RANGE_NAME = "База"

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)


safety_settings = [
    {
        "category": "HARM_CATEGORY_DANGEROUS",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE",
    },
]

gemini = genai.Client(api_key=GOOGLE_API_KEY)

def get_title_and_choices():
    # выясняем номер заседания
    meeting = ''
    logger.info(SPREADSHEET_ID)
    client = GoogleAPIClient(book_id=SPREADSHEET_ID, sheet_title=RANGE_NAME, logger=logger)
    data = client.get_sheet(dictionary=False)
    logger.info(data)
    
    for line in data:
        if len(line) > 5 and 'седание' in line[5]:
            meeting = line[5]
            
    _, num = meeting.split('№')
    title = f"Выбираем книгу для заседания №{int(num.strip())+1}!"
    # выясняем количество книг
    total = 0
    for line in data:
        if line[0] and line[1] == 'FALSE':
            total = line[0]
    # "бросаем кости"
    choices = random.sample(range(1, int(total) + 1), 10)
    # перебираем книги
    books = []
    for line in data:
        if not line[0] or line[1] != 'FALSE':
            continue
        num = int(line[0])
        
        if num in choices:
            book = f"«{line[2]}» — {line[3]} ({line[4]})"
            books.append(book)
            
    return title, books

def get_binance_avg_price(symbol):
    # Определяем временные метки для начала и конца предыдущего месяца
    now = datetime.datetime.now()
    first_day = (now - datetime.timedelta(days=30))
    start_timestamp = int(first_day.timestamp() * 1000)
    end_timestamp = int(now.timestamp() * 1000)

    # Параметры для API запроса
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": "1d",  # дневные свечи
        "startTime": start_timestamp,
        "endTime": end_timestamp
    }
    
    # Запрос данных с Binance
    response = requests.get(url, params=params)
    data = response.json()
    
    # Вычисление среднего значения для каждого дня
    avg_prices = []
    for day in data:
        open_price = float(day[1])
        close_price = float(day[4])
        avg_price = (open_price + close_price) / 2
        avg_prices.append(avg_price)
    
    return avg_prices

def describe_book(book_title, author):
    """Отправка запроса на описание книги"""
    
    response = gemini.models.generate_content(
        model="gemini-2.0-flash",
        config=gai_types.GenerateContentConfig(
            system_instruction="Ты помощник в книжном клубе. Отвечай без использования символов разметки и не задавай уточняющих вопросов."),
        contents=f"Почему стоит почитать книгу {book_title} автора {author}? Если книга тебе неизвестна, так и скажи."
    )
    
    return response.text

def describe_books(books):
    """Отправка запроса на описание нескольких книг"""
    response = gemini.models.generate_content(
        model="gemini-2.0-flash",
        config=gai_types.GenerateContentConfig(
            system_instruction="Ты помощник в книжном клубе. Отвечай без использования символов разметки и не задавай уточняющих вопросов."),
        contents=f"""
            Вот список книг: {books}. 
            Для КАЖДОЙ книги дай ответ в одно предложение - почему стоит ее почитать? Между описаниями добавь отступы.
            Если какая-то книга тебе неизвестна, так и скажи.
        """
    )
    
    return response.text

@dp.message_handler(commands=['mean_btc'])
async def get_mean_btc(message: types.Message):
    symbol = 'BTCUSDT'
    averages = get_binance_avg_price(symbol)
    mean_btc = np.mean(averages)
    min_btc = np.min(averages)
    max_btc = np.max(averages)
    await message.reply(f"Symbol: {symbol}\nMean price: {mean_btc:.2f}\nMin price: {min_btc:.2f}\nMax price: {max_btc:.2f}\n")
    
@dp.message_handler(commands=['add'])
async def add_book(message: types.Message):
    # Используем регулярное выражение для разбора команды
    client = GoogleAPIClient(book_id=SPREADSHEET_ID, sheet_title=RANGE_NAME)
    data = client.get_sheet(dictionary=False)
    
    pattern = r"\/add\s(.+?)\s[-—]\s(.+)"
    match = re.match(pattern, message.text)
    if not match:
        await message.reply("Пожалуйста, введите данные в формате: /add Фамилия автора, Имя автора - Книга")
        return
    author = match.group(1).strip()
    book = match.group(2).strip()
    user = message.from_user.username or message.from_user.first_name
    # выясняем количество книг
    total = 0
    for num, line in enumerate(data):
        if line[0] and line[1] == 'FALSE':
            total = line[0], num
    total, num = int(total[0]), total[1]
    client.add_values_from_list(values=[total + 1, 'FALSE', book, author, f'@{user}'], start_row=num+2)
    
    await message.reply("Книга сохранена")
    await message.reply(describe_book(book_title=book, author=author))

@dp.poll_answer_handler()
async def poll_answer(poll_answer: types.PollAnswer):
    # this handler starts after user choosed any answer 
    answer_ids = poll_answer.option_ids # list of answers     
    user_id = poll_answer.user.id
    poll_id = poll_answer.poll_id

# Логика команды /create_poll
@dp.message_handler(commands=['create_poll'])
async def get_create_poll(message: types.Message):
    
    question, options = get_title_and_choices()
    await message.reply_poll(question, options, is_anonymous=False, allows_multiple_answers=True)
    desc = describe_books(books='; '.join(options))
    await message.reply(desc)


if __name__ == '__main__':
    logger.info("Start Bot")
    executor.start_polling(dp)
