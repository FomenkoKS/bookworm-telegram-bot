import os
import re
import random
from aiogram import Bot, Dispatcher, executor, types
from dotenv import load_dotenv
from loguru import logger
from google_client import GoogleAPIClient
from openai import OpenAI
import datetime
import requests
import numpy as np

logger.add('bot/logs/bot.log', format='{time:DD-MM-YY HH:mm:ss} - {level} - {message}', level='INFO', rotation='1 week', compression='zip')

load_dotenv()
TOKEN = os.getenv('TOKEN')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
OPEN_API_KEY = os.getenv('OPEN_API_KEY')
RANGE_NAME = os.getenv('RANGE_NAME')
SHEET_ID = os.getenv('SHEET_ID')
SYS_PROMPT_CUSTOMER_SERVICE = "Ты помощник в книжном клубе. Отвечай без использования символов разметки и не задавай уточняющих вопросов."
    
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

oai_client = OpenAI(api_key=OPEN_API_KEY)
g_client = GoogleAPIClient(book_id=SPREADSHEET_ID, sheet_title=RANGE_NAME, sheet_id = SHEET_ID)

def get_title_and_choices():
    # выясняем номер заседания
    meeting = ''
    
    data = g_client.get_sheet(dictionary=False)
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

def describe_book(book_title, author):
    """Отправка запроса на описание книги"""
    
    response = oai_client.responses.create(
        instructions=SYS_PROMPT_CUSTOMER_SERVICE,
        model="gpt-4o-mini",
        input=f"Почему стоит почитать книгу {book_title} автора {author}? Если книга тебе неизвестна, так и скажи."
    )
    
    return response.output_text

def describe_books(books):
    """Отправка запроса на описание нескольких книг"""
    response = oai_client.responses.create(
        instructions=SYS_PROMPT_CUSTOMER_SERVICE,
        model="gpt-4o-mini",
        input=f"""
                Вот список книг: {books}. 
                Для КАЖДОЙ книги дай ответ в одно предложение - почему стоит ее почитать? Между описаниями добавь отступы.
                Если какая-то книга тебе неизвестна, так и скажи.
                """
    )
    
    return response.output_text

@dp.message_handler(commands=['add', 'describe'])
async def add_book(message: types.Message):    
    # Используем регулярное выражение для разбора команды
    pattern = r"\/(add|describe)\s(.+?)\s[-—]\s(.+)"
    match = re.match(pattern, message.text)
    if not match:
        await message.reply(
            f"Пожалуйста, введите данные в формате: <code>{message.text.split(' ')[0].split('@')[0]} Фамилия автора, Имя автора — Книга</code>",
            parse_mode = "HTML"
        )
        return
    isAdd = match.group(1).strip() == 'add'
    author = match.group(2).strip()
    book = match.group(3).strip()
    
    if isAdd:
        user = message.from_user.username or message.from_user.first_name
        # выясняем количество книг
        total = 0
        
        data = g_client.get_sheet(dictionary=False)
        for num, line in enumerate(data):
            if line[0] and line[1] == 'FALSE':
                total = line[0], num
        total, num = int(total[0]), total[1]
        g_client.add_values_from_list(values=[total + 1, 'FALSE', book, author, f'@{user}'], start_row=num+2)
        
        await message.reply(
            "Книга сохранена",
            reply_markup = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        {
                            "text":"Проверить список книг", 
                            "url": "https://docs.google.com/spreadsheets/d/1dI8FGgefou4Jnz2MEFk1Ey5BbFux4uV5dHgwjC4UMgM/edit?gid=1261866365#gid=1261866365"
                        }
                    ]
                ]
            ),
        )
        
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
