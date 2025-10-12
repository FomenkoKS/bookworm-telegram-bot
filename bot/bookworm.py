"""Telegram бот для книжного клуба с оптимизированной архитектурой."""
import os
import re
import random
from typing import Tuple, List

from aiogram import Bot, Dispatcher, executor, types
from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI

from google_client import GoogleAPIClient

# Константы для работы с таблицей
COL_NUM = 0
COL_STATUS = 1
COL_TITLE = 2
COL_AUTHOR = 3
COL_PROPOSER = 4

COMMAND_PATTERN = r"/(add|describe)\s(.+?)\s[-—]\s(.+)"

# Настройка логирования
logger.add(
    'bot/logs/bot.log',
    format='{time:DD-MM-YY HH:mm:ss} - {level} - {message}',
    level='INFO',
    rotation='1 week',
    compression='zip'
)

# Загрузка конфигурации
load_dotenv()

class Config:
    """Конфигурация бота из переменных окружения."""
    TOKEN = os.getenv('TOKEN')
    SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
    OPEN_API_KEY = os.getenv('OPEN_API_KEY')
    RANGE_NAME = os.getenv('RANGE_NAME')
    SHEET_ID = os.getenv('SHEET_ID')
    SYS_PROMPT = (
        "Ты помощник в книжном клубе. "
        "Отвечай без использования символов разметки и не задавай уточняющих вопросов."
    )

# Инициализация клиентов
bot = Bot(token=Config.TOKEN)
dp = Dispatcher(bot)
oai_client = OpenAI(api_key=Config.OPEN_API_KEY)
g_client = GoogleAPIClient(
    book_id=Config.SPREADSHEET_ID,
    sheet_title=Config.RANGE_NAME,
    sheet_id=Config.SHEET_ID
)


def format_book(line: List[str]) -> str:
    """Форматирует информацию о книге для отображения."""
    return f"«{line[COL_TITLE]}» — {line[COL_AUTHOR]} ({line[COL_PROPOSER]})"


def get_title_and_choices() -> Tuple[str, List[str]]:
    """Генерирует заголовок голосования и случайный выбор книг."""
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


def describe_book(book_title: str, author: str) -> str:
    """Получает описание книги через OpenAI API."""
    response = oai_client.responses.create(
        instructions=Config.SYS_PROMPT,
        model="gpt-4o-mini",
        input=(
            f"Почему стоит почитать книгу {book_title} автора {author}? "
            "Если книга тебе неизвестна, так и скажи."
        )
    )
    return response.output_text


def describe_books(books: List[str]) -> str:
    """Получает описания нескольких книг через OpenAI API."""
    books_str = '; '.join(books)
    response = oai_client.responses.create(
        instructions=Config.SYS_PROMPT,
        model="gpt-4o-mini",
        input=(
            f"Вот список книг: {books_str}. "
            "Для КАЖДОЙ книги дай ответ в одно предложение - почему стоит ее почитать? "
            "Между описаниями добавь отступы. Если какая-то книга тебе неизвестна, так и скажи."
        )
    )
    return response.output_text


async def save_book_to_sheet(book: str, author: str, username: str) -> None:
    """Сохраняет книгу в таблицу Google Sheets."""
    data = g_client.get_sheet(dictionary=False)
    
    # Находим последнюю строку с непрочитанными книгами
    last_total, last_row_idx = 0, 0
    for idx, line in enumerate(data):
        if line[COL_NUM] and line[COL_STATUS] == STATUS_UNREAD:
            last_total, last_row_idx = int(line[COL_NUM]), idx
    
    # Добавляем новую книгу
    new_values = [last_total + 1, STATUS_UNREAD, book, author, f'@{username}']
    g_client.add_values_from_list(values=new_values, start_row=last_row_idx + 2)


@dp.message_handler(commands=['add', 'describe'])
async def handle_book_command(message: types.Message):
    """Обрабатывает команды /add и /describe для работы с книгами."""
    match = re.match(COMMAND_PATTERN, message.text)
    
    if not match:
        command = message.text.split(' ')[0].split('@')[0]
        await message.reply(
            f"Пожалуйста, введите данные в формате: {command} Автор — Название книги"
        )
        return
    
    command, author, book = match.group(1).strip(), match.group(2).strip(), match.group(3).strip()
    is_add = command == 'add'
    
    if is_add:
        username = message.from_user.username or message.from_user.first_name
        await save_book_to_sheet(book, author, username)
        
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[[
                types.InlineKeyboardButton(
                    text="Проверить список книг",
                    url="https://docs.google.com/spreadsheets/d/"
                        "1dI8FGgefou4Jnz2MEFk1Ey5BbFux4uV5dHgwjC4UMgM/"
                        "edit?gid=1261866365#gid=1261866365"
                )
            ]]
        )
        await message.reply("Книга сохранена", reply_markup=keyboard)
    
    # Описание книги отправляется в обоих случаях
    description = describe_book(book_title=book, author=author)
    await message.reply(description)


@dp.message_handler(commands=['create_poll'])
async def handle_create_poll(message: types.Message):
    """Создает голосование за выбор книги для следующего заседания."""
    question, options = get_title_and_choices()
    
    await message.reply_poll(
        question,
        options,
        is_anonymous=False,
        allows_multiple_answers=True
    )
    
    descriptions = describe_books(books=options)
    await message.reply(descriptions)


if __name__ == '__main__':
    logger.info("Запуск бота книжного клуба")
    executor.start_polling(dp)
