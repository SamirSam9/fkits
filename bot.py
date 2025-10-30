import asyncio
import logging
import sqlite3
import random
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F, router
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from datetime import datetime
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.filters import Command
from dotenv import load_dotenv
import os

async def handle(request):
    return web.Response(text="Bot is running OK")

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()
registered_users = set()
# ================== НАСТРОЙКИ ==================
API_TOKEN = os.getenv('API_TOKEN')
if not API_TOKEN:
    logger.error("❌ API_TOKEN не найден! Проверьте файл .env")
    exit(1)
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}{WEBHOOK_PATH}"
PORT = int(os.getenv("PORT", 10000))
CARD_NUMBER = os.getenv('CARD_NUMBER', '6262 4700 5534 4787')
ADMIN_IDS = [5009858379, 587180281, 1225271746]
# Константы
ORDER_NEW = 'new'
ORDER_WAITING_CONFIRM = 'waiting_confirm'
ORDER_CONFIRMED = 'confirmed'
ORDER_CANCELLED = 'cancelled'
CUSTOMIZATION_PRICE = 50000

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

@router.message(Command("start"))
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    # Логируем подробно
    logger.info(f"🚀 START от пользователя: ID={user_id}, Имя={first_name}")
    
    # Регистрируем пользователя
    registered_users.add(user_id)
    logger.info(f"✅ ПОЛЬЗОВАТЕЛЬ ЗАРЕГИСТРИРОВАН: {user_id}")
    
    await message.answer("✅ Регистрация завершена! Теперь вы можете использовать бота.")

@router.message()
async def all_messages_handler(message: types.Message):
    user_id = message.from_user.id
    text = message.text or "No text"
    
    logger.info(f"📨 Сообщение от {user_id}: '{text}'")
    
    # Проверяем регистрацию
    if user_id not in registered_users:
        logger.warning(f"❌ ОТКАЗ: Пользователь {user_id} не зарегистрирован!")
        await message.answer("❌ Для использования бота необходимо завершить регистрацию. Нажмите /start")
        return
    
    logger.info(f"✅ ДОСТУП РАЗРЕШЕН: Пользователь {user_id} зарегистрирован")
    await message.answer("✅ Вы зарегистрированы! Бот работает.")

# Добавьте команду для сброса (на случай если застряли)
@router.message(Command("reset"))
async def reset_handler(message: types.Message):
    user_id = message.from_user.id
    if user_id in registered_users:
        registered_users.remove(user_id)
        logger.info(f"🔄 СБРОС регистрации для пользователя: {user_id}")
        await message.answer("🔔 Регистрация сброшена. Нажмите /start для новой регистрации.")
    else:
        await message.answer("ℹ️ Вы еще не зарегистрированы. Нажмите /start")
# ================== БАЗА ДАННЫХ ==================
def setup_database():
    try:
        conn = sqlite3.connect('football_shop.db', check_same_thread=False)
        cursor = conn.cursor()
       
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                phone TEXT NOT NULL,
                name TEXT NOT NULL,
                language TEXT DEFAULT 'ru',
                region TEXT,
                post_office TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
       
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_ru TEXT NOT NULL,
                name_uz TEXT NOT NULL,
                price INTEGER NOT NULL,
                category_ru TEXT NOT NULL,
                category_uz TEXT NOT NULL,
                image_url TEXT,
                description_ru TEXT,
                description_uz TEXT,
                sizes_ru TEXT,
                sizes_uz TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
       
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                review_text_ru TEXT NOT NULL,
                review_text_uz TEXT NOT NULL,
                photo_url TEXT,
                rating INTEGER DEFAULT 5,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
       
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_phone TEXT NOT NULL,
                user_name TEXT,
                user_region TEXT,
                user_post_office TEXT,
                product_name TEXT NOT NULL,
                product_price INTEGER NOT NULL,
                product_size TEXT,
                customization_text TEXT,
                customization_price INTEGER DEFAULT 0,
                payment_method TEXT DEFAULT 'card_pending',
                status TEXT DEFAULT 'new',
                receipt_photo_id TEXT,
                confirmed_by INTEGER,
                confirmed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
       
        # Добавляем тестовые отзывы если их нет
        cursor.execute("SELECT COUNT(*) FROM reviews")
        if cursor.fetchone()[0] == 0:
            test_reviews = [
                ('Алишер', 'Отличное качество! Форма сидит идеально.', 'Ajoyib sifat! Forma aynan mos keldi.', '', 5),
                ('Мария', 'Быстрая доставка, всё пришло в целости.', 'Tez yetkazib berish, hammasi butun holda keldi.', '', 5),
                ('Сергей', 'Качество печати на высшем уровне!', 'Bosma sifatı eng yuqori darajada!', '', 4),
            ]
            cursor.executemany(
                "INSERT INTO reviews (customer_name, review_text_ru, review_text_uz, photo_url, rating) VALUES (?, ?, ?, ?, ?)",
                test_reviews
            )
       
        # Добавляем тестовые товары если их нет
        cursor.execute("SELECT COUNT(*) FROM products")
        if cursor.fetchone()[0] == 0:
            test_products = [
                ('Форма Пахтакор 2025', 'Paxtakor Formasi 2025', 180000, 'Формы 2025/2026', '2025/2026 Formalari', '', 'Официальная форма ФК Пахтакор', 'Rasmiy Paxtakor FK formasi', 'S, M, L, XL', 'S, M, L, XL'),
                ('Ретро форма Навбахор', 'Navbahor Retro Formasi', 150000, 'Ретро', 'Retro', '', 'Ретро форма 90-х годов', '90-yillarning retro formasi', 'S, M, L, XL', 'S, M, L, XL'),
                ('Бутсы Nike Mercurial', 'Nike Mercurial Futbolka', 220000, 'Бутсы', 'Futbolkalar', '', 'Профессиональные футбольные бутсы', 'Professional futbolkalar', '40, 41, 42, 43, 44', '40, 41, 42, 43, 44'),
            ]
            cursor.executemany(
                "INSERT INTO products (name_ru, name_uz, price, category_ru, category_uz, image_url, description_ru, description_uz, sizes_ru, sizes_uz) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                test_products
            )
       
        conn.commit()
        conn.close()
        print("✅ База данных готова")
    except Exception as e:
        logger.error(f"❌ Ошибка базы данных: {e}")
        raise

# ================== РЕГИОНЫ И ПОЧТОВЫЕ ОТДЕЛЕНИЯ ==================
POST_OFFICES = {
    'tashkent': {
        'ru': [
            "📍 Ташкент - отправьте вашу геолокацию\n📞 Наш курьер свяжется с вами для уточнения адреса",
        ],
        'uz': [
            "📍 Toshkent - joylashuvingizni yuboring\n📞 Bizning kuryerimiz manzilni aniqlash uchun siz bilan bog'lanadi",
        ]
    },
    'andijan': {
        'ru': [
            "📮 Андижанское ОПС №12\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Andijan, S.Ayni Street, 1\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Andijan, S.Ayni Street, 1",
            "📮 Андижанское ОПС №4\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Andijan, Bobur Street, 10\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Andijan, Bobur Street, 10",
            "📮 Андижанское ОПС №6\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Andijan, Navoi Avenue, 15\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Andijan, Navoi Avenue, 15",
            "📮 Андижанское ОПС №1\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Andijan, Alisher Navoi Street, 5\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Andijan, Alisher Navoi Street, 5",
            "📮 Андижанское ОПС №3\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Andijan, Milliy Bog Street, 20\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Andijan, Milliy Bog Street, 20",
            "📮 Андижанское ОПС №7\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Andijan, Fergana Street, 12\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Andijan, Fergana Street, 12",
            "📮 Андижанское ОПС №2\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Andijan, Mashrab Street, 8\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Andijan, Mashrab Street, 8"
        ],
        'uz': [
            "📮 Andijon OПХ №12\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Andijan, S.Ayni Street, 1\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Andijan, S.Ayni Street, 1",
            "📮 Andijon OПХ №4\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Andijan, Bobur Street, 10\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Andijan, Bobur Street, 10",
            "📮 Andijon OПХ №6\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Andijan, Navoi Avenue, 15\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Andijan, Navoi Avenue, 15",
            "📮 Andijon OПХ №1\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Andijan, Alisher Navoi Street, 5\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Andijan, Alisher Navoi Street, 5",
            "📮 Andijon OПХ №3\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Andijan, Milliy Bog Street, 20\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Andijan, Milliy Bog Street, 20",
            "📮 Andijon OПХ №7\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Andijan, Fergana Street, 12\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Andijan, Fergana Street, 12",
            "📮 Andijon OПХ №2\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Andijan, Mashrab Street, 8\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Andijan, Mashrab Street, 8"
        ]
    },
    'bukhara': {
        'ru': [
            "📮 Бухарское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Bukhara, Street Jalol Ikrami, 19\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Bukhara, Street Jalol Ikrami, 19",
            "📮 Бухарское ОПС №1\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Bukhara, Alisher Navoi Street, 5\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Bukhara, Alisher Navoi Street, 5",
            "📮 Бухарское ОПС №2\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Bukhara, Mustakillik Street, 10\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Bukhara, Mustakillik Street, 10",
            "📮 Бухарское ОПС №3\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Bukhara, B. Nakshbandi Street, 15\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Bukhara, B. Nakshbandi Street, 15",
            "📮 Бухарское ОПС №4\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Bukhara, I. Muminov Street, 20\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Bukhara, I. Muminov Street, 20",
            "📮 Бухарское ОПС №5\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Bukhara, Gizhduvon Street, 8\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Bukhara, Gizhduvon Street, 8"
        ],
        'uz': [
            "📮 Buxoro OПХ\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Bukhara, Street Jalol Ikrami, 19\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Bukhara, Street Jalol Ikrami, 19",
            "📮 Buxoro OПХ №1\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Bukhara, Alisher Navoi Street, 5\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Bukhara, Alisher Navoi Street, 5",
            "📮 Buxoro OПХ №2\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Bukhara, Mustakillik Street, 10\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Bukhara, Mustakillik Street, 10",
            "📮 Buxoro OПХ №3\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Bukhara, B. Nakshbandi Street, 15\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Bukhara, B. Nakshbandi Street, 15",
            "📮 Buxoro OПХ №4\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Bukhara, I. Muminov Street, 20\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Bukhara, I. Muminov Street, 20",
            "📮 Buxoro OПХ №5\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Bukhara, Gizhduvon Street, 8\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Bukhara, Gizhduvon Street, 8"
        ]
    },
    'fergana': {
        'ru': [
            "📮 Ферганское ОПС 'AKJAR'\n🗺️ Яндекс: https://yandex.uz/maps/?text=150502, Ferghana region, Dangara district, Bagish village\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=150502, Ferghana region, Dangara district, Bagish village",
            "📮 Ферганское ОПС 'JILVA'\n🗺️ Яндекс: https://yandex.uz/maps/?text=150506, Ferghana region, Dangara district, Navbahor l.g.c, Olmos Street, 22\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=150506, Ferghana region, Dangara district, Navbahor l.g.c, Olmos Street, 22",
            "📮 Ферганское ОПС 'KAPASAROY'\n🗺️ Яндекс: https://yandex.uz/maps/?text=150507, Ferghana region, Dangara district, Kapasaroy village\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=150507, Ferghana region, Dangara district, Kapasaroy village",
            "📮 Ферганское ОПС 'KIRKLAR'\n🗺️ Яндекс: https://yandex.uz/maps/?text=150510, Ferghana region, Dangara district, Bustonlik village\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=150510, Ferghana region, Dangara district, Bustonlik village",
            "📮 Ферганское ОПС 'LAGAN'\n🗺️ Яндекс: https://yandex.uz/maps/?text=150406, Ferghana region, Ferghana district, unknown village, Ijodkor Street, 2\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=150406, Ferghana region, Ferghana district, unknown village, Ijodkor Street, 2"
        ],
        'uz': [
            "📮 Farg'ona OПХ 'AKJAR'\n🗺️ Yandex: https://yandex.uz/maps/?text=150502, Ferghana region, Dangara district, Bagish village\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=150502, Ferghana region, Dangara district, Bagish village",
            "📮 Farg'ona OПХ 'JILVA'\n🗺️ Yandex: https://yandex.uz/maps/?text=150506, Ferghana region, Dangara district, Navbahor l.g.c, Olmos Street, 22\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=150506, Ferghana region, Dangara district, Navbahor l.g.c, Olmos Street, 22",
            "📮 Farg'ona OПХ 'KAPASAROY'\n🗺️ Yandex: https://yandex.uz/maps/?text=150507, Ferghana region, Dangara district, Kapasaroy village\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=150507, Ferghana region, Dangara district, Kapasaroy village",
            "📮 Farg'ona OПХ 'KIRKLAR'\n🗺️ Yandex: https://yandex.uz/maps/?text=150510, Ferghana region, Dangara district, Bustonlik village\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=150510, Ferghana region, Dangara district, Bustonlik village",
            "📮 Farg'ona OПХ 'LAGAN'\n🗺️ Yandex: https://yandex.uz/maps/?text=150406, Ferghana region, Ferghana district, unknown village, Ijodkor Street, 2\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=150406, Ferghana region, Ferghana district, unknown village, Ijodkor Street, 2"
        ]
    },
    'jizzakh': {
        'ru': [
            "📮 Джизакское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Jizzakh, Sharaf Rashidov Avenue, 64\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Jizzakh, Sharaf Rashidov Avenue, 64",
            "📮 Джизакское ОПС №1\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Jizzakh, Rashidov Street, 10\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Jizzakh, Rashidov Street, 10",
            "📮 Джизакское ОПС №2\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Jizzakh, Navoi Street, 15\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Jizzakh, Navoi Street, 15",
            "📮 Джизакское ОПС №3\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Jizzakh, Alisher Navoi Avenue, 5\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Jizzakh, Alisher Navoi Avenue, 5"
        ],
        'uz': [
            "📮 Jizzax OПХ\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Jizzakh, Sharaf Rashidov Avenue, 64\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Jizzakh, Sharaf Rashidov Avenue, 64",
            "📮 Jizzax OПХ №1\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Jizzakh, Rashidov Street, 10\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Jizzakh, Rashidov Street, 10",
            "📮 Jizzax OПХ №2\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Jizzakh, Navoi Street, 15\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Jizzakh, Navoi Street, 15",
            "📮 Jizzax OПХ №3\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Jizzakh, Alisher Navoi Avenue, 5\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Jizzakh, Alisher Navoi Avenue, 5"
        ]
    },
    'khorezm': {
        'ru': [
            "📮 Хорезмское ОПС 'KHANKA'\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, 220800, Khorezm region, Khanka, Khalklar dustligi Street, 25\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, 220800, Khorezm region, Khanka, Khalklar dustligi Street, 25",
            "📮 Хорезмское ОПС 'KUSHKUPYR'\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, 220600, Khorezm region, Kushkupyr, Sh.Rashidov Street, 47\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, 220600, Khorezm region, Kushkupyr, Sh.Rashidov Street, 47",
            "📮 Хорезмское ОПС №1\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Khorezm, Urgench, Istiklol Street\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Khorezm, Urgench, Istiklol Street",
            "📮 Хорезмское ОПС №2\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Khorezm, Urgench, Al-Khwarizmi Avenue, 56\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Khorezm, Urgench, Al-Khwarizmi Avenue, 56"
        ],
        'uz': [
            "📮 Xorazm OПХ 'KHANKA'\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, 220800, Khorezm region, Khanka, Khalklar dustligi Street, 25\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, 220800, Khorezm region, Khanka, Khalklar dustligi Street, 25",
            "📮 Xorazm OПХ 'KUSHKUPYR'\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, 220600, Khorezm region, Kushkupyr, Sh.Rashidov Street, 47\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, 220600, Khorezm region, Kushkupyr, Sh.Rashidov Street, 47",
            "📮 Xorazm OПХ №1\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Khorezm, Urgench, Istiklol Street\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Khorezm, Urgench, Istiklol Street",
            "📮 Xorazm OПХ №2\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Khorezm, Urgench, Al-Khwarizmi Avenue, 56\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Khorezm, Urgench, Al-Khwarizmi Avenue, 56"
        ]
    },
    'namangan': {
        'ru': [
            "📮 Наманганское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Namangan region, NAMANGAN, AMIR TEMUR street, 54\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Namangan region, NAMANGAN, AMIR TEMUR street, 54",
            "📮 Наманганское ОПС №1\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Namangan, Navoi Street, 10\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Namangan, Navoi Street, 10",
            "📮 Наманганское ОПС №2\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Namangan, Bobur Street, 15\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Namangan, Bobur Street, 15",
            "📮 Наманганское ОПС №3\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Namangan, Dustlik Avenue, 5\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Namangan, Dustlik Avenue, 5",
            "📮 Наманганское ОПС №4\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Namangan, Alisher Navoi Street, 20\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Namangan, Alisher Navoi Street, 20"
        ],
        'uz': [
            "📮 Namangan OПХ\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Namangan region, NAMANGAN, AMIR TEMUR street, 54\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Namangan region, NAMANGAN, AMIR TEMUR street, 54",
            "📮 Namangan OПХ №1\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Namangan, Navoi Street, 10\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Namangan, Navoi Street, 10",
            "📮 Namangan OПХ №2\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Namangan, Bobur Street, 15\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Namangan, Bobur Street, 15",
            "📮 Namangan OПХ №3\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Namangan, Dustlik Avenue, 5\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Namangan, Dustlik Avenue, 5",
            "📮 Namangan OПХ №4\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Namangan, Alisher Navoi Street, 20\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Namangan, Alisher Navoi Street, 20"
        ]
    },
    'navoi': {
        'ru': [
            "📮 Навоийское ОПС Центральное\n🗺️ Яндекс: https://yandex.uz/maps/?text=3A Khalklar Dustligi Avenue, Navoi 210100, Uzbekistan\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=3A Khalklar Dustligi Avenue, Navoi 210100, Uzbekistan",
            "📮 Навоийское ОПС 'UZBEKISTON POCHTASI'\n🗺️ Яндекс: https://yandex.uz/maps/?text=3 Aloqa ko'chasi, Navoiy 210100, Uzbekistan\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=3 Aloqa ko'chasi, Navoiy 210100, Uzbekistan",
            "📮 Навоийское ОПС FedEx\n🗺️ Яндекс: https://yandex.uz/maps/?text=36 Navoiy St, Navoi 210100, Uzbekistan\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=36 Navoiy St, Navoi 210100, Uzbekistan",
            "📮 Навоийское ОПС №1\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Navoi, Memorlar Street, 21\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Navoi, Memorlar Street, 21"
        ],
        'uz': [
            "📮 Navoiy OПХ Markaziy\n🗺️ Yandex: https://yandex.uz/maps/?text=3A Khalklar Dustligi Avenue, Navoi 210100, Uzbekistan\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=3A Khalklar Dustligi Avenue, Navoi 210100, Uzbekistan",
            "📮 Navoiy OПХ 'UZBEKISTON POCHTASI'\n🗺️ Yandex: https://yandex.uz/maps/?text=3 Aloqa ko'chasi, Navoiy 210100, Uzbekistan\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=3 Aloqa ko'chasi, Navoiy 210100, Uzbekistan",
            "📮 Navoiy OПХ FedEx\n🗺️ Yandex: https://yandex.uz/maps/?text=36 Navoiy St, Navoi 210100, Uzbekistan\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=36 Navoiy St, Navoi 210100, Uzbekistan",
            "📮 Navoiy OПХ №1\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Navoi, Memorlar Street, 21\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Navoi, Memorlar Street, 21"
        ]
    },
    'kashkadarya': {
        'ru': [
            "📮 Кашкадарьинское ОПС 'SHAKHRISABZ'\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, 181300, Kashkadarya region, Shakhrisabz, Ipak Yuli Street, 38\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, 181300, Kashkadarya region, Shakhrisabz, Ipak Yuli Street, 38",
            "📮 Кашкадарьинское ОПС 'KITAB'\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, 180700, Kashkadarya region, Kitab, Ipak Yuli Street\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, 180700, Kashkadarya region, Kitab, Ipak Yuli Street",
            "📮 Кашкадарьинское ОПС 'KASAN'\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, 180800, Kashkadarya region, Kasan, Mustakillik Street, 102\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, 180800, Kashkadarya region, Kasan, Mustakillik Street, 102",
            "📮 Кашкадарьинское ОПС №1\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Kashkadarya, Karshi, Islam Karimov Street, 10\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Kashkadarya, Karshi, Islam Karimov Street, 10"
        ],
        'uz': [
            "📮 Qashqadaryo OПХ 'SHAKHRISABZ'\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, 181300, Kashkadarya region, Shakhrisabz, Ipak Yuli Street, 38\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, 181300, Kashkadarya region, Shakhrisabz, Ipak Yuli Street, 38",
            "📮 Qashqadaryo OПХ 'KITAB'\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, 180700, Kashkadarya region, Kitab, Ipak Yuli Street\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, 180700, Kashkadarya region, Kitab, Ipak Yuli Street",
            "📮 Qashqadaryo OПХ 'KASAN'\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, 180800, Kashkadarya region, Kasan, Mustakillik Street, 102\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, 180800, Kashkadarya region, Kasan, Mustakillik Street, 102",
            "📮 Qashqadaryo OПХ №1\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Kashkadarya, Karshi, Islam Karimov Street, 10\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Kashkadarya, Karshi, Islam Karimov Street, 10"
        ]
    },
    'samarkand': {
        'ru': [
            "📮 Самаркандское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Samarkand region, 140100, SAMARKAND, POCHTOVAYA street, 5\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Samarkand region, 140100, SAMARKAND, POCHTOVAYA street, 5",
            "📮 Самаркандское ОПС №1\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Samarkand, Islom Karimov Street, 10\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Samarkand, Islom Karimov Street, 10",
            "📮 Самаркандское ОПС №2\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Samarkand, Dagbit Street, 15\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Samarkand, Dagbit Street, 15",
            "📮 Самаркандское ОПС №3\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Samarkand, Registan Street, 20\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Samarkand, Registan Street, 20",
            "📮 Самаркандское ОПС №4\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Samarkand, Amir Temur Street, 5\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Samarkand, Amir Temur Street, 5",
            "📮 Самаркандское ОПС №5\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Samarkand, University Boulevard, 8\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Samarkand, University Boulevard, 8"
        ],
        'uz': [
            "📮 Samarqand OПХ\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Samarkand region, 140100, SAMARKAND, POCHTOVAYA street, 5\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Samarkand region, 140100, SAMARKAND, POCHTOVAYA street, 5",
            "📮 Samarqand OПХ №1\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Samarkand, Islom Karimov Street, 10\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Samarkand, Islom Karimov Street, 10",
            "📮 Samarqand OПХ №2\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Samarkand, Dagbit Street, 15\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Samarkand, Dagbit Street, 15",
            "📮 Samarqand OПХ №3\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Samarkand, Registan Street, 20\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Samarkand, Registan Street, 20",
            "📮 Samarqand OПХ №4\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Samarkand, Amir Temur Street, 5\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Samarkand, Amir Temur Street, 5",
            "📮 Samarqand OПХ №5\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Samarkand, University Boulevard, 8\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Samarkand, University Boulevard, 8"
        ]
    },
    'sirdarya': {
        'ru': [
            "📮 Сырдарьинское ОПС 'EXPRESS MAIL UNIVERSAL'\n🗺️ Яндекс: https://yandex.uz/maps/?text=120100, Sirdarya region, Gulistan, Street Saykhun, 2A\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=120100, Sirdarya region, Gulistan, Street Saykhun, 2A",
            "📮 Сырдарьинское ОПС №1\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Sirdarya, Gulistan, Uzbekistan Avenue\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Sirdarya, Gulistan, Uzbekistan Avenue",
            "📮 Сырдарьинское ОПС №2\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Sirdarya, Yangiyer, Navoi Street, 10\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Sirdarya, Yangiyer, Navoi Street, 10"
        ],
        'uz': [
            "📮 Sirdaryo OПХ 'EXPRESS MAIL UNIVERSAL'\n🗺️ Yandex: https://yandex.uz/maps/?text=120100, Sirdarya region, Gulistan, Street Saykhun, 2A\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=120100, Sirdarya region, Gulistan, Street Saykhun, 2A",
            "📮 Sirdaryo OПХ №1\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Sirdarya, Gulistan, Uzbekistan Avenue\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Sirdarya, Gulistan, Uzbekistan Avenue",
            "📮 Sirdaryo OПХ №2\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Sirdarya, Yangiyer, Navoi Street, 10\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Sirdarya, Yangiyer, Navoi Street, 10"
        ]
    },
    'surkhandarya': {
        'ru': [
            "📮 Сурхандарьинское ОПС 'SHURCHI'\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, 191500, Surkhandarya region, Shurchy, Mustakillik Street, 41\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, 191500, Surkhandarya region, Shurchy, Mustakillik Street, 41",
            "📮 Сурхандарьинское ОПС 'DENAU'\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, 190500, Surkhandarya region, Denau, Astanakulov Street, 89\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, 190500, Surkhandarya region, Denau, Astanakulov Street, 89",
            "📮 Сурхандарьинское ОПС №1\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Surkhandarya, Termez, Islam Karimov Street, 19\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Surkhandarya, Termez, Islam Karimov Street, 19",
            "📮 Сурхандарьинское ОПС №2\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Surkhandarya, Termez, Barkamol Avlod Street, 7\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Surkhandarya, Termez, Barkamol Avlod Street, 7"
        ],
        'uz': [
            "📮 Surxondaryo OПХ 'SHURCHI'\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, 191500, Surkhandarya region, Shurchy, Mustakillik Street, 41\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, 191500, Surkhandarya region, Shurchy, Mustakillik Street, 41",
            "📮 Surxondaryo OПХ 'DENAU'\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, 190500, Surkhandarya region, Denau, Astanakulov Street, 89\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, 190500, Surkhandarya region, Denau, Astanakulov Street, 89",
            "📮 Surxondaryo OПХ №1\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Surkhandarya, Termez, Islam Karimov Street, 19\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Surkhandarya, Termez, Islam Karimov Street, 19",
            "📮 Surxondaryo OПХ №2\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Surkhandarya, Termez, Barkamol Avlod Street, 7\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Surkhandarya, Termez, Barkamol Avlod Street, 7"
        ]
    },
    'tashkent_region': {
        'ru': [
            "📮 Ташкентское областное ОПС №1\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Tashkent region, Chirchik, ulitsa Ramazan\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Tashkent region, Chirchik, ulitsa Ramazan",
            "📮 Ташкентское областное ОПС №2\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Tashkent region, Angren, Alisher Navoi Street\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Tashkent region, Angren, Alisher Navoi Street",
            "📮 Ташкентское областное ОПС №3\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Tashkent region, Bekabad, Sirdaryo Street\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Tashkent region, Bekabad, Sirdaryo Street",
            "📮 Ташкентское областное ОПС №4\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Tashkent region, Yangiyul, Uzbekistan Street\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Tashkent region, Yangiyul, Uzbekistan Street"
        ],
        'uz': [
            "📮 Toshkent viloyati OПХ №1\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Tashkent region, Chirchik, ulitsa Ramazan\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Tashkent region, Chirchik, ulitsa Ramazan",
            "📮 Toshkent viloyati OПХ №2\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Tashkent region, Angren, Alisher Navoi Street\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Tashkent region, Angren, Alisher Navoi Street",
            "📮 Toshkent viloyati OПХ №3\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Tashkent region, Bekabad, Sirdaryo Street\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Tashkent region, Bekabad, Sirdaryo Street",
            "📮 Toshkent viloyati OПХ №4\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Tashkent region, Yangiyul, Uzbekistan Street\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Tashkent region, Yangiyul, Uzbekistan Street"
        ]
    },
    'karakalpakstan': {
        'ru': [
            "📮 Каракалпакское ОПС 'UZBEKISTAN POCHTASI. JSC KARAKALPAK BRANCH'\n🗺️ Яндекс: https://yandex.uz/maps/?text=230100, Republic of Karakalpakstan, Nukus, Aksholak Street, 6\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=230100, Republic of Karakalpakstan, Nukus, Aksholak Street, 6",
            "📮 Каракалпакское ОПС 'EastLine Express'\n🗺️ Яндекс: https://yandex.uz/maps/?text=S. Kamalov kóshesi, Karakalpakstan\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=S. Kamalov kóshesi, Karakalpakstan",
            "📮 Каракалпакское ОПС 'BTS EXPRESS CARGO SERVIS'\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Karakalpakstan, Nukus, street SHAMURADOV, 2\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Karakalpakstan, Nukus, street SHAMURADOV, 2",
            "📮 Каракалпакское ОПС №1\n🗺️ Яндекс: https://yandex.uz/maps/?text=Uzbekistan, Karakalpakstan, Nukus, Gʻarezsizlik koʻchasi, 50\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Karakalpakstan, Nukus, Gʻarezsizlik koʻchasi, 50"
        ],
        'uz': [
            "📮 Qoraqalpog'iston OПХ 'UZBEKISTAN POCHTASI. JSC KARAKALPAK BRANCH'\n🗺️ Yandex: https://yandex.uz/maps/?text=230100, Republic of Karakalpakstan, Nukus, Aksholak Street, 6\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=230100, Republic of Karakalpakstan, Nukus, Aksholak Street, 6",
            "📮 Qoraqalpog'iston OПХ 'EastLine Express'\n🗺️ Yandex: https://yandex.uz/maps/?text=S. Kamalov kóshesi, Karakalpakstan\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=S. Kamalov kóshesi, Karakalpakstan",
            "📮 Qoraqalpog'iston OПХ 'BTS EXPRESS CARGO SERVIS'\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Karakalpakstan, Nukus, street SHAMURADOV, 2\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Karakalpakstan, Nukus, street SHAMURADOV, 2",
            "📮 Qoraqalpog'iston OПХ №1\n🗺️ Yandex: https://yandex.uz/maps/?text=Uzbekistan, Karakalpakstan, Nukus, Gʻarezsizlik koʻchasi, 50\n🗺️ Google: https://www.google.com/maps/search/?api=1&query=Uzbekistan, Karakalpakstan, Nukus, Gʻarezsizlik koʻchasi, 50"
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
# ================== ХРАНЕНИЕ ДАННЫХ ==================
user_sessions = {}
user_selections = {}
user_carts = {}
support_requests = {}
admin_sessions = {}
# ================== КЛАВИАТУРЫ ==================
def get_language_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🇷🇺 Русский"))
    builder.add(KeyboardButton(text="🇺🇿 O'zbekcha"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_contact_keyboard(language):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Отправить контакт" if language == 'ru' else "📞 Kontaktni yuborish", request_contact=True)],
            [KeyboardButton(text="📱 Ввести номер вручную" if language == 'ru' else "📱 Raqamni qo'lda kiritish")]
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
    regions = REGIONS[language]
    for region_key in regions:
        builder.add(KeyboardButton(text=regions[region_key]))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_post_office_keyboard(region, language):
    builder = ReplyKeyboardBuilder()
    if region in POST_OFFICES:
        offices = POST_OFFICES[region][language]
        for office in offices:
            office_name = office.split('\n')[0]
            builder.add(KeyboardButton(text=office_name))
    builder.add(KeyboardButton(text="↩️ Назад" if language == 'ru' else "↩️ Orqaga"))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

def get_location_keyboard(language):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Отправить геолокацию" if language == 'ru' else "📍 Geolokatsiyani yuborish", request_location=True)],
            [KeyboardButton(text="↩️ Назад" if language == 'ru' else "↩️ Orqaga")]
        ],
        resize_keyboard=True
    )

def get_main_menu(language):
    builder = ReplyKeyboardBuilder()
   
    if language == 'ru':
        builder.add(KeyboardButton(text="🛍️ Каталог"))
        builder.add(KeyboardButton(text="⭐ Мнения клиентов"))
        builder.add(KeyboardButton(text="🛒 Корзина"))
        builder.add(KeyboardButton(text="📦 Мои заказы"))
        builder.add(KeyboardButton(text="ℹ️ Помощь"))
    else:
        builder.add(KeyboardButton(text="🛍️ Katalog"))
        builder.add(KeyboardButton(text="⭐ Mijozlar fikri"))
        builder.add(KeyboardButton(text="🛒 Savat"))
        builder.add(KeyboardButton(text="📦 Mening buyurtmalarim"))
        builder.add(KeyboardButton(text="ℹ️ Yordam"))
   
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_catalog_keyboard(language):
    builder = ReplyKeyboardBuilder()
   
    if language == 'ru':
        builder.add(KeyboardButton(text="👕 Формы"))
        builder.add(KeyboardButton(text="⚽ Бутсы"))
        builder.add(KeyboardButton(text="🔥 Акции"))
        builder.add(KeyboardButton(text="↩️ Назад"))
    else:
        builder.add(KeyboardButton(text="👕 Formalar"))
        builder.add(KeyboardButton(text="⚽ Futbolkalar"))
        builder.add(KeyboardButton(text="🔥 Aksiyalar"))
        builder.add(KeyboardButton(text="↩️ Orqaga"))
   
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)

def get_forms_submenu(language):
    builder = ReplyKeyboardBuilder()
   
    if language == 'ru':
        builder.add(KeyboardButton(text="🕰️ Ретро формы"))
        builder.add(KeyboardButton(text="🔮 Формы 2025/2026"))
        builder.add(KeyboardButton(text="↩️ Назад"))
    else:
        builder.add(KeyboardButton(text="🕰️ Retro formalar"))
        builder.add(KeyboardButton(text="🔮 2025/2026 Formalari"))
        builder.add(KeyboardButton(text="↩️ Orqaga"))
   
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_customization_keyboard(language):
    builder = ReplyKeyboardBuilder()
   
    if language == 'ru':
        builder.add(KeyboardButton(text="✅ Да, добавить имя и номер"))
        builder.add(KeyboardButton(text="❌ Нет, без кастомизации"))
        builder.add(KeyboardButton(text="🔙 Назад к товарам"))
    else:
        builder.add(KeyboardButton(text="✅ Ha, ism va raqam qo'shing"))
        builder.add(KeyboardButton(text="❌ Yo'q, be'zashsiz"))
        builder.add(KeyboardButton(text="🔙 Mahsulotlarga qaytish"))
   
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_size_keyboard(language, product_category):
    builder = InlineKeyboardBuilder()
   
    if 'Формы' in product_category or 'Forma' in product_category:
        sizes = [("S", "size_S"), ("M", "size_M"), ("L", "size_L"), ("XL", "size_XL"), ("XXL", "size_XXL")]
    else:
        sizes = [("40", "size_40"), ("41", "size_41"), ("42", "size_42"), ("43", "size_43"), ("44", "size_44")]
   
    for size, callback_data in sizes:
        builder.add(types.InlineKeyboardButton(text=size, callback_data=callback_data))
   
    help_text = "📏 Помощь" if language == 'ru' else "📏 Yordam"
    builder.add(types.InlineKeyboardButton(text=help_text, callback_data="size_help"))
   
    builder.adjust(3, 3, 1)
    return builder.as_markup()

def get_cart_keyboard(language):
    builder = ReplyKeyboardBuilder()
   
    if language == 'ru':
        builder.add(KeyboardButton(text="🛒 Корзина"))
        builder.add(KeyboardButton(text="➕ Добавить еще товар"))
        builder.add(KeyboardButton(text="💳 Оформить заказ"))
        builder.add(KeyboardButton(text="🗑️ Очистить корзину"))
        builder.add(KeyboardButton(text="🔙 Главное меню"))
    else:
        builder.add(KeyboardButton(text="🛒 Savat"))
        builder.add(KeyboardButton(text="➕ Yana mahsulot qo'shish"))
        builder.add(KeyboardButton(text="💳 Buyurtma berish"))
        builder.add(KeyboardButton(text="🗑️ Savatni tozalash"))
        builder.add(KeyboardButton(text="🔙 Asosiy menyu"))
   
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_payment_menu(language):
    builder = ReplyKeyboardBuilder()
   
    if language == 'ru':
        builder.add(KeyboardButton(text="💳 Перевод на карту"))
        builder.add(KeyboardButton(text="❌ Отмена"))
    else:
        builder.add(KeyboardButton(text="💳 Karta orqali to'lash"))
        builder.add(KeyboardButton(text="❌ Bekor qilish"))
   
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_reviews_menu(language):
    builder = ReplyKeyboardBuilder()
    if language == 'ru':
        builder.add(KeyboardButton(text="⭐ Посмотреть отзывы"))
        builder.add(KeyboardButton(text="✍️ Оставить отзыв"))
        builder.add(KeyboardButton(text="↩️ Назад"))
    else:
        builder.add(KeyboardButton(text="⭐ Sharhlarni ko'rish"))
        builder.add(KeyboardButton(text="✍️ Sharh qoldirish"))
        builder.add(KeyboardButton(text="↩️ Orqaga"))
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_back_menu(language):
    text = "↩️ Назад" if language == 'ru' else "↩️ Orqaga"
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text)]],
        resize_keyboard=True
    )

# ================== АДМИН КЛАВИАТУРЫ ==================
def get_admin_menu():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="📊 Статистика"))
    builder.add(KeyboardButton(text="📦 Заказы"))
    builder.add(KeyboardButton(text="➕ Добавить товар"))
    builder.add(KeyboardButton(text="🛍️ Управление товарами"))
    builder.add(KeyboardButton(text="📝 Отзывы"))
    builder.add(KeyboardButton(text="🔙 Выйти из админки"))
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup(resize_keyboard=True)

def get_orders_menu():
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="🔄 Ожидают подтверждения", callback_data="admin_orders_pending"))
    builder.add(types.InlineKeyboardButton(text="✅ Подтвержденные", callback_data="admin_orders_confirmed"))
    builder.add(types.InlineKeyboardButton(text="📋 Все заказы", callback_data="admin_orders_all"))
    builder.adjust(1)
    return builder.as_markup()

def get_order_actions(order_id):
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{order_id}"))
    builder.add(types.InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order_id}"))
    builder.add(types.InlineKeyboardButton(text="📞 Связаться", callback_data=f"contact_{order_id}"))
    builder.adjust(2, 1)
    return builder.as_markup()

def get_categories_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="👕 Формы 2025/2026"))
    builder.add(KeyboardButton(text="🕰️ Ретро формы"))
    builder.add(KeyboardButton(text="⚽ Бутсы"))
    builder.add(KeyboardButton(text="🔥 Акции"))
    builder.add(KeyboardButton(text="🔙 Назад"))
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_products_management_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="📦 Просмотреть все товары", callback_data="admin_products_view"))
    builder.add(types.InlineKeyboardButton(text="🗑️ Удалить товар", callback_data="admin_products_delete"))
    builder.add(types.InlineKeyboardButton(text="🔙 Назад", callback_data="admin_products_back"))
    builder.adjust(1)
    return builder.as_markup()

def get_products_list_keyboard(products, action):
    builder = InlineKeyboardBuilder()
    for product in products:
        product_id, name_ru, name_uz, price = product
        builder.add(types.InlineKeyboardButton(
            text=f"{product_id}. {name_ru} - {format_price(price, 'ru')}",
            callback_data=f"{action}_{product_id}"
        ))
    builder.add(types.InlineKeyboardButton(text="🔙 Назад", callback_data="admin_products_back"))
    builder.adjust(1)
    return builder.as_markup()

# ================== ТЕКСТЫ ==================
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
        'contact_received': {
            'ru': "✅ Контакт получен!",
            'uz': "✅ Kontakt qabul qilindi!"
        },
        'phone_received': {
            'ru': "✅ Номер получен!",
            'uz': "✅ Raqam qabul qilindi!"
        },
        'post_office_received': {
            'ru': "✅ Отделение выбрано! Теперь вы можете выбирать товары:",
            'uz': "✅ Boʻlim tanlandi! Endi mahsulotlarni tanlashingiz mumkin:"
        },
        'help_text': {
            'ru': "🤝 Помощь\n\n📞 Телефон: +998 88 111-10-81\n📞 Телефон: +998 97 455-55-82\n📍 Адрес: Ташкент, м. Новза\n⏰ Время работы: 9:00-23:00\n\n💬 Задайте ваш вопрос:",
            'uz': "🤝 Yordam\n\n📞 Telefon: +998 88 111-10-81\n📞 Telefon: +998 97 455-55-82\n📍 Manzil: Toshkent, Novza metrosi\n⏰ Ish vaqti: 9:00-23:00\n\n💬 Savolingizni bering:"
        },
        'choose_size': {
            'ru': "📏 Выберите размер:",
            'uz': "📏 Oʻlchamni tanlang:"
        },
        'size_selected': {
            'ru': "✅ Размер выбран: ",
            'uz': "✅ Oʻlcham tanlandi: "
        },
        'order_cancelled': {
            'ru': "❌ Заказ отменен",
            'uz': "❌ Buyurtma bekor qilindi"
        }
    }
    return texts.get(key, {}).get(language, key)

# ================== БАЗА ДАННЫХ ФУНКЦИИ ==================
def get_db_connection():
    return sqlite3.connect('football_shop.db', check_same_thread=False)

def save_user(user_id, phone, name, language, region=None, post_office=None):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO users (user_id, phone, name, language, region, post_office) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, phone, name, language, region, post_office)
        )
        conn.commit()

def get_user(user_id):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT phone, name, language, region, post_office FROM users WHERE user_id = ?", (user_id,))
            return cursor.fetchone()
    except Exception as e:
        logger.error(f"Ошибка получения пользователя {user_id}: {e}")
        return None

def get_products_by_category(category, language):
    with get_db_connection() as conn:
        cursor = conn.cursor()
       
        if language == 'ru':
            cursor.execute("SELECT id, name_ru, price, image_url, description_ru, sizes_ru FROM products WHERE category_ru = ?", (category,))
        else:
            cursor.execute("SELECT id, name_uz, price, image_url, description_uz, sizes_uz FROM products WHERE category_uz = ?", (category,))
           
        return cursor.fetchall()

def get_product_by_id(product_id, language):
    with get_db_connection() as conn:
        cursor = conn.cursor()
       
        if language == 'ru':
            cursor.execute("SELECT name_ru, price, image_url, description_ru, sizes_ru FROM products WHERE id = ?", (product_id,))
        else:
            cursor.execute("SELECT name_uz, price, image_url, description_uz, sizes_uz FROM products WHERE id = ?", (product_id,))
           
        return cursor.fetchone()

def save_order(user_id, phone, name, region, post_office, product_name, product_price, product_size=None, customization_text=None, customization_price=0, payment_method='card_pending'):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO orders (user_id, user_phone, user_name, user_region, user_post_office, product_name, product_price, product_size, customization_text, customization_price, payment_method)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, phone, name, region, post_office, product_name, product_price, product_size, customization_text, customization_price, payment_method)
        )
        order_id = cursor.lastrowid
        conn.commit()
        return order_id

def get_user_orders(user_id, language):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT product_name, product_price, customization_price, status, payment_method, created_at
            FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 5""",
            (user_id,)
        )
        return cursor.fetchall()

def get_all_orders(status=None):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if status:
            cursor.execute(
                """SELECT id, user_id, user_name, user_phone, user_region, user_post_office, product_name,
                product_price, product_size, customization_text, customization_price, status, created_at
                FROM orders WHERE status = ? ORDER BY created_at DESC""",
                (status,)
            )
        else:
            cursor.execute(
                """SELECT id, user_id, user_name, user_phone, user_region, user_post_office, product_name,
                product_price, product_size, customization_text, customization_price, status, created_at
                FROM orders ORDER BY created_at DESC LIMIT 50"""
            )
        return cursor.fetchall()

def update_order_status(order_id, status, admin_id=None):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if admin_id:
            cursor.execute("UPDATE orders SET status = ?, confirmed_by = ?, confirmed_at = CURRENT_TIMESTAMP WHERE id = ?",
                          (status, admin_id, order_id))
        else:
            cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        conn.commit()

def get_order_by_id(order_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, user_id, user_name, user_phone, user_region, user_post_office, product_name,
            product_price, product_size, customization_text, customization_price, status, receipt_photo_id
            FROM orders WHERE id = ?""",
            (order_id,)
        )
        return cursor.fetchone()

def get_statistics():
    with get_db_connection() as conn:
        cursor = conn.cursor()
       
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
       
        cursor.execute("SELECT COUNT(*) FROM orders")
        total_orders = cursor.fetchone()[0]
       
        cursor.execute("SELECT status, COUNT(*) FROM orders GROUP BY status")
        status_stats = cursor.fetchall()
       
        cursor.execute("SELECT SUM(product_price + customization_price) FROM orders WHERE status = 'confirmed'")
        total_revenue = cursor.fetchone()[0] or 0
       
        return {
            'total_users': total_users,
            'total_orders': total_orders,
            'status_stats': dict(status_stats),
            'total_revenue': total_revenue
        }

def add_product(name_ru, name_uz, price, category_ru, category_uz, description_ru, description_uz, sizes_ru, sizes_uz, image_url=None):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO products (name_ru, name_uz, price, category_ru, category_uz, image_url, description_ru, description_uz, sizes_ru, sizes_uz)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name_ru, name_uz, price, category_ru, category_uz, image_url, description_ru, description_uz, sizes_ru, sizes_uz)
        )
        product_id = cursor.lastrowid
        conn.commit()
        return product_id

def get_all_products():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name_ru, name_uz, price FROM products ORDER BY id DESC LIMIT 20")
        return cursor.fetchall()

def delete_product(product_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        return cursor.rowcount > 0

def get_all_reviews():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT customer_name, review_text_ru, review_text_uz, photo_url, rating, created_at FROM reviews ORDER BY created_at DESC LIMIT 10")
        return cursor.fetchall()

def format_price(price, language):
    formatted = f"{price:,} UZS".replace(',', ' ')
    return formatted

# ================== КАРТОЧКИ ТОВАРОВ ==================
async def send_product_card(chat_id, product, language):
    product_id, name, price, image_url, description, sizes = product
   
    if any(word in name.lower() for word in ['форма', 'formasi']):
        emoji = "👕"
    elif any(word in name.lower() for word in ['бутсы', 'futbolka']):
        emoji = "⚽"
    else:
        emoji = "🔥"
   
    if language == 'ru':
        caption = (
            f"{emoji} <b>{name}</b>\n\n"
            f"📝 {description}\n\n"
            f"📏 <b>{sizes}</b>\n\n"
            f"💵 <b>Цена: {format_price(price, language)}</b>\n\n"
            f"🆔 <code>ID: {product_id}</code>\n\n"
            f"✨ <i>Чтобы заказать, напишите номер товара</i>"
        )
    else:
        caption = (
            f"{emoji} <b>{name}</b>\n\n"
            f"📝 {description}\n\n"
            f"📏 <b>{sizes}</b>\n\n"
            f"💵 <b>Narx: {format_price(price, language)}</b>\n\n"
            f"🆔 <code>ID: {product_id}</code>\n\n"
            f"✨ <i>Buyurtma berish uchun mahsulot raqamini yozing</i>"
        )
   
    try:
        if image_url:
            await bot.send_photo(
                chat_id=chat_id,
                photo=image_url,
                caption=caption,
                parse_mode='HTML',
                reply_markup=get_back_menu(language)
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode='HTML',
                reply_markup=get_back_menu(language)
            )
    except Exception as e:
        logging.error(f"Ошибка загрузки фото: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode='HTML',
            reply_markup=get_back_menu(language)
        )

# ================== УВЕДОМЛЕНИЯ АДМИНАМ ==================
async def notify_admins(text, photo_id=None):
    for admin_id in ADMIN_IDS:
        try:
            if photo_id:
                await bot.send_photo(admin_id, photo_id, caption=text)
            else:
                await bot.send_message(admin_id, text)
        except Exception as e:
            logging.error(f"Ошибка отправки админу {admin_id}: {e}")

# ================== КОРЗИНА ==================
async def show_cart(user_id, language, message):
    cart = user_carts.get(user_id, [])
   
    if not cart:
        if language == 'ru':
            await message.answer("🛒 Корзина пуста", reply_markup=get_main_menu(language))
        else:
            await message.answer("🛒 Savat bo'sh", reply_markup=get_main_menu(language))
        return
   
    total_price = 0
    cart_text = "🛒 Ваша корзина:\n\n" if language == 'ru' else "🛒 Sizning savatingiz:\n\n"
   
    for i, item in enumerate(cart, 1):
        item_price = item['product_price'] + (item.get('customization', {}).get('price', 0) if item.get('customization') else 0)
        total_price += item_price
       
        cart_text += f"{i}. {item['product_name']}\n"
        if item.get('size'):
            cart_text += f" 📏 Размер: {item['size']}\n" if language == 'ru' else f" 📏 Oʻlcham: {item['size']}\n"
        if item.get('customization'):
            cart_text += f" ✨ Кастомизация: {item['customization']['text']}\n" if language == 'ru' else f" ✨ Be'zash: {item['customization']['text']}\n"
        cart_text += f" 💵 {format_price(item_price, language)}\n\n"
   
    cart_text += f"💰 Итого: {format_price(total_price, language)}" if language == 'ru' else f"💰 Jami: {format_price(total_price, language)}"
   
    await message.answer(cart_text, reply_markup=get_cart_keyboard(language))

# ================== АДМИН ФУНКЦИИ ==================
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет доступа к админ-панели")
        return
   
    admin_sessions[message.from_user.id] = {'is_admin': True}
    await message.answer("🛠️ Добро пожаловать в админ-панель!", reply_markup=get_admin_menu())

# Обработка админ-меню
@dp.message(F.text.in_(["📊 Статистика", "📦 Заказы", "➕ Добавить товар", "🛍️ Управление товарами", "📝 Отзывы", "🔙 Выйти из админки"]))
async def handle_admin_commands(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
   
    if message.text == "📊 Статистика":
        stats = get_statistics()
        text = (
            f"📊 <b>СТАТИСТИКА МАГАЗИНА</b>\n\n"
            f"👥 Пользователей: <b>{stats['total_users']}</b>\n"
            f"📦 Всего заказов: <b>{stats['total_orders']}</b>\n"
            f"💰 Выручка: <b>{format_price(stats['total_revenue'], 'ru')}</b>\n\n"
            f"<b>Статусы заказов:</b>\n"
            f"✅ Подтвержденные: <b>{stats['status_stats'].get('confirmed', 0)}</b>\n"
            f"🔄 Ожидают: <b>{stats['status_stats'].get('waiting_confirm', 0)}</b>\n"
            f"🆕 Новые: <b>{stats['status_stats'].get('new', 0)}</b>\n"
            f"❌ Отклоненные: <b>{stats['status_stats'].get('cancelled', 0)}</b>"
        )
        await message.answer(text, parse_mode='HTML')
       
    elif message.text == "📦 Заказы":
        await message.answer("📦 <b>УПРАВЛЕНИЕ ЗАКАЗАМИ</b>", parse_mode='HTML', reply_markup=get_orders_menu())
       
    elif message.text == "➕ Добавить товар":
        admin_sessions[message.from_user.id] = {'adding_product': True, 'step': 'category'}
        await message.answer("Выберите категорию товара:", reply_markup=get_categories_keyboard())
       
    elif message.text == "🛍️ Управление товарами":
        await message.answer("🛍️ Управление товарами:", reply_markup=get_products_management_keyboard())
       
    elif message.text == "📝 Отзывы":
        reviews = get_all_reviews()
        if not reviews:
            await message.answer("📝 Пока нет отзывов")
            return
       
        for review in reviews[:5]:
            customer_name, review_text_ru, review_text_uz, photo_url, rating, created_at = review
            stars = "⭐" * rating
            text = f"{stars}\n👤 {customer_name}\n💬 {review_text_ru}\n📅 {created_at[:16]}"
           
            if photo_url:
                await message.answer_photo(photo_url, caption=text)
            else:
                await message.answer(text)
               
    elif message.text == "🔙 Выйти из админки":
        if message.from_user.id in admin_sessions:
            del admin_sessions[message.from_user.id]
        await message.answer("✅ Вы вышли из админ-панели", reply_markup=types.ReplyKeyboardRemove())

# Обработка добавления товара
@dp.message(F.text.in_(["👕 Формы 2025/2026", "🕰️ Ретро формы", "⚽ Бутсы", "🔥 Акции"]))
async def handle_product_category(message: types.Message):
    if message.from_user.id not in ADMIN_IDS or not admin_sessions.get(message.from_user.id, {}).get('adding_product'):
        return
    
    category_map = {
        "👕 Формы 2025/2026": ("Формы 2025/2026", "2025/2026 Formalari"),
        "🕰️ Ретро формы": ("Ретро", "Retro"),
        "⚽ Бутсы": ("Бутсы", "Futbolkalar"),
        "🔥 Акции": ("Акции", "Aksiyalar")
    }
   
    category_ru, category_uz = category_map[message.text]
    admin_sessions[message.from_user.id].update({
        'step': 'name_ru',
        'category_ru': category_ru,
        'category_uz': category_uz
    })
   
    await message.answer("Введите название товара на русском:", reply_markup=types.ReplyKeyboardRemove())

@dp.message(F.text)
async def handle_product_creation(message: types.Message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS or not admin_sessions.get(user_id, {}).get('adding_product'):
        return await handle_main_menu(message)
   
    session = admin_sessions[user_id]
    step = session.get('step')
   
    if step == 'name_ru':
        session['name_ru'] = message.text
        session['step'] = 'name_uz'
        await message.answer("Введите название товара на узбекском:")
       
    elif step == 'name_uz':
        session['name_uz'] = message.text
        session['step'] = 'price'
        await message.answer("Введите цену товара (только цифры):")
       
    elif step == 'price':
        try:
            session['price'] = int(message.text)
            session['step'] = 'description_ru'
            await message.answer("Введите описание товара на русском:")
        except ValueError:
            await message.answer("❌ Неверный формат цены. Введите только цифры:")
           
    elif step == 'description_ru':
        session['description_ru'] = message.text
        session['step'] = 'description_uz'
        await message.answer("Введите описание товара на узбекском:")
       
    elif step == 'description_uz':
        session['description_uz'] = message.text
        session['step'] = 'sizes_ru'
        await message.answer("Введите размеры на русском (через запятую):")
       
    elif step == 'sizes_ru':
        session['sizes_ru'] = message.text
        session['step'] = 'sizes_uz'
        await message.answer("Введите размеры на узбекском (через запятую):")
       
    elif step == 'sizes_uz':
        session['sizes_uz'] = message.text
        session['step'] = 'image'
        await message.answer("Отправьте фото товара (или отправьте 'пропустить' чтобы добавить без фото):")
       
    elif step == 'image':
        if message.text.lower() == 'пропустить':
            product_data = {
                'name_ru': session['name_ru'],
                'name_uz': session['name_uz'],
                'price': session['price'],
                'category_ru': session['category_ru'],
                'category_uz': session['category_uz'],
                'description_ru': session['description_ru'],
                'description_uz': session['description_uz'],
                'sizes_ru': session['sizes_ru'],
                'sizes_uz': session['sizes_uz'],
                'image_url': None
            }
           
            product_id = add_product(**product_data)
            del admin_sessions[user_id]
           
            await message.answer(f"✅ Товар успешно добавлен! ID: {product_id}", reply_markup=get_admin_menu())

@dp.message(F.photo)
async def handle_product_photo(message: types.Message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS or not admin_sessions.get(user_id, {}).get('adding_product'):
        return
   
    session = admin_sessions[user_id]
    if session.get('step') == 'image':
        product_data = {
            'name_ru': session['name_ru'],
            'name_uz': session['name_uz'],
            'price': session['price'],
            'category_ru': session['category_ru'],
            'category_uz': session['category_uz'],
            'description_ru': session['description_ru'],
            'description_uz': session['description_uz'],
            'sizes_ru': session['sizes_ru'],
            'sizes_uz': session['sizes_uz'],
            'image_url': message.photo[-1].file_id
        }
       
        product_id = add_product(**product_data)
        del admin_sessions[user_id]
       
        await message.answer(f"✅ Товар с фото успешно добавлен! ID: {product_id}", reply_markup=get_admin_menu())

# Управление товарами
@dp.callback_query(F.data.startswith("admin_products_"))
async def handle_products_management_callback(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
   
    action = callback.data
   
    if action == "admin_products_view":
        products = get_all_products()
       
        if not products:
            await callback.message.answer("📦 Товаров нет в базе данных")
            return
       
        for product in products:
            product_id, name_ru, name_uz, price = product
            text = f"🆔 {product_id}\n🏷️ {name_ru}\n💵 {format_price(price, 'ru')}"
            await callback.message.answer(text)
       
        await callback.message.answer("📦 Все товары показаны выше")
   
    elif action == "admin_products_delete":
        products = get_all_products()
       
        if not products:
            await callback.message.answer("📦 Товаров нет для удаления")
            return
       
        await callback.message.answer("🗑️ Выберите товар для удаления:",
                                    reply_markup=get_products_list_keyboard(products, "delete_product"))
   
    elif action == "admin_products_back":
        await callback.message.answer("🔙 Возврат в админ-панель", reply_markup=get_admin_menu())
   
    await callback.answer()

@dp.callback_query(F.data.startswith("delete_product_"))
async def handle_delete_product(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
   
    product_id = int(callback.data.replace("delete_product_", ""))
   
    if delete_product(product_id):
        await callback.message.answer(f"✅ Товар #{product_id} успешно удален")
    else:
        await callback.message.answer(f"❌ Ошибка при удалении товара #{product_id}")
   
    await callback.answer()

# Просмотр заказов
@dp.callback_query(F.data.startswith("admin_orders_"))
async def handle_admin_orders(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
   
    status_map = {
        "admin_orders_pending": "waiting_confirm",
        "admin_orders_confirmed": "confirmed",
        "admin_orders_all": None
    }
   
    status = status_map[callback.data]
    orders = get_all_orders(status)
   
    if not orders:
        await callback.message.answer("📦 Заказы не найдены")
        return
   
    for order in orders[:10]:
        order_id, user_id, user_name, user_phone, user_region, user_post_office, product_name, product_price, product_size, customization_text, customization_price, order_status, created_at = order
       
        status_emoji = {
            'new': '🆕',
            'waiting_confirm': '🔄',
            'confirmed': '✅',
            'cancelled': '❌'
        }.get(order_status, '📦')
       
        text = (
            f"{status_emoji} <b>ЗАКАЗ #{order_id}</b>\n\n"
            f"👤 <b>{user_name}</b>\n"
            f"📞 {user_phone}\n"
            f"🏙️ {REGIONS['ru'].get(user_region, user_region)}\n"
            f"📮 {user_post_office}\n\n"
            f"📦 <b>{product_name}</b>\n"
            f"📏 Размер: {product_size or 'Не указан'}\n"
        )
       
        if customization_text:
            text += f"✨ Кастомизация: {customization_text}\n"
           
        total_price = product_price + (customization_price or 0)
        text += f"💵 Сумма: {format_price(total_price, 'ru')}\n"
        text += f"📅 {created_at[:16]}\n"
        text += f"🔰 Статус: {order_status}"
       
        await callback.message.answer(text, parse_mode='HTML', reply_markup=get_order_actions(order_id))
   
    await callback.answer()

# Обработка действий с заказами
@dp.callback_query(F.data.startswith("confirm_") | F.data.startswith("reject_") | F.data.startswith("contact_"))
async def handle_order_actions(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
   
    action, order_id = callback.data.split("_")
    order_id = int(order_id)
    order = get_order_by_id(order_id)
   
    if not order:
        await callback.answer("❌ Заказ не найден")
        return
   
    if action == "confirm":
        update_order_status(order_id, 'confirmed', callback.from_user.id)
        await callback.message.edit_text(f"✅ Заказ #{order_id} подтвержден")
       
        user_id = order[1]
        try:
            await bot.send_message(user_id, f"✅ Ваш заказ #{order_id} подтвержден! Скоро мы его отправим.")
        except:
            pass
           
    elif action == "reject":
        update_order_status(order_id, 'cancelled', callback.from_user.id)
        await callback.message.edit_text(f"❌ Заказ #{order_id} отклонен")
       
        user_id = order[1]
        try:
            await bot.send_message(user_id, f"❌ Ваш заказ #{order_id} отклонен. Для уточнения деталей свяжитесь с нами.")
        except:
            pass
           
    elif action == "contact":
        user_phone = order[3]
        user_name = order[2]
        await callback.message.answer(f"📞 Контакт пользователя:\n👤 {user_name}\n📞 {user_phone}")
   
    await callback.answer()

# ================== ОСНОВНЫЕ КОМАНДЫ ==================
@dp.message(Command("start"))
async def start_bot(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    # Всегда сбрасываем состояние и начинаем с чистого листа
    user_sessions[user_id] = {'step': 'language'}
    
    if user:
        language = user[2]
        if user_id in ADMIN_IDS:
            await admin_panel(message)
        else:
            text = get_text('welcome_back', language)
            await message.answer(text, reply_markup=get_main_menu(language))
    else:
        await message.answer(get_text('welcome', 'ru'), reply_markup=get_language_keyboard())

# ВЫБОР ЯЗЫКА
@dp.message(F.text.in_(["🇷🇺 Русский", "🇺🇿 O'zbekcha"]))
async def handle_language(message: types.Message):
    user_id = message.from_user.id
    language = 'ru' if message.text == "🇷🇺 Русский" else 'uz'
   
    user_sessions[user_id] = {'step': 'contact', 'language': language}
    await message.answer(get_text('contact_request', language), reply_markup=get_contact_keyboard(language))

# РУЧНОЙ ВВОД НОМЕРА
@dp.message(F.text.in_(["📱 Ввести номер вручную", "📱 Raqamni qo'lda kiritish"]))
async def handle_manual_phone_request(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
   
    if session.get('step') != 'contact':
        return
   
    language = session.get('language', 'ru')
    user_sessions[user_id]['step'] = 'manual_phone'
   
    await message.answer(get_text('manual_phone_request', language), reply_markup=get_manual_phone_keyboard(language))

# ОБРАБОТКА РУЧНОГО ВВОДА НОМЕРА
@dp.message(F.text.startswith('+'))
async def handle_manual_phone_input(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
   
    if session.get('step') != 'manual_phone':
        return
   
    language = session.get('language', 'ru')
    phone = message.text.strip()
   
    if not phone.startswith('+998') or len(phone) != 13 or not phone[1:].isdigit():
        if language == 'ru':
            await message.answer("❌ Неверный формат номера. Введите в формате: +998901234567")
        else:
            await message.answer("❌ Noto'g'ri raqam formati. Formatda kiriting: +998901234567")
        return
   
    user_sessions[user_id]['step'] = 'region'
    user_sessions[user_id]['phone'] = phone
    user_sessions[user_id]['name'] = message.from_user.first_name or "Пользователь"
   
    await message.answer(get_text('phone_received', language))
    await message.answer(get_text('region_request', language), reply_markup=get_region_keyboard(language))

# ПОЛУЧЕНИЕ КОНТАКТА
@dp.message(F.contact)
async def handle_contact(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
   
    if session.get('step') != 'contact':
        return
   
    language = session.get('language', 'ru')
    phone = message.contact.phone_number
    name = message.contact.first_name or message.from_user.first_name
   
    save_user(user_id, phone, name, language)
    user_sessions[user_id]['step'] = 'region'
    user_sessions[user_id]['phone'] = phone
    user_sessions[user_id]['name'] = name
   
    await message.answer(get_text('contact_received', language))
    await message.answer(get_text('region_request', language), reply_markup=get_region_keyboard(language))

# ВЫБОР РЕГИОНА И ПОЧТОВОГО ОТДЕЛЕНИЯ
@dp.message(F.text)
async def handle_text_messages(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
   
    # Если пользователь выбирает регион
    if session.get('step') == 'region':
        language = session.get('language', 'ru')
        text = message.text
       
        selected_region = None
        for region_key, region_name in REGIONS[language].items():
            if text == region_name:
                selected_region = region_key
                break
       
        if not selected_region:
            if language == 'ru':
                await message.answer("❌ Пожалуйста, выберите регион из списка")
            else:
                await message.answer("❌ Iltimos, ro'yxatdan viloyatni tanlang")
            return
       
        user_sessions[user_id]['step'] = 'post_office'
        user_sessions[user_id]['region'] = selected_region
       
        if selected_region == 'tashkent':
            # Для Ташкента просим геолокацию
            if language == 'ru':
                await message.answer("📍 Ташкент - отправьте вашу геолокацию\n📞 Наш курьер свяжется с вами для уточнения адреса",
                                   reply_markup=get_location_keyboard(language))
            else:
                await message.answer("📍 Toshkent - joylashuvingizni yuboring\n📞 Bizning kuryerimiz manzilni aniqlash uchun siz bilan bog'lanadi",
                                   reply_markup=get_location_keyboard(language))
        else:
            # Для других регионов показываем почтовые отделения
            if selected_region in POST_OFFICES:
                offices = POST_OFFICES[selected_region][language]
                for office in offices:
                    await message.answer(office)
               
                await message.answer(get_text('post_office_request', language),
                                   reply_markup=get_post_office_keyboard(selected_region, language))
        return
   
    # Если пользователь выбирает почтовое отделение
    elif session.get('step') == 'post_office':
        language = session.get('language', 'ru')
        region = session.get('region')
        text = message.text
       
        if text in ["↩️ Назад", "↩️ Orqaga"]:
            user_sessions[user_id]['step'] = 'region'
            await message.answer(get_text('region_request', language), reply_markup=get_region_keyboard(language))
            return
       
        save_user(user_id, session['phone'], session['name'], language, region, text)
        user_sessions[user_id]['step'] = 'main_menu'
        user_sessions[user_id]['post_office'] = text
       
        await message.answer(get_text('post_office_received', language),
                           reply_markup=get_main_menu(language))
        return
   
    # Обработка главного меню
    await handle_main_menu(message)

# ОБРАБОТКА ГЕОЛОКАЦИИ ДЛЯ ТАШКЕНТА
@dp.message(F.location)
async def handle_location(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
   
    if session.get('step') == 'post_office' and session.get('region') == 'tashkent':
        language = session.get('language', 'ru')
        location_text = f"📍 Геолокация получена: {message.location.latitude}, {message.location.longitude}"
       
        save_user(user_id, session['phone'], session['name'], language, 'tashkent', location_text)
        user_sessions[user_id]['step'] = 'main_menu'
        user_sessions[user_id]['post_office'] = location_text
       
        if language == 'ru':
            await message.answer("✅ Геолокация получена! Курьер свяжется с вами для уточнения адреса.",
                               reply_markup=get_main_menu(language))
        else:
            await message.answer("✅ Geolokatsiya qabul qilindi! Kuryer manzilni aniqlash uchun siz bilan bog'lanadi.",
                               reply_markup=get_main_menu(language))

# ОБРАБОТКА ГЛАВНОГО МЕНЮ
async def handle_main_menu(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    # ЕСЛИ ПОЛЬЗОВАТЕЛЬ НЕ ЗАРЕГИСТРИРОВАН, ПРЕДЛАГАЕМ НАЧАТЬ СНАЧАЛА
    if not user:
        await message.answer("❌ Для использования бота необходимо завершить регистрацию. Нажмите /start")
        return
    
    phone, name, language, region, post_office = user
    text = message.text
   
    # Обработка кнопок главного меню
    if text in ["🛍️ Каталог", "🛍️ Katalog"]:
        await show_catalog(message)
    elif text in ["⭐ Мнения клиентов", "⭐ Mijozlar fikri"]:
        await show_reviews_menu(message)
    elif text in ["🛒 Корзина", "🛒 Savat"]:
        await show_cart_command(message)
    elif text in ["📦 Мои заказы", "📦 Mening buyurtmalarim"]:
        await show_my_orders(message)
    elif text in ["ℹ️ Помощь", "ℹ️ Yordam"]:
        await show_help(message)
    elif text in ["👕 Формы", "👕 Formalar"]:
        await show_forms_menu(message)
    elif text in ["⚽ Бутсы", "⚽ Futbolkalar"]:
        await show_boots(message)
    elif text in ["🔥 Акции", "🔥 Aksiyalar"]:
        await show_sales(message)
    elif text in ["🕰️ Ретро формы", "🕰️ Retro formalar"]:
        await show_retro_forms(message)
    elif text in ["🔮 Формы 2025/2026", "🔮 2025/2026 Formalari"]:
        await show_new_forms(message)
    elif text in ["↩️ Назад", "↩️ Orqaga"]:
        await back_to_main_menu(message)
    elif text in ["❌ Отмена", "❌ Bekor qilish"]:
        await handle_cancel(message)
    elif text in ["⭐ Посмотреть отзывы", "⭐ Sharhlarni ko'rish"]:
        await show_reviews(message)
    elif text in ["✍️ Оставить отзыв", "✍️ Sharh qoldirish"]:
        await start_review(message)
    elif text in ["➕ Добавить еще товар", "➕ Yana mahsulot qo'shish"]:
        await add_more_products(message)
    elif text in ["💳 Оформить заказ", "💳 Buyurtma berish"]:
        await checkout_cart(message)
    elif text in ["🗑️ Очистить корзину", "🗑️ Savatni tozalash"]:
        await clear_cart(message)
    elif text in ["💳 Перевод на карту", "💳 Karta orqali to'lash"]:
        await handle_payment(message)
    elif text in ["✅ Да, добавить имя и номер", "✅ Ha, ism va raqam qo'shing"]:
        await handle_customization_choice(message, True)
    elif text in ["❌ Нет, без кастомизации", "❌ Yo'q, be'zashsiz"]:
        await handle_customization_choice(message, False)
    elif text in ["🔙 Назад к товарам", "🔙 Mahsulotlarga qaytish"]:
        await back_to_catalog(message)
    else:
        # Проверяем, не является ли сообщение номером товара
        if text.isdigit():
            await handle_product_selection(message)
        elif user_id in support_requests and support_requests[user_id].get('waiting_question'):
            question = message.text
            admin_text = f"❓ ВОПРОС ОТ ПОЛЬЗОВАТЕЛЯ\n\n👤 {name} (@{message.from_user.username or 'N/A'})\n📞 {phone}\n💬 {question}"
            await notify_admins(admin_text)
           
            if language == 'ru':
                await message.answer("✅ Ваш вопрос отправлен! Мы ответим вам в ближайшее время.", reply_markup=get_main_menu(language))
            else:
                await message.answer("✅ Savolingiz yuborildi! Tez orada sizga javob beramiz.", reply_markup=get_main_menu(language))
           
            support_requests[user_id]['waiting_question'] = False
        elif user_id in user_sessions and user_sessions[user_id].get('waiting_review'):
            review_text = message.text
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO reviews (customer_name, review_text_ru, review_text_uz, rating)
                    VALUES (?, ?, ?, ?)
                """, (name, review_text, review_text, 5))
                conn.commit()
           
            admin_text = f"📝 НОВЫЙ ОТЗЫВ\n\n👤 {name} (@{message.from_user.username or 'N/A'})\n📞 {phone}\n💬 {review_text}"
            await notify_admins(admin_text)
           
            if language == 'ru':
                await message.answer("✅ Спасибо за ваш отзыв! Мы ценим ваше мнение!", reply_markup=get_main_menu(language))
            else:
                await message.answer("✅ Sharhingiz uchun rahmat! Biz sizning fikringizni qadrlaymiz!", reply_markup=get_main_menu(language))
           
            user_sessions[user_id]['waiting_review'] = False
        elif user_id in user_sessions and user_sessions[user_id].get('waiting_customization_text'):
            await handle_customization_text(message)
        else:
            await message.answer("❌ Не понимаю команду. Используйте кнопки меню." if language == 'ru' else "❌ Buyruqni tushunmayman. Menyu tugmalaridan foydalaning.",
                               reply_markup=get_main_menu(language))

async def show_catalog(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала завершите регистрацию через /start")
        return
   
    phone, name, language, region, post_office = user
   
    if language == 'ru':
        text = "🛍️ Выберите категорию:"
    else:
        text = "🛍️ Toifani tanlang:"
   
    await message.answer(text, reply_markup=get_catalog_keyboard(language))

async def show_forms_menu(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала завершите регистрацию через /start")
        return
   
    phone, name, language, region, post_office = user
    await message.answer("👕 Выберите тип форм:" if language == 'ru' else "👕 Formalar turini tanlang:",
                       reply_markup=get_forms_submenu(language))

async def show_retro_forms(message: types.Message):
    await show_category_products(message, "Ретро", "Retro")

async def show_new_forms(message: types.Message):
    await show_category_products(message, "Формы 2025/2026", "2025/2026 Formalari")

async def show_boots(message: types.Message):
    await show_category_products(message, "Бутсы", "Futbolkalar")

async def show_sales(message: types.Message):
    await show_category_products(message, "Акции", "Aksiyalar")

async def show_category_products(message: types.Message, category_ru: str, category_uz: str):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала завершите регистрацию через /start")
        return
   
    phone, name, language, region, post_office = user
       
    products = get_products_by_category(category_ru, language)
   
    if products:
        category_name = category_ru if language == 'ru' else category_uz
        if language == 'ru':
            await message.answer(f"🏷️ {category_name}:\n\n👇 Вот наши товары:")
        else:
            await message.answer(f"🏷️ {category_name}:\n\n👇 Bizning mahsulotlarimiz:")
           
        for product in products:
            await send_product_card(message.chat.id, product, language)
           
    else:
        if language == 'ru':
            await message.answer(f"😔 В категории '{category_ru}' пока нет товаров", reply_markup=get_main_menu(language))
        else:
            await message.answer(f"😔 '{category_uz}' toifasida hozircha mahsulotlar yo'q", reply_markup=get_main_menu(language))

# ВЫБОР ТОВАРА
@dp.message(F.text.regexp(r'^\d+$'))
async def handle_product_selection(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала завершите регистрацию через /start")
        return
   
    phone, name, language, region, post_office = user
   
    try:
        product_id = int(message.text)
        product = get_product_by_id(product_id, language)
       
        if product:
            product_name, product_price, image_url, description, sizes = product
           
            if any(word in product_name.lower() for word in ['форма', 'formasi']):
                user_selections[message.from_user.id] = {
                    'product_id': product_id,
                    'product_name': product_name,
                    'product_price': product_price,
                    'image_url': image_url,
                    'category': 'Формы'
                }
                await ask_customization(message, language, product_name, product_price)
            else:
                user_selections[message.from_user.id] = {
                    'product_id': product_id,
                    'product_name': product_name,
                    'product_price': product_price,
                    'image_url': image_url,
                    'category': 'Бутсы'
                }
                category = 'Бутсы'
                if language == 'ru':
                    text = f"🛒 Вы выбрали:\n\n📦 {product_name}\n💵 {format_price(product_price, language)}\n\n{get_text('choose_size', language)}"
                else:
                    text = f"🛒 Siz tanladingiz:\n\n📦 {product_name}\n💵 {format_price(product_price, language)}\n\n{get_text('choose_size', language)}"
                await message.answer(text, reply_markup=get_size_keyboard(language, category))
        else:
            if language == 'ru':
                await message.answer("❌ Товар не найден")
            else:
                await message.answer("❌ Mahsulot topilmadi")
           
    except Exception as e:
        logging.error(f"Ошибка выбора товара: {e}")
        if language == 'ru':
            await message.answer("❌ Ошибка выбора товара")
        else:
            await message.answer("❌ Mahsulotni tanlashda xato")

# КАСТОМИЗАЦИЯ
async def ask_customization(message: types.Message, language: str, product_name: str, product_price: int):
    if language == 'ru':
        text = (
            f"🎨 <b>Добавить имя и номер на форму?</b>\n\n"
            f"📦 Товар: {product_name}\n"
            f"💵 Базовая цена: {format_price(product_price, language)}\n\n"
            f"✨ <b>Кастомизация (+{format_price(CUSTOMIZATION_PRICE, language)}):</b>\n"
            f"• Имя на спине\n• Номер на спине\n• Профессиональная печать\n\n"
            f"Выберите вариант:"
        )
    else:
        text = (
            f"🎨 <b>Formaga ism va raqam qo'shilsinmi?</b>\n\n"
            f"📦 Mahsulot: {product_name}\n"
            f"💵 Asosiy narx: {format_price(product_price, language)}\n\n"
            f"✨ <b>Be'zash (+{format_price(CUSTOMIZATION_PRICE, language)}):</b>\n"
            f"• Orqaga ism\n• Orqaga raqam\n• Professional bosma\n\n"
            f"Variantni tanlang:"
        )
   
    await message.answer(text, parse_mode='HTML', reply_markup=get_customization_keyboard(language))

async def handle_customization_choice(message: types.Message, wants_customization: bool):
    user = get_user(message.from_user.id)
    if not user or message.from_user.id not in user_selections:
        return
   
    language = user[2]
    selection = user_selections[message.from_user.id]
   
    if wants_customization:
        selection['customization'] = {'price': CUSTOMIZATION_PRICE}
       
        if language == 'ru':
            text = "✍️ Введите имя и номер для печати (например: «РАХМОН 7» или «ALI 9»):"
        else:
            text = "✍️ Bosma uchun ism va raqamni kiriting (masalan: «RAHMON 7» yoki «ALI 9»):"
       
        await message.answer(text, reply_markup=get_back_menu(language))
        user_sessions[message.from_user.id] = {'waiting_customization_text': True}
    else:
        selection['customization'] = None
        category = selection['category']
       
        if language == 'ru':
            text = f"🛒 Вы выбрали:\n\n📦 {selection['product_name']}\n💵 {format_price(selection['product_price'], language)}\n\n{get_text('choose_size', language)}"
        else:
            text = f"🛒 Siz tanladingiz:\n\n📦 {selection['product_name']}\n💵 {format_price(selection['product_price'], language)}\n\n{get_text('choose_size', language)}"
       
        await message.answer(text, reply_markup=get_size_keyboard(language, category))

async def handle_customization_text(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
   
    if not session.get('waiting_customization_text'):
        return
   
    user = get_user(user_id)
    if not user or user_id not in user_selections:
        return
   
    language = user[2]
    selection = user_selections[user_id]
   
    selection['customization'] = {'price': CUSTOMIZATION_PRICE, 'text': message.text}
    user_sessions[user_id] = {}
   
    category = selection['category']
   
    if language == 'ru':
        text = f"✅ Кастомизация добавлена: «{message.text}»\n\n📦 {selection['product_name']}\n💵 {format_price(selection['product_price'], language)} + {format_price(CUSTOMIZATION_PRICE, language)}\n\n{get_text('choose_size', language)}"
    else:
        text = f"✅ Be'zash qo'shildi: «{message.text}»\n\n📦 {selection['product_name']}\n💵 {format_price(selection['product_price'], language)} + {format_price(CUSTOMIZATION_PRICE, language)}\n\n{get_text('choose_size', language)}"
   
    await message.answer(text, reply_markup=get_size_keyboard(language, category))

# ВЫБОР РАЗМЕРА
@dp.callback_query(F.data.startswith('size_'))
async def handle_size_selection(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user or callback.from_user.id not in user_selections:
        await callback.answer("❌ Сначала выберите товар")
        return
   
    language = user[2]
    size = callback.data.replace('size_', '')
   
    if size == "help":
        if language == 'ru':
            text = (
                "📏 **ТАБЛИЦА РАЗМЕРОВ**\n\n"
                "**👕 ФУТБОЛКИ И ФОРМЫ:**\n"
                "• S (46-48) - Обхват груди: 92-96см\n"
                "• M (48-50) - Обхват груди: 96-100см\n"
                "• L (50-52) - Обхват груди: 100-104см\n"
                "• XL (52-54) - Обхват груди: 104-108см\n"
                "• XXL (54-56) - Обхват груди: 108-112см\n\n"
                "**⚽ БУТСЫ:**\n"
                "• 40 EU - Для стопы ~25.5см\n"
                "• 41 EU - Для стопы ~26.5см\n"
                "• 42 EU - Для стопы ~27см\n"
                "• 43 EU - Для стопы ~27.5см\n"
                "• 44 EU - Для стопы ~28.5см\n\n"
                "ℹ️ Если сомневаетесь в размере, напишите нам!"
            )
        else:
            text = (
                "📏 **OʻLCHAMLAR JADVALI**\n\n"
                "**👕 FUTBOLKALAR VA FORMALAR:**\n"
                "• S (46-48) - Ko'krak qafasi: 92-96sm\n"
                "• M (48-50) - Ko'krak qafasi: 96-100sm\n"
                "• L (50-52) - Ko'krak qafasi: 100-104sm\n"
                "• XL (52-54) - Ko'krak qafasi: 104-108sm\n"
                "• XXL (54-56) - Ko'krak qafasi: 108-112sm\n\n"
                "**⚽ FUTBOLKALAR:**\n"
                "• 40 EU - Oyoq uchun ~25.5sm\n"
                "• 41 EU - Oyoq uchun ~26.5sm\n"
                "• 42 EU - Oyoq uchun ~27sm\n"
                "• 43 EU - Oyoq uchun ~27.5sm\n"
                "• 44 EU - Oyoq uchun ~28.5sm\n\n"
                "ℹ️ Oʻlchamda shubhangiz boʻlsa, bizga yozing!"
            )
       
        await callback.message.answer(text, parse_mode='HTML')
        await callback.answer()
        return
   
    selection = user_selections[callback.from_user.id]
    selection['size'] = size
   
    if callback.from_user.id not in user_carts:
        user_carts[callback.from_user.id] = []
   
    user_carts[callback.from_user.id].append(selection.copy())
   
    if language == 'ru':
        await callback.message.answer(f"✅ Товар добавлен в корзину! Размер: {size}")
    else:
        await callback.message.answer(f"✅ Mahsulot savatga qo'shildi! Oʻlcham: {size}")
   
    await show_cart(callback.from_user.id, language, callback.message)
    await callback.answer()

async def show_cart_command(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала завершите регистрацию через /start")
        return
   
    language = user[2]
    await show_cart(message.from_user.id, language, message)

async def add_more_products(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
   
    language = user[2]
    await message.answer("📋 Выберите категорию:" if language == 'ru' else "📋 Toifani tanlang:",
                       reply_markup=get_catalog_keyboard(language))

async def checkout_cart(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
   
    language = user[2]
    cart = user_carts.get(message.from_user.id, [])
   
    if not cart:
        if language == 'ru':
            await message.answer("❌ Корзина пуста")
        else:
            await message.answer("❌ Savat bo'sh")
        return
   
    total_price = sum(item['product_price'] + (item.get('customization', {}).get('price', 0) if item.get('customization') else 0) for item in cart)
   
    if language == 'ru':
        text = f"🛒 Оформление заказа\n\nТоваров: {len(cart)}\n💰 Сумма: {format_price(total_price, language)}\n\nВыберите способ оплаты:"
    else:
        text = f"🛒 Buyurtma rasmiylashtirish\n\nMahsulotlar: {len(cart)}\n💰 Summa: {format_price(total_price, language)}\n\nTo'lov usulini tanlang:"
   
    user_sessions[message.from_user.id] = {'checkout_cart': cart.copy()}
    await message.answer(text, reply_markup=get_payment_menu(language))

async def clear_cart(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_carts:
        del user_carts[user_id]
   
    user = get_user(user_id)
    if user:
        language = user[2]
        if language == 'ru':
            await message.answer("✅ Корзина очищена", reply_markup=get_main_menu(language))
        else:
            await message.answer("✅ Savat tozalandi", reply_markup=get_main_menu(language))

# ОПЛАТА
async def handle_payment(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
   
    phone, name, language, region, post_office = user
   
    if message.text in ["❌ Отмена", "❌ Bekor qilish"]:
        await handle_cancel(message)
        return
   
    cart = user_sessions[message.from_user.id]['checkout_cart']
    total_price = sum(item['product_price'] + (item.get('customization', {}).get('price', 0) if item.get('customization') else 0) for item in cart)
   
    order_ids = []
   
    for item in cart:
        order_id = save_order(
            message.from_user.id, phone, name, region, post_office,
            item['product_name'], item['product_price'],
            item.get('size'),
            item.get('customization', {}).get('text') if item.get('customization') else None,
            item.get('customization', {}).get('price', 0) if item.get('customization') else 0,
            'card_pending'
        )
        order_ids.append(order_id)
   
    if language == 'ru':
        text = (
            f"💳 Перевод на карту\n\n"
            f"📦 Заказов: {len(cart)}\n"
            f"💵 Сумма: {format_price(total_price, language)}\n\n"
            f"🔄 Переведите на карту:\n"
            f"<code>{CARD_NUMBER}</code>\n\n"
            f"📸 После перевода отправьте скриншот чека\n"
            f"Мы подтвердим заказы в течение 15 минут!"
        )
    else:
        text = (
            f"💳 Karta orqali to'lash\n\n"
            f"📦 Buyurtmalar: {len(cart)}\n"
            f"💵 Summa: {format_price(total_price, language)}\n\n"
            f"🔄 Kartaga o'tkazing:\n"
            f"<code>{CARD_NUMBER}</code>\n\n"
            f"📸 O'tkazishdan so'ng chek skrinshotini yuboring\n"
            f"Buyurtmalarni 15 daqiqa ichida tasdiqlaymiz!"
        )
   
    await message.answer(text, parse_mode='HTML')
    user_sessions[message.from_user.id] = {'waiting_receipt': True, 'order_ids': order_ids}

# ОБРАБОТКА ЧЕКА ОПЛАТЫ
@dp.message(F.photo)
async def handle_receipt_photo(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
   
    if not session.get('waiting_receipt'):
        return
   
    user = get_user(user_id)
    if not user:
        return
   
    language = user[2]
    order_ids = session.get('order_ids', [])
   
    for order_id in order_ids:
        update_order_status(order_id, 'waiting_confirm')
   
    cart = session.get('checkout_cart', [])
    order_details = []
    total_price = 0
   
    for item in cart:
        item_price = item['product_price'] + (item.get('customization', {}).get('price', 0) if item.get('customization') else 0)
        total_price += item_price
       
        item_detail = f"• {item['product_name']}"
        if item.get('size'):
            item_detail += f" | Размер: {item['size']}"
        if item.get('customization'):
            item_detail += f" | Кастомизация: {item['customization']['text']}"
        item_detail += f" | {format_price(item_price, 'ru')}"
        order_details.append(item_detail)
   
    admin_text = (
        f"🆕 НОВЫЙ ЗАКАЗ С ОПЛАТОЙ\n\n"
        f"👤 {user[1]} (@{message.from_user.username or 'N/A'})\n"
        f"📞 {user[0]}\n"
        f"🏙️ {REGIONS['ru'].get(user[3], user[3])}\n"
        f"📮 {user[4]}\n\n"
        f"📦 Товары:\n" + "\n".join(order_details) + f"\n\n"
        f"💰 Итого: {format_price(total_price, 'ru')}\n"
        f"💳 Оплата: картой ✅\n"
        f"🆔 Заказы: {', '.join(map(str, order_ids))}\n"
        f"🕒 {datetime.now().strftime('%H:%M %d.%m.%Y')}"
    )
   
    try:
        await notify_admins(admin_text, message.photo[-1].file_id)
       
        if language == 'ru':
            await message.answer("✅ Чек получен! Мы проверяем оплату и скоро подтвердим ваш заказ.", reply_markup=get_main_menu(language))
        else:
            await message.answer("✅ Chek qabul qilindi! Biz to'lovni tekshiramiz va tez orada buyurtmangizni tasdiqlaymiz.", reply_markup=get_main_menu(language))
       
        if user_id in user_carts:
            del user_carts[user_id]
        user_sessions[user_id] = {}
       
    except Exception as e:
        logging.error(f"Ошибка отправки чека: {e}")
        if language == 'ru':
            await message.answer("❌ Ошибка при отправке чека. Попробуйте еще раз.")
        else:
            await message.answer("❌ Chek yuborishda xatolik. Qayta urinib ko'ring.")

# СИСТЕМА ОТЗЫВОВ
async def show_reviews_menu(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала завершите регистрацию через /start")
        return
   
    phone, name, language, region, post_office = user
    if language == 'ru':
        text = "⭐ Мнение клиентов\n\nЗдесь вы можете посмотреть отзывы наших клиентов или оставить свой отзыв!"
    else:
        text = "⭐ Mijozlar fikri\n\nBu yerda mijozlarimiz sharhlarini ko'rishingiz yoki o'z sharhingizni qoldirishingiz mumkin!"
   
    await message.answer(text, reply_markup=get_reviews_menu(language))

async def show_reviews(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
   
    phone, name, language, region, post_office = user
   
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT customer_name, review_text_ru, review_text_uz, photo_url, rating FROM reviews ORDER BY created_at DESC LIMIT 10")
        reviews = cursor.fetchall()
   
    if not reviews:
        if language == 'ru':
            await message.answer("😔 Пока нет отзывов")
        else:
            await message.answer("😔 Hozircha sharhlar yo'q")
        return
   
    for review in reviews:
        customer_name, review_text_ru, review_text_uz, photo_url, rating = review
       
        stars = "⭐" * rating
        review_text = review_text_ru if language == 'ru' else review_text_uz
       
        caption = f"{stars}\n👤 {customer_name}\n💬 {review_text}"
       
        try:
            if photo_url:
                await bot.send_photo(
                    chat_id=message.chat.id,
                    photo=photo_url,
                    caption=caption
                )
            else:
                await message.answer(caption)
        except Exception as e:
            await message.answer(caption)

async def start_review(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
   
    phone, name, language, region, post_office = user
   
    if language == 'ru':
        text = (
            "✍️ Напишите ваш отзыв о нашем магазине!\n\n"
            "Можете отправить:\n"
            "• Текст отзыва\n• Фото + текст\n"
            "• Просто фото\n\n"
            "Мы добавим ваш отзыв в наш канал!"
        )
    else:
        text = (
            "✍️ Do'konimiz haqida sharhingizni yozing!\n\n"
            "Yuborishingiz mumkin:\n"
            "• Sharh matni\n• Rasm + matn\n"
            "• Shunchaki rasm\n\n"
            "Biz sharhingizni kanalimizga qo'shamiz!"
        )
   
    await message.answer(text)
    user_sessions[message.from_user.id] = {'waiting_review': True}

# МОИ ЗАКАЗЫ
async def show_my_orders(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала завершите регистрацию через /start")
        return
   
    phone, name, language, region, post_office = user
    orders = get_user_orders(message.from_user.id, language)
   
    if orders:
        if language == 'ru':
            response = "📦 Ваши заказы:\n\n"
        else:
            response = "📦 Sizning buyurtmalaringiz:\n\n"
           
        for i, (product_name, product_price, customization_price, status, payment, created_at) in enumerate(orders, 1):
            total_price = product_price + (customization_price or 0)
            status_icon = "✅" if status == "confirmed" else "🔄" if status == "waiting_confirm" else "🆕"
           
            status_text = "Подтвержден" if status == "confirmed" else "Ожидает подтверждения" if status == "waiting_confirm" else "Новый"
            if language == 'uz':
                status_text = "Tasdiqlangan" if status == "confirmed" else "Tasdiqlanish kutilmoqda" if status == "waiting_confirm" else "Yangi"
           
            response += f"{i}. {product_name}\n"
            response += f"💵 {format_price(total_price, language)}\n"
            response += f"{status_icon} {status_text}\n"
            response += f"📅 {created_at[:16]}\n\n"
    else:
        if language == 'ru':
            response = "📦 У вас еще нет заказов"
        else:
            response = "📦 Sizda hali buyurtmalar yo'q"
   
    await message.answer(response, reply_markup=get_main_menu(language))

# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
async def show_help(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала завершите регистрацию через /start")
        return
   
    phone, name, language, region, post_office = user
    await message.answer(get_text('help_text', language), parse_mode='HTML')
    support_requests[message.from_user.id] = {'waiting_question': True}

async def back_to_main_menu(message: types.Message):
    user = get_user(message.from_user.id)
    if user:
        language = user[2]
        await message.answer("📋 Главное меню:" if language == 'ru' else "📋 Asosiy menyu:",
                           reply_markup=get_main_menu(language))

async def back_to_catalog(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
   
    language = user[2]
    await show_catalog(message)

async def handle_cancel(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if user:
        language = user[2]
        if user_id in user_selections:
            del user_selections[user_id]
        if user_id in user_sessions:
            user_sessions[user_id] = {}
       
        await message.answer(get_text('order_cancelled', language),
                           reply_markup=get_main_menu(language))

# ================== ЗАПУСК ==================
async def main():
    try:
        setup_database()
        print("🚀 Бот запущен!")
        print(f"✅ Токен: {'*' * 10}{API_TOKEN[-5:]}")
        print(f"👑 Админы: {ADMIN_IDS}")
        print(f"💳 Карта: {CARD_NUMBER}")
        print("⭐ Система отзывов готова!")
        print("🛍️ Каталог товаров готов!")
        print("📱 Регистрация через контакт или ручной ввод номера")
        print("📍 Система доставки с почтовыми отделениями активирована!")
        print("🛠️ Админ-панель активирована!")
       
        # СОЗДАЕМ aiohttp ПРИЛОЖЕНИЕ ДЛЯ WEBHOOK
        app = web.Application()
        app.router.add_get("/", handle)

        # СОЗДАЕМ И РЕГИСТРИРУЕМ WEBHOOK ОБРАБОТЧИК
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
        )
        webhook_requests_handler.register(app, path=WEBHOOK_PATH)

        # НАСТРАИВАЕМ ПРИЛОЖЕНИЕ
        setup_application(app, dp, bot=bot)

        # ЗАПУСКАЕМ СЕРВЕР
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()

        print(f"✅ Webhook сервер запущен на порту {PORT}")
        print(f"🔗 Webhook URL: {WEBHOOK_URL}")

        # УСТАНАВЛИВАЕМ WEBHOOK В TELEGRAM
        await bot.set_webhook(WEBHOOK_URL)
        print("✅ Webhook установлен в Telegram")

        # БЕСКОНЕЧНЫЙ ЦИКЛ ДЛЯ ПОДДЕРЖАНИЯ РАБОТЫ СЕРВЕРА
        await asyncio.Event().wait()
       
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())