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
ADMIN_IDS = [5009858379, 587180281, 1225271746]  # Все 3 админа

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
    },
    'jizzakh': {
        'ru': [
            "📮 Джизакское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791026\n🗺️ Google: https://maps.app.goo.gl/example26",
            "📮 ОПС Галляарал\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791027\n🗺️ Google: https://maps.app.goo.gl/example27",
            "📮 ОПС Дустлик\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791028\n🗺️ Google: https://maps.app.goo.gl/example28",
            "📮 ОПС Зафарабад\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791029\n🗺️ Google: https://maps.app.goo.gl/example29",
            "📮 ОПС Пахтакор\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791030\n🗺️ Google: https://maps.app.goo.gl/example30"
        ],
        'uz': [
            "📮 Jizzax OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791026\n🗺️ Google: https://maps.app.goo.gl/example26",
            "📮 G'allaorol OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791027\n🗺️ Google: https://maps.app.goo.gl/example27",
            "📮 Do'stlik OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791028\n🗺️ Google: https://maps.app.goo.gl/example28",
            "📮 Zafarobod OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791029\n🗺️ Google: https://maps.app.goo.gl/example29",
            "📮 Paxtakor OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791030\n🗺️ Google: https://maps.app.goo.gl/example30"
        ]
    },
    'kashkadarya': {
        'ru': [
            "📮 Каршинское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791031\n🗺️ Google: https://maps.app.goo.gl/example31",
            "📮 ОПС Шахрисабз\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791032\n🗺️ Google: https://maps.app.goo.gl/example32",
            "📮 ОПС Китаб\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791033\n🗺️ Google: https://maps.app.goo.gl/example33",
            "📮 ОПС Мубарек\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791034\n🗺️ Google: https://maps.app.goo.gl/example34",
            "📮 ОПС Яккабаг\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791035\n🗺️ Google: https://maps.app.goo.gl/example35"
        ],
        'uz': [
            "📮 Qarshi OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791031\n🗺️ Google: https://maps.app.goo.gl/example31",
            "📮 Shahrisabz OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791032\n🗺️ Google: https://maps.app.goo.gl/example32",
            "📮 Kitob OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791033\n🗺️ Google: https://maps.app.goo.gl/example33",
            "📮 Muborak OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791034\n🗺️ Google: https://maps.app.goo.gl/example34",
            "📮 Yakkabog' OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791035\n🗺️ Google: https://maps.app.goo.gl/example35"
        ]
    },
    'khorezm': {
        'ru': [
            "📮 Ургенчское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791036\n🗺️ Google: https://maps.app.goo.gl/example36",
            "📮 ОПС Хива\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791037\n🗺️ Google: https://maps.app.goo.gl/example37",
            "📮 ОПС Питнак\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791038\n🗺️ Google: https://maps.app.goo.gl/example38",
            "📮 ОПС Шават\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791039\n🗺️ Google: https://maps.app.goo.gl/example39",
            "📮 ОПС Багат\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791040\n🗺️ Google: https://maps.app.goo.gl/example40"
        ],
        'uz': [
            "📮 Urganch OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791036\n🗺️ Google: https://maps.app.goo.gl/example36",
            "📮 Xiva OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791037\n🗺️ Google: https://maps.app.goo.gl/example37",
            "📮 Pitnak OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791038\n🗺️ Google: https://maps.app.goo.gl/example38",
            "📮 Shovot OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791039\n🗺️ Google: https://maps.app.goo.gl/example39",
            "📮 Bog'ot OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791040\n🗺️ Google: https://maps.app.goo.gl/example40"
        ]
    },
    'namangan': {
        'ru': [
            "📮 Наманганское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791041\n🗺️ Google: https://maps.app.goo.gl/example41",
            "📮 ОПС Чуст\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791042\n🗺️ Google: https://maps.app.goo.gl/example42",
            "📮 ОПС Касансай\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791043\n🗺️ Google: https://maps.app.goo.gl/example43",
            "📮 ОПС Пап\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791044\n🗺️ Google: https://maps.app.goo.gl/example44",
            "📮 ОПС Учкурган\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791045\n🗺️ Google: https://maps.app.goo.gl/example45"
        ],
        'uz': [
            "📮 Namangan OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791041\n🗺️ Google: https://maps.app.goo.gl/example41",
            "📮 Chust OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791042\n🗺️ Google: https://maps.app.goo.gl/example42",
            "📮 Kosonsoy OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791043\n🗺️ Google: https://maps.app.goo.gl/example43",
            "📮 Pop OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791044\n🗺️ Google: https://maps.app.goo.gl/example44",
            "📮 Uchqo'rg'on OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791045\n🗺️ Google: https://maps.app.goo.gl/example45"
        ]
    },
    'navoi': {
        'ru': [
            "📮 Навоийское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791046\n🗺️ Google: https://maps.app.goo.gl/example46",
            "📮 ОПС Зарафшан\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791047\n🗺️ Google: https://maps.app.goo.gl/example47",
            "📮 ОПС Кармана\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791048\n🗺️ Google: https://maps.app.goo.gl/example48",
            "📮 ОПС Кызылтепа\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791049\n🗺️ Google: https://maps.app.goo.gl/example49",
            "📮 ОПС Нурата\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791050\n🗺️ Google: https://maps.app.goo.gl/example50"
        ],
        'uz': [
            "📮 Navoiy OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791046\n🗺️ Google: https://maps.app.goo.gl/example46",
            "📮 Zarafshon OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791047\n🗺️ Google: https://maps.app.goo.gl/example47",
            "📮 Karmana OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791048\n🗺️ Google: https://maps.app.goo.gl/example48",
            "📮 Qiziltepa OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791049\n🗺️ Google: https://maps.app.goo.gl/example49",
            "📮 Nurota OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791050\n🗺️ Google: https://maps.app.goo.gl/example50"
        ]
    },
    'surkhandarya': {
        'ru': [
            "📮 Термезское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791051\n🗺️ Google: https://maps.app.goo.gl/example51",
            "📮 ОПС Денау\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791052\n🗺️ Google: https://maps.app.goo.gl/example52",
            "📮 ОПС Шерабад\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791053\n🗺️ Google: https://maps.app.goo.gl/example53",
            "📮 ОПС Шурчи\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791054\n🗺️ Google: https://maps.app.goo.gl/example54",
            "📮 ОПС Байсун\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791055\n🗺️ Google: https://maps.app.goo.gl/example55"
        ],
        'uz': [
            "📮 Termiz OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791051\n🗺️ Google: https://maps.app.goo.gl/example51",
            "📮 Denov OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791052\n🗺️ Google: https://maps.app.goo.gl/example52",
            "📮 Sherobod OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791053\n🗺️ Google: https://maps.app.goo.gl/example53",
            "📮 Sho'rchi OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791054\n🗺️ Google: https://maps.app.goo.gl/example54",
            "📮 Boysun OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791055\n🗺️ Google: https://maps.app.goo.gl/example55"
        ]
    },
    'syrdarya': {
        'ru': [
            "📮 Гулистанское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791056\n🗺️ Google: https://maps.app.goo.gl/example56",
            "📮 ОПС Сырдарья\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791057\n🗺️ Google: https://maps.app.goo.gl/example57",
            "📮 ОПС Баяут\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791058\n🗺️ Google: https://maps.app.goo.gl/example58",
            "📮 ОПС Сардоба\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791059\n🗺️ Google: https://maps.app.goo.gl/example59",
            "📮 ОПС Хаваст\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791060\n🗺️ Google: https://maps.app.goo.gl/example60"
        ],
        'uz': [
            "📮 Guliston OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791056\n🗺️ Google: https://maps.app.goo.gl/example56",
            "📮 Sirdaryo OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791057\n🗺️ Google: https://maps.app.goo.gl/example57",
            "📮 Boyovut OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791058\n🗺️ Google: https://maps.app.goo.gl/example58",
            "📮 Sardoba OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791059\n🗺️ Google: https://maps.app.goo.gl/example59",
            "📮 Xovos OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791060\n🗺️ Google: https://maps.app.goo.gl/example60"
        ]
    },
    'karakalpakstan': {
        'ru': [
            "📮 Нукусское ОПС\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791061\n🗺️ Google: https://maps.app.goo.gl/example61",
            "📮 ОПС Ходжейли\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791062\n🗺️ Google: https://maps.app.goo.gl/example62",
            "📮 ОПС Кунград\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791063\n🗺️ Google: https://maps.app.goo.gl/example63",
            "📮 ОПС Беруни\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791064\n🗺️ Google: https://maps.app.goo.gl/example64",
            "📮 ОПС Чимбай\n🗺️ Яндекс: https://yandex.uz/maps/org/108225791065\n🗺️ Google: https://maps.app.goo.gl/example65"
        ],
        'uz': [
            "📮 Nukus OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791061\n🗺️ Google: https://maps.app.goo.gl/example61",
            "📮 Xo'jayli OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791062\n🗺️ Google: https://maps.app.goo.gl/example62",
            "📮 Qo'ng'irot OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791063\n🗺️ Google: https://maps.app.goo.gl/example63",
            "📮 Beruniy OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791064\n🗺️ Google: https://maps.app.goo.gl/example64",
            "📮 Chimboy OПХ\n🗺️ Yandex: https://yandex.uz/maps/org/108225791065\n🗺️ Google: https://maps.app.goo.gl/example65"
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

# ================== АДМИН КЛАВИАТУРЫ ==================
def get_admin_menu():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="📊 Статистика"))
    builder.add(KeyboardButton(text="📦 Заказы"))
    builder.add(KeyboardButton(text="➕ Добавить товар"))
    builder.add(KeyboardButton(text="📝 Отзывы"))
    builder.add(KeyboardButton(text="🔙 Выйти из админки"))
    builder.adjust(2, 2, 1)
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
        
        # Общее количество пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # Общее количество заказов
        cursor.execute("SELECT COUNT(*) FROM orders")
        total_orders = cursor.fetchone()[0]
        
        # Заказы по статусам
        cursor.execute("SELECT status, COUNT(*) FROM orders GROUP BY status")
        status_stats = cursor.fetchall()
        
        # Общая выручка
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

# ================== АДМИН ФУНКЦИИ ==================
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет доступа к админ-панели")
        return
    
    admin_sessions[message.from_user.id] = {'is_admin': True}
    await message.answer("🛠️ Добро пожаловать в админ-панель!", reply_markup=get_admin_menu())

# Обработка админ-меню
@dp.message(F.text.in_(["📊 Статистика", "📦 Заказы", "➕ Добавить товар", "📝 Отзывы", "🔙 Выйти из админки"]))
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
        
    elif message.text == "📝 Отзывы":
        reviews = get_all_reviews()
        if not reviews:
            await message.answer("📝 Пока нет отзывов")
            return
        
        for review in reviews[:5]:  # Показываем последние 5 отзывов
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
        # Завершаем создание товара
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
        
        # Очищаем сессию
        del admin_sessions[user_id]
        
        await message.answer(f"✅ Товар успешно добавлен! ID: {product_id}", reply_markup=get_admin_menu())

@dp.message(F.photo)
async def handle_product_photo(message: types.Message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS or not admin_sessions.get(user_id, {}).get('adding_product'):
        return
    
    session = admin_sessions[user_id]
    if session.get('step') == 'image':
        # Сохраняем фото и завершаем создание товара
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
        
        # Очищаем сессию
        del admin_sessions[user_id]
        
        await message.answer(f"✅ Товар с фото успешно добавлен! ID: {product_id}", reply_markup=get_admin_menu())

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
    
    for order in orders[:10]:  # Показываем первые 10 заказов
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
        
        # Уведомляем пользователя
        user_id = order[1]
        try:
            await bot.send_message(user_id, f"✅ Ваш заказ #{order_id} подтвержден! Скоро мы его отправим.")
        except:
            pass
            
    elif action == "reject":
        update_order_status(order_id, 'cancelled', callback.from_user.id)
        await callback.message.edit_text(f"❌ Заказ #{order_id} отклонен")
        
        # Уведомляем пользователя
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

def get_all_reviews():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT customer_name, review_text_ru, review_text_uz, photo_url, rating, created_at FROM reviews ORDER BY created_at DESC LIMIT 10")
        return cursor.fetchall()

# ================== ОСНОВНЫЕ КОМАНДЫ ==================
@dp.message(Command("start"))
async def start_bot(message: types.Message):
    # Проверяем, не админ ли это
    if message.from_user.id in ADMIN_IDS:
        await admin_panel(message)
        return
        
    user_sessions[message.from_user.id] = {'step': 'language'}
    await message.answer(get_text('welcome', 'ru'), reply_markup=get_language_keyboard())

# ... (остальной код пользовательской части остается без изменений, как в предыдущем варианте)

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
        print("🛠️ Админ-панель активирована!")
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())