import asyncio
import logging
import sqlite3
import random
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.filters import Command
from dotenv import load_dotenv
import os

load_dotenv()

# ================== НАСТРОЙКИ ==================
API_TOKEN = os.getenv('API_TOKEN')
CARD_NUMBER = os.getenv('CARD_NUMBER', '6262 4700 5534 4787')  
ADMIN_IDS = [5009858379, 587180281]  # Убрал нерабочий ID

# Константы
ORDER_NEW = 'new'
ORDER_WAITING_CONFIRM = 'waiting_confirm'
ORDER_CONFIRMED = 'confirmed'
ORDER_CANCELLED = 'cancelled'
CUSTOMIZATION_PRICE = 50000

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# ================== БАЗА ДАННЫХ ==================
def setup_database():
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

# ================== РЕГИОНЫ И ПОЧТОВЫЕ ОТДЕЛЕНИЯ ==================
POST_OFFICES = {
    'tashkent': {
        'ru': [
            "📮 Чиланзарское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791001\n🗺️ Google: https://maps.app.goo.gl/example1",
            "📮 Юнусабадское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791002\n🗺️ Google: https://maps.app.goo.gl/example2",
            "📮 Мирзо-Улугбекское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791003\n🗺️ Google: https://maps.app.goo.gl/example3",
            "📮 Шайхантахурское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791004\n🗺️ Google: https://maps.app.goo.gl/example4",
            "📮 Алмазарское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791005\n🗺️ Google: https://maps.app.goo.gl/example5"
        ],
        'uz': [
            "📮 Chilanzar OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791001\n🗺️ Google: https://maps.app.goo.gl/example1",
            "📮 Yunusobod OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791002\n🗺️ Google: https://maps.app.goo.gl/example2",
            "📮 Mirzo-Ulugʻbek OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791003\n🗺️ Google: https://maps.app.goo.gl/example3",
            "📮 Shayxontoxur OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791004\n🗺️ Google: https://maps.app.goo.gl/example4",
            "📮 Olmazor OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791005\n🗺️ Google: https://maps.app.goo.gl/example5"
        ]
    },
    'samarkand': {
        'ru': [
            "📮 Самаркандское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791006\n🗺️ Google: https://maps.app.goo.gl/example6",
            "📮 ОПС Сиаб\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791007\n🗺️ Google: https://maps.app.goo.gl/example7",
            "📮 ОПС Регистан\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791008\n🗺️ Google: https://maps.app.goo.gl/example8",
            "📮 ОПС Амира Темура\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791009\n🗺️ Google: https://maps.app.goo.gl/example9",
            "📮 ОПС Ургут\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791010\n🗺️ Google: https://maps.app.goo.gl/example10"
        ],
        'uz': [
            "📮 Samarqand OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791006\n🗺️ Google: https://maps.app.goo.gl/example6",
            "📮 Siob OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791007\n🗺️ Google: https://maps.app.goo.gl/example7",
            "📮 Registon OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791008\n🗺️ Google: https://maps.app.goo.gl/example8",
            "📮 Amir Temur OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791009\n🗺️ Google: https://maps.app.goo.gl/example9",
            "📮 Urgut OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791010\n🗺️ Google: https://maps.app.goo.gl/example10"
        ]
    },
    'andijan': {
        'ru': [
            "📮 Андижанское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791011\n🗺️ Google: https://maps.app.goo.gl/example11",
            "📮 ОПС Ханабад\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791012\n🗺️ Google: https://maps.app.goo.gl/example12",
            "📮 ОПС Асака\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791013\n🗺️ Google: https://maps.app.goo.gl/example13",
            "📮 ОПС Шахрихан\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791014\n🗺️ Google: https://maps.app.goo.gl/example14",
            "📮 ОПС Балыкчи\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791015\n🗺️ Google: https://maps.app.goo.gl/example15"
        ],
        'uz': [
            "📮 Andijon OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791011\n🗺️ Google: https://maps.app.goo.gl/example11",
            "📮 Xonobod OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791012\n🗺️ Google: https://maps.app.goo.gl/example12",
            "📮 Asaka OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791013\n🗺️ Google: https://maps.app.goo.gl/example13",
            "📮 Shahrixon OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791014\n🗺️ Google: https://maps.app.goo.gl/example14",
            "📮 Baliqchi OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791015\n🗺️ Google: https://maps.app.goo.gl/example15"
        ]
    },
    'bukhara': {
        'ru': [
            "📮 Бухарское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791016\n🗺️ Google: https://maps.app.goo.gl/example16",
            "📮 ОПС Гиждуван\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791017\n🗺️ Google: https://maps.app.goo.gl/example17",
            "📮 ОПС Каган\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791018\n🗺️ Google: https://maps.app.goo.gl/example18",
            "📮 ОПС Ромитан\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791019\n🗺️ Google: https://maps.app.goo.gl/example19",
            "📮 ОПС Шафиркан\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791020\n🗺️ Google: https://maps.app.goo.gl/example20"
        ],
        'uz': [
            "📮 Buxoro OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791016\n🗺️ Google: https://maps.app.goo.gl/example16",
            "📮 G'ijduvon OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791017\n🗺️ Google: https://maps.app.goo.gl/example17",
            "📮 Kogon OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791018\n🗺️ Google: https://maps.app.goo.gl/example18",
            "📮 Romitan OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791019\n🗺️ Google: https://maps.app.goo.gl/example19",
            "📮 Shofirkon OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791020\n🗺️ Google: https://maps.app.goo.gl/example20"
        ]
    },
    'fergana': {
        'ru': [
            "📮 Ферганское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791021\n🗺️ Google: https://maps.app.goo.gl/example21",
            "📮 ОПС Маргилан\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791022\n🗺️ Google: https://maps.app.goo.gl/example22",
            "📮 ОПС Кувасай\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791023\n🗺️ Google: https://maps.app.goo.gl/example23",
            "📮 ОПС Коканд\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791024\n🗺️ Google: https://maps.app.goo.gl/example24",
            "📮 ОПС Риштан\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791025\n🗺️ Google: https://maps.app.goo.gl/example25"
        ],
        'uz': [
            "📮 Farg'ona OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791021\n🗺️ Google: https://maps.app.goo.gl/example21",
            "📮 Marg'ilon OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791022\n🗺️ Google: https://maps.app.goo.gl/example22",
            "📮 Quvasoy OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791023\n🗺️ Google: https://maps.app.goo.gl/example23",
            "📮 Qo'qon OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791024\n🗺️ Google: https://maps.app.goo.gl/example24",
            "📮 Rishton OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791025\n🗺️ Google: https://maps.app.goo.gl/example25"
        ]
    }
}

REGIONS = {
    'ru': {
        'tashkent': '🏙️ Ташкент',
        'andijan': '🏙️ Андижан', 
        'bukhara': '🏙️ Бухара',
        'fergana': '🏙️ Фергана',
        'jizzakh': '🏙️ Джизак',
        'kashkadarya': '🏙️ Кашкадарья',
        'khorezm': '🏙️ Хорезм',
        'namangan': '🏙️ Наманган',
        'navoi': '🏙️ Навои',
        'samarkand': '🏙️ Самарканд',
        'surkhandarya': '🏙️ Сурхандарья',
        'syrdarya': '🏙️ Сырдарья',
        'karakalpakstan': '🏙️ Каракалпакстан'
    },
    'uz': {
        'tashkent': '🏙️ Toshkent',
        'andijan': '🏙️ Andijon', 
        'bukhara': '🏙️ Buxoro',
        'fergana': '🏙️ Fargʻona',
        'jizzakh': '🏙️ Jizzax',
        'kashkadarya': '🏙️ Qashqadaryo',
        'khorezm': '🏙️ Xorazm',
        'namangan': '🏙️ Namangan',
        'navoi': '🏙️ Navoiy',
        'samarkand': '🏙️ Samarqand',
        'surkhandarya': '🏙️ Surxondaryo',
        'syrdarya': '🏙️ Sirdaryo',
        'karakalpakstan': '🏙️ Qoraqalpogʻiston'
    }
}

# ================== ХРАНЕНИЕ ДАННЫХ ==================
user_sessions = {}
user_selections = {}
user_carts = {}
support_requests = {}

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
            # Берем только первую строку с названием отделения
            office_name = office.split('\n')[0]
            builder.add(KeyboardButton(text=office_name))
    builder.add(KeyboardButton(text="↩️ Назад" if language == 'ru' else "↩️ Orqaga"))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

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

# ================== ТЕКСТЫ ==================
def get_text(key, language):
    texts = {
        'welcome': {
            'ru': "👋 Добро пожаловать в FootballKits.uz!\n\nВыберите язык:",
            'uz': "👋 FootballKits.uz ga xush kelibsiz!\n\nTilni tanlang:"
        },
        'contact_request': {
            'ru': "📞 Для продолжения поделитесь контактом или введите номер вручную:",
            'uz': "📞 Davom etish uchun kontaktni ulashing yoki raqamni qo'lda kiriting:"
        },
        'manual_phone_request': {
            'ru': "📱 Введите ваш номер телефона в формате:\n+998901234567",
            'uz': "📱 Telefon raqamingizni quyidagi formatda kiriting:\n+998901234567"
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
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT phone, name, language, region, post_office FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

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

def update_order_status(order_id, status, admin_id=None):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if admin_id:
            cursor.execute("UPDATE orders SET status = ?, confirmed_by = ?, confirmed_at = CURRENT_TIMESTAMP WHERE id = ?", 
                          (status, admin_id, order_id))
        else:
            cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        conn.commit()

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

# ================== КОРЗИНА ==================
async def show_cart(user_id, language, message):
    cart = user_carts.get(user_id, [])
    
    if not cart:
        if language == 'ru':
            text = "🛒 Ваша корзина пуста"
        else:
            text = "🛒 Sizning savatingiz bo'sh"
        await message.answer(text, reply_markup=get_main_menu(language))
        return
    
    total_price = 0
    cart_text = ""
    
    for i, item in enumerate(cart, 1):
        item_price = item['product_price'] + (item.get('customization', {}).get('price', 0) if item.get('customization') else 0)
        total_price += item_price
        
        if language == 'ru':
            cart_text += f"{i}. {item['product_name']}\n"
            cart_text += f"   📏 Размер: {item.get('size', 'Не выбран')}\n"
            if item.get('customization'):
                cart_text += f"   ✨ Кастомизация: {item['customization']['text']}\n"
            cart_text += f"   💵 {format_price(item_price, language)}\n\n"
        else:
            cart_text += f"{i}. {item['product_name']}\n"
            cart_text += f"   📏 Oʻlcham: {item.get('size', 'Tanlanmagan')}\n"
            if item.get('customization'):
                cart_text += f"   ✨ Be'zash: {item['customization']['text']}\n"
            cart_text += f"   💵 {format_price(item_price, language)}\n\n"
    
    if language == 'ru':
        cart_text += f"💰 <b>Итого: {format_price(total_price, language)}</b>"
        action_text = "Выберите действие:"
    else:
        cart_text += f"💰 <b>Jami: {format_price(total_price, language)}</b>"
        action_text = "Harakatni tanlang:"
    
    await message.answer(cart_text, parse_mode='HTML')
    await message.answer(action_text, reply_markup=get_cart_keyboard(language))

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

# ================== ОСНОВНЫЕ КОМАНДЫ ==================
@dp.message(Command("start"))
async def start_bot(message: types.Message):
    user_sessions[message.from_user.id] = {'step': 'language'}
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
    
    await message.answer(get_text('manual_phone_request', language), reply_markup=get_back_menu(language))

# ОБРАБОТКА РУЧНОГО ВВОДА НОМЕРА
@dp.message(F.text.startswith('+'))
async def handle_manual_phone_input(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    
    if session.get('step') != 'manual_phone':
        return await handle_main_menu(message)
    
    language = session.get('language', 'ru')
    phone = message.text.strip()
    
    # Простая валидация номера
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
    name = message.contact.first_name
    
    # Сразу сохраняем пользователя и переходим к выбору региона
    save_user(user_id, phone, name, language)
    user_sessions[user_id]['step'] = 'region'
    user_sessions[user_id]['phone'] = phone
    user_sessions[user_id]['name'] = name
    
    await message.answer(get_text('contact_received', language))
    await message.answer(get_text('region_request', language), reply_markup=get_region_keyboard(language))

# ВЫБОР РЕГИОНА
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
        
        # Показываем почтовые отделения для выбранного региона
        if selected_region in POST_OFFICES:
            offices = POST_OFFICES[selected_region][language]
            for office in offices:
                await message.answer(office)
            
            await message.answer(get_text('post_office_request', language), 
                               reply_markup=get_post_office_keyboard(selected_region, language))
        else:
            # Если региона нет в списке, переходим сразу к главному меню
            save_user(user_id, session['phone'], session['name'], language, selected_region)
            user_sessions[user_id]['step'] = 'main_menu'
            await message.answer("✅ Регистрация завершена!", reply_markup=get_main_menu(language))
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
        
        # Сохраняем выбранное отделение
        save_user(user_id, session['phone'], session['name'], language, region, text)
        user_sessions[user_id]['step'] = 'main_menu'
        user_sessions[user_id]['post_office'] = text
        
        await message.answer(get_text('post_office_received', language), 
                           reply_markup=get_main_menu(language))
        return
    
    # Если пользователь уже в главном меню
    await handle_main_menu(message)

# ОБРАБОТКА ГЛАВНОГО МЕНЮ
async def handle_main_menu(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user:
        await message.answer("❌ Сначала завершите регистрацию через /start")
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
        await handle_customization_choice(message)
    elif text in ["❌ Нет, без кастомизации", "❌ Yo'q, be'zashsiz"]:
        await handle_customization_choice(message)
    elif text in ["🔙 Назад к товарам", "🔙 Mahsulotlarga qaytish"]:
        await back_to_catalog(message)
    else:
        # Проверяем, не является ли сообщение номером товара
        if text.isdigit():
            await handle_product_selection(message)
        elif user_id in support_requests and support_requests[user_id].get('waiting_question'):
            # Обработка вопроса в поддержку
            question = message.text
            admin_text = f"❓ ВОПРОС ОТ ПОЛЬЗОВАТЕЛЯ\n\n👤 {name} (@{message.from_user.username or 'N/A'})\n📞 {phone}\n💬 {question}"
            await notify_admins(admin_text)
            
            if language == 'ru':
                await message.answer("✅ Ваш вопрос отправлен! Мы ответим вам в ближайшее время.", reply_markup=get_main_menu(language))
            else:
                await message.answer("✅ Savolingiz yuborildi! Tez orada sizga javob beramiz.", reply_markup=get_main_menu(language))
            
            support_requests[user_id]['waiting_question'] = False
        elif user_id in user_sessions and user_sessions[user_id].get('waiting_review'):
            # Обработка текста отзыва
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
            # Обработка текста кастомизации
            await handle_customization_text(message)
        else:
            await message.answer("❌ Не понимаю команду. Используйте кнопки меню." if language == 'ru' else "❌ Buyruqni tushunmayman. Menyu tugmalaridan foydalaning.", 
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
            user_sessions[user_id].pop('waiting_receipt', None)
            user_sessions[user_id].pop('waiting_customization_text', None)
            user_sessions[user_id].pop('waiting_review', None)
        
        await message.answer(get_text('order_cancelled', language), 
                           reply_markup=get_main_menu(language))

# КАТАЛОГ
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

# КАТЕГОРИИ ТОВАРОВ
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
            
            # Для форм предлагаем кастомизацию
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

async def handle_customization_choice(message: types.Message):
    user = get_user(message.from_user.id)
    if not user or message.from_user.id not in user_selections:
        return
    
    language = user[2]
    selection = user_selections[message.from_user.id]
    
    wants_customization = message.text in ["✅ Да, добавить имя и номер", "✅ Ha, ism va raqam qo'shing"]
    
    if wants_customization:
        selection['customization'] = {'price': CUSTOMIZATION_PRICE}
        
        if language == 'ru':
            text = "✍️ Введите имя и номер для печати (например: «РАХМОН 7» или «ALI 9»):"
        else:
            text = "✍️ Bosma uchun ism va raqamni kiriting (masalan: «RAHMON 7» yoki «ALI 9»):"
        
        await message.answer(text, reply_markup=get_back_menu(language))
        user_sessions[message.from_user.id]['waiting_customization_text'] = True
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
    user_sessions[user_id]['waiting_customization_text'] = False
    
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
        # Показываем таблицу размеров
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
    
    await show_cart(callback.from_user.id, language, callback.message)
    await callback.answer()

# КОРЗИНА
async def show_cart_command(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала завершите регистрацию")
        return
    
    language = user[2]
    await show_cart(message.from_user.id, language, message)

async def add_more_products(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    language = user[2]
    await message.answer("📋 Выберите категорию:" if language == 'ru' else "📋 Toifani tanlang:", 
                       reply_markup=get_main_menu(language))

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
    
    user_sessions[message.from_user.id]['checkout_cart'] = cart.copy()
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
    
    # Только карта - убрана наличка
    cart = user_sessions[message.from_user.id]['checkout_cart']
    total_price = sum(item['product_price'] + (item.get('customization', {}).get('price', 0) if item.get('customization') else 0) for item in cart)
    
    order_ids = []
    order_details = []
    
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
        
        # Формируем детали заказа для админа
        item_detail = f"• {item['product_name']}"
        if item.get('size'):
            item_detail += f" | Размер: {item['size']}"
        if item.get('customization'):
            item_detail += f" | Кастомизация: {item['customization']['text']}"
        item_detail += f" | {format_price(item['product_price'] + (item.get('customization', {}).get('price', 0) if item.get('customization') else 0), 'ru')}"
        order_details.append(item_detail)
    
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
    user_sessions[message.from_user.id]['waiting_receipt'] = True
    user_sessions[message.from_user.id]['order_ids'] = order_ids
    
    # Отправляем уведомление админам о новом заказе
    admin_text = (
        f"🆕 НОВЫЙ ЗАКАЗ\n\n"
        f"👤 {name} (@{message.from_user.username or 'N/A'})\n"
        f"📞 {phone}\n"
        f"🏙️ {REGIONS['ru'].get(region, region)}\n"
        f"📮 {post_office}\n\n"
        f"📦 Товары:\n" + "\n".join(order_details) + f"\n\n"
        f"💰 Итого: {format_price(total_price, 'ru')}\n"
        f"💳 Оплата: картой\n"
        f"🆔 Заказы: {', '.join(map(str, order_ids))}\n"
        f"🕒 {datetime.now().strftime('%H:%M %d.%m.%Y')}"
    )
    await notify_admins(admin_text)

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
    
    # Обновляем статус заказов
    for order_id in order_ids:
        update_order_status(order_id, 'waiting_confirm')
    
    # Отправляем чек админам
    admin_text = f"📸 ЧЕК ОПЛАТЫ\n\nЗаказы: {', '.join(map(str, order_ids))}\nПользователь: {user[1]} (@{message.from_user.username or 'N/A'})"
    
    try:
        await notify_admins(admin_text, message.photo[-1].file_id)
        
        if language == 'ru':
            await message.answer("✅ Чек получен! Мы проверяем оплату и скоро подтвердим ваш заказ.", reply_markup=get_main_menu(language))
        else:
            await message.answer("✅ Chek qabul qilindi! Biz to'lovni tekshiramiz va tez orada buyurtmangizni tasdiqlaymiz.", reply_markup=get_main_menu(language))
        
        # Очищаем корзину
        if user_id in user_carts:
            del user_carts[user_id]
        if 'checkout_cart' in user_sessions[user_id]:
            del user_sessions[user_id]['checkout_cart']
        user_sessions[user_id]['waiting_receipt'] = False
        
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
    
    language = user[2]
    if language == 'ru':
        text = "⭐ Мнение клиентов\n\nЗдесь вы можете посмотреть отзывы наших клиентов или оставить свой отзыв!"
    else:
        text = "⭐ Mijozlar fikri\n\nBu yerda mijozlarimiz sharhlarini ko'rishingiz yoki o'z sharhingizni qoldirishingiz mumkin!"
    
    await message.answer(text, reply_markup=get_reviews_menu(language))

async def show_reviews(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    language = user[2]
    
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
    
    if language == 'ru':
        await message.answer("📢 Больше отзывов: https://t.me/footballkitsreview", 
                           reply_markup=get_reviews_menu(language))
    else:
        await message.answer("📢 Ko'proq sharhlar: https://t.me/footballkitsreview", 
                           reply_markup=get_reviews_menu(language))

async def start_review(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    language = user[2]
    
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

@dp.message(F.photo)
async def handle_review_photo(message: types.Message):
    user_id = message.from_user.id
    if (user_id in user_sessions and user_sessions[user_id].get('waiting_review') and
        message.caption):
        
        user = get_user(user_id)
        if not user:
            return
        
        language = user[2]
        review_text = message.caption
        
        # Сохраняем отзыв с фото
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reviews (customer_name, review_text_ru, review_text_uz, photo_url, rating)
                VALUES (?, ?, ?, ?, ?)
            """, (user[1], review_text, review_text, message.photo[-1].file_id, 5))
            conn.commit()
        
        # Уведомляем админов
        admin_text = (
            f"📝 НОВЫЙ ОТЗЫВ С ФОТО\n\n"
            f"👤 {user[1]} (@{message.from_user.username or 'N/A'})\n"
            f"📞 {user[0]}\n"
            f"💬 {review_text}"
        )
        
        await notify_admins(admin_text, message.photo[-1].file_id)
        
        if language == 'ru':
            await message.answer("✅ Спасибо за отзыв с фото! Мы ценим ваше мнение!", 
                               reply_markup=get_main_menu(language))
        else:
            await message.answer("✅ Rasmli sharh uchun rahmat! Biz sizning fikringizni qadrlaymiz!", 
                               reply_markup=get_main_menu(language))
        
        user_sessions[user_id]['waiting_review'] = False

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
            payment_icon = "💳"
            
            status_text = "Подтвержден" if status == "confirmed" else "Ожидает подтверждения" if status == "waiting_confirm" else "Новый"
            if language == 'uz':
                status_text = "Tasdiqlangan" if status == "confirmed" else "Tasdiqlanish kutilmoqda" if status == "waiting_confirm" else "Yangi"
            
            response += f"{i}. {product_name}\n"
            response += f"💵 {format_price(total_price, language)} {payment_icon}\n"
            response += f"{status_icon} {status_text}\n"
            response += f"📅 {created_at[:16]}\n\n"
    else:
        if language == 'ru':
            response = "📦 У вас еще нет заказов"
        else:
            response = "📦 Sizda hali buyurtmalar yo'q"
    
    await message.answer(response, reply_markup=get_main_menu(language))

# ================== ЗАПУСК ==================
async def main():
    try:
        setup_database()
        print("🚀 Бот запущен!")
        print(f"👑 Админы: {ADMIN_IDS}")
        print(f"💳 Карта для оплаты: {CARD_NUMBER}")
        print("⭐ Система отзывов готова!")
        print("🛍️ Каталог товаров готов!")
        print("📱 Регистрация через контакт или ручной ввод номера")
        print("📍 Система доставки с почтовыми отделениями активирована!")
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())