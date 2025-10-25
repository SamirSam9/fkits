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
ADMIN_IDS = [5009858379, 587180281, 1225271746]

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
            location TEXT,
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
            user_location TEXT,
            product_name TEXT NOT NULL,
            product_price INTEGER NOT NULL,
            product_size TEXT,
            customization_text TEXT,
            customization_price INTEGER DEFAULT 0,
            payment_method TEXT DEFAULT 'cash',
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

# ================== РЕГИОНЫ И ФИЛИАЛЫ ПОЧТ ==================
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

POST_OFFICES = {
    'tashkent': {
        'ru': [
            '📮 Чиланзарское ОПС', '📮 Юнусабадское ОПС', '📮 Мирзо-Улугбекское ОПС',
            '📮 Шайхантахурское ОПС', '📮 Алмазарское ОПС', '📮 Яккасарайское ОПС',
            '📮 Сергелийское ОПС', '📮 Бектемирское ОПС', '📮 ОПС Мирабад',
            '📮 ОПС Хамза', '📮 ОПС Куйлюк', '📮 ОПС Каракамыш'
        ],
        'uz': [
            '📮 Chilanzar OПХ', '📮 Yunusobod OПХ', '📮 Mirzo-Ulugʻbek OПХ',
            '📮 Shayxontohur OПХ', '📮 Olmazar OПХ', '📮 Yakkasaroy OПХ',
            '📮 Sergeli OПХ', '📮 Bektemir OПХ', '📮 Mirabad OПХ',
            '📮 Hamza OПХ', '📮 Quyliq OПХ', '📮 Qoraqamish OПХ'
        ]
    },
    'samarkand': {
        'ru': [
            '📮 Самаркандское ОПС', '📮 ОПС Сиаб', '📮 ОПС Регистан',
            '📮 ОПС Булунгур', '📮 ОПС Джамбай', '📮 ОПС Иштыхан',
            '📮 ОПС Каттакурган', '📮 ОПС Нуробад', '📮 ОПС Пайарык',
            '📮 ОПС Пастдаргом', '📮 ОПС Пахтачи', '📮 ОПС Тайлак',
            '📮 ОПС Ургут'
        ],
        'uz': [
            '📮 Samarqand OПХ', '📮 Siob OПХ', '📮 Registon OПХ',
            '📮 Bulungʻur OПХ', '📮 Jomboy OПХ', '📮 Ishtixon OПХ',
            '📮 Kattaqoʻrgʻon OПХ', '📮 Nurobod OПХ', '📮 Payariq OПХ',
            '📮 Pastdargʻom OПХ', '📮 Paxtachi OПХ', '📮 Tayloq OПХ',
            '📮 Urgut OПХ'
        ]
    },
    'andijan': {
        'ru': [
            '📮 Андижанское ОПС', '📮 ОПС Асака', '📮 ОПС Баликчи',
            '📮 ОПС Боз', '📮 ОПС Булакбаши', '📮 ОПС Джалакудук',
            '📮 ОПС Избаскан', '📮 ОПС Кургантепа', '📮 ОПС Мархамат',
            '📮 ОПС Олтинкул', '📮 ОПС Пахтаобад', '📮 ОПС Улугнор',
            '📮 ОПС Ходжаабад', '📮 ОПС Шахрихан'
        ],
        'uz': [
            '📮 Andijon OПХ', '📮 Asaka OПХ', '📮 Baliqchi OПХ',
            '📮 Boʻz OПХ', '📮 Buloqboshi OПХ', '📮 Jalaquduq OПХ',
            '📮 Izboskan OПХ', '📮 Qoʻrgʻontepa OПХ', '📮 Marhamat OПХ',
            '📮 Oltinkoʻl OПХ', '📮 Paxtaobod OПХ', '📮 Ulugʻnor OПХ',
            '📮 Xoʻjaobod OПХ', '📮 Shahrixon OПХ'
        ]
    },
    'bukhara': {
        'ru': [
            '📮 Бухарское ОПС', '📮 ОПС Алат', '📮 ОПС Вабкент',
            '📮 ОПС Газли', '📮 ОПС Гиждуван', '📮 ОПС Жондор',
            '📮 ОПС Каракуль', '📮 ОПС Караулбазар', '📮 ОПС Пешку',
            '📮 ОПС Ромитан', '📮 ОПС Шафиркан'
        ],
        'uz': [
            '📮 Buxoro OПХ', '📮 Olot OПХ', '📮 Vobkent OПХ',
            '📮 Gʻazli OПХ', '📮 Gʻijduvon OПХ', '📮 Jondor OПХ',
            '📮 Qorakoʻl OПХ', '📮 Qorovulbozor OПХ', '📮 Peshku OПХ',
            '📮 Romitan OПХ', '📮 Shofirkon OПХ'
        ]
    },
    'fergana': {
        'ru': [
            '📮 Ферганское ОПС', '📮 ОПС Алтыарык', '📮 ОПС Багдад',
            '📮 ОПС Бешарык', '📮 ОПС Бувайда', '📮 ОПС Дангара',
            '📮 ОПС Кува', '📮 ОПС Кувасай', '📮 ОПС Маргилан',
            '📮 ОПС Риштан', '📮 ОПС Сах', '📮 ОПС Ташлак',
            '📮 ОПС Учкуприк', '📮 ОПС Узбекистан', '📮 ОПС Фуркат',
            '📮 ОПС Язъяван'
        ],
        'uz': [
            '📮 Fargʻona OПХ', '📮 Oltiariq OПХ', '📮 Bagʻdod OПХ',
            '📮 Beshariq OПХ', '📮 Buvayda OПХ', '📮 Dangʻara OПХ',
            '📮 Quva OПХ', '📮 Quvasoy OПХ', '📮 Margʻilon OПХ',
            '📮 Rishton OПХ', '📮 Soʻx OПХ', '📮 Toshloq OПХ',
            '📮 Uchkoʻprik OПХ', '📮 Oʻzbekiston OПХ', '📮 Furqat OПХ',
            '📮 Yozyovon OПХ'
        ]
    },
    'namangan': {
        'ru': [
            '📮 Наманганское ОПС', '📮 ОПС Косонсой', '📮 ОПС Мингбулак',
            '📮 ОПС Норин', '📮 ОПС Поп', '📮 ОПС Торакурган',
            '📮 ОПС Уйчи', '📮 ОПС Учкурган', '📮 ОПС Чартак',
            '📮 ОПС Чуст', '📮 ОПС Янгикурган'
        ],
        'uz': [
            '📮 Namangan OПХ', '📮 Kosonsoy OПХ', '📮 Mingbuloq OПХ',
            '📮 Norin OПХ', '📮 Pop OПХ', '📮 Toʻraqoʻrgʻon OПХ',
            '📮 Uychi OПХ', '📮 Uchqoʻrgʻon OПХ', '📮 Chortoq OПХ',
            '📮 Chust OПХ', '📮 Yangiqoʻrgʻon OПХ'
        ]
    },
    'jizzakh': {
        'ru': [
            '📮 Джизакское ОПС', '📮 ОПС Арнасай', '📮 ОПС Бахмат',
            '📮 ОПС Гагарин', '📮 ОПС Дустлик', '📮 ОПС Зафарабад',
            '📮 ОПС Замин', '📮 ОПС Мирзачул', '📮 ОПС Пахтакор',
            '📮 ОПС Фариш', '📮 ОПС Янгиабад'
        ],
        'uz': [
            '📮 Jizzax OПХ', '📮 Arnasoy OПХ', '📮 Baxmal OПХ',
            '📮 Gagarin OПХ', '📮 Doʻstlik OПХ', '📮 Zafarobod OПХ',
            '📮 Zomin OПХ', '📮 Mirzachoʻl OПХ', '📮 Paxtakor OПХ',
            '📮 Farish OПХ', '📮 Yangiobod OПХ'
        ]
    },
    'kashkadarya': {
        'ru': [
            '📮 Каршинское ОПС', '📮 ОПС Гузар', '📮 ОПС Дехканабад',
            '📮 ОПС Камаши', '📮 ОПС Карши', '📮 ОПС Китаб',
            '📮 ОПС Миришкор', '📮 ОПС Мубарек', '📮 ОПС Нишан',
            '📮 ОПС Чиракчи', '📮 ОПС Шахрисабз', '📮 ОПС Яккабаг'
        ],
        'uz': [
            '📮 Qarshi OПХ', '📮 Gʻuzor OПХ', '📮 Dehqonobod OПХ',
            '📮 Qamashi OПХ', '📮 Qarshi OПХ', '📮 Kitob OПХ',
            '📮 Mirishkor OПХ', '📮 Muborak OПХ', '📮 Nishon OПХ',
            '📮 Chiroqchi OПХ', '📮 Shahrisabz OПХ', '📮 Yakkabogʻ OПХ'
        ]
    },
    'khorezm': {
        'ru': [
            '📮 Ургенчское ОПС', '📮 ОПС Багат', '📮 ОПС Гурлен',
            '📮 ОПС Кошкупыр', '📮 ОПС Питнак', '📮 ОПС Тупроқкала',
            '📮 ОПС Ургенч', '📮 ОПС Хазарасп', '📮 ОПС Ханка',
            '📮 ОПС Хива', '📮 ОПС Шават', '📮 ОПС Янгиарык',
            '📮 ОПС Янгибазар'
        ],
        'uz': [
            '📮 Urganch OПХ', '📮 Bogʻot OПХ', '📮 Gurlan OПХ',
            '📮 Qoʻshkoʻpir OПХ', '📮 Pitnak OПХ', '📮 Tuproqqala OПХ',
            '📮 Urganch OПХ', '📮 Xazorasp OПХ', '📮 Xonqa OПХ',
            '📮 Xiva OПХ', '📮 Shovot OПХ', '📮 Yangiariq OПХ',
            '📮 Yangibozor OПХ'
        ]
    },
    'navoi': {
        'ru': [
            '📮 Навоийское ОПС', '📮 ОПС Зарафшан', '📮 ОПС Кармана',
            '📮 ОПС Кызылтепа', '📮 ОПС Навбахор', '📮 ОПС Нурата',
            '📮 ОПС Тамдыбулак', '📮 ОПС Учкудук', '📮 ОПС Хатырчи'
        ],
        'uz': [
            '📮 Navoiy OПХ', '📮 Zarafshon OПХ', '📮 Karmana OПХ',
            '📮 Qiziltepa OПХ', '📮 Navbaxor OПХ', '📮 Nurota OПХ',
            '📮 Tomdibuloq OПХ', '📮 Uchquduq OПХ', '📮 Xatirchi OПХ'
        ]
    },
    'surkhandarya': {
        'ru': [
            '📮 Термезское ОПС', '📮 ОПС Ангор', '📮 ОПС Байсун',
            '📮 ОПС Денау', '📮 ОПС Жаркурган', '📮 ОПС Кумкурган',
            '📮 ОПС Музрабад', '📮 ОПС Сариасия', '📮 ОПС Термез',
            '📮 ОПС Узун', '📮 ОПС Шерабад', '📮 ОПС Шурчи'
        ],
        'uz': [
            '📮 Termiz OПХ', '📮 Angor OПХ', '📮 Boysun OПХ',
            '📮 Denov OПХ', '📮 Jarqoʻrgʻon OПХ', '📮 Qumqoʻrgʻon OПХ',
            '📮 Muzrabot OПХ', '📮 Sariosiyo OПХ', '📮 Termiz OПХ',
            '📮 Uzun OПХ', '📮 Sherobod OПХ', '📮 Shoʻrchi OПХ'
        ]
    },
    'syrdarya': {
        'ru': [
            '📮 Гулистанское ОПС', '📮 ОПС Акалтын', '📮 ОПС Бахт',
            '📮 ОПС Гулистан', '📮 ОПС Мирзаабад', '📮 ОПС Сайхунобад',
            '📮 ОПС Сардоба', '📮 ОПС Сырдарья', '📮 ОПС Хаваст'
        ],
        'uz': [
            '📮 Guliston OПХ', '📮 Oqoltin OПХ', '📮 Baxt OПХ',
            '📮 Guliston OПХ', '📮 Mirzaobod OПХ', '📮 Sayxunobod OПХ',
            '📮 Sardoba OПХ', '📮 Sirdaryo OПХ', '📮 Xovos OПХ'
        ]
    },
    'karakalpakstan': {
        'ru': [
            '📮 Нукусское ОПС', '📮 ОПС Амударья', '📮 ОПС Беруний',
            '📮 ОПС Кегейли', '📮 ОПС Кунград', '📮 ОПС Муйнак',
            '📮 ОПС Нукус', '📮 ОПС Тахтакупыр', '📮 ОПС Турткуль',
            '📮 ОПС Ходжейли', '📮 ОПС Чимбай', '📮 ОПС Шуманай'
        ],
        'uz': [
            '📮 Nukus OПХ', '📮 Amudaryo OПХ', '📮 Beruniy OПХ',
            '📮 Kegeyli OПХ', '📮 Qoʻngʻirot OПХ', '📮 Moʻynoq OПХ',
            '📮 Nukus OПХ', '📮 Taxtakoʻpir OПХ', '📮 Toʻrtkoʻl OПХ',
            '📮 Xoʻjayli OПХ', '📮 Chimboy OПХ', '📮 Shumanay OПХ'
        ]
    }
}

# ================== СИСТЕМА РАЗМЕРОВ ==================
SIZE_GUIDE = {
    'ru': {
        'S': "S (46-48) - Обхват груди: 92-96см, Рост: 170-176см",
        'M': "M (48-50) - Обхват груди: 96-100см, Рост: 176-182см", 
        'L': "L (50-52) - Обхват груди: 100-104см, Рост: 182-186см",
        'XL': "XL (52-54) - Обхват груди: 104-108см, Рост: 186-190см",
        'XXL': "XXL (54-56) - Обхват груди: 108-112см, Рост: 190-194см",
        '40': "40 EU - Для стопы ~25.5см",
        '41': "41 EU - Для стопы ~26.5см", 
        '42': "42 EU - Для стопы ~27см",
        '43': "43 EU - Для стопы ~27.5см",
        '44': "44 EU - Для стопы ~28.5см"
    },
    'uz': {
        'S': "S (46-48) - Ko'krak qafasi: 92-96sm, Bo'y: 170-176sm",
        'M': "M (48-50) - Ko'krak qafasi: 96-100sm, Bo'y: 176-182sm",
        'L': "L (50-52) - Ko'krak qafasi: 100-104sm, Bo'y: 182-186sm", 
        'XL': "XL (52-54) - Ko'krak qafasi: 104-108sm, Bo'y: 186-190sm",
        'XXL': "XXL (54-56) - Ko'krak qafasi: 108-112sm, Bo'y: 190-194sm",
        '40': "40 EU - Oyoq uchun ~25.5sm",
        '41': "41 EU - Oyoq uchun ~26.5sm",
        '42': "42 EU - Oyoq uchun ~27sm",
        '43': "43 EU - Oyoq uchun ~27.5sm", 
        '44': "44 EU - Oyoq uchun ~28.5sm"
    }
}

# ================== ХРАНЕНИЕ ДАННЫХ ==================
user_sessions = {}
user_selections = {}
user_carts = {}
support_requests = {}
admin_product_creation = {}

# ================== КЛАВИАТУРЫ ==================
def get_language_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🇷🇺 Русский"))
    builder.add(KeyboardButton(text="🇺🇿 O'zbekcha"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_contact_keyboard(language):
    text = "📞 Отправить контакт" if language == 'ru' else "📞 Kontaktni yuborish"
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_phone_input_keyboard(language):
    text = "📱 Ввести номер вручную" if language == 'ru' else "📱 Raqamni qo'lda kiritish"
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text)]],
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

def get_location_keyboard(language):
    text = "📍 Отправить локацию" if language == 'ru' else "📍 Manzilni yuborish"
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text, request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_post_office_keyboard(region, language):
    builder = ReplyKeyboardBuilder()
    offices = POST_OFFICES.get(region, {}).get(language, ['📮 Центральное отделение' if language == 'ru' else '📮 Markaziy boʻlim'])
    for office in offices:
        builder.add(KeyboardButton(text=office))
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
        builder.add(KeyboardButton(text="💵 Наличные"))
        builder.add(KeyboardButton(text="❌ Отмена"))
    else:
        builder.add(KeyboardButton(text="💳 Karta orqali to'lash"))
        builder.add(KeyboardButton(text="💵 Naqd pul"))
        builder.add(KeyboardButton(text="❌ Bekor qilish"))
    
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_admin_menu():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="➕ Добавить товар"))
    builder.add(KeyboardButton(text="📊 Статистика"))
    builder.add(KeyboardButton(text="📦 Заказы"))
    builder.add(KeyboardButton(text="⭐ Управление отзывами"))
    builder.add(KeyboardButton(text="🔙 Главное меню"))
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_reviews_menu(language):
    builder = ReplyKeyboardBuilder()
    if language == 'ru':
        builder.add(KeyboardButton(text="⭐ Посмотреть отзывы"))
        builder.add(KeyboardButton(text="✍️ Оставить отзыв"))
        builder.add(KeyboardButton(text="🔙 Назад"))
    else:
        builder.add(KeyboardButton(text="⭐ Sharhlarni ko'rish"))
        builder.add(KeyboardButton(text="✍️ Sharh qoldirish"))
        builder.add(KeyboardButton(text="🔙 Orqaga"))
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
        'phone_confirmation': {
            'ru': "📱 Это ваш основной номер?",
            'uz': "📱 Bu sizning asosiy raqamingizmi?"
        },
        'region_request': {
            'ru': "🏙️ Выберите ваш регион для доставки:",
            'uz': "🏙️ Yetkazib berish uchun viloyatingizni tanlang:"
        },
        'location_request_tashkent': {
            'ru': "📍 Теперь поделитесь вашим местоположением для доставки:",
            'uz': "📍 Endi yetkazib berish uchun manzilingizni ulashing:"
        },
        'post_office_request': {
            'ru': "📮 Выберите ближайшее почтовое отделение:",
            'uz': "📮 Eng yaqin pochta boʻlimini tanlang:"
        },
        'contact_received': {
            'ru': "✅ Контакт получен!",
            'uz': "✅ Kontakt qabul qilindi!"
        },
        'phone_received': {
            'ru': "✅ Номер получен!",
            'uz': "✅ Raqam qabul qilindi!"
        },
        'location_received': {
            'ru': "✅ Локация получена! Теперь вы можете выбирать товары:",
            'uz': "✅ Manzil qabul qilindi! Endi mahsulotlarni tanlashingiz mumkin:"
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

def save_user(user_id, phone, name, language, region=None, location=None):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO users (user_id, phone, name, language, region, location) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, phone, name, language, region, location)
        )
        conn.commit()

def get_user(user_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT phone, name, language, region, location FROM users WHERE user_id = ?", (user_id,))
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

def save_order(user_id, phone, name, region, location, product_name, product_price, product_size=None, customization_text=None, customization_price=0, payment_method='cash'):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO orders (user_id, user_phone, user_name, user_region, user_location, product_name, product_price, product_size, customization_text, customization_price, payment_method) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, phone, name, region, location, product_name, product_price, product_size, customization_text, customization_price, payment_method)
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
        await bot.send_photo(
            chat_id=chat_id,
            photo=image_url,
            caption=caption,
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
    await message.answer(get_text('contact_request', language), 
                       reply_markup=ReplyKeyboardMarkup(
                           keyboard=[
                               [KeyboardButton(text="📞 Отправить контакт" if language == 'ru' else "📞 Kontaktni yuborish", request_contact=True)],
                               [KeyboardButton(text="📱 Ввести номер вручную" if language == 'ru' else "📱 Raqamni qo'lda kiritish")]
                           ],
                           resize_keyboard=True,
                           one_time_keyboard=True
                       ))

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
        return await handle_text_messages(message)
    
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
async def handle_region(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    
    if session.get('step') != 'region':
        return await handle_text_messages(message)
    
    language = session.get('language', 'ru')
    text = message.text
    
    selected_region = None
    for region_key, region_name in REGIONS[language].items():
        if text == region_name:
            selected_region = region_key
            break
    
    if not selected_region:
        await message.answer("❌ Пожалуйста, выберите регион из списка")
        return
    
    user_sessions[user_id]['step'] = 'location'
    user_sessions[user_id]['region'] = selected_region
    
    save_user(user_id, session['phone'], session['name'], language, selected_region)
    
    if selected_region == 'tashkent':
        await message.answer(get_text('location_request_tashkent', language), 
                           reply_markup=get_location_keyboard(language))
    else:
        await message.answer(get_text('post_office_request', language),
                           reply_markup=get_post_office_keyboard(selected_region, language))

# ОБРАБОТКА ВЫБОРА ПОЧТОВОГО ОТДЕЛЕНИЯ
@dp.message(F.text)
async def handle_post_office(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    
    if session.get('step') != 'location' or session.get('region') == 'tashkent':
        return await handle_text_messages(message)
    
    language = session.get('language', 'ru')
    region = session.get('region')
    
    offices = POST_OFFICES.get(region, {}).get(language, [])
    if message.text not in offices:
        await message.answer("❌ Пожалуйста, выберите отделение из списка")
        return
    
    location = message.text
    save_user(user_id, session['phone'], session['name'], language, region, location)
    
    user_sessions[user_id]['step'] = 'main_menu'
    user_sessions[user_id]['location'] = location
    
    await message.answer(get_text('post_office_received', language), 
                       reply_markup=get_main_menu(language))

# ПОЛУЧЕНИЕ ЛОКАЦИИ
@dp.message(F.location)
async def handle_location(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    
    if session.get('step') != 'location' or session.get('region') != 'tashkent':
        return
    
    language = session.get('language', 'ru')
    location = f"{message.location.latitude},{message.location.longitude}"
    
    save_user(user_id, session['phone'], session['name'], language, 'tashkent', location)
    user_sessions[user_id]['step'] = 'main_menu'
    user_sessions[user_id]['location'] = location
    
    await message.answer(get_text('location_received', language), 
                       reply_markup=get_main_menu(language))

# ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ
async def handle_text_messages(message: types.Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user:
        await message.answer("❌ Сначала завершите регистрацию через /start")
        return
    
    phone, name, language, region, location = user
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
    elif text in ["↩️ Назад", "↩️ Orqaga"]:
        await back_to_main_menu(message)
    elif text in ["❌ Отмена", "❌ Bekor qilish"]:
        await handle_cancel(message)
    else:
        # Проверяем, не является ли сообщение номером товара
        if text.isdigit():
            await handle_product_selection(message)
        else:
            await message.answer("❌ Не понимаю команду. Используйте кнопки меню." if language == 'ru' else "❌ Buyruqni tushunmayman. Menyu tugmalaridan foydalaning.", 
                               reply_markup=get_main_menu(language))

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
        
        await message.answer(get_text('order_cancelled', language), 
                           reply_markup=get_main_menu(language))

# КАТАЛОГ
@dp.message(F.text.in_(["🛍️ Каталог", "🛍️ Katalog"]))
async def show_catalog(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала завершите регистрацию через /start")
        return
    
    phone, name, language, region, location = user
    
    if language == 'ru':
        text = "🛍️ Выберите категорию:"
    else:
        text = "🛍️ Toifani tanlang:"
    
    await message.answer(text, reply_markup=get_catalog_keyboard(language))

# КАТЕГОРИИ ТОВАРОВ
@dp.message(F.text.in_(["👕 Формы", "👕 Formalar"]))
async def show_forms_menu(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала завершите регистрацию через /start")
        return
    
    phone, name, language, region, location = user
    await message.answer("👕 Выберите тип форм:" if language == 'ru' else "👕 Formalar turini tanlang:", 
                       reply_markup=get_forms_submenu(language))

@dp.message(F.text.in_(["🕰️ Ретро формы", "🕰️ Retro formalar"]))
async def show_retro_forms(message: types.Message):
    await show_category_products(message, "Ретро", "Retro")

@dp.message(F.text.in_(["🔮 Формы 2025/2026", "🔮 2025/2026 Formalari"]))
async def show_new_forms(message: types.Message):
    await show_category_products(message, "Формы 2025/2026", "2025/2026 Formalari")

@dp.message(F.text.in_(["⚽ Бутсы", "⚽ Futbolkalar"]))
async def show_boots(message: types.Message):
    await show_category_products(message, "Бутсы", "Futbolkalar")

@dp.message(F.text.in_(["🔥 Акции", "🔥 Aksiyalar"]))
async def show_sales(message: types.Message):
    await show_category_products(message, "Акции", "Aksiyalar")

@dp.message(F.text.in_(["ℹ️ Помощь", "ℹ️ Yordam"]))
async def show_help(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала завершите регистрацию через /start")
        return
    
    phone, name, language, region, location = user
    await message.answer(get_text('help_text', language), parse_mode='HTML')
    support_requests[message.from_user.id] = {'waiting_question': True}

@dp.message(F.text.in_(["↩️ Назад", "↩️ Orqaga"]))
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
    
    phone, name, language, region, location = user
    
    if not location:
        text = "❌ Сначала укажите локацию!" if language == 'ru' else "❌ Avval manzilni ko'rsating!"
        await message.answer(text)
        return
        
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
    
    phone, name, language, region, location = user
    
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

@dp.message(F.text.in_(["✅ Да, добавить имя и номер", "✅ Ha, ism va raqam qo'shing", "❌ Нет, без кастомизации", "❌ Yo'q, be'zashsiz"]))
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
        user_sessions[message.from_user.id]['step'] = 'waiting_customization_text'
    else:
        selection['customization'] = None
        category = selection['category']
        
        if language == 'ru':
            text = f"🛒 Вы выбрали:\n\n📦 {selection['product_name']}\n💵 {format_price(selection['product_price'], language)}\n\n{get_text('choose_size', language)}"
        else:
            text = f"🛒 Siz tanladingiz:\n\n📦 {selection['product_name']}\n💵 {format_price(selection['product_price'], language)}\n\n{get_text('choose_size', language)}"
        
        await message.answer(text, reply_markup=get_size_keyboard(language, category))

@dp.message(F.text)
async def handle_customization_text(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    
    if session.get('step') != 'waiting_customization_text':
        return await handle_text_messages(message)
    
    user = get_user(user_id)
    if not user or user_id not in user_selections:
        return
    
    language = user[2]
    selection = user_selections[user_id]
    
    selection['customization']['text'] = message.text
    user_sessions[user_id]['step'] = None
    
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
    selection = user_selections[callback.from_user.id]
    
    selection['size'] = size
    
    if callback.from_user.id not in user_carts:
        user_carts[callback.from_user.id] = []
    
    user_carts[callback.from_user.id].append(selection.copy())
    
    await show_cart(callback.from_user.id, language, callback.message)
    await callback.answer()

@dp.callback_query(F.data == "size_help")
async def handle_size_help(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Сначала завершите регистрацию")
        return
    
    language = user[2]
    
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

# КОРЗИНА
@dp.message(F.text.in_(["🛒 Корзина", "🛒 Savat"]))
async def show_cart_command(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала завершите регистрацию")
        return
    
    language = user[2]
    await show_cart(message.from_user.id, language, message)

@dp.message(F.text.in_(["➕ Добавить еще товар", "➕ Yana mahsulot qo'shish"]))
async def add_more_products(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    language = user[2]
    await message.answer("📋 Выберите категорию:" if language == 'ru' else "📋 Toifani tanlang:", 
                       reply_markup=get_main_menu(language))

@dp.message(F.text.in_(["💳 Оформить заказ", "💳 Buyurtma berish"]))
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

@dp.message(F.text.in_(["🗑️ Очистить корзину", "🗑️ Savatni tozalash"]))
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
@dp.message(F.text.in_(["💳 Перевод на карту", "💳 Karta orqali to'lash", "💵 Наличные", "💵 Naqd pul"]))
async def handle_payment(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return
    
    phone, name, language, region, location = user
    
    is_card = message.text in ["💳 Перевод на карту", "💳 Karta orqali to'lash"]
    
    if 'checkout_cart' in user_sessions.get(message.from_user.id, {}):
        # Оформление всей корзины
        cart = user_sessions[message.from_user.id]['checkout_cart']
        total_price = sum(item['product_price'] + (item.get('customization', {}).get('price', 0) if item.get('customization') else 0) for item in cart)
        
        if is_card:
            order_ids = []
            for item in cart:
                order_id = save_order(
                    message.from_user.id, phone, name, region, location,
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
            user_sessions[message.from_user.id]['waiting_receipt'] = True
            user_sessions[message.from_user.id]['order_ids'] = order_ids
                
        else:
            for item in cart:
                order_id = save_order(
                    message.from_user.id, phone, name, region, location,
                    item['product_name'], item['product_price'],
                    item.get('size'),
                    item.get('customization', {}).get('text') if item.get('customization') else None,
                    item.get('customization', {}).get('price', 0) if item.get('customization') else 0,
                    'cash'
                )
            
            if language == 'ru':
                text = f"✅ Заказы приняты! Всего {len(cart)} товара(ов)\n\n💵 Сумма: {format_price(total_price, language)}\n💵 Оплата: наличными при получении\n\nМы свяжемся с вами для подтверждения!"
            else:
                text = f"✅ Buyurtmalar qabul qilindi! Jami {len(cart)} mahsulot\n\n💵 Summa: {format_price(total_price, language)}\n💵 To'lov: yetkazib berishda naqd pul\n\nTasdiqlash uchun siz bilan bog'lanamiz!"
            
            await message.answer(text, reply_markup=get_main_menu(language))
            
            order_text = (
                f"🆕 НАЛИЧНЫЕ ЗАКАЗЫ\n\n"
                f"👤 {name} (@{message.from_user.username or 'N/A'})\n"
                f"📞 {phone}\n"
                f"🏙️ {REGIONS['ru'].get(region, region)}\n"
                f"📍 {location}\n"
                f"📦 Товаров: {len(cart)}\n"
                f"💵 Сумма: {format_price(total_price, 'ru')}\n"
                f"💰 Наличные\n"
                f"🕒 {datetime.now().strftime('%H:%M %d.%m.%Y')}"
            )
            await notify_admins(order_text)
        
        if not is_card:
            if message.from_user.id in user_carts:
                del user_carts[message.from_user.id]
            if 'checkout_cart' in user_sessions[message.from_user.id]:
                del user_sessions[message.from_user.id]['checkout_cart']
    
    else:
        # Старая логика для одного товара
        if message.from_user.id not in user_selections:
            if language == 'ru':
                await message.answer("❌ Сначала выберите товар")
            else:
                await message.answer("❌ Avval mahsulotni tanlang")
            return
        
        selection = user_selections[message.from_user.id]
        product_name = selection['product_name']
        product_price = selection['product_price']
        product_size = selection.get('size', 'Не указан')
        customization_text = selection.get('customization', {}).get('text') if selection.get('customization') else None
        customization_price = selection.get('customization', {}).get('price', 0) if selection.get('customization') else 0
        
        if is_card:
            order_id = save_order(
                message.from_user.id, phone, name, region, location,
                product_name, product_price, product_size, customization_text, customization_price, 'card_pending'
            )
            
            if language == 'ru':
                text = (
                    f"💳 Перевод на карту\n\n"
                    f"📦 Заказ: {product_name}\n"
                    f"📏 Размер: {product_size}\n"
                    f"💵 Сумма: {format_price(product_price + customization_price, language)}\n\n"
                    f"🔄 Переведите на карту:\n"
                    f"<code>{CARD_NUMBER}</code>\n\n"
                    f"📸 После перевода отправьте скриншот чека\n"
                    f"Мы подтвердим заказ в течение 15 минут!"
                )
            else:
                text = (
                    f"💳 Karta orqali to'lash\n\n"
                    f"📦 Buyurtma: {product_name}\n"
                    f"📏 Oʻlcham: {product_size}\n"
                    f"💵 Summa: {format_price(product_price + customization_price, language)}\n\n"
                    f"🔄 Kartaga o'tkazing:\n"
                    f"<code>{CARD_NUMBER}</code>\n\n"
                    f"📸 O'tkazishdan so'ng chek skrinshotini yuboring\n"
                    f"Buyurtmani 15 daqiqa ichida tasdiqlaymiz!"
                )
            
            await message.answer(text, parse_mode='HTML')
            user_sessions[message.from_user.id]['waiting_receipt'] = True
            user_sessions[message.from_user.id]['order_id'] = order_id
                
        else:
            order_id = save_order(
                message.from_user.id, phone, name, region, location,
                product_name, product_price, product_size, customization_text, customization_price, 'cash'
            )
            
            if language == 'ru':
                text = f"✅ Заказ #{order_id} принят!\n\n📦 {product_name}\n📏 Размер: {product_size}\n💵 {format_price(product_price + customization_price, language)}\n💵 Оплата: наличными при получении\n\nМы свяжемся с вами для подтверждения!"
            else:
                text = f"✅ #{order_id}-buyurtma qabul qilindi!\n\n📦 {product_name}\n📏 Oʻlcham: {product_size}\n💵 {format_price(product_price + customization_price, language)}\n💵 To'lov: yetkazib berishda naqd pul\n\nTasdiqlash uchun siz bilan bog'lanamiz!"
            
            await message.answer(text, reply_markup=get_main_menu(language))
            
            order_text = (
                f"🆕 НАЛИЧНЫЙ ЗАКАЗ #{order_id}\n\n"
                f"👤 {name} (@{message.from_user.username or 'N/A'})\n"
                f"📞 {phone}\n"
                f"🏙️ {REGIONS['ru'].get(region, region)}\n"
                f"📍 {location}\n"
                f"📦 {product_name}\n"
                f"📏 Размер: {product_size}\n"
                f"💵 {format_price(product_price + customization_price, 'ru')}\n"
                f"💰 Наличные\n"
                f"🕒 {datetime.now().strftime('%H:%M %d.%m.%Y')}"
            )
            await notify_admins(order_text)
        
        if not is_card and message.from_user.id in user_selections:
            del user_selections[message.from_user.id]

# ЧЕКИ
@dp.message(F.photo)
async def handle_receipt_photo(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    
    if not session.get('waiting_receipt'):
        return
    
    user = get_user(user_id)
    if not user:
        return
    
    phone, name, language, region, location = user
    
    if 'order_ids' in session:
        # Обработка нескольких заказов из корзины
        order_ids = session['order_ids']
        for order_id in order_ids:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE orders SET status = 'waiting_confirm', receipt_photo_id = ? WHERE id = ?",
                    (message.photo[-1].file_id, order_id)
                )
                conn.commit()
        
        admin_text = (
            f"📸 ПОСТУПИЛ ЧЕК ДЛЯ {len(order_ids)} ЗАКАЗОВ\n\n"
            f"👤 Клиент: {name} (@{message.from_user.username or 'N/A'})\n"
            f"📞 Телефон: {phone}\n"
            f"🏙️ Регион: {REGIONS['ru'].get(region, region)}\n"
            f"📍 Адрес: {location}\n"
            f"🆔 Заказы: {', '.join([f'#{oid}' for oid in order_ids])}\n\n"
            f"✅ Для подтверждения: /confirm_all_{user_id}\n"
            f"❌ Для отмены: /cancel_all_{user_id}"
        )
        
    else:
        # Обработка одного заказа
        order_id = session['order_id']
        selection = user_selections.get(user_id, {})
        product_size = selection.get('size', 'Не указан')
        customization_text = selection.get('customization', {}).get('text') if selection.get('customization') else None
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE orders SET status = 'waiting_confirm', receipt_photo_id = ? WHERE id = ?",
                (message.photo[-1].file_id, order_id)
            )
            conn.commit()
        
        admin_text = (
            f"📸 ПОСТУПИЛ ЧЕК\n\n"
            f"🆔 Заказ: #{order_id}\n"
            f"👤 Клиент: {name} (@{message.from_user.username or 'N/A'})\n"
            f"📞 Телефон: {phone}\n"
            f"🏙️ Регион: {REGIONS['ru'].get(region, region)}\n"
            f"📍 Адрес: {location}\n"
            f"📦 Товар: {selection.get('product_name', 'N/A')}\n"
            f"📏 Размер: {product_size}\n"
            f"✨ Кастомизация: {customization_text or 'Нет'}\n"
            f"💵 Сумма: {format_price(selection.get('product_price', 0) + (selection.get('customization', {}).get('price', 0) if selection.get('customization') else 0), 'ru')}\n\n"
            f"✅ Для подтверждения: /confirm_{order_id}\n"
            f"❌ Для отмены: /cancel_{order_id}"
        )
    
    await notify_admins(admin_text, message.photo[-1].file_id)
    
    if language == 'ru':
        text = "✅ Чек получен! Ожидайте подтверждения в течение 15 минут."
    else:
        text = "✅ Chek qabul qilindi! 15 daqiqa ichida tasdiqlanishini kuting."
    
    await message.answer(text, reply_markup=get_main_menu(language))
    
    # Очистка
    user_sessions[user_id]['waiting_receipt'] = False
    if 'order_id' in user_sessions[user_id]:
        del user_sessions[user_id]['order_id']
    if 'order_ids' in user_sessions[user_id]:
        del user_sessions[user_id]['order_ids']
    if user_id in user_selections:
        del user_selections[user_id]
    if user_id in user_carts:
        del user_carts[user_id]

# ПОДДЕРЖКА
@dp.message()
async def handle_support_question(message: types.Message):
    user_id = message.from_user.id
    
    if user_id in support_requests and support_requests[user_id].get('waiting_question'):
        user = get_user(user_id)
        if not user:
            return
        
        language = user[2]
        question = message.text
        
        support_requests[user_id] = {
            'question': question,
            'waiting_admin': True,
            'language': language
        }
        
        admin_text = (
            f"❓ <b>НОВЫЙ ВОПРОС ОТ ПОЛЬЗОВАТЕЛЯ</b>\n\n"
            f"👤 {user[1]} (@{message.from_user.username or 'N/A'})\n"
            f"📞 {user[0]}\n"
            f"🌍 {REGIONS['ru'].get(user[3], user[3])}\n\n"
            f"💬 <b>Вопрос:</b>\n{question}\n\n"
            f"✍️ <b>Ответьте на это сообщение, чтобы ответить пользователю</b>"
        )
        
        for admin_id in ADMIN_IDS:
            try:
                sent_msg = await bot.send_message(admin_id, admin_text, parse_mode='HTML')
                support_requests[user_id]['admin_message_id'] = sent_msg.message_id
            except Exception as e:
                logging.error(f"Ошибка отправки админу: {e}")
        
        if language == 'ru':
            await message.answer("✅ Ваш вопрос отправлен! Ожидайте ответа в ближайшее время.")
        else:
            await message.answer("✅ Savolingiz yuborildi! Tez orada javob kutiling.")
        
        support_requests[user_id]['waiting_question'] = False

# ОТВЕТЫ АДМИНОВ
@dp.message(F.reply_to_message)
async def handle_admin_reply(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    replied_message = message.reply_to_message
    admin_response = message.text
    
    for user_id, request in support_requests.items():
        if request.get('admin_message_id') == replied_message.message_id:
            user = get_user(user_id)
            if not user:
                continue
            
            language = request['language']
            
            # УБИРАЕМ ИИ - просто отправляем ответ как есть
            improved_response = admin_response
            
            if language == 'ru':
                response_text = f"🤝 <b>Ответ поддержки:</b>\n\n{improved_response}"
            else:
                response_text = f"🤝 <b>Yordam xizmati javobi:</b>\n\n{improved_response}"
            
            try:
                await bot.send_message(user_id, response_text, parse_mode='HTML')
                await message.answer("✅ Ответ отправлен пользователю")
                del support_requests[user_id]
            except Exception as e:
                await message.answer(f"❌ Ошибка отправки пользователю: {e}")
            break

# АДМИН КОМАНДЫ
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await message.answer("👑 Панель администратора:", reply_markup=get_admin_menu())

@dp.message(F.text == "➕ Добавить товар")
async def start_product_creation(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    admin_product_creation[message.from_user.id] = {'step': 'waiting_photo'}
    await message.answer("📸 Пришлите фото товара:")

@dp.message(F.text == "📊 Статистика")
async def show_admin_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
        
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'new'")
        new_orders = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'waiting_confirm'")
        waiting_confirm = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'confirmed'")
        confirmed_orders = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM products")
        total_products = cursor.fetchone()[0]
    
    await message.answer(
        f"📊 СТАТИСТИКА\n\n"
        f"🆕 Новых заказов: {new_orders}\n"
        f"📸 Ожидают подтверждения: {waiting_confirm}\n"
        f"✅ Подтвержденных: {confirmed_orders}\n"
        f"👥 Пользователей: {total_users}\n"
        f"🏷️ Товаров: {total_products}\n\n"
        f"🕒 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

@dp.message(F.text == "📦 Заказы")
async def show_admin_orders(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_name, product_name, product_price, status, created_at 
            FROM orders ORDER BY created_at DESC LIMIT 10
        """)
        orders = cursor.fetchall()
    
    if not orders:
        await message.answer("📦 Нет заказов")
        return
    
    orders_text = "📦 ПОСЛЕДНИЕ ЗАКАЗЫ:\n\n"
    for order in orders:
        order_id, user_name, product_name, product_price, status, created_at = order
        status_icon = "✅" if status == "confirmed" else "🔄" if status == "waiting_confirm" else "🆕"
        orders_text += f"{status_icon} #{order_id} - {user_name}\n"
        orders_text += f"   {product_name}\n"
        orders_text += f"   💵 {format_price(product_price, 'ru')}\n"
        orders_text += f"   📅 {created_at[:16]}\n\n"
    
    await message.answer(orders_text)

@dp.message(F.text == "⭐ Управление отзывами")
async def manage_reviews(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="👀 Просмотр отзывов"))
    builder.add(KeyboardButton(text="➕ Добавить отзыв"))
    builder.add(KeyboardButton(text="🔙 Назад в админку"))
    builder.adjust(2, 1)
    
    await message.answer("⭐ Управление отзывами:", reply_markup=builder.as_markup(resize_keyboard=True))

@dp.message(F.text == "👀 Просмотр отзывов")
async def show_admin_reviews(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT customer_name, review_text_ru, photo_url, rating FROM reviews ORDER BY created_at DESC LIMIT 10")
        reviews = cursor.fetchall()
    
    if not reviews:
        await message.answer("😔 Нет отзывов")
        return
    
    for review in reviews:
        customer_name, review_text, photo_url, rating = review
        stars = "⭐" * rating
        
        caption = f"{stars}\n👤 {customer_name}\n💬 {review_text}"
        
        try:
            if photo_url:
                await bot.send_photo(message.chat.id, photo_url, caption=caption)
            else:
                await message.answer(caption)
        except:
            await message.answer(caption)
    
    await message.answer("📢 Канал с отзывами: https://t.me/footballkitsreview")

@dp.message(F.text == "➕ Добавить отзыв")
async def add_review_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await message.answer(
        "✍️ Добавление отзыва:\n\n"
        "Отправьте в формате:\n"
        "<code>Имя | Текст отзыва | Рейтинг</code>\n\n"
        "Пример:\n"
        "<code>Алишер | Отличное качество! | 5</code>"
    )
    admin_product_creation[message.from_user.id] = {'step': 'waiting_review'}

@dp.message(F.text.contains('|'))
async def handle_review_creation(message: types.Message):
    if (message.from_user.id not in ADMIN_IDS or 
        message.from_user.id not in admin_product_creation or
        admin_product_creation[message.from_user.id].get('step') != 'waiting_review'):
        return
    
    try:
        data = message.text.split('|')
        if len(data) >= 3:
            customer_name = data[0].strip()
            review_text = data[1].strip()
            rating = int(data[2].strip())
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO reviews (customer_name, review_text_ru, review_text_uz, rating)
                    VALUES (?, ?, ?, ?)
                """, (customer_name, review_text, review_text, rating))
                conn.commit()
            
            await message.answer("✅ Отзыв добавлен!")
            
        else:
            await message.answer("❌ Неверный формат. Нужно: Имя | Текст | Рейтинг")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    
    if message.from_user.id in admin_product_creation:
        del admin_product_creation[message.from_user.id]

# БЫСТРОЕ СОЗДАНИЕ ТОВАРОВ
@dp.message(Command("add"))
async def quick_add_product(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await message.answer(
        "🎯 <b>Быстрое создание товара</b>\n\n"
        "Отправьте в ОДНОМ сообщении:\n"
        "• Фото товара\n" 
        "• Название\n"
        "• Цена\n"
        "• Категория\n"
        "• Размеры\n\n"
        "<b>Пример:</b>\n"
        "<code>Форма Пахтакор 2025\n"
        "180000\n"
        "Формы\n"
        "S, M, L, XL</code>",
        parse_mode='HTML'
    )
    admin_product_creation[message.from_user.id] = {'step': 'waiting_quick_data'}

@dp.message(F.photo)
async def handle_quick_product_creation(message: types.Message):
    if (message.from_user.id not in ADMIN_IDS or 
        message.from_user.id not in admin_product_creation or
        not message.caption):
        return
    
    try:
        # Парсим данные из подписи к фото
        lines = message.caption.split('\n')
        if len(lines) >= 4:
            name_ru = lines[0].strip()
            price = int(lines[1].strip())
            category_ru = lines[2].strip()
            sizes_ru = lines[3].strip()
            
            # Автогенерация остальных данных
            category_map = {
                'Формы': ('Формы', 'Formalar'),
                'Бутсы': ('Бутсы', 'Futbolkalar'), 
                'Акции': ('Акции', 'Aksiyalar'),
                'Ретро': ('Ретро', 'Retro')
            }
            
            category_ru, category_uz = category_map.get(category_ru, ('Формы', 'Formalar'))
            
            # Автоперевод названия (простая версия)
            name_uz = name_ru
            if 'форма' in name_ru.lower():
                name_uz = name_ru.replace('форма', 'formasi').replace('Форма', 'Formasi')
            elif 'бутсы' in name_ru.lower():
                name_uz = name_ru.replace('бутсы', 'futbolka').replace('Бутсы', 'Futbolka')
            
            # Сохраняем в базу
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO products 
                    (name_ru, name_uz, price, category_ru, category_uz, image_url, description_ru, description_uz, sizes_ru, sizes_uz)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    name_ru,
                    name_uz,
                    price,
                    category_ru,
                    category_uz,
                    message.photo[-1].file_id,
                    f"Качественный товар: {name_ru}",
                    f"Sifatli mahsulot: {name_uz}", 
                    f"Размеры: {sizes_ru}",
                    f"Oʻlchamlar: {sizes_ru}"
                ))
                conn.commit()
                product_id = cursor.lastrowid
            
            # Создаем и показываем карточку
            product = (
                product_id,
                name_ru,
                price,
                message.photo[-1].file_id,
                f"Качественный товар: {name_ru}",
                f"Размеры: {sizes_ru}"
            )
            
            await send_product_card(message.chat.id, product, 'ru')
            await message.answer("✅ <b>Готово, Сэр! Товар добавлен!</b>", parse_mode='HTML')
            
        else:
            await message.answer("❌ Недостаточно данных. Нужно: название, цена, категория, размеры")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    
    # Очищаем сессию
    if message.from_user.id in admin_product_creation:
        del admin_product_creation[message.from_user.id]

# СИСТЕМА ОТЗЫВОВ
@dp.message(F.text.in_(["⭐ Мнения клиентов", "⭐ Mijozlar fikri"]))
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

@dp.message(F.text.in_(["⭐ Посмотреть отзывы", "⭐ Sharhlarni ko'rish"]))
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

@dp.message(F.text.in_(["✍️ Оставить отзыв", "✍️ Sharh qoldirish"]))
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

@dp.message(F.text)
async def handle_review_text(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_sessions or not user_sessions[user_id].get('waiting_review'):
        return
    
    user = get_user(user_id)
    if not user:
        return
    
    language = user[2]
    review_text = message.text
    
    # Сохраняем отзыв в базу
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO reviews (customer_name, review_text_ru, review_text_uz, rating)
            VALUES (?, ?, ?, ?)
        """, (user[1], review_text, review_text, 5))
        conn.commit()
    
    # Уведомляем админов
    admin_text = (
        f"📝 НОВЫЙ ОТЗЫВ\n\n"
        f"👤 {user[1]} (@{message.from_user.username or 'N/A'})\n"
        f"📞 {user[0]}\n"
        f"💬 {review_text}\n\n"
        f"✅ Чтобы добавить в канал, перешлите это сообщение в @footballkitsreview"
    )
    
    await notify_admins(admin_text)
    
    if language == 'ru':
        await message.answer("✅ Спасибо за ваш отзыв! Мы ценим ваше мнение!", 
                           reply_markup=get_main_menu(language))
    else:
        await message.answer("✅ Sharhingiz uchun rahmat! Biz sizning fikringizni qadrlaymiz!", 
                           reply_markup=get_main_menu(language))
    
    del user_sessions[user_id]['waiting_review']

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
        
        del user_sessions[user_id]['waiting_review']

# АДМИН КОМАНДЫ ПОДТВЕРЖДЕНИЯ
@dp.message(F.text.startswith('/confirm_'))
async def confirm_order(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        order_id = int(message.text.split('_')[1])
        update_order_status(order_id, ORDER_CONFIRMED, message.from_user.id)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, product_name, product_price FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
        
        if order:
            user_id, product_name, product_price = order
            user = get_user(user_id)
            if user:
                phone, name, language, region, location = user
                if language == 'ru':
                    text = f"✅ Заказ #{order_id} подтвержден! Спасибо за оплату!"
                else:
                    text = f"✅ #{order_id}-buyurtma tasdiqlandi! To'lov uchun rahmat!"
                
                await bot.send_message(user_id, text)
        
        await message.answer(f"✅ Заказ #{order_id} подтвержден!")
        
    except Exception as e:
        await message.answer("❌ Ошибка подтверждения заказа")

@dp.message(F.text.startswith('/cancel_'))
async def cancel_order(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        order_id = int(message.text.split('_')[1])
        update_order_status(order_id, ORDER_CANCELLED)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
        
        if order:
            user_id = order[0]
            user = get_user(user_id)
            if user:
                phone, name, language, region, location = user
                if language == 'ru':
                    text = f"❌ Заказ #{order_id} отменен. Чек не прошел проверку."
                else:
                    text = f"❌ #{order_id}-buyurtma bekor qilindi. Chek tekshiruvdan o'tmadi."
                
                await bot.send_message(user_id, text)
        
        await message.answer(f"❌ Заказ #{order_id} отменен!")
        
    except Exception as e:
        await message.answer("❌ Ошибка отмены заказа")

# МОИ ЗАКАЗЫ
@dp.message(F.text.in_(["📦 Мои заказы", "📦 Mening buyurtmalarim"]))
async def show_my_orders(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала завершите регистрацию через /start")
        return
    
    phone, name, language, region, location = user
    orders = get_user_orders(message.from_user.id, language)
    
    if orders:
        if language == 'ru':
            response = "📦 Ваши заказы:\n\n"
        else:
            response = "📦 Sizning buyurtmalaringiz:\n\n"
            
        for i, (product_name, product_price, customization_price, status, payment, created_at) in enumerate(orders, 1):
            total_price = product_price + (customization_price or 0)
            status_icon = "✅" if status == "confirmed" else "🔄" if status == "waiting_confirm" else "🆕"
            payment_icon = "💳" if payment == "card_pending" else "💵"
            
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
        print("🛍️ Админ-панель для создания товаров активирована!")
        print("📱 Регистрация через контакт или ручной ввод номера")
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())