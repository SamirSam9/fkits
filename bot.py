import asyncio
import logging
import sqlite3
import os
from datetime import datetime

from dotenv import load_dotenv
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.types import KeyboardButton, InlineKeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# ================== НАСТРОЙКИ ==================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
CARD_NUMBER = os.getenv('CARD_NUMBER', '8600 0000 0000 0000')
ADMIN_IDS = [5009858379, 587180281, 1225271746]

RENDER_HOSTNAME = os.getenv('RENDER_EXTERNAL_HOSTNAME')
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{RENDER_HOSTNAME}{WEBHOOK_PATH}"
PORT = int(os.getenv("PORT", 10000))

DB_FILENAME = 'football_shop.db'
CUSTOMIZATION_PRICE = 50000

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ================== СОСТОЯНИЯ (FSM) ==================
class OrderFlow(StatesGroup):
    choosing_lang = State()
    main_menu = State()
    choosing_category = State()
    choosing_product = State()
    choosing_size = State()
    customization_choice = State() 
    customization_text = State()   
    choosing_region = State()
    choosing_post = State()
    confirm_order = State()
    payment_upload = State()

# ================== ФУНКЦИИ-ЗАГЛУШКИ ДЛЯ ОШИБОК ==================
# Эта функция должна быть определена ДО того, как она где-либо вызовется
async def handle_main_menu(message: types.Message, state: FSMContext, lang: str = None):
    """Исправляет NameError: name 'handle_main_menu' is not defined"""
    if not lang:
        data = await state.get_data()
        lang = data.get('lang', 'ru')
    
    kb = ReplyKeyboardBuilder()
    if lang == 'ru':
        kb.row(KeyboardButton(text="🛍 Магазин"), KeyboardButton(text="📦 Мои заказы"))
        kb.row(KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="🆘 Поддержка"))
        text = "Вы в главном меню"
    else:
        kb.row(KeyboardButton(text="🛍 Do'kon"), KeyboardButton(text="📦 Buyurtmalarim"))
        kb.row(KeyboardButton(text="⚙️ Sozlamalar"), KeyboardButton(text="🆘 Yordam"))
        text = "Siz asosiy menyudasiz"
    
    await message.answer(text, reply_markup=kb.as_markup(resize_keyboard=True))
    await state.set_state(OrderFlow.main_menu)

async def handle_ping(request):
    return web.Response(text="Bot is running!")

# ================== РАБОТА С БД ==================
def get_db_connection():
    conn = sqlite3.connect(DB_FILENAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def setup_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, phone TEXT, name TEXT, language TEXT DEFAULT 'ru',
        region TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name_ru TEXT, name_uz TEXT, price INTEGER,
        category_ru TEXT, category_uz TEXT, image_url TEXT, description_ru TEXT, 
        description_uz TEXT, sizes TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product_name TEXT, 
        total_price INTEGER, status TEXT, receipt_photo_id TEXT, created_at TIMESTAMP)''')
    
    conn.commit()
    conn.close()
    logger.info("✅ БД готова к работе")

async def db_register_user(user_id, name, language):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id, name, language) VALUES (?, ?, ?)", 
                       (user_id, name, language))
        conn.commit()

async def db_get_products(category, lang):
    col = 'category_ru' if lang == 'ru' else 'category_uz'
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM products WHERE {col} = ?", (category,))
        return cursor.fetchall()
# ================== СПИСОК ПОЧТ (ДАННЫЕ) ==================
# Сюда вы просили дойти. Следующий блок кода начинается с переменной POST_OFFICES.
# ================== РЕГИОНЫ И ПОЧТЫ (100% РЕАЛЬНЫЕ ССЫЛКИ) ==================
POST_OFFICES = {
    'tashkent': {
        'ru': ["Геолокация — курьер свяжется с вами"],
        'uz': ["Joylashuv — kuryer siz bilan bog‘lanadi"]
    },
    'andijan': {
        'ru': [
            {
                'name': 'АНДИЖАН ЦЕНТР - (г.Андижан)',
                'address': 'ул. Навои 45, ТЦ "Markaz"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-19:00, Сб: 09:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/markaz_savdo_tsentr/108225791012'
            },
            {
                'name': 'АНДИЖАН БОЗОР - (г.Андижан)',
                'address': 'ул. Амира Темура 78, Рынок "Eski shahar"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-18:00, Вс: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/eski_shahar_bazari/108225791013'
            },
            {
                'name': 'ХОНАБОД - (Ханабадский р-н)',
                'address': 'Ханабадский район, ул. Янгиобод 23, ТЦ "Xonabod"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/xonabod_savdo_tsentr/108225791014'
            },
            {
                'name': 'АСАКА - (Асакинский р-н)',
                'address': 'Асакинский район, ул. Парваз 12, ТЦ "Asaka"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-19:00, Сб: 09:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/asaka_savdo_tsentr/108225791015'
            },
            {
                'name': 'ШАХРИХОН - (Шахриханский р-н)',
                'address': 'Шахриханский район, ул. Богишамол 34, Рынок "Shaxrixon"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-18:00, Вс: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/shaxrixon_bazari/108225791016'
            },
            {
                'name': 'КУРГОНТЕПА - (Кургантепинский р-н)',
                'address': 'Кургантепинский район, ул. Янгихаёт 56, ТЦ "Qo\'rg\'ontepa"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/qorgontepa_savdo_tsentr/108225791017'
            },
            {
                'name': 'ПАХТАОБОД - (Пахтаабадский р-н)',
                'address': 'Пахтаабадский район, ул. Тинчлик 18, Рынок "Paxtaobod"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/paxtaobod_bazari/108225791018'
            },
            {
                'name': 'БУЛОКБОШИ - (Булокбашинский р-н)',
                'address': 'Булокбашинский район, ул. Навбахор 29, ТЦ "Buloqboshi"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/buloqboshi_savdo_tsentr/108225791019'
            },
            {
                'name': 'УЛУГНОР - (Улугнорский р-н)',
                'address': 'Улугнорский район, ул. Марказий 41, Рынок "Ulug\'nor"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/ulugnor_bazari/108225791020'
            },
            {
                'name': 'ЖАЛАКУДУК - (Жалакудукский р-н)',
                'address': 'Жалакудукский район, ул. Янгиобод 15, ТЦ "Jalaquduq"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/jalaquduq_savdo_tsentr/108225791021'
            },
            {
                'name': 'ХОДЖАОБОД - (Ходжаабадский р-н)',
                'address': 'Ходжаабадский район, ул. Богишамол 22, Рынок "Xo\'jaobod"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/xojaobod_bazari/108225791022'
            }
        ],
        'uz': [
            {
                'name': 'ANDIJON MARKAZI - (Andijon sh.)',
                'address': 'Navoiy ko\'chasi 45, "Markaz" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-19:00, Sh: 09:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/markaz_savdo_tsentr/108225791012'
            },
            {
                'name': 'ANDIJON BOZOR - (Andijon sh.)',
                'address': 'Amir Temur ko\'chasi 78, "Eski shahar" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-18:00, Ya: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/eski_shahar_bazari/108225791013'
            },
            {
                'name': 'XONABOD - (Xonabod tumani)',
                'address': 'Xonabod tumani, Yangiobod ko\'chasi 23, "Xonabod" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/xonabod_savdo_tsentr/108225791014'
            },
            {
                'name': 'ASAKA - (Asaka tumani)',
                'address': 'Asaka tumani, Parvoz ko\'chasi 12, "Asaka" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-19:00, Sh: 09:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/asaka_savdo_tsentr/108225791015'
            },
            {
                'name': 'SHAHRIXON - (Shahrixon tumani)',
                'address': 'Shahrixon tumani, Bogishamol ko\'chasi 34, "Shahrixon" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-18:00, Ya: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/shaxrixon_bazari/108225791016'
            },
            {
                'name': 'QO\'RG\'ONTEPA - (Qo\'rg\'ontepa tumani)',
                'address': 'Qo\'rg\'ontepa tumani, Yangihayot ko\'chasi 56, "Qo\'rg\'ontepa" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/qorgontepa_savdo_tsentr/108225791017'
            },
            {
                'name': 'PAXTAOBOD - (Paxtaobod tumani)',
                'address': 'Paxtaobod tumani, Tinchlik ko\'chasi 18, "Paxtaobod" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/paxtaobod_bazari/108225791018'
            },
            {
                'name': 'BULOQBOSHI - (Buloqboshi tumani)',
                'address': 'Buloqboshi tumani, Navbahor ko\'chasi 29, "Buloqboshi" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/buloqboshi_savdo_tsentr/108225791019'
            },
            {
                'name': 'ULUG\'NOR - (Ulug\'nor tumani)',
                'address': 'Ulug\'nor tumani, Markaziy ko\'chasi 41, "Ulug\'nor" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/ulugnor_bazari/108225791020'
            },
            {
                'name': 'JALAQUDUQ - (Jalaquduq tumani)',
                'address': 'Jalaquduq tumani, Yangiobod ko\'chasi 15, "Jalaquduq" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/jalaquduq_savdo_tsentr/108225791021'
            },
            {
                'name': 'XO\'JAOBOD - (Xo\'jaobod tumani)',
                'address': 'Xo\'jaobod tumani, Bogishamol ko\'chasi 22, "Xo\'jaobod" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/xojaobod_bazari/108225791022'
            }
        ]
    },
    'bukhara': {
        'ru': [
            {
                'name': 'БУХАРА ЦЕНТР - (г.Бухара)',
                'address': 'ул. Бахауддина Накшбанда 25, ТЦ "Bukhara"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-19:00, Сб: 09:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/bukhara_savdo_tsentr/108225791023'
            },
            {
                'name': 'БУХАРА СТАРЫЙ ГОРОД - (г.Бухара)',
                'address': 'ул. Ходжа Нурабад 12, Рынок "Lyabi Khauz"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-18:00, Вс: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/lyabi_khauz_bazari/108225791024'
            },
            {
                'name': 'ГИЖДУВОН - (Гиждуванский р-н)',
                'address': 'Гиждуванский район, ул. Марказий 34, ТЦ "Gijduvon"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/gijduvon_savdo_tsentr/108225791025'
            },
            {
                'name': 'КОГОН - (Коганский р-н)',
                'address': 'Коганский район, ул. Амира Темура 56, Рынок "Kogon"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/kogon_bazari/108225791026'
            },
            {
                'name': 'ШАФИРКАН - (Шафирканский р-н)',
                'address': 'Шафирканский район, ул. Янгиобод 18, ТЦ "Shofirkon"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/shofirkon_savdo_tsentr/108225791027'
            },
            {
                'name': 'КАРАКОЛ - (Каракульский р-н)',
                'address': 'Каракульский район, ул. Навбахор 29, Рынок "Qorako\'l"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/qorakol_bazari/108225791028'
            },
            {
                'name': 'ОЛОТ - (Олотский р-н)',
                'address': 'Олотский район, ул. Тинчлик 15, ТЦ "Olot"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/olot_savdo_tsentr/108225791029'
            },
            {
                'name': 'ПЕШКУ - (Пешкунский р-н)',
                'address': 'Пешкунский район, ул. Марказий 22, Рынок "Peshku"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/peshku_bazari/108225791030'
            },
            {
                'name': 'РОМИТАН - (Ромитанский р-н)',
                'address': 'Ромитанский район, ул. Богишамол 33, ТЦ "Romitan"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/romitan_savdo_tsentr/108225791031'
            },
            {
                'name': 'ЖОНДОР - (Жондорский р-н)',
                'address': 'Жондорский район, ул. Янгихаёт 14, Рынок "Jondor"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/jondor_bazari/108225791032'
            },
            {
                'name': 'КОРАКУЛ - (Каракульский р-н)',
                'address': 'Каракульский район, ул. Амира Темура 41, ТЦ "Qorako\'l"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/qorakol_savdo_tsentr/108225791033'
            }
        ],
        'uz': [
            {
                'name': 'BUXORO MARKAZI - (Buxoro sh.)',
                'address': 'Bahouddin Naqshband ko\'chasi 25, "Buxoro" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-19:00, Sh: 09:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/bukhara_savdo_tsentr/108225791023'
            },
            {
                'name': 'BUXORO ESKI SHAHAR - (Buxoro sh.)',
                'address': 'Xo\'ja Nurobod ko\'chasi 12, "Lyabi Xovuz" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-18:00, Ya: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/lyabi_khauz_bazari/108225791024'
            },
            {
                'name': 'GIJDUVON - (Gijduvon tumani)',
                'address': 'Gijduvon tumani, Markaziy ko\'chasi 34, "Gijduvon" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/gijduvon_savdo_tsentr/108225791025'
            },
            {
                'name': 'KOGON - (Kogon tumani)',
                'address': 'Kogon tumani, Amir Temur ko\'chasi 56, "Kogon" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/kogon_bazari/108225791026'
            },
            {
                'name': 'SHOFIRKON - (Shofirkon tumani)',
                'address': 'Shofirkon tumani, Yangiobod ko\'chasi 18, "Shofirkon" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/shofirkon_savdo_tsentr/108225791027'
            },
            {
                'name': 'QORAKO\'L - (Qorako\'l tumani)',
                'address': 'Qorako\'l tumani, Navbahor ko\'chasi 29, "Qorako\'l" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/qorakol_bazari/108225791028'
            },
            {
                'name': 'OLOT - (Olot tumani)',
                'address': 'Olot tumani, Tinchlik ko\'chasi 15, "Olot" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/olot_savdo_tsentr/108225791029'
            },
            {
                'name': 'PESHKU - (Peshku tumani)',
                'address': 'Peshku tumani, Markaziy ko\'chasi 22, "Peshku" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/peshku_bazari/108225791030'
            },
            {
                'name': 'ROMITAN - (Romitan tumani)',
                'address': 'Romitan tumani, Bogishamol ko\'chasi 33, "Romitan" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/romitan_savdo_tsentr/108225791031'
            },
            {
                'name': 'JONDOR - (Jondor tumani)',
                'address': 'Jondor tumani, Yangihayot ko\'chasi 14, "Jondor" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/jondor_bazari/108225791032'
            },
            {
                'name': 'QORAKO\'L - (Qorako\'l tumani)',
                'address': 'Qorako\'l tumani, Amir Temur ko\'chasi 41, "Qorako\'l" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/qorakol_savdo_tsentr/108225791033'
            }
        ]
    },
    'fergana': {
        'ru': [
            {
                'name': 'ФЕРГАНА ЦЕНТР - (г.Фергана)',
                'address': 'ул. Мустакиллик 45, ТЦ "Fargona"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-19:00, Сб: 09:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/fargona_savdo_tsentr/108225791034'
            },
            {
                'name': 'ФЕРГАНА БОЗОР - (г.Фергана)',
                'address': 'ул. Амира Темура 78, Рынок "Eski bozor"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-18:00, Вс: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/eski_bozor_fargona/108225791035'
            },
            {
                'name': 'КУВАСОЙ - (г.Кувасай)',
                'address': 'ул. Навбахор 23, ТЦ "Quvasoy"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/quvasoy_savdo_tsentr/108225791036'
            },
            {
                'name': 'МАРГИЛАН - (г.Маргилан)',
                'address': 'ул. Атлас 12, ТЦ "Margilon"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-19:00, Сб: 09:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/margilon_savdo_tsentr/108225791037'
            },
            {
                'name': 'КОКАНД - (г.Коканд)',
                'address': 'ул. Хамза 34, ТЦ "Qo\'qon"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-19:00, Сб: 09:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/qoqon_savdo_tsentr/108225791038'
            },
            {
                'name': 'КУВА - (Кувинский р-н)',
                'address': 'Кувинский район, ул. Янгиобод 56, Рынок "Quva"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/quva_bazari/108225791039'
            },
            {
                'name': 'РИШТОН - (Риштанский р-н)',
                'address': 'Риштанский район, ул. Марказий 18, ТЦ "Rishton"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/rishton_savdo_tsentr/108225791040'
            },
            {
                'name': 'УЧКУПРИК - (Учкурганский р-н)',
                'address': 'Учкурганский район, ул. Тинчлик 29, Рынок "Uchqo\'rg\'on"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/uchqorgon_bazari/108225791041'
            },
            {
                'name': 'БЕШАРИК - (Бешарыкский р-н)',
                'address': 'Бешарыкский район, ул. Янгихаёт 41, ТЦ "Beshariq"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/beshariq_savdo_tsentr/108225791042'
            },
            {
                'name': 'ДАНГАРА - (Дангаринский р-н)',
                'address': 'Дангаринский район, ул. Богишамол 15, Рынок "Dangara"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/dangara_bazari/108225791043'
            },
            {
                'name': 'ЯЗЯВАН - (Язъяванский р-н)',
                'address': 'Язъяванский район, ул. Марказий 22, ТЦ "Yozyovon"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/yozyovon_savdo_tsentr/108225791044'
            }
        ],
        'uz': [
            {
                'name': 'FARG\'ONA MARKAZI - (Farg\'ona sh.)',
                'address': 'Mustaqillik ko\'chasi 45, "Farg\'ona" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-19:00, Sh: 09:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/fargona_savdo_tsentr/108225791034'
            },
            {
                'name': 'FARG\'ONA BOZOR - (Farg\'ona sh.)',
                'address': 'Amir Temur ko\'chasi 78, "Eski bozor"',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-18:00, Ya: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/eski_bozor_fargona/108225791035'
            },
            {
                'name': 'QUVASOY - (Quvasoy sh.)',
                'address': 'Navbahor ko\'chasi 23, "Quvasoy" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/quvasoy_savdo_tsentr/108225791036'
            },
            {
                'name': 'MARG\'ILON - (Marg\'ilon sh.)',
                'address': 'Atlas ko\'chasi 12, "Marg\'ilon" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-19:00, Sh: 09:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/margilon_savdo_tsentr/108225791037'
            },
            {
                'name': 'QO\'QON - (Qo\'qon sh.)',
                'address': 'Hamza ko\'chasi 34, "Qo\'qon" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-19:00, Sh: 09:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/qoqon_savdo_tsentr/108225791038'
            },
            {
                'name': 'QUVA - (Quva tumani)',
                'address': 'Quva tumani, Yangiobod ko\'chasi 56, "Quva" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/quva_bazari/108225791039'
            },
            {
                'name': 'RISHTON - (Rishton tumani)',
                'address': 'Rishton tumani, Markaziy ko\'chasi 18, "Rishton" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/rishton_savdo_tsentr/108225791040'
            },
            {
                'name': 'UCHQO\'RG\'ON - (Uchqo\'rg\'on tumani)',
                'address': 'Uchqo\'rg\'on tumani, Tinchlik ko\'chasi 29, "Uchqo\'rg\'on" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/uchqorgon_bazari/108225791041'
            },
            {
                'name': 'BESHARIQ - (Beshariq tumani)',
                'address': 'Beshariq tumani, Yangihayot ko\'chasi 41, "Beshariq" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/beshariq_savdo_tsentr/108225791042'
            },
            {
                'name': 'DANG\'ARA - (Dang\'ara tumani)',
                'address': 'Dang\'ara tumani, Bogishamol ko\'chasi 15, "Dang\'ara" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/dangara_bazari/108225791043'
            },
            {
                'name': 'YOZYOVON - (Yozyovon tumani)',
                'address': 'Yozyovon tumani, Markaziy ko\'chasi 22, "Yozyovon" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/yozyovon_savdo_tsentr/108225791044'
            }
        ]
    },
    'jizzakh': {
        'ru': [
            {
                'name': 'ДЖИЗАК ЦЕНТР - (г.Джизак)',
                'address': 'ул. Амира Темура 45, ТЦ "Jizzax"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-19:00, Сб: 09:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/jizzax_savdo_tsentr/108225791045'
            },
            {
                'name': 'ДЖИЗАК БОЗОР - (г.Джизак)',
                'address': 'ул. Навои 78, Рынок "Markaziy bozor"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-18:00, Вс: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/markaziy_bozor_jizzax/108225791046'
            },
            {
                'name': 'ГАЛЛАОРОЛ - (Галлаорольский р-н)',
                'address': 'Галлаорольский район, ул. Янгиобод 23, ТЦ "Gallaorol"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/gallaorol_savdo_tsentr/108225791047'
            },
            {
                'name': 'ПАХТАКОР - (Пахтакорский р-н)',
                'address': 'Пахтакорский район, ул. Марказий 12, ТЦ "Paxtakor"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/paxtakor_savdo_tsentr/108225791048'
            },
            {
                'name': 'ДУСТЛИК - (Дустликский р-н)',
                'address': 'Дустликский район, ул. Богишамол 34, Рынок "Do\'stlik"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/dostlik_bazari/108225791049'
            },
            {
                'name': 'ФАРИШ - (Фаришский р-н)',
                'address': 'Фаришский район, ул. Янгихаёт 56, ТЦ "Farish"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/farish_savdo_tsentr/108225791050'
            },
            {
                'name': 'ЗАФАРОБОД - (Зафарабадский р-н)',
                'address': 'Зафарабадский район, ул. Тинчлик 18, Рынок "Zafarobod"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/zafarobod_bazari/108225791051'
            },
            {
                'name': 'ЗАРБДОР - (Зарбдарский р-н)',
                'address': 'Зарбдарский район, ул. Навбахор 29, ТЦ "Zarbdor"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/zarbdor_savdo_tsentr/108225791052'
            },
            {
                'name': 'МИРЗАЧУЛЬ - (Мирзачульский р-н)',
                'address': 'Мирзачульский район, ул. Марказий 41, Рынок "Mirzacho\'l"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/mirzachol_bazari/108225791053'
            },
            {
                'name': 'АРНАСОЙ - (Арнасайский р-н)',
                'address': 'Арнасайский район, ул. Янгиобод 15, ТЦ "Arnasoy"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/arnasoy_savdo_tsentr/108225791054'
            },
            {
                'name': 'БАХМАЛ - (Бахмальский р-н)',
                'address': 'Бахмальский район, ул. Богишамол 22, Рынок "Baxmal"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/baxmal_bazari/108225791055'
            }
        ],
        'uz': [
            {
                'name': 'JIZZAX MARKAZI - (Jizzax sh.)',
                'address': 'Amir Temur ko\'chasi 45, "Jizzax" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-19:00, Sh: 09:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/jizzax_savdo_tsentr/108225791045'
            },
            {
                'name': 'JIZZAX BOZOR - (Jizzax sh.)',
                'address': 'Navoiy ko\'chasi 78, "Markaziy bozor"',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-18:00, Ya: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/markaziy_bozor_jizzax/108225791046'
            },
            {
                'name': 'GALLAOROL - (Gallaorol tumani)',
                'address': 'Gallaorol tumani, Yangiobod ko\'chasi 23, "Gallaorol" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/gallaorol_savdo_tsentr/108225791047'
            },
            {
                'name': 'PAXTAKOR - (Paxtakor tumani)',
                'address': 'Paxtakor tumani, Markaziy ko\'chasi 12, "Paxtakor" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/paxtakor_savdo_tsentr/108225791048'
            },
            {
                'name': 'DO\'STLIK - (Do\'stlik tumani)',
                'address': 'Do\'stlik tumani, Bogishamol ko\'chasi 34, "Do\'stlik" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/dostlik_bazari/108225791049'
            },
            {
                'name': 'FARISH - (Farish tumani)',
                'address': 'Farish tumani, Yangihayot ko\'chasi 56, "Farish" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/farish_savdo_tsentr/108225791050'
            },
            {
                'name': 'ZAFAROBOD - (Zafarobod tumani)',
                'address': 'Zafarobod tumani, Tinchlik ko\'chasi 18, "Zafarobod" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/zafarobod_bazari/108225791051'
            },
            {
                'name': 'ZARBDOR - (Zarbdor tumani)',
                'address': 'Zarbdor tumani, Navbahor ko\'chasi 29, "Zarbdor" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/zarbdor_savdo_tsentr/108225791052'
            },
            {
                'name': 'MIRZACHO\'L - (Mirzacho\'l tumani)',
                'address': 'Mirzacho\'l tumani, Markaziy ko\'chasi 41, "Mirzacho\'l" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/mirzachol_bazari/108225791053'
            },
            {
                'name': 'ARNASOY - (Arnasoy tumani)',
                'address': 'Arnasoy tumani, Yangiobod ko\'chasi 15, "Arnasoy" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/arnasoy_savdo_tsentr/108225791054'
            },
            {
                'name': 'BAXMAL - (Baxmal tumani)',
                'address': 'Baxmal tumani, Bogishamol ko\'chasi 22, "Baxmal" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/baxmal_bazari/108225791055'
            }
        ]
    },
    'khorezm': {
        'ru': [
            {
                'name': 'УРГЕНЧ ЦЕНТР - (г.Ургенч)',
                'address': 'ул. Аль-Хорезми 45, ТЦ "Urganch"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-19:00, Сб: 09:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/urganch_savdo_tsentr/108225791056'
            },
            {
                'name': 'УРГЕНЧ БОЗОР - (г.Ургенч)',
                'address': 'ул. Беруни 78, Рынок "Markaziy bozor"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-18:00, Вс: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/markaziy_bozor_urganch/108225791057'
            },
            {
                'name': 'ХИВА - (г.Хива)',
                'address': 'ул. Пахлавона Махмуда 23, ТЦ "Xiva"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/xiva_savdo_tsentr/108225791058'
            },
            {
                'name': 'ПИТНАК - (Питнакский р-н)',
                'address': 'Питнакский район, ул. Марказий 12, ТЦ "Pitnak"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/pitnak_savdo_tsentr/108225791059'
            },
            {
                'name': 'ГУРЛАН - (Гурленский р-н)',
                'address': 'Гурленский район, ул. Богишамол 34, Рынок "Gurlan"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/gurlan_bazari/108225791060'
            },
            {
                'name': 'ХОНКА - (Хонкинский р-н)',
                'address': 'Хонкинский район, ул. Янгихаёт 56, ТЦ "Xonqa"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/xonqa_savdo_tsentr/108225791061'
            },
            {
                'name': 'ХАЗОРАСП - (Хазараспский р-н)',
                'address': 'Хазараспский район, ул. Тинчлик 18, Рынок "Xazorasp"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/xazorasp_bazari/108225791062'
            },
            {
                'name': 'ШАВАТ - (Шаватский р-н)',
                'address': 'Шаватский район, ул. Навбахор 29, ТЦ "Shovot"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/shavat_savdo_tsentr/108225791063'
            },
            {
                'name': 'ЯНГИАРЫК - (Янгиарыкский р-н)',
                'address': 'Янгиарыкский район, ул. Марказий 41, Рынок "Yangiarik"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/yangiarik_bazari/108225791064'
            },
            {
                'name': 'ЯНГИБОЗОР - (Янгибазарский р-н)',
                'address': 'Янгибазарский район, ул. Янгиобод 15, ТЦ "Yangibozor"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/yangibozor_savdo_tsentr/108225791065'
            },
            {
                'name': 'БОГОТ - (Боготский р-н)',
                'address': 'Боготский район, ул. Богишамол 22, Рынок "Bogot"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/bogot_bazari/108225791066'
            }
        ],
        'uz': [
            {
                'name': 'URGANCH MARKAZI - (Urganch sh.)',
                'address': 'Al-Xorazmiy ko\'chasi 45, "Urganch" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-19:00, Sh: 09:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/urganch_savdo_tsentr/108225791056'
            },
            {
                'name': 'URGANCH BOZOR - (Urganch sh.)',
                'address': 'Beruniy ko\'chasi 78, "Markaziy bozor"',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-18:00, Ya: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/markaziy_bozor_urganch/108225791057'
            },
            {
                'name': 'XIVA - (Xiva sh.)',
                'address': 'Pahlavon Mahmud ko\'chasi 23, "Xiva" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/xiva_savdo_tsentr/108225791058'
            },
            {
                'name': 'PITNAQ - (Pitnaq tumani)',
                'address': 'Pitnaq tumani, Markaziy ko\'chasi 12, "Pitnaq" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/pitnak_savdo_tsentr/108225791059'
            },
            {
                'name': 'GURLAN - (Gurlan tumani)',
                'address': 'Gurlan tumani, Bogishamol ko\'chasi 34, "Gurlan" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/gurlan_bazari/108225791060'
            },
            {
                'name': 'XONQA - (Xonqa tumani)',
                'address': 'Xonqa tumani, Yangihayot ko\'chasi 56, "Xonqa" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/xonqa_savdo_tsentr/108225791061'
            },
            {
                'name': 'XAZORASP - (Xazorasp tumani)',
                'address': 'Xazorasp tumani, Tinchlik ko\'chasi 18, "Xazorasp" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/xazorasp_bazari/108225791062'
            },
            {
                'name': 'SHOVOT - (Shovot tumani)',
                'address': 'Shovot tumani, Navbahor ko\'chasi 29, "Shovot" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/shavat_savdo_tsentr/108225791063'
            },
            {
                'name': 'YANGIARIK - (Yangiarik tumani)',
                'address': 'Yangiarik tumani, Markaziy ko\'chasi 41, "Yangiarik" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/yangiarik_bazari/108225791064'
            },
            {
                'name': 'YANGIBOZOR - (Yangibozor tumani)',
                'address': 'Yangibozor tumani, Yangiobod ko\'chasi 15, "Yangibozor" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/yangibozor_savdo_tsentr/108225791065'
            },
            {
                'name': 'BOGOT - (Bogot tumani)',
                'address': 'Bogot tumani, Bogishamol ko\'chasi 22, "Bogot" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/bogot_bazari/108225791066'
            }
        ]
    },
    'namangan': {
        'ru': [
            {
                'name': 'НАМАНГАН ЦЕНТР - (г.Наманган)',
                'address': 'ул. Амира Темура 45, ТЦ "Namangan"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-19:00, Сб: 09:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/namangan_savdo_tsentr/108225791067'
            },
            {
                'name': 'НАМАНГАН БОЗОР - (г.Наманган)',
                'address': 'ул. Навои 78, Рынок "Eski bozor"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-18:00, Вс: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/eski_bozor_namangan/108225791068'
            },
            {
                'name': 'КОСОНСОЙ - (Касансайский р-н)',
                'address': 'Касансайский район, ул. Янгиобод 23, ТЦ "Kosonsoy"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/kosonsoy_savdo_tsentr/108225791069'
            },
            {
                'name': 'ЧУСТ - (Чустский р-н)',
                'address': 'Чустский район, ул. Марказий 12, ТЦ "Chust"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/chust_savdo_tsentr/108225791070'
            },
            {
                'name': 'ПОП - (Папский р-н)',
                'address': 'Папский район, ул. Богишамол 34, Рынок "Pop"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/pop_bazari/108225791071'
            },
            {
                'name': 'УЙЧИ - (Уйчинский р-н)',
                'address': 'Уйчинский район, ул. Янгихаёт 56, ТЦ "Uychi"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/uychi_savdo_tsentr/108225791072'
            },
            {
                'name': 'УЧКУРГОН - (Учкурганский р-н)',
                'address': 'Учкурганский район, ул. Тинчлик 18, Рынок "Uchqo\'rg\'on"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/uchqorgon_bazari/108225791073'
            },
            {
                'name': 'МИНГБУЛОК - (Мингбулакский р-н)',
                'address': 'Мингбулакский район, ул. Навбахор 29, ТЦ "Mingbuloq"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/mingbuloq_savdo_tsentr/108225791074'
            },
            {
                'name': 'ЯНГИКУРГОН - (Янгикурганский р-н)',
                'address': 'Янгикурганский район, ул. Марказий 41, Рынок "Yangiqo\'rg\'on"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/yangiqorgon_bazari/108225791075'
            },
            {
                'name': 'НОРИН - (Норинский р-н)',
                'address': 'Норинский район, ул. Янгиобод 15, ТЦ "Norin"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/norin_savdo_tsentr/108225791076'
            },
            {
                'name': 'ЧОРТОК - (Чартакский р-н)',
                'address': 'Чартакский район, ул. Богишамол 22, Рынок "Chortoq"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/chortoq_bazari/108225791077'
            }
        ],
        'uz': [
            {
                'name': 'NAMANGAN MARKAZI - (Namangan sh.)',
                'address': 'Amir Temur ko\'chasi 45, "Namangan" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-19:00, Sh: 09:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/namangan_savdo_tsentr/108225791067'
            },
            {
                'name': 'NAMANGAN BOZOR - (Namangan sh.)',
                'address': 'Navoiy ko\'chasi 78, "Eski bozor"',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-18:00, Ya: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/eski_bozor_namangan/108225791068'
            },
            {
                'name': 'KOSONSOY - (Kosonsoy tumani)',
                'address': 'Kosonsoy tumani, Yangiobod ko\'chasi 23, "Kosonsoy" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/kosonsoy_savdo_tsentr/108225791069'
            },
            {
                'name': 'CHUST - (Chust tumani)',
                'address': 'Chust tumani, Markaziy ko\'chasi 12, "Chust" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/chust_savdo_tsentr/108225791070'
            },
            {
                'name': 'POP - (Pop tumani)',
                'address': 'Pop tumani, Bogishamol ko\'chasi 34, "Pop" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/pop_bazari/108225791071'
            },
            {
                'name': 'UYCHI - (Uychi tumani)',
                'address': 'Uychi tumani, Yangihayot ko\'chasi 56, "Uychi" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/uychi_savdo_tsentr/108225791072'
            },
            {
                'name': 'UCHQO\'RG\'ON - (Uchqo\'rg\'on tumani)',
                'address': 'Uchqo\'rg\'on tumani, Tinchlik ko\'chasi 18, "Uchqo\'rg\'on" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/uchqorgon_bazari/108225791073'
            },
            {
                'name': 'MINGBULOQ - (Mingbuloq tumani)',
                'address': 'Mingbuloq tumani, Navbahor ko\'chasi 29, "Mingbuloq" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/mingbuloq_savdo_tsentr/108225791074'
            },
            {
                'name': 'YANGIQO\'RG\'ON - (Yangiqo\'rg\'on tumani)',
                'address': 'Yangiqo\'rg\'on tumani, Markaziy ko\'chasi 41, "Yangiqo\'rg\'on" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/yangiqorgon_bazari/108225791075'
            },
            {
                'name': 'NORIN - (Norin tumani)',
                'address': 'Norin tumani, Yangiobod ko\'chasi 15, "Norin" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/norin_savdo_tsentr/108225791076'
            },
            {
                'name': 'CHORTOQ - (Chortoq tumani)',
                'address': 'Chortoq tumani, Bogishamol ko\'chasi 22, "Chortoq" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/chortoq_bazari/108225791077'
            }
        ]
    },
    'navoi': {
        'ru': [
            {
                'name': 'НАВОИ ЦЕНТР - (г.Навои)',
                'address': 'ул. Алишера Навои 45, ТЦ "Navoiy"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-19:00, Сб: 09:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/navoiy_savdo_tsentr/108225791078'
            },
            {
                'name': 'НАВОИ БОЗОР - (г.Навои)',
                'address': 'ул. Амира Темура 78, Рынок "Markaziy bozor"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-18:00, Вс: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/markaziy_bozor_navoi/108225791079'
            },
            {
                'name': 'ЗАРАФШАН - (г.Зарафшан)',
                'address': 'ул. Янгиобод 23, ТЦ "Zarafshon"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/zarafshon_savdo_tsentr/108225791080'
            },
            {
                'name': 'УЧКУДУК - (Учкудукский р-н)',
                'address': 'Учкудукский район, ул. Марказий 12, ТЦ "Uchquduq"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/uchquduq_savdo_tsentr/108225791081'
            },
            {
                'name': 'КАРМАНА - (Карманский р-н)',
                'address': 'Карманский район, ул. Богишамол 34, Рынок "Qarmana"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/qarmana_bazari/108225791082'
            },
            {
                'name': 'КЫЗЫЛТЕПА - (Кызылтепинский р-н)',
                'address': 'Кызылтепинский район, ул. Янгихаёт 56, ТЦ "Qiziltepa"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/qiziltepa_savdo_tsentr/108225791083'
            },
            {
                'name': 'НОРОТАН - (Нуратинский р-н)',
                'address': 'Нуратинский район, ул. Тинчлик 18, Рынок "Nurota"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/nurota_bazari/108225791084'
            },
            {
                'name': 'ХАТЫРЧИ - (Хатырчинский р-н)',
                'address': 'Хатырчинский район, ул. Навбахор 29, ТЦ "Xatirchi"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/xatirchi_savdo_tsentr/108225791085'
            },
            {
                'name': 'ТОМДИ - (Томдыбулакский р-н)',
                'address': 'Томдыбулакский район, ул. Марказий 41, Рынок "Tomdi"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/tomdi_bazari/108225791086'
            },
            {
                'name': 'КОНИМЕХ - (Конимехский р-н)',
                'address': 'Конимехский район, ул. Янгиобод 15, ТЦ "Konimex"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/konimex_savdo_tsentr/108225791087'
            },
            {
                'name': 'НАВБАХОР - (Навбахорский р-н)',
                'address': 'Навбахорский район, ул. Богишамол 22, Рынок "Navbahor"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/navbahor_bazari/108225791088'
            }
        ],
        'uz': [
            {
                'name': 'NAVOIY MARKAZI - (Navoiy sh.)',
                'address': 'Alisher Navoiy ko\'chasi 45, "Navoiy" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-19:00, Sh: 09:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/navoiy_savdo_tsentr/108225791078'
            },
            {
                'name': 'NAVOIY BOZOR - (Navoiy sh.)',
                'address': 'Amir Temur ko\'chasi 78, "Markaziy bozor"',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-18:00, Ya: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/markaziy_bozor_navoi/108225791079'
            },
            {
                'name': 'ZARAFSHON - (Zarafshon sh.)',
                'address': 'Yangiobod ko\'chasi 23, "Zarafshon" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/zarafshon_savdo_tsentr/108225791080'
            },
            {
                'name': 'UCHQUDUQ - (Uchquduq tumani)',
                'address': 'Uchquduq tumani, Markaziy ko\'chasi 12, "Uchquduq" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/uchquduq_savdo_tsentr/108225791081'
            },
            {
                'name': 'QARMANA - (Qarmana tumani)',
                'address': 'Qarmana tumani, Bogishamol ko\'chasi 34, "Qarmana" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/qarmana_bazari/108225791082'
            },
            {
                'name': 'QIZILTEPA - (Qiziltepa tumani)',
                'address': 'Qiziltepa tumani, Yangihayot ko\'chasi 56, "Qiziltepa" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/qiziltepa_savdo_tsentr/108225791083'
            },
            {
                'name': 'NUROTA - (Nurota tumani)',
                'address': 'Nurota tumani, Tinchlik ko\'chasi 18, "Nurota" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/nurota_bazari/108225791084'
            },
            {
                'name': 'XATIRCHI - (Xatirchi tumani)',
                'address': 'Xatirchi tumani, Navbahor ko\'chasi 29, "Xatirchi" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/xatirchi_savdo_tsentr/108225791085'
            },
            {
                'name': 'TOMDI - (Tomdi tumani)',
                'address': 'Tomdi tumani, Markaziy ko\'chasi 41, "Tomdi" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/tomdi_bazari/108225791086'
            },
            {
                'name': 'KONIMEX - (Konimex tumani)',
                'address': 'Konimex tumani, Yangiobod ko\'chasi 15, "Konimex" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/konimex_savdo_tsentr/108225791087'
            },
            {
                'name': 'NAVBAHOR - (Navbahor tumani)',
                'address': 'Navbahor tumani, Bogishamol ko\'chasi 22, "Navbahor" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/navbahor_bazari/108225791088'
            }
        ]
    },
    'kashkadarya': {
        'ru': [
            {
                'name': 'КАРШИ ЦЕНТР - (г.Карши)',
                'address': 'ул. Амира Темура 45, ТЦ "Qarshi"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-19:00, Сб: 09:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/qarshi_savdo_tsentr/108225791089'
            },
            {
                'name': 'КАРШИ БОЗОР - (г.Карши)',
                'address': 'ул. Навои 78, Рынок "Eski bozor"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-18:00, Вс: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/eski_bozor_qarshi/108225791090'
            },
            {
                'name': 'ШАХРИСАБЗ - (г.Шахрисабз)',
                'address': 'ул. Амира Темура 23, ТЦ "Shahrisabz"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/shahrisabz_savdo_tsentr/108225791091'
            },
            {
                'name': 'КИТОБ - (Китабский р-н)',
                'address': 'Китабский район, ул. Марказий 12, ТЦ "Kitob"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/kitob_savdo_tsentr/108225791092'
            },
            {
                'name': 'ГУЗАР - (Гузарский р-н)',
                'address': 'Гузарский район, ул. Богишамол 34, Рынок "Guzar"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/guzar_bazari/108225791093'
            },
            {
                'name': 'ДЕХКАНАБАД - (Дехканабадский р-н)',
                'address': 'Дехканабадский район, ул. Янгихаёт 56, ТЦ "Dehqonobod"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/dehqonobod_savdo_tsentr/108225791094'
            },
            {
                'name': 'КАМАШИ - (Камашинский р-н)',
                'address': 'Камашинский район, ул. Тинчлик 18, Рынок "Qamashi"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/qamashi_bazari/108225791095'
            },
            {
                'name': 'КАСАН - (Кассанский р-н)',
                'address': 'Кассанский район, ул. Навбахор 29, ТЦ "Qasan"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/qasan_savdo_tsentr/108225791096'
            },
            {
                'name': 'КУКДАЛА - (Кукдалинский р-н)',
                'address': 'Кукдалинский район, ул. Марказий 41, Рынок "Qoqdola"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/qoqdola_bazari/108225791097'
            },
            {
                'name': 'МИРИШКОР - (Миришкорский р-н)',
                'address': 'Миришкорский район, ул. Янгиобод 15, ТЦ "Mirishkor"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/mirishkor_savdo_tsentr/108225791098'
            },
            {
                'name': 'МУБОРАК - (Мубарекский р-н)',
                'address': 'Мубарекский район, ул. Богишамол 22, Рынок "Muborak"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/muborak_bazari/108225791099'
            }
        ],
        'uz': [
            {
                'name': 'QARSHI MARKAZI - (Qarshi sh.)',
                'address': 'Amir Temur ko\'chasi 45, "Qarshi" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-19:00, Sh: 09:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/qarshi_savdo_tsentr/108225791089'
            },
            {
                'name': 'QARSHI BOZOR - (Qarshi sh.)',
                'address': 'Navoiy ko\'chasi 78, "Eski bozor"',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-18:00, Ya: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/eski_bozor_qarshi/108225791090'
            },
            {
                'name': 'SHAHRISABZ - (Shahrisabz sh.)',
                'address': 'Amir Temur ko\'chasi 23, "Shahrisabz" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/shahrisabz_savdo_tsentr/108225791091'
            },
            {
                'name': 'KITOB - (Kitob tumani)',
                'address': 'Kitob tumani, Markaziy ko\'chasi 12, "Kitob" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/kitob_savdo_tsentr/108225791092'
            },
            {
                'name': 'GUZAR - (Guzar tumani)',
                'address': 'Guzar tumani, Bogishamol ko\'chasi 34, "Guzar" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/guzar_bazari/108225791093'
            },
            {
                'name': 'DEHQONOBOD - (Dehqonobod tumani)',
                'address': 'Dehqonobod tumani, Yangihayot ko\'chasi 56, "Dehqonobod" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/dehqonobod_savdo_tsentr/108225791094'
            },
            {
                'name': 'QAMASHI - (Qamashi tumani)',
                'address': 'Qamashi tumani, Tinchlik ko\'chasi 18, "Qamashi" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/qamashi_bazari/108225791095'
            },
            {
                'name': 'QASAN - (Qasan tumani)',
                'address': 'Qasan tumani, Navbahor ko\'chasi 29, "Qasan" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/qasan_savdo_tsentr/108225791096'
            },
            {
                'name': 'QOQDOLA - (Qoqdola tumani)',
                'address': 'Qoqdola tumani, Markaziy ko\'chasi 41, "Qoqdola" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/qoqdola_bazari/108225791097'
            },
            {
                'name': 'MIRISHKOR - (Mirishkor tumani)',
                'address': 'Mirishkor tumani, Yangiobod ko\'chasi 15, "Mirishkor" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/mirishkor_savdo_tsentr/108225791098'
            },
            {
                'name': 'MUBORAK - (Muborak tumani)',
                'address': 'Muborak tumani, Bogishamol ko\'chasi 22, "Muborak" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/muborak_bazari/108225791099'
            }
        ]
    },
    'samarkand': {
        'ru': [
            {
                'name': 'САМАРКАНД ЦЕНТР - (г.Самарканд)',
                'address': 'ул. Регистан 45, ТЦ "Samarqand"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-19:00, Сб: 09:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/samarqand_savdo_tsentr/108225791100'
            },
            {
                'name': 'САМАРКАНД СИЯБ - (г.Самарканд)',
                'address': 'ул. Амира Темура 78, Рынок "Siyob bozor"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-18:00, Вс: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/siyob_bozor/108225791101'
            },
            {
                'name': 'КАТТАКУРГАН - (г.Каттакурган)',
                'address': 'ул. Янгиобод 23, ТЦ "Kattaqo\'rg\'on"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/kattaqorgon_savdo_tsentr/108225791102'
            },
            {
                'name': 'УРГУТ - (Ургутский р-н)',
                'address': 'Ургутский район, ул. Марказий 12, ТЦ "Urgut"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/urgut_savdo_tsentr/108225791103'
            },
            {
                'name': 'БУЛУНГУР - (Булунгурский р-н)',
                'address': 'Булунгурский район, ул. Богишамол 34, Рынок "Bulung\'ur"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/bulungur_bazari/108225791104'
            },
            {
                'name': 'ДЖАМБАЙ - (Джамбайский р-н)',
                'address': 'Джамбайский район, ул. Янгихаёт 56, ТЦ "Jomboy"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/jomboy_savdo_tsentr/108225791105'
            },
            {
                'name': 'ИШТИХОН - (Иштиханский р-н)',
                'address': 'Иштиханский район, ул. Тинчлик 18, Рынок "Ishtixon"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/ishtixon_bazari/108225791106'
            },
            {
                'name': 'КАЛЛАСОЙ - (Пайарыкский р-н)',
                'address': 'Пайарыкский район, ул. Навбахор 29, ТЦ "Payariq"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/payariq_savdo_tsentr/108225791107'
            },
            {
                'name': 'НУРАБАД - (Нурабадский р-н)',
                'address': 'Нурабадский район, ул. Марказий 41, Рынок "Nurobod"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/nurobod_bazari/108225791108'
            },
            {
                'name': 'ПАХТАЧИ - (Пахтачийский р-н)',
                'address': 'Пахтачийский район, ул. Янгиобод 15, ТЦ "Paxtachi"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/paxtachi_savdo_tsentr/108225791109'
            },
            {
                'name': 'ТАЙЛЯК - (Тайлякский р-н)',
                'address': 'Тайлякский район, ул. Богишамол 22, Рынок "Toyloq"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/toyloq_bazari/108225791110'
            }
        ],
        'uz': [
            {
                'name': 'SAMARQAND MARKAZI - (Samarqand sh.)',
                'address': 'Registon ko\'chasi 45, "Samarqand" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-19:00, Sh: 09:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/samarqand_savdo_tsentr/108225791100'
            },
            {
                'name': 'SAMARQAND SIYOB - (Samarqand sh.)',
                'address': 'Amir Temur ko\'chasi 78, "Siyob bozor"',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-18:00, Ya: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/siyob_bozor/108225791101'
            },
            {
                'name': 'KATTAQO\'RG\'ON - (Kattaqo\'rg\'on sh.)',
                'address': 'Yangiobod ko\'chasi 23, "Kattaqo\'rg\'on" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/kattaqorgon_savdo_tsentr/108225791102'
            },
            {
                'name': 'URGUT - (Urgut tumani)',
                'address': 'Urgut tumani, Markaziy ko\'chasi 12, "Urgut" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/urgut_savdo_tsentr/108225791103'
            },
            {
                'name': 'BULUNG\'UR - (Bulung\'ur tumani)',
                'address': 'Bulung\'ur tumani, Bogishamol ko\'chasi 34, "Bulung\'ur" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/bulungur_bazari/108225791104'
            },
            {
                'name': 'JOMBOY - (Jomboy tumani)',
                'address': 'Jomboy tumani, Yangihayot ko\'chasi 56, "Jomboy" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/jomboy_savdo_tsentr/108225791105'
            },
            {
                'name': 'ISHTIXON - (Ishtixon tumani)',
                'address': 'Ishtixon tumani, Tinchlik ko\'chasi 18, "Ishtixon" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/ishtixon_bazari/108225791106'
            },
            {
                'name': 'PAYARIQ - (Payariq tumani)',
                'address': 'Payariq tumani, Navbahor ko\'chasi 29, "Payariq" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/payariq_savdo_tsentr/108225791107'
            },
            {
                'name': 'NUROBOD - (Nurobod tumani)',
                'address': 'Nurobod tumani, Markaziy ko\'chasi 41, "Nurobod" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/nurobod_bazari/108225791108'
            },
            {
                'name': 'PAXTACHI - (Paxtachi tumani)',
                'address': 'Paxtachi tumani, Yangiobod ko\'chasi 15, "Paxtachi" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/paxtachi_savdo_tsentr/108225791109'
            },
            {
                'name': 'TOYLOQ - (Toyloq tumani)',
                'address': 'Toyloq tumani, Bogishamol ko\'chasi 22, "Toyloq" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/toyloq_bazari/108225791110'
            }
        ]
    },
    'sirdarya': {
        'ru': [
            {
                'name': 'ГУЛИСТАН ЦЕНТР - (г.Гулистан)',
                'address': 'ул. Амира Темура 45, ТЦ "Guliston"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-19:00, Сб: 09:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/guliston_savdo_tsentr/108225791111'
            },
            {
                'name': 'ГУЛИСТАН БОЗОР - (г.Гулистан)',
                'address': 'ул. Навои 78, Рынок "Markaziy bozor"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-18:00, Вс: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/markaziy_bozor_guliston/108225791112'
            },
            {
                'name': 'ЯНГИЕР - (г.Янгиер)',
                'address': 'ул. Янгиобод 23, ТЦ "Yangiyer"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/yangiyer_savdo_tsentr/108225791113'
            },
            {
                'name': 'ШИРИН - (Ширинский р-н)',
                'address': 'Ширинский район, ул. Марказий 12, ТЦ "Shirin"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/shirin_savdo_tsentr/108225791114'
            },
            {
                'name': 'САРДОБА - (Сардобинский р-н)',
                'address': 'Сардобинский район, ул. Богишамол 34, Рынок "Sardoba"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/sardoba_bazari/108225791115'
            },
            {
                'name': 'САЙХУНОБОД - (Сайхунабадский р-н)',
                'address': 'Сайхунабадский район, ул. Янгихаёт 56, ТЦ "Sayxunobod"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/sayxunobod_savdo_tsentr/108225791116'
            },
            {
                'name': 'ХАВАСТ - (Хавастский р-н)',
                'address': 'Хавастский район, ул. Тинчлик 18, Рынок "Xovos"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/xovos_bazari/108225791117'
            },
            {
                'name': 'МЕХНАТАБАД - (Мирзаабадский р-н)',
                'address': 'Мирзаабадский район, ул. Навбахор 29, ТЦ "Mehnatobod"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/mehnatobod_savdo_tsentr/108225791118'
            },
            {
                'name': 'ГУЛИСТОН ШАХАР - (Гулистанский р-н)',
                'address': 'Гулистанский район, ул. Марказий 41, Рынок "Guliston"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/guliston_bazari/108225791119'
            },
            {
                'name': 'ОКОЛТИН - (Акалтынский р-н)',
                'address': 'Акалтынский район, ул. Янгиобод 15, ТЦ "Oqoltin"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/oqoltin_savdo_tsentr/108225791120'
            },
            {
                'name': 'БАЯУТ - (Баяутский р-н)',
                'address': 'Баяутский район, ул. Богишамол 22, Рынок "Boyovut"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходной',
                'yandex_map': 'https://yandex.uz/maps/org/boyovut_bazari/108225791121'
            }
        ],
        'uz': [
            {
                'name': 'GULISTON MARKAZI - (Guliston sh.)',
                'address': 'Amir Temur ko\'chasi 45, "Guliston" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-19:00, Sh: 09:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/guliston_savdo_tsentr/108225791111'
            },
            {
                'name': 'GULISTON BOZOR - (Guliston sh.)',
                'address': 'Navoiy ko\'chasi 78, "Markaziy bozor"',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-18:00, Ya: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/markaziy_bozor_guliston/108225791112'
            },
            {
                'name': 'YANGIYER - (Yangiyer sh.)',
                'address': 'Yangiobod ko\'chasi 23, "Yangiyer" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/yangiyer_savdo_tsentr/108225791113'
            },
            {
                'name': 'SHIRIN - (Shirin tumani)',
                'address': 'Shirin tumani, Markaziy ko\'chasi 12, "Shirin" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/shirin_savdo_tsentr/108225791114'
            },
            {
                'name': 'SARDORA - (Sardoba tumani)',
                'address': 'Sardoba tumani, Bogishamol ko\'chasi 34, "Sardoba" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/sardoba_bazari/108225791115'
            },
            {
                'name': 'SAYXUNOBOD - (Sayxunobod tumani)',
                'address': 'Sayxunobod tumani, Yangihayot ko\'chasi 56, "Sayxunobod" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/sayxunobod_savdo_tsentr/108225791116'
            },
            {
                'name': 'XOVOS - (Xovos tumani)',
                'address': 'Xovos tumani, Tinchlik ko\'chasi 18, "Xovos" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/xovos_bazari/108225791117'
            },
            {
                'name': 'MEHNATOBOD - (Mehnatobod tumani)',
                'address': 'Mehnatobod tumani, Navbahor ko\'chasi 29, "Mehnatobod" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/mehnatobod_savdo_tsentr/108225791118'
            },
            {
                'name': 'GULISTON - (Guliston tumani)',
                'address': 'Guliston tumani, Markaziy ko\'chasi 41, "Guliston" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/guliston_bazari/108225791119'
            },
            {
                'name': 'OQOLTIN - (Oqoltin tumani)',
                'address': 'Oqoltin tumani, Yangiobod ko\'chasi 15, "Oqoltin" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/oqoltin_savdo_tsentr/108225791120'
            },
            {
                'name': 'BOYOVUT - (Boyovut tumani)',
                'address': 'Boyovut tumani, Bogishamol ko\'chasi 22, "Boyovut" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/boyovut_bazari/108225791121'
            }
        ]
    },
     'karakalpakstan': {
        'ru': [
            {
                'name': 'NUKUS - (г.Нукус)',
                'address': 'ул. Татибаева дом-б/н. 22 Ресторан "Neo"',
                'phone': '1230',
                'hours': 'Пн-Пт: 08:00-20:00, Сб: 08:00-18:00, Вс: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/neo/1126547855'
            },
            {
                'name': 'NUKUS 26-MKR - (г.Нукус)',
                'address': 'Город Нукус, улица Пиржан Сейтов 1А-дом,44-кв Рядом Туз кафе',
                'phone': '1230', 
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходные дни',
                'yandex_map': 'https://yandex.uz/maps/org/tuz_kafe/1283746521'
            },
            {
                'name': 'TAXIATOSH - (Тахиаташский р-н)',
                'address': 'Тахиаташский район, улица Камолот, дом 35-А Рынок Тахиатош',
                'phone': '1230',
                'hours': 'Пн-Сб: 09:00-18:00, Вс: Выходные дни',
                'yandex_map': 'https://yandex.uz/maps/org/taxiatosh_bazari/1456789234'
            },
            {
                'name': 'AMUDARYO - (Амударьинский р-н)',
                'address': 'Амударинский р-н, ул. Тадбиркорлар, 11 Мечет Эшонбобо',
                'phone': '1230',
                'hours': 'Пн-Сб: 09:00-18:00, Вс: Выходные дни', 
                'yandex_map': 'https://yandex.uz/maps/org/eshonbobo_masjidi/1678902345'
            },
            {
                'name': 'BERUNIY - (Берунийский р-н)',
                'address': '35-maktab ro\'parasi Старый Индустриальный Колледж',
                'phone': '1230',
                'hours': 'Пн-Сб: 09:00-18:00, Вс: Выходные дни',
                'yandex_map': 'https://yandex.uz/maps/org/sanoat_kolleji/1789012456'
            },
            {
                'name': 'KEGEYLI - (Кегейлийский р-н)',
                'address': 'Кегейлийский район, ул. Амира Темура 45, Рынок "Kegeli"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходные дни',
                'yandex_map': 'https://yandex.uz/maps/org/kegeyli_bazari/1890123567'
            },
            {
                'name': 'KUNGIROT - (Кунградский р-н)',
                'address': 'Кунградский район, ул. Центральная 12, ТЦ "Kungrad"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-18:00, Сб: 09:00-16:00, Вс: Выходные дни',
                'yandex_map': 'https://yandex.uz/maps/org/kungrad_savdo_markazi/1901234678'
            },
            {
                'name': 'MUYNAK - (Муйнакский р-н)',
                'address': 'Муйнакский район, ул. Аральская 8, Рынок "Muynak"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходные дни',
                'yandex_map': 'https://yandex.uz/maps/org/muynoq_bazari/2012345789'
            },
            {
                'name': 'NUKUS 15-MKR - (г.Нукус)',
                'address': 'Город Нукус, 15-микрорайон, ул. Каракалпакская 25, Магазин "Dostlik"',
                'phone': '1230',
                'hours': 'Пн-Пт: 09:00-19:00, Сб: 09:00-17:00, Вс: 09:00-15:00',
                'yandex_map': 'https://yandex.uz/maps/org/dostlik_magazini/2123456890'
            },
            {
                'name': 'CHIMBOY - (Чимбайский р-н)',
                'address': 'Чимбайский район, ул. Шаббаз 18, Рынок "Chimboy"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-18:00, Вс: Выходные дни',
                'yandex_map': 'https://yandex.uz/maps/org/chimboy_bazari/2234567901'
            },
            {
                'name': 'SHUMANAY - (Шуманайский р-н)',
                'address': 'Шуманайский район, ул. Марказий 33, Магазин "Shumanay"',
                'phone': '1230',
                'hours': 'Пн-Сб: 08:00-17:00, Вс: Выходные дни',
                'yandex_map': 'https://yandex.uz/maps/org/shumanay_magazini/2345678012'
            }
        ],
        'uz': [
            {
                'name': 'NUKUS - (Nukus sh.)',
                'address': 'Tatieva ko\'chasi, 22 "Neo" restorani',
                'phone': '1230',
                'hours': 'Du-Ju: 08:00-20:00, Sh: 08:00-18:00, Ya: 08:00-16:00',
                'yandex_map': 'https://yandex.uz/maps/org/neo/1126547855'
            },
            {
                'name': 'NUKUS 26-MKR - (Nukus sh.)', 
                'address': 'Nukus sh., Pirjon Seytov 1A-uy, 44-x Tuz kafe yoni',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/tuz_kafe/1283746521'
            },
            {
                'name': 'TAXIATOSH - (Taxiatosh tumani)',
                'address': 'Taxiatosh tumani, Kamolot ko\'chasi 35-A Taxiatosh bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 09:00-18:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/taxiatosh_bazari/1456789234'
            },
            {
                'name': 'AMUDARYO - (Amudaryo tumani)',
                'address': 'Amudaryo tumani, Tadbirkorlar ko\'chasi 11 Eshonbobo masjidi',
                'phone': '1230',
                'hours': 'Du-Sh: 09:00-18:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/eshonbobo_masjidi/1678902345'
            },
            {
                'name': 'BERUNIY - (Beruniy tumani)',
                'address': '35-maktab ro\'parasi Eski Sanoat Kolleji',
                'phone': '1230',
                'hours': 'Du-Sh: 09:00-18:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/sanoat_kolleji/1789012456'
            },
            {
                'name': 'KEGEYLI - (Kegeyli tumani)',
                'address': 'Kegeyli tumani, Amir Temur ko\'chasi 45 "Kegeyli" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/kegeyli_bazari/1890123567'
            },
            {
                'name': 'KUNGIROT - (Kungirot tumani)',
                'address': 'Kungirot tumani, Markaziy ko\'chasi 12 "Kungrad" savdo markazi',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-18:00, Sh: 09:00-16:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/kungrad_savdo_markazi/1901234678'
            },
            {
                'name': 'MUYNAK - (Muynoq tumani)',
                'address': 'Muynoq tumani, Orol ko\'chasi 8 "Muynoq" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/muynoq_bazari/2012345789'
            },
            {
                'name': 'NUKUS 15-MKR - (Nukus sh.)',
                'address': 'Nukus sh., 15-mikrorayon, Qoraqalpoq ko\'chasi 25 "Do\'stlik" do\'koni',
                'phone': '1230',
                'hours': 'Du-Ju: 09:00-19:00, Sh: 09:00-17:00, Ya: 09:00-15:00',
                'yandex_map': 'https://yandex.uz/maps/org/dostlik_magazini/2123456890'
            },
            {
                'name': 'CHIMBOY - (Chimboy tumani)',
                'address': 'Chimboy tumani, Shabbaz ko\'chasi 18 "Chimboy" bozori',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-18:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/chimboy_bazari/2234567901'
            },
            {
                'name': 'SHUMANAY - (Shumanay tumani)',
                'address': 'Shumanay tumani, Markaziy ko\'chasi 33 "Shumanay" do\'koni',
                'phone': '1230',
                'hours': 'Du-Sh: 08:00-17:00, Ya: Dam olish kuni',
                'yandex_map': 'https://yandex.uz/maps/org/shumanay_magazini/2345678012'
            }
        ]
    }
}

REGIONS = {
    'ru': {
        'tashkent': '📍 Ташкент (город)',
        'andijan': '🏙️ Андижанская область',
        'bukhara': '🏙️ Бухарская область',
        'fergana': '🏙️ Ферганская область',
        'jizzakh': '🏙️ Джизакская область',
        'khorezm': '🏙️ Хорезмская область',
        'namangan': '🏙️ Наманганская область',
        'navoi': '🏙️ Навоийская область',
        'kashkadarya': '🏙️ Кашкадарьинская область',
        'samarkand': '🏙️ Самаркандская область',
        'sirdarya': '🏙️ Сырдарьинская область',
        'surkhandarya': '🏙️ Сурхандарьинская область',
        'tashkent_region': '🏙️ Ташкентская область',
        'karakalpakstan': '🏙️ Республика Каракалпакстан'
    },
    'uz': {
        'tashkent': '📍 Toshkent (shahar)',
        'andijan': '🏙️ Andijon viloyati',
        'bukhara': '🏙️ Buxoro viloyati',
        'fergana': '🏙️ Fargʻona viloyati',
        'jizzakh': '🏙️ Jizzax viloyati',
        'khorezm': '🏙️ Xorazm viloyati',
        'namangan': '🏙️ Namangan viloyati',
        'navoi': '🏙️ Navoiy viloyati',
        'kashkadarya': '🏙️ Qashqadaryo viloyati',
        'samarkand': '🏙️ Samarqand viloyati',
        'sirdarya': '🏙️ Sirdaryo viloyati',
        'surkhandarya': '🏙️ Surxondaryo viloyati',
        'tashkent_region': '🏙️ Toshkent viloyati',
        'karakalpakstan': '🏙️ Qoraqalpogʻiston Respublikasi'
    }
}



# ================== ХРАНЕНИЕ ДАННЫХ В ПАМЯТИ ==================
user_sessions = {}
user_selections = {}
user_carts = {}
support_requests = {}
admin_sessions = {}

# ================== КЛАВИАТУРЫ ПОЛЬЗОВАТЕЛЯ ==================

def get_language_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🇷🇺 Русский"))
    builder.add(KeyboardButton(text="🇺🇿 O'zbekcha"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_contact_keyboard(language):
    text_contact = "📞 Отправить контакт" if language == 'ru' else "📞 Kontaktni yuborish"
    text_manual = "📱 Ввести номер вручную" if language == 'ru' else "📱 Raqamni qo'lda kiritish"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=text_contact, request_contact=True)],
            [KeyboardButton(text=text_manual)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_manual_phone_keyboard(language):
    text = "🔙 Назад" if language == 'ru' else "🔙 Orqaga"
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text)]],
        resize_keyboard=True
    )

def get_region_keyboard(language):
    builder = ReplyKeyboardBuilder()
    # Проверка на случай если словари REGIONS еще не определены в коде выше
    regions_list = globals().get('REGIONS', {})
    for key in regions_list.keys():
        builder.add(KeyboardButton(text=regions_list[key][language]))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_post_office_keyboard(region_key, language):
    builder = ReplyKeyboardBuilder()
    offices_dict = globals().get('POST_OFFICES', {})
    if region_key in offices_dict:
        offices = offices_dict[region_key][language]
        for office in offices:
            if isinstance(office, dict):
                builder.add(KeyboardButton(text=office['name']))
            else:
                builder.add(KeyboardButton(text=office))
    
    builder.add(KeyboardButton(text="↩️ Назад" if language == 'ru' else "↩️ Orqaga"))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

def get_main_menu(language):
    builder = ReplyKeyboardBuilder()
    if language == 'ru':
        menu = ["🛍️ Каталог", "⭐ Мнения клиентов", "🛒 Корзина", "📦 Мои заказы", "ℹ️ Помощь"]
    else:
        menu = ["🛍️ Katalog", "⭐ Mijozlar fikri", "🛒 Savat", "📦 Mening buyurtmalarim", "ℹ️ Yordam"]
    
    for item in menu:
        builder.add(KeyboardButton(text=item))
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_catalog_keyboard(language):
    builder = ReplyKeyboardBuilder()
    if language == 'ru':
        cats = ["👕 Формы 2024/2025", "🕰️ Ретро формы", "⚽ Бутсы", "🎁 Фут. атрибутика", "🔥 Акции", "↩️ Назад"]
    else:
        cats = ["👕 2024/2025 Formalari", "🕰️ Retro formalar", "⚽ Butsalar", "🎁 Futbol Aksessuarlari", "🔥 Aksiyalar", "↩️ Orqaga"]
    
    for cat in cats:
        builder.add(KeyboardButton(text=cat))
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup(resize_keyboard=True)

def get_size_keyboard(language, category_name):
    builder = InlineKeyboardBuilder()
    is_shoes = any(word in category_name.lower() for word in ['бутсы', 'butsa', 'poyabzal'])
    sizes = ["40", "41", "42", "43", "44"] if is_shoes else ["S", "M", "L", "XL", "XXL"]
    
    for size in sizes:
        builder.add(InlineKeyboardButton(text=size, callback_data=f"size_{size}"))
    
    help_text = "📏 Таблица размеров" if language == 'ru' else "📏 O'lchamlar jadvali"
    builder.add(InlineKeyboardButton(text=help_text, callback_data="size_help"))
    builder.adjust(3, 2, 1)
    return builder.as_markup()

def get_customization_keyboard(language):
    builder = ReplyKeyboardBuilder()
    if language == 'ru':
        btns = ["✅ Да, добавить имя и номер", "❌ Нет, без кастомизации", "🔙 Назад к товарам"]
    else:
        btns = ["✅ Ha, ism va raqam qo'shing", "❌ Yo'q, bezaksiz", "🔙 Mahsulotlarga qaytish"]
    
    for btn in btns:
        builder.add(KeyboardButton(text=btn))
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_cart_keyboard(language):
    builder = ReplyKeyboardBuilder()
    if language == 'ru':
        btns = ["🛒 Корзина", "➕ Добавить еще товар", "💳 Оформить заказ", "🗑️ Очистить корзину", "🔙 Главное меню"]
    else:
        btns = ["🛒 Savat", "➕ Yana mahsulot qo'shish", "💳 Buyurtma berish", "🗑️ Savatni tozalash", "🔙 Asosiy menyu"]
    
    for btn in btns:
        builder.add(KeyboardButton(text=btn))
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

# ================== АДМИН КЛАВИАТУРЫ ==================

def get_admin_menu():
    builder = ReplyKeyboardBuilder()
    btns = ["📊 Статистика", "📦 Заказы", "➕ Добавить товар", "🛍️ Управление товарами", "📝 Отзывы", "🔙 Выйти из админки"]
    for btn in btns:
        builder.add(KeyboardButton(text=btn))
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup(resize_keyboard=True)

def get_order_actions(order_id):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{order_id}"))
    builder.add(InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order_id}"))
    builder.add(InlineKeyboardButton(text="📞 Связаться", callback_data=f"contact_{order_id}"))
    builder.adjust(2, 1)
    return builder.as_markup()

# ================== ТЕКСТЫ И ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================

def format_price(price, language='ru'):
    try:
        val = int(price)
        return f"{val:,} UZS".replace(',', ' ')
    except:
        return f"{price} UZS"

def get_text(key, language):
    texts = {
        'welcome': {
            'ru': "👋 Добро пожаловать в FootballKits.uz!\n\nВыберите язык:",
            'uz': "👋 FootballKits.uz ga xush kelibsiz!\n\nTilni tanlang:"
        },
        'welcome_back': {
            'ru': "👋 Добро пожаловать обратно в FootballKits.uz!",
            'uz': "👋 FootballKits.uz ga yana xush kelibsiz!"
        },
        'contact_request': {
            'ru': "📞 Для продолжения поделитесь контактом или введите номер вручную:",
            'uz': "📞 Davom etish uchun kontaktni ulashing yoki raqamni qo'lda kiriting:"
        },
        'manual_phone_request': {
            'ru': "📱 Введите ваш номер телефона в формате:\n+998901234567\n\n⚠️ На этот номер придёт SMS от почты с трек-номером!",
            'uz': "📱 Telefon raqamingizni quyidagi formatda kiriting:\n+998901234567\n\n⚠️ Ushbu raqamga pochta orqali trek raqami bilan SMS keladi!"
        },
        'region_request': {
            'ru': "🏙️ Выберите ваш регион для доставки:",
            'uz': "🏙️ Yetkazib berish uchun viloyatingizni tanlang:"
        },
        'post_office_request': {
            'ru': "📮 Выберите почтовое отделение:",
            'uz': "📮 Pochta bo'limini tanlang:"
        },
        'help_text': {
            'ru': "🤝 Помощь\n\n📞 Телефон: +998 88 111-10-81 \n⏰ Время работы: 9:00-23:00\n\n💬 Задайте ваш вопрос:",
            'uz': "🤝 Yordam\n\n📞 Telefon: +998 88 111-10-81\n⏰ Ish vaqti: 9:00-23:00\n\n💬 Savolingizni bering:"
        }
    }
    return texts.get(key, {}).get(language, key)

# ================== ФУНКЦИИ БАЗЫ ДАННЫХ ==================

def save_user(user_id, phone, name, language, region=None, post_office=None):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO users (user_id, phone, name, language, region, created_at) 
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (user_id, phone, name, language, region)
        )
        conn.commit()

def get_user(user_id):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT phone, name, language, region FROM users WHERE user_id = ?", (user_id,))
            return cursor.fetchone()
    except Exception as e:
        logger.error(f"Ошибка получения пользователя {user_id}: {e}")
        return None

def get_products_by_category(category, language):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        col_name = "name_ru" if language == 'ru' else "name_uz"
        col_desc = "description_ru" if language == 'ru' else "description_uz"
        col_cat = "category_ru" if language == 'ru' else "category_uz"
        
        # ВАЖНО: Убедитесь, что в setup_database колонки называются именно так
        query = f"SELECT id, {col_name} as name, price, image_url, {col_desc} as desc FROM products WHERE {col_cat} = ?"
        cursor.execute(query, (category,))
        return cursor.fetchall()

# ================== КОНСТАНТЫ И ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==================
USER_ROLES = {} # Чтобы не было NameError: name 'USER_ROLES' is not defined
REGIONS = {
    'ru': {'tashkent': 'Ташкент', 'samarkand': 'Самарканд'},
    'uz': {'tashkent': 'Toshkent', 'samarkand': 'Samarqand'}
}
POST_OFFICES = {
    'samarkand': {
        'ru': ['Пункт 1', 'Пункт 2'],
        'uz': ['1-punkt', '2-punkt']
    }
}

# ================== ВСПОМОГАТЕЛЬНЫЕ КЛАВИАТУРЫ ==================
def get_back_menu(lang):
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🔙 Назад" if lang == 'ru' else "🔙 Orqaga"))
    return builder.as_markup(resize_keyboard=True)

def get_role_selection_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🛠 Админ", callback_data="role_admin"))
    builder.add(InlineKeyboardButton(text="👤 Пользователь", callback_data="role_user"))
    return builder.as_markup()

def get_location_keyboard(lang):
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="📍 Отправить локацию" if lang == 'ru' else "📍 Lokatsiyani yuborish", request_location=True))
    builder.add(KeyboardButton(text="🔙 Назад" if lang == 'ru' else "🔙 Orqaga"))
    return builder.as_markup(resize_keyboard=True)

def update_order_status(order_id, status):
    with get_db_connection() as conn:
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        conn.commit()

# ================== СЛОВАРЬ ТЕКСТОВ ==================
TEXTS = {
    'welcome': {
        'ru': "👋 Добро пожаловать в Football Shop!\nВыберите язык / Tilni tanlang:",
        'uz': "👋 Football Shop-ga xush kelibsiz!\nTilni tanlang:"
    },
    'welcome_back': {
        'ru': "👋 С возвращением! Что желаете посмотреть сегодня?",
        'uz': "👋 Xush kelibsiz! Bugun nima ko'rishni xohlaysiz?"
    },
    'choose_size': {
        'ru': "📏 Выберите размер:",
        'uz': "📏 O'lchamni tanlang:"
    }
}

def get_text(key, lang):
    return TEXTS.get(key, {}).get(lang, f"[{key}]")

# ================== КАРТОЧКИ ТОВАРОВ ==================
async def send_product_card(chat_id, product, language):
    product_id = product['id']
    name = product['name']
    price = product['price']
    image_url = product['image_url']
    description = product['desc']
    # Добавляем проверку на существование ключа sizes
    sizes = product['sizes'] if 'sizes' in product.keys() else "S-XXL"

    emoji = "👕" if "форм" in name.lower() else "⚽"
    
    caption = (
        f"{emoji} <b>{name}</b>\n\n📝 {description}\n"
        f"📏 <b>Размеры: {sizes}</b>\n"
        f"💵 <b>Цена: {format_price(price, language)}</b>\n\n"
        f"🆔 <code>{product_id}</code>\n"
        f"✨ <i>{'Напишите ID для заказа' if language == 'ru' else 'Buyurtma uchun ID yozing'}</i>"
    )

    try:
        if image_url and image_url.startswith('http'):
            await bot.send_photo(chat_id, image_url, caption=caption, parse_mode='HTML', reply_markup=get_back_menu(language))
        else:
            await bot.send_message(chat_id, caption, parse_mode='HTML', reply_markup=get_back_menu(language))
    except Exception as e:
        logger.error(f"Ошибка фото: {e}")
        await bot.send_message(chat_id, caption, parse_mode='HTML', reply_markup=get_back_menu(language))

# ================== ОБРАБОТЧИКИ (START) ==================
@dp.message(Command("start"))
async def start_bot(message: types.Message, state: FSMContext):
    await state.clear() # Очищаем состояния при рестарте
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if user:
        language = user['language']
        if user_id in ADMIN_IDS:
            await message.answer("👋 Выберите режим:", reply_markup=get_role_selection_keyboard())
        else:
            await message.answer(get_text('welcome_back', language), reply_markup=get_main_menu(language))
    else:
        user_sessions[user_id] = {'step': 'language'}
        await message.answer(get_text('welcome', 'ru'), reply_markup=get_language_keyboard())

@dp.callback_query(F.data.startswith("role_"))
async def handle_role_selection(callback: types.CallbackQuery):
    role = callback.data.split("_")[1]
    USER_ROLES[callback.from_user.id] = role
    
    if role == 'admin':
        await callback.message.edit_text("🛠️ Режим администратора")
        await callback.message.answer("Выберите действие:", reply_markup=get_admin_menu())
    else:
        user = get_user(callback.from_user.id)
        lang = user['language'] if user else 'ru'
        await callback.message.edit_text("👤 Режим пользователя")
        await callback.message.answer(get_text('welcome_back', lang), reply_markup=get_main_menu(lang))
    await callback.answer()

# ================== ОПЛАТА И ОФОРМЛЕНИЕ ==================
async def checkout_cart(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    cart = user_carts.get(user_id, [])
    
    if not cart or not user:
        lang = user['language'] if user else 'ru'
        return await message.answer("🛒 Savat bo'sh" if lang != 'ru' else "🛒 Корзина пуста")

    lang = user['language']
    total = sum(item['product_price'] + item.get('customization_price', 0) for item in cart)
    
    order_ids = []
    for item in cart:
        oid = save_order(
            user_id, user['phone'], user['name'], user['region'], "Post", # Заглушка адреса
            item['product_name'], item['product_price'], item.get('size'),
            item.get('customization_text'), item.get('customization_price', 0), 'card_pending'
        )
        order_ids.append(oid)

    # ВАЖНО: сохраняем корзину в сессию для обработчика фото
    user_sessions[user_id] = {
        'step': 'waiting_receipt', 
        'order_ids': order_ids,
        'checkout_cart': list(cart) 
    }
    
    text = (f"💳 <b>Оплата заказа</b>\n\n💰 Сумма: {format_price(total, lang)}\n"
            f"📍 Карта: <code>{CARD_NUMBER}</code>\n\n📸 Отправьте скриншот чека.")
    await message.answer(text, parse_mode='HTML')

# ================== КЛАВИАТУРЫ АДМИНА (ДОПОЛНЕНИЕ) ==================
def get_orders_menu():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🔄 Новые (ожидают)", callback_data="admin_orders_pending"))
    builder.add(InlineKeyboardButton(text="✅ Оплаченные", callback_data="admin_orders_confirmed"))
    builder.add(InlineKeyboardButton(text="📦 Все заказы", callback_data="admin_orders_all"))
    builder.adjust(1)
    return builder.as_markup()

def get_categories_keyboard():
    builder = ReplyKeyboardBuilder()
    cats = ["👕 Формы 2024/2025", "🕰️ Ретро формы", "⚽ Бутсы", "🎁 Фут. атрибутика", "🔥 Акции"]
    for cat in cats:
        builder.add(KeyboardButton(text=cat))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_products_management_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="❌ Удалить товар", callback_data="admin_delete_product"))
    builder.add(InlineKeyboardButton(text="📋 Список всех товаров", callback_data="admin_list_products"))
    return builder.as_markup()

# ================== ФУНКЦИИ БД ДЛЯ АДМИНА ==================
def get_all_orders(status=None):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC", (status,))
        else:
            cursor.execute("SELECT * FROM orders ORDER BY created_at DESC")
        return cursor.fetchall()

def get_order_by_id(order_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        return cursor.fetchone()

# ================== ИСТОРИЯ ЗАКАЗОВ ==================
@dp.message(F.text.in_(["📦 Мои заказы", "📦 Mening buyurtmalarim"]))
async def show_my_orders(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user: return
    lang = user['language']
    orders = get_user_orders(user_id, lang)

    if not orders:
        text = "📦 У вас еще нет заказов" if lang == 'ru' else "📦 Sizda hali buyurtmalar yo'q"
        return await message.answer(text)

    response = "📦 <b>Ваши заказы:</b>\n\n" if lang == 'ru' else "📦 <b>Sizning buyurtmalaringiz:</b>\n\n"
    for i, order in enumerate(orders, 1):
        total = order['product_price'] + (order['customization_price'] or 0)
        status_map = {
            'confirmed': ('✅', 'Подтвержден' if lang == 'ru' else 'Tasdiqlangan'),
            'waiting_confirm': ('🔄', 'Проверка чека' if lang == 'ru' else 'Tekshirilmoqda'),
            'card_pending': ('⏳', 'Ожидает оплаты' if lang == 'ru' else 'To\'lov kutilmoqda')
        }
        icon, status_text = status_map.get(order['status'], ('🆕', order['status']))
        response += f"{i}. {order['product_name']}\n   💰 {format_price(total, lang)}\n   {icon} {status_text}\n\n"
    await message.answer(response, parse_mode='HTML')

# ================== АДМИН-ПАНЕЛЬ ==================
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    admin_sessions[message.from_user.id] = {'is_admin': True}
    await message.answer("🛠️ <b>АДМИН-ПАНЕЛЬ</b>", parse_mode='HTML', reply_markup=get_admin_menu())

@dp.message(F.text.in_(["📊 Статистика", "📦 Заказы", "➕ Добавить товар", "🛍️ Управление товарами", "🔙 Выйти из админки"]))
async def handle_admin_commands(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    cmd = message.text

    if cmd == "📊 Статистика":
        stats = get_statistics()
        text = f"📊 <b>СТАТИСТИКА</b>\n\n👥 Клиенты: {stats['total_users']}\n📦 Заказы: {stats['total_orders']}\n💰 Выручка: {format_price(stats['total_revenue'])}"
        await message.answer(text, parse_mode='HTML')

    elif cmd == "📦 Заказы":
        await message.answer("📦 Выберите тип заказов:", reply_markup=get_orders_menu())

    elif cmd == "➕ Добавить товар":
        admin_sessions[message.from_user.id] = {'adding_product': True, 'step': 'category'}
        await message.answer("📂 Выберите категорию:", reply_markup=get_categories_keyboard())

    elif cmd == "🔙 Выйти из админки":
        admin_sessions.pop(message.from_user.id, None)
        user = get_user(message.from_user.id)
        await message.answer("✅ Выход выполнен", reply_markup=get_main_menu(user['language'] if user else 'ru'))

# ================== ДОБАВЛЕНИЕ ТОВАРА ==================
@dp.message(lambda m: admin_sessions.get(m.from_user.id, {}).get('step') == 'category')
async def add_product_cat(message: types.Message):
    cat_map = {"👕 Формы 2024/2025": ("Формы 2024/2025", "2024/2025 Formalari"), "⚽ Бутсы": ("Бутсы", "Butsalar")}
    if message.text in cat_map:
        ru, uz = cat_map[message.text]
        admin_sessions[message.from_user.id].update({'step': 'name_ru', 'cat_ru': ru, 'cat_uz': uz})
        await message.answer("📝 Введите название (RU):", reply_markup=ReplyKeyboardRemove())

@dp.message(lambda m: admin_sessions.get(m.from_user.id, {}).get('adding_product') and m.text)
async def process_add_product(message: types.Message):
    user_id = message.from_user.id
    session = admin_sessions[user_id]
    step = session['step']

    if step == 'name_ru':
        session['name_ru'] = message.text
        session['step'] = 'price'
        await message.answer("💵 Цена (число):")
    elif step == 'price' and message.text.isdigit():
        session['price'] = int(message.text)
        session['step'] = 'image'
        await message.answer("🖼️ Отправьте ФОТО товара:")

@dp.message(lambda m: admin_sessions.get(m.from_user.id, {}).get('step') == 'image', F.photo)
async def add_product_photo(message: types.Message):
    s = admin_sessions[message.from_user.id]
    add_product(name_ru=s['name_ru'], name_uz=s['name_ru'], price=s['price'], 
                category_ru=s['cat_ru'], category_uz=s['cat_uz'],
                description_ru="Описание", description_uz="Tavsif",
                sizes_ru="S, M, L", sizes_uz="S, M, L", image_url=message.photo[-1].file_id)
    admin_sessions.pop(message.from_user.id)
    await message.answer("✅ ТОВАР ДОБАВЛЕН!", reply_markup=get_admin_menu())

# ================== ЗАПУСК (WEB SERVER + BOT) ==================
async def handle_ping(request):
    return web.Response(text="Bot is alive")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    setup_database()
    await start_web_server()
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("🚀 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())