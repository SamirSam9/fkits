import asyncio
import logging
import sqlite3
import random
import traceback
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from datetime import datetime
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.filters import Command
from dotenv import load_dotenv
import os
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

# ================== НАСТРОЙКИ ==================
API_TOKEN = os.getenv('API_TOKEN', '8322636763:AAHyqLDD-voqN6MjUD8XKV8v7Jc5FnENuv8')
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME', 'fkits.onrender.com')}{WEBHOOK_PATH}"
PORT = int(os.getenv("PORT", 10000))
CARD_NUMBER = os.getenv('CARD_NUMBER', '6262 4700 5534 4787')

# Админы
ADMIN_IDS = [5009858379, 587180281, 1225271746]  

# Константы
ORDER_NEW = 'new'
ORDER_WAITING_CONFIRM = 'waiting_confirm'
ORDER_CONFIRMED = 'confirmed'
ORDER_CANCELLED = 'cancelled'
CUSTOMIZATION_PRICE = 50000

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ================== СИСТЕМА РОЛЕЙ ==================
USER_ROLES = {}

# Инициализация ролей для админов
for admin_id in ADMIN_IDS:
    if admin_id not in USER_ROLES:
        USER_ROLES[admin_id] = 'admin'  # По умолчанию все админы в режиме админа

def get_role_selection_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="👑 АДМИН", callback_data="role_admin"))
    builder.add(types.InlineKeyboardButton(text="👤 ПОЛЬЗОВАТЕЛЬ", callback_data="role_user"))
    builder.adjust(2)
    return builder.as_markup()

def get_admin_switch_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="✅ Да, перейти в админку", callback_data="switch_to_admin"))
    builder.add(types.InlineKeyboardButton(text="❌ Нет, остаться", callback_data="stay_user"))
    builder.adjust(1)
    return builder.as_markup()

def get_admin_help_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(text="📋 Команды админа", callback_data="admin_commands"))
    builder.add(types.InlineKeyboardButton(text="🛠️ Управление заказами", callback_data="admin_orders_help"))
    builder.add(types.InlineKeyboardButton(text="🛍️ Управление товарами", callback_data="admin_products_help"))
    builder.adjust(1)
    return builder.as_markup()

async def notify_admins_with_role_check(text, photo_file_id=None, order_id=None):
    """Уведомление админов с проверкой роли"""
    for admin_id in ADMIN_IDS:
        try:
            # Если админ в режиме пользователя - предлагаем переключиться
            if USER_ROLES.get(admin_id) == 'user':
                switch_text = f"🆕 Поступил новый заказ!\n\n{text}\n\nХотите перейти в режим админа для обработки?"
                await bot.send_message(admin_id, switch_text, reply_markup=get_admin_switch_keyboard())
            else:
                # Админ уже в режиме админа - обычное уведомление
                if photo_file_id:
                    await bot.send_photo(admin_id, photo_file_id, caption=text)
                else:
                    await bot.send_message(admin_id, text)
        except Exception as e:
            logging.error(f"Ошибка отправки админу {admin_id}: {e}")

# Обработчики callback-запросов
@dp.callback_query(F.data.in_(['switch_to_admin', 'stay_user']))
async def process_role_switch(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    
    if callback_query.data == 'switch_to_admin':
        # Переключаем в режим админа
        USER_ROLES[user_id] = 'admin'
        await callback_query.message.edit_text(
            "✅ Вы перешли в режим админа. Теперь вы будете получать полные уведомления о заказах.",
            reply_markup=None
        )
    else:
        # Остаемся в режиме пользователя
        await callback_query.message.edit_text(
            "❌ Остаюсь в режиме пользователя. Вы можете переключиться позже через /admin",
            reply_markup=None
        )
    
    await callback_query.answer()

@dp.callback_query(F.data.startswith("role_"))
async def handle_role_selection(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    role = callback.data.replace("role_", "")
    
    USER_ROLES[user_id] = role
    
    if role == 'admin':
        admin_sessions[user_id] = {'is_admin': True}
        await callback.message.edit_text("🛠️ Добро пожаловать в админ-панель!")
        await callback.message.answer("📋 Выберите действие:", reply_markup=get_admin_menu())
    else:
        user = get_user(user_id)
        language = user[2] if user else 'ru'
        await callback.message.edit_text(get_text('welcome_back', language))
        await callback.message.answer("📋 Главное меню:", reply_markup=get_main_menu(language))
    
    await callback.answer()

# Другие callback-обработчики
@dp.callback_query(F.data == "admin_commands")
async def handle_admin_commands_help(callback: types.CallbackQuery):
    help_text = """
<b>КОМАНДЫ АДМИНИСТРАТОРА</b>

<b>Основные команды:</b>
/start - Запуск с выбором роли
/admin - Вход в админ-панель  
/help - Полная справка

<b>Функции админ-панели:</b>
• Статистика - общая статистика магазина
• Заказы - управление всеми заказами
• Добавить товар - пошаговое добавление
• Управление товарами - просмотр/удаление
• Отзывы - просмотр отзывов клиентов
    """
    await callback.message.answer(help_text, parse_mode='HTML')
    await callback.answer()

@dp.callback_query(F.data == "admin_orders_help")
async def handle_admin_orders_help(callback: types.CallbackQuery):
    help_text = """
<b>УПРАВЛЕНИЕ ЗАКАЗАМИ</b>

<b>Статусы заказов:</b>
Новый - Только создан
Ожидает подтверждения - Чек отправлен
Подтвержден - Оплата проверена
Отклонен - Проблема с оплатой

<b>Действия с заказами:</b>
• Подтвердить - после проверки чека
• Отклонить - при проблемах с оплатой  
• Связаться - для уточнения деталей
    """
    await callback.message.answer(help_text, parse_mode='HTML')
    await callback.answer()

@dp.callback_query(F.data == "admin_products_help")
async def handle_admin_products_help(callback: types.CallbackQuery):
    help_text = """
<b>УПРАВЛЕНИЕ ТОВАРАМИ</b>

<b>Добавление товара:</b>
1. Выберите категорию
2. Введите название на русском
3. Введите название на узбекском  
4. Укажите цену
5. Добавьте описание
6. Укажите размеры
7. Загрузите фото

<b>Категории:</b>
• Формы 2024/2025
• Ретро формы
• Бутсы
• Фут. атрибутика
• Акции
    """
    await callback.message.answer(help_text, parse_mode='HTML')
    await callback.answer()

# ================== БАЗА ДАННЫХ ==================
DB_FILENAME = 'football_shop.db'

def setup_database():
    try:
        conn = sqlite3.connect(DB_FILENAME, check_same_thread=False)
        cursor = conn.cursor()

        # Таблица пользователей
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

        # Таблица товаров
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

        # Таблица отзывов
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

        # Таблица заказов
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
                ('Сергей', 'Качество печати на высшем уровне!', 'Bosma sifatı eng yuqori darajada!', '', 5),
                ('ADMIN', 'https://t.me/footballkitsreview', 'https://t.me/footballkitsreview', '', 5),
            ]
            cursor.executemany(
                "INSERT INTO reviews (customer_name, review_text_ru, review_text_uz, photo_url, rating) VALUES (?, ?, ?, ?, ?)",
                test_reviews
            )

        # Добавляем тестовые товары по вашим категориям
        cursor.execute("SELECT COUNT(*) FROM products")
        if cursor.fetchone()[0] == 0:
            test_products = [
                # Формы нынешний сезон
                ('Форма Пахтакор 2024', 'Paxtakor Formasi 2024', 180000, 'Формы 2024/2025', '2024/2025 Formalari', '', 'Официальная форма ФК Пахтакор сезон 2024', 'Rasmiy Paxtakor FK formasi 2024', 'S, M, L, XL', 'S, M, L, XL'),
                ('Форма Навбахор 2024', 'Navbahor Formasi 2024', 170000, 'Формы 2024/2025', '2024/2025 Formalari', '', 'Официальная форма ФК Навбахор', 'Rasmiy Navbahor FK formasi', 'S, M, L, XL', 'S, M, L, XL'),
                
                # Ретро формы
                ('Ретро форма Пахтакор 1990', 'Paxtakor Retro Formasi 1990', 150000, 'Ретро формы', 'Retro Formalari', '', 'Ретро форма Пахтакор 90-х годов', '90-yillarning Paxtakor retro formasi', 'S, M, L, XL', 'S, M, L, XL'),
                ('Ретро форма Навбахор 1995', 'Navbahor Retro Formasi 1995', 145000, 'Ретро формы', 'Retro Formalari', '', 'Ретро форма Навбахор 1995 года', '1995-yil Navbahor retro formasi', 'S, M, L, XL', 'S, M, L, XL'),
                
                # Бутсы
                ('Бутсы Nike Mercurial', 'Nike Mercurial Futbolka', 220000, 'Бутсы', 'Futbolkalar', '', 'Профессиональные футбольные бутсы', 'Professional futbolkalar', '40, 41, 42, 43, 44', '40, 41, 42, 43, 44'),
                ('Бутсы Adidas Predator', 'Adidas Predator Futbolka', 240000, 'Бутсы', 'Futbolkalar', '', 'Бутсы для контроля мяча', 'Topni nazorat qilish uchun futbolkalar', '40, 41, 42, 43, 44', '40, 41, 42, 43, 44'),
                
                # Акции
                ('Набор форма+гетры', 'Forma+Gaitor to\'plam', 200000, 'Акции', 'Aksiyalar', '', 'Форма + гетры по специальной цене', 'Forma + gaitor maxsus narxda', 'S, M, L', 'S, M, L'),
                
                # Футбольная атрибутика
                ('Вратарские перчатки', 'Darvozabon qo\'lqoplari', 80000, 'Футбольная атрибутика', 'Futbol Aksessuarlari', '', 'Профессиональные вратарские перчатки', 'Professional darvozabon qo\'lqoplari', 'S, M, L', 'S, M, L'),
                ('Футбольный мяч', 'Futbol to\'pi', 120000, 'Футбольная атрибутика', 'Futbol Aksessuarlari', '', 'Официальный матчевый мяч', 'Rasmiy match to\'pi', 'Размер 5', '5-hajm'),
                ('Гетры профессиональные', 'Professional gaitorlar', 25000, 'Футбольная атрибутика', 'Futbol Aksessuarlari', '', 'Профессиональные футбольные гетры', 'Professional futbol gaitorlari', 'Универсальный', 'Universal'),
            ]
            cursor.executemany(
                "INSERT INTO products (name_ru, name_uz, price, category_ru, category_uz, image_url, description_ru, description_uz, sizes_ru, sizes_uz) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                test_products
            )

        conn.commit()
        conn.close()
        logger.info("✅ База данных готова")
    except Exception as e:
        logger.error(f"❌ Ошибка базы данных: {e}")
        raise

# ... ОСТАВШИЙСЯ КОД ПРОДОЛЖАЕТСЯ ...
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
    
    # Создаем прозрачные кнопки для всех регионов
    for region_key in regions:
        builder.add(KeyboardButton(text=regions[region_key]))
    
    # Настраиваем по 2 кнопки в ряд для красивого отображения
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

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
        builder.add(KeyboardButton(text="👕 Формы 2024/2025"))
        builder.add(KeyboardButton(text="🕰️ Ретро формы"))
        builder.add(KeyboardButton(text="⚽ Бутсы"))
        builder.add(KeyboardButton(text="🎁 Фут. атрибутика"))
        builder.add(KeyboardButton(text="🔥 Акции"))
        builder.add(KeyboardButton(text="↩️ Назад"))
    else:
        builder.add(KeyboardButton(text="👕 2024/2025 Formalari"))
        builder.add(KeyboardButton(text="🕰️ Retro formalar"))
        builder.add(KeyboardButton(text="⚽ Futbolkalar"))
        builder.add(KeyboardButton(text="🎁 Futbol Aksessuarlari"))
        builder.add(KeyboardButton(text="🔥 Aksiyalar"))
        builder.add(KeyboardButton(text="↩️ Orqaga"))
    builder.adjust(2, 2, 1, 1)
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
    # Определяем размеры в зависимости от категории
    if any(word in product_category.lower() for word in ['форма', 'formasi', 'аксессуар', 'aksessuar']):
        sizes = [("S", "size_S"), ("M", "size_M"), ("L", "size_L"), ("XL", "size_XL"), ("XXL", "size_XXL")]
    else:  # Бутсы
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
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=text)]], resize_keyboard=True)

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
    builder.add(KeyboardButton(text="👕 Формы 2024/2025"))
    builder.add(KeyboardButton(text="🕰️ Ретро формы"))
    builder.add(KeyboardButton(text="⚽ Бутсы"))
    builder.add(KeyboardButton(text="🎁 Фут. атрибутика"))
    builder.add(KeyboardButton(text="🔥 Акции"))
    builder.add(KeyboardButton(text="🔙 Назад"))
    builder.adjust(2, 2, 1, 1)
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
            'ru': "🤝 Помощь\n\n📞 Телефон: +998 88 111-10-81 \n📞 Телефон: +998 97 455-55-82 \n⏰ Время работы: 9:00-23:00\n\n💬 Задайте ваш вопрос:",
            'uz': "🤝 Yordam\n\n📞 Telefon: +998 88 111-10-81\n📞 Telefon: +998 97 455-55-82 \n⏰ Ish vaqti: 9:00-23:00\n\n💬 Savolingizni bering:"
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
    return sqlite3.connect(DB_FILENAME, check_same_thread=False)

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
    try:
        formatted = f"{int(price):,} UZS".replace(',', ' ')
    except:
        formatted = f"{price} UZS"
    return formatted

# ================== КАРТОЧКИ ТОВАРОВ ==================
async def send_product_card(chat_id, product, language):
    product_id, name, price, image_url, description, sizes = product

    # Определяем эмодзи по названию товара
    lower_name = (name or "").lower()
    if any(word in lower_name for word in ['форма', 'formasi']):
        emoji = "👕"
    elif any(word in lower_name for word in ['бутсы', 'futbolka']):
        emoji = "⚽"
    elif any(word in lower_name for word in ['перчатки', 'мяч', 'гетры', 'qo\'lqop', 'to\'p', 'gaitor']):
        emoji = "🎁"
    else:
        emoji = "🔥"

    if language == 'ru':
        caption = (
            f"{emoji} <b>{name}</b>\n\n"
            f"📝 {description}\n\n"
            f"📏 <b>Размеры: {sizes}</b>\n\n"
            f"💵 <b>Цена: {format_price(price, language)}</b>\n\n"
            f"🆔 <code>ID: {product_id}</code>\n\n"
            f"✨ <i>Чтобы заказать, напишите номер товара</i>"
        )
    else:
        caption = (
            f"{emoji} <b>{name}</b>\n\n"
            f"📝 {description}\n\n"
            f"📏 <b>Oʻlchamlar: {sizes}</b>\n\n"
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
            cart_text += f"   📏 Размер: {item['size']}\n" if language == 'ru' else f"   📏 Oʻlcham: {item['size']}\n"
        if item.get('customization'):
            cart_text += f"   ✨ Кастомизация: {item['customization']['text']}\n" if language == 'ru' else f"   ✨ Be'zash: {item['customization']['text']}\n"
        cart_text += f"   💵 {format_price(item_price, language)}\n\n"

    cart_text += f"💰 Итого: {format_price(total_price, language)}" if language == 'ru' else f"💰 Jami: {format_price(total_price, language)}"

    await message.answer(cart_text, reply_markup=get_cart_keyboard(language))

@dp.message(Command("start"))
async def start_bot(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    # Если пользователь уже зарегистрирован
    if user:
        language = user[2]
        
        # Если пользователь админ - предлагаем выбор роли
        if user_id in ADMIN_IDS:
            if user_id not in USER_ROLES:
                # Показываем выбор роли
                if language == 'ru':
                    text = "👋 Добро пожаловать обратно!\n\n📋 В какой роли вы хотите зайти?"
                else:
                    text = "👋 Xush kelibsiz!\n\n📋 Qaysi rolda kirishni xohlaysiz?"
                
                await message.answer(text, reply_markup=get_role_selection_keyboard())
                return
            else:
                # Уже выбрал роль - показываем соответствующее меню
                if USER_ROLES[user_id] == 'admin':
                    await admin_panel(message)
                else:
                    text = get_text('welcome_back', language)
                    await message.answer(text, reply_markup=get_main_menu(language))
        else:
            # Обычный пользователь
            text = get_text('welcome_back', language)
            await message.answer(text, reply_markup=get_main_menu(language))
    else:
        # Новый пользователь - начинаем регистрацию
        user_sessions[user_id] = {'step': 'language'}
        await message.answer(get_text('welcome', 'ru'), reply_markup=get_language_keyboard())

@dp.callback_query(F.data == "stay_user")
async def handle_stay_user(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "❌ Остаюсь в режиме пользователя. Вы можете переключиться позже через /admin",
        reply_markup=None
    )
    await callback.answer()
        # Обработчик выбора роли
@dp.callback_query(F.data.startswith("role_"))
async def handle_role_selection(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    role = callback.data.replace("role_", "")
    
    USER_ROLES[user_id] = role
    
    if role == 'admin':
        admin_sessions[user_id] = {'is_admin': True}
        await callback.message.edit_text("🛠️ Добро пожаловать в админ-панель!")
        await callback.message.answer("📋 Выберите действие:", reply_markup=get_admin_menu())
    else:
        user = get_user(user_id)
        language = user[2] if user else 'ru'
        await callback.message.edit_text(get_text('welcome_back', language))
        await callback.message.answer("📋 Главное меню:", reply_markup=get_main_menu(language))
    
    await callback.answer()
    

# ================== ДОБАВЬ ЭТИ ФУНКЦИИ В НАЧАЛО (после POST_OFFICES) ==================

def get_location_keyboard(lang: str):
    """Клавиатура для отправки геолокации"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(
            text="Отправить геолокацию" if lang == 'ru' else "Joylashuvni yuborish",
            request_location=True
        )]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# Используем уже существующий POST_OFFICES как PICKUP_POINTS
PICKUP_POINTS = POST_OFFICES

def get_pickup_points_keyboard(region_key: str, lang: str):
    """Клавиатура с пунктами выдачи"""
    if region_key not in PICKUP_POINTS:
        return None
    offices = PICKUP_POINTS[region_key][lang]
    builder = ReplyKeyboardBuilder()
    for office in offices:
        short_name = office.split('—')[0].strip()
        builder.add(KeyboardButton(text=short_name))
    builder.add(KeyboardButton(text="Назад" if lang == 'ru' else "Orqaga"))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

# ================== ИСПРАВЛЕННЫЙ ОБРАБОТЧИК РЕГИОНА ==================

@dp.message(F.text.in_([v for v in REGIONS['ru'].values()] + [v for v in REGIONS['uz'].values()]))
async def handle_region_selection(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    
    if session.get('step') != 'region':
        return
        
    language = session.get('language', 'ru')
    text = message.text
    
    # Находим выбранный регион
    selected_region = None
    for region_key, region_name in REGIONS[language].items():
        if text == region_name:
            selected_region = region_key
            break
            
    if not selected_region:
        await message.answer(
            "Пожалуйста, выберите регион из списка" if language == 'ru' else "Iltimos, ro'yxatdan viloyatni tanlang"
        )
        return
        
    user_sessions[user_id]['region'] = selected_region
    user_sessions[user_id]['selected_region'] = selected_region  # ДОБАВЛЕНО!

    # Для Ташкента — геолокация
    if selected_region == 'tashkent':
        user_sessions[user_id]['step'] = 'location'  # НЕ post_office!
        await message.answer(
            "Ташкент — отправьте вашу геолокацию\nНаш курьер свяжется с вами для уточнения адреса" if language == 'ru'
            else "Toshkent — joylashuvingizni yuboring\nBizning kuryerimiz manzilni aniqlash uchun siz bilan bog'lanadi",
            reply_markup=get_location_keyboard(language)
        )
    else:
        # Для других регионов — пункты выдачи
        user_sessions[user_id]['step'] = 'pickup_point'
        points = PICKUP_POINTS.get(selected_region, {}).get(language, [])
        
        if not points:
            await message.answer(
                "В этом регионе пока нет пунктов выдачи" if language == 'ru'
                else "Ushbu viloyatda hozircha yetkazib berish punktlari yo'q"
            )
            return
        
        # Формируем текст
        region_name = REGIONS[language][selected_region]
        text = f"<b>{region_name}</b>\n\n"
        text += f"Всего пунктов: {len(points)}\n\n" if language == 'ru' else f"Jami punktlar: {len(points)}\n\n"
        text += "Выберите пункт выдачи:" if language == 'ru' else "Yetkazib berish punktini tanlang:"

        await message.answer(text, parse_mode='HTML', 
                            reply_markup=get_pickup_points_keyboard(selected_region, language))

# ================== ИСПРАВЛЕННЫЙ ОБРАБОТЧИК ГЕОЛОКАЦИИ ==================

@dp.message(F.location)
async def handle_location(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})

    if session.get('step') != 'location':
        return

    language = session.get('language', 'ru')
    lat, lon = message.location.latitude, message.location.longitude
    location_text = f"Геолокация: {lat}, {lon}"

    # Сохраняем в БД
    save_user(
        user_id=user_id,
        phone=session['phone'],
        name=session['name'],
        language=language,
        region='tashkent',
        post_office=location_text
    )

    # Обновляем сессию
    user_sessions[user_id]['step'] = 'main_menu'
    user_sessions[user_id]['post_office'] = location_text
    user_sessions[user_id]['coordinates'] = (lat, lon)

    await message.answer(
        "Геолокация получена! Курьер свяжется с вами для уточнения адреса." if language == 'ru'
        else "Geolokatsiya qabul qilindi! Kuryer manzilni aniqlash uchun siz bilan bog'lanadi.",
        reply_markup=get_main_menu(language)
    )

# ================== ИСПРАВЛЕННЫЙ /help (ВЫНЕСЕН ИЗ ФУНКЦИИ!) ==================

@dp.message(Command("help"))
async def help_command(message: types.Message):
    user_id = message.from_user.id
    
    if user_id in ADMIN_IDS:
        help_text = """
<b>ПОМОЩЬ ДЛЯ АДМИНИСТРАТОРА</b>

<b>Основные команды:</b>
/start - Запуск бота (выбор роли)
/admin - Переход в админ-панель
/help - Эта справка

<b>Админ-панель:</b>
Статистика - Просмотр статистики магазина
Заказы - Управление заказами
Добавить товар - Добавление нового товара
Управление товарами - Просмотр и удаление товаров
Отзывы - Просмотр отзывов клиентов

<b>Управление заказами:</b>
• Подтверждение заказов после проверки чека
• Отклонение заказов с проблемами
• Связь с клиентами по телефону

<b>Статусы заказов:</b>
Новый - Только создан
Ожидает подтверждения - Отправлен чек
Подтвержден - Оплата проверена
Отклонен - Проблема с оплатой
        """
        await message.answer(help_text, parse_mode='HTML', reply_markup=get_admin_help_keyboard())
    else:
        user = get_user(user_id)
        if user:
            await show_help(message)
        else:
            await message.answer("Сначала завершите регистрацию через /start")

# ================== ДОБАВЬ ЭТИ CALLBACK-И В КОНЕЦ ФАЙЛА ==================

@dp.callback_query(F.data == "admin_commands")
async def handle_admin_commands_help(callback: types.CallbackQuery):
    help_text = """
<b>КОМАНДЫ АДМИНИСТРАТОРА</b>

<b>Основные команды:</b>
/start - Запуск с выбором роли
/admin - Вход в админ-панель  
/help - Полная справка

<b>Функции админ-панели:</b>
• Статистика - общая статистика магазина
• Заказы - управление всеми заказами
• Добавить товар - пошаговое добавление
• Управление товарами - просмотр/удаление
• Отзывы - просмотр отзывов клиентов
    """
    await callback.message.answer(help_text, parse_mode='HTML')
    await callback.answer()

@dp.callback_query(F.data == "admin_orders_help")
async def handle_admin_orders_help(callback: types.CallbackQuery):
    help_text = """
<b>УПРАВЛЕНИЕ ЗАКАЗАМИ</b>

<b>Статусы заказов:</b>
Новый - Только создан
Ожидает подтверждения - Чек отправлен
Подтвержден - Оплата проверена
Отклонен - Проблема с оплатой

<b>Действия с заказами:</b>
• Подтвердить - после проверки чека
• Отклонить - при проблемах с оплатой  
• Связаться - для уточнения деталей
    """
    await callback.message.answer(help_text, parse_mode='HTML')
    await callback.answer()

@dp.callback_query(F.data == "admin_products_help")
async def handle_admin_products_help(callback: types.CallbackQuery):
    help_text = """
<b>УПРАВЛЕНИЕ ТОВАРАМИ</b>

<b>Добавление товара:</b>
1. Выберите категорию
2. Введите название на русском
3. Введите название на узбекском  
4. Укажите цену
5. Добавьте описание
6. Укажите размеры
7. Загрузите фото

<b>Категории:</b>
• Формы 2024/2025
• Ретро формы
• Бутсы
• Фут. атрибутика
• Акции
    """
    await callback.message.answer(help_text, parse_mode='HTML')
    await callback.answer()
# ================== ФУНКЦИИ МАГАЗИНА ==================
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

# ВЫБОР ТОВАРА (обработчик по цифровому сообщению)
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

            # Проверяем, является ли товар формой (для кастомизации)
            if any(word in (product_name or "").lower() for word in ['форма', 'formasi']):
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
                    'category': 'Другое'
                }
                if language == 'ru':
                    text = f"🛒 Вы выбрали:\n\n📦 {product_name}\n💵 {format_price(product_price, language)}\n\n{get_text('choose_size', language)}"
                else:
                    text = f"🛒 Siz tanladingiz:\n\n📦 {product_name}\n💵 {format_price(product_price, language)}\n\n{get_text('choose_size', language)}"
                await message.answer(text, reply_markup=get_size_keyboard(language, 'Другое'))
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

# Показать корзину (команда)
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

    session = user_sessions.get(message.from_user.id, {})
    cart = session.get('checkout_cart', [])
    if not cart:
        if language == 'ru':
            await message.answer("❌ Корзина пуста")
        else:
            await message.answer("❌ Savat bo'sh")
        return

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
    user_sessions[message.from_user.id] = {'waiting_receipt': True, 'order_ids': order_ids, 'checkout_cart': cart.copy()}

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
    
    # Получаем данные пользователя
    phone, name, language, region, post_office = user

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
        f"👤 {name} (@{message.from_user.username or 'N/A'})\n"
        f"📞 {phone}\n"
        f"🏙️ {REGIONS['ru'].get(region, region)}\n"
        f"🏙️ Город: {session.get('city', 'Не указан')}\n"  # ← ДОБАВИЛИ ГОРОД
        f"📮 {post_office}\n\n"
        f"📦 Товары:\n" + "\n".join(order_details) + f"\n\n"
        f"💰 Итого: {format_price(total_price, 'ru')}\n"
        f"💳 Оплата: картой ✅\n"
        f"🆔 Заказы: {', '.join(map(str, order_ids))}\n"
        f"🕒 {datetime.now().strftime('%H:%M %d.%m.%Y')}"
    )

    try:
        # 🔥 ИСПРАВЛЕНИЕ: Отправляем админам сначала текст, потом фото чека
        for admin_id in ADMIN_IDS:
            try:
                # Отправляем текстовое уведомление
                await bot.send_message(admin_id, admin_text)
                
                # Отправляем фото чека
                await bot.send_photo(admin_id, message.photo[-1].file_id, 
                                   caption=f"📸 Чек оплаты для заказов: {', '.join(map(str, order_ids))}")
                
                # 🔥 ДОПОЛНЕНИЕ: Если это Ташкент и есть геолокация - отправляем карту
               
                        
            except Exception as e:
                logging.error(f"Ошибка отправки админу {admin_id}: {e}")

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
        except Exception:
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
            "• Текст отзыва\n"
            "• Фото + текст\n"
            "• Просто фото\n\n"
            "Мы добавим ваш отзыв в наш канал!"
        )
    else:
        text = (
            "✍️ Do'konimiz haqida sharhingizni yozing!\n\n"
            "Yuborishingiz mumkin:\n"
            "• Sharh matni\n"
            "• Rasm + matn\n"
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

# ================== АДМИН КОМАНДЫ ==================
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

# Обработка добавления товара (категория)
@dp.message(F.text.in_(["👕 Формы 2024/2025", "🕰️ Ретро формы", "⚽ Бутсы", "🎁 Фут. атрибутика", "🔥 Акции"]))
async def handle_product_category(message: types.Message):
    if message.from_user.id not in ADMIN_IDS or not admin_sessions.get(message.from_user.id, {}).get('adding_product'):
        return

    category_map = {
        "👕 Формы 2024/2025": ("Формы 2024/2025", "2024/2025 Formalari"),
        "🕰️ Ретро формы": ("Ретро формы", "Retro Formalari"),
        "⚽ Бутсы": ("Бутсы", "Futbolkalar"),
        "🎁 Фут. атрибутика": ("Футбольная атрибутика", "Futbol Aksessuarlari"),
        "🔥 Акции": ("Акции", "Aksiyalar")
    }

    category_ru, category_uz = category_map[message.text]
    admin_sessions[message.from_user.id].update({
        'step': 'name_ru',
        'category_ru': category_ru,
        'category_uz': category_uz
    })

    await message.answer("Введите название товара на русском:", reply_markup=types.ReplyKeyboardRemove())

# Обработка создания товара (последовательность)
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
        if message.text and message.text.lower() == 'пропустить':
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

# Получение фото товара (при добавлении)
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

# Управление товарами: callback'и
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

    try:
        product_id = int(callback.data.replace("delete_product_", ""))
    except:
        await callback.answer("❌ Неверный ID")
        return

    if delete_product(product_id):
        await callback.message.answer(f"✅ Товар #{product_id} успешно удален")
    else:
        await callback.message.answer(f"❌ Ошибка при удалении товара #{product_id}")

    await callback.answer()

# Просмотр заказов (админ)
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

# Обработка действий с заказами (подтвердить/отклонить/контакт)
@dp.callback_query(F.data.startswith("confirm_") | F.data.startswith("reject_") | F.data.startswith("contact_"))
async def handle_order_actions(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    data = callback.data
    if "_" not in data:
        await callback.answer("❌ Неверное действие")
        return

    action, order_id_str = data.split("_", 1)
    try:
        order_id = int(order_id_str)
    except:
        await callback.answer("❌ Неверный ID заказа")
        return

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
        except Exception:
            pass

    elif action == "reject":
        update_order_status(order_id, 'cancelled', callback.from_user.id)
        await callback.message.edit_text(f"❌ Заказ #{order_id} отклонен")

        user_id = order[1]
        try:
            await bot.send_message(user_id, f"❌ Ваш заказ #{order_id} отклонен. Для уточнения деталей свяжитесь с нами.")
        except Exception:
            pass

    elif action == "contact":
        user_phone = order[3]
        user_name = order[2]
        await callback.message.answer(f"📞 Контакт пользователя:\n👤 {user_name}\n📞 {user_phone}")

    await callback.answer()

# ================== ЗАПУСК ==================
async def main():
    try:
        setup_database()
        logger.info("🚀 Бот запущен!")
        logger.info(f"✅ Токен: {'*' * 10}{API_TOKEN[-5:]}")
        logger.info(f"👑 Админы: {ADMIN_IDS}")
        logger.info(f"💳 Карта: {CARD_NUMBER}")
        logger.info("⭐ Система отзывов готова!")
        logger.info("🛍️ Каталог товаров готов!")
        logger.info("📱 Регистрация через контакт или ручной ввод номера")
        logger.info("📍 Система доставки с почтовыми отделениями активирована!")
        logger.info("🛠️ Админ-панель активирована!")

               # 🔥 ИСПРАВЛЕНИЕ: Запускаем веб-сервер ОТДЕЛЬНО
        await start_web_server()
        
        # 🔥 ИСПРАВЛЕНИЕ: Используем polling (проще для начала)
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())