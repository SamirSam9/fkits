import asyncio
import logging
import sqlite3
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
CARD_NUMBER = os.getenv('CARD_NUMBER')
ADMIN_IDS = [5009858379, 587180281, 1225271746]

# Константы для статусов заказов
ORDER_NEW = 'new'
ORDER_WAITING_CONFIRM = 'waiting_confirm'
ORDER_CONFIRMED = 'confirmed'
ORDER_CANCELLED = 'cancelled'

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
            sizes_uz TEXT
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
            payment_method TEXT DEFAULT 'cash',
            status TEXT DEFAULT 'new',
            receipt_photo_id TEXT,
            confirmed_by INTEGER,
            confirmed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        test_products = [
            # Бутсы
            ('Бутсы Nike Mercurial Superfly 9', 'Nike Mercurial Superfly 9 futbolka', 450000, 'Бутсы', 'Futbolkalar', 
             'https://example.com/mercurial.jpg', 'Инновационные бутсы для скорости', 'Tezlik uchun innovatsion futbolka',
             'Размеры: 40, 41, 42, 43, 44', 'Oʻlchamlar: 40, 41, 42, 43, 44'),
            
            ('Бутсы Adidas Predator Accuracy', 'Adidas Predator Accuracy futbolka', 420000, 'Бутсы', 'Futbolkalar',
             'https://example.com/predator.jpg', 'Премиум контроль мяча', 'Premium toʻp nazorati',
             'Размеры: 39, 40, 41, 42, 43', 'Oʻlchamlar: 39, 40, 41, 42, 43'),
            
            # Формы (Ретро)
            ('Ретро форма Узбекистан 1994', 'Oʻzbekiston 1994 retro formasi', 250000, 'Ретро', 'Retro',
             'https://example.com/retro1994.jpg', 'Легендарная ретро форма', 'Afsonaviy retro forma',
             'Размеры: S, M, L, XL', 'Oʻlchamlar: S, M, L, XL'),
            
            ('Ретро форма Пахтакор 2000', 'Paxtakor 2000 retro formasi', 220000, 'Ретро', 'Retro',
             'https://example.com/retropaxtakor.jpg', 'Классическая форма Пахтакора', 'Paxtakorning klassik formasi',
             'Размеры: S, M, L, XL', 'Oʻlchamlar: S, M, L, XL'),
            
            # Формы (2025/2026)
            ('Форма Пахтакор 2025', 'Paxtakor 2025 formasi', 180000, 'Формы 2025/2026', '2025/2026 Formalari',
             'https://example.com/paxtakor2025.jpg', 'Новая форма сезона 2025', '2025 yilgi yangi forma',
             'Размеры: S, M, L, XL, XXL', 'Oʻlchamlar: S, M, L, XL, XXL'),
            
            ('Форма Насаф 2026', 'Nasaf 2026 formasi', 170000, 'Формы 2025/2026', '2025/2026 Formalari',
             'https://example.com/nasaf2026.jpg', 'Стильная форма Насафа 2026', 'Nasafning uslubiy 2026 formasi',
             'Размеры: S, M, L, XL', 'Oʻlchamlar: S, M, L, XL'),
            
            # Акции
            ('🔥 АКЦИЯ: Форма + бутсы', '🔥 AKSIYA: Forma + futbolka', 550000, 'Акции', 'Aksiyalar',
             'https://example.com/combo.jpg', 'Выгодный комплект', 'Foydali komplekt',
             'Комплект: форма L + бутсы 42', 'Komplekt: L forma + 42 futbolka'),
            
            ('⚡ Скидка 20% на ретро', '⚡ 20% chegirma retroga', 200000, 'Акции', 'Aksiyalar',
             'https://example.com/sale.jpg', 'Специальное предложение', 'Maxsus taklif',
             'Размеры: M, L, XL', 'Oʻlchamlar: M, L, XL')
        ]
        cursor.executemany("""
            INSERT INTO products (name_ru, name_uz, price, category_ru, category_uz, image_url, description_ru, description_uz, sizes_ru, sizes_uz) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, test_products)
    
    conn.commit()
    conn.close()
    print("✅ База данных готова")

# ================== ХРАНЕНИЕ ДАННЫХ ПОЛЬЗОВАТЕЛЕЙ ==================
user_sessions = {}
user_selections = {}

# ================== РЕГИОНЫ И ОТДЕЛЕНИЯ ==================
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
        'ru': ['📮 Чиланзар', '📮 Юнусабад', '📮 Мирзо-Улугбек', '📮 Шайхантахур', '📮 Алмазар'],
        'uz': ['📮 Chilanzar', '📮 Yunusobod', '📮 Mirzo-Ulugʻbek', '📮 Shayxontohur', '📮 Olmazar']
    },
    'andijan': {
        'ru': ['📮 Центральное отделение', '📮 Отделение №2'],
        'uz': ['📮 Markaziy boʻlim', '📮 Boʻlim №2']
    },
    'karakalpakstan': {
        'ru': ['📮 Нукус центральный', '📮 Отделение Ходжейли'],
        'uz': ['📮 Nukus markaziy', '📮 Xoʻjayli boʻlimi']
    }
}

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

def get_phone_confirmation_keyboard(language):
    builder = ReplyKeyboardBuilder()
    if language == 'ru':
        builder.add(KeyboardButton(text="✅ Да, это мой номер"))
        builder.add(KeyboardButton(text="❌ Нет, изменить номер"))
    else:
        builder.add(KeyboardButton(text="✅ Ha, bu mening raqamim"))
        builder.add(KeyboardButton(text="❌ Yoʻq, raqamni oʻzgartirish"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

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
    offices = POST_OFFICES.get(region, {}).get(language, [])
    for office in offices:
        builder.add(KeyboardButton(text=office))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

def get_main_menu(language):
    builder = ReplyKeyboardBuilder()
    
    if language == 'ru':
        builder.add(KeyboardButton(text="👕 Формы"))
        builder.add(KeyboardButton(text="⚽ Бутсы")) 
        builder.add(KeyboardButton(text="🔥 Акции"))
        builder.add(KeyboardButton(text="📦 Мои заказы"))
        builder.add(KeyboardButton(text="ℹ️ Помощь"))
    else:
        builder.add(KeyboardButton(text="👕 Formalar"))
        builder.add(KeyboardButton(text="⚽ Futbolkalar")) 
        builder.add(KeyboardButton(text="🔥 Aksiyalar"))
        builder.add(KeyboardButton(text="📦 Mening buyurtmalarim"))
        builder.add(KeyboardButton(text="ℹ️ Yordam"))
    
    builder.adjust(2, 2, 1)
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

def get_size_keyboard(language):
    builder = InlineKeyboardBuilder()
    
    if language == 'ru':
        sizes = [("S", "size_S"), ("M", "size_M"), ("L", "size_L"), ("XL", "size_XL"), ("XXL", "size_XXL")]
        for size, callback_data in sizes:
            builder.add(types.InlineKeyboardButton(text=size, callback_data=callback_data))
    else:
        sizes = [("S", "size_S"), ("M", "size_M"), ("L", "size_L"), ("XL", "size_XL"), ("XXL", "size_XXL")]
        for size, callback_data in sizes:
            builder.add(types.InlineKeyboardButton(text=size, callback_data=callback_data))
    
    builder.adjust(5)
    return builder.as_markup()

def get_back_menu(language):
    text = "↩️ Назад" if language == 'ru' else "↩️ Orqaga"
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text)]],
        resize_keyboard=True
    )

# ================== ТЕКСТЫ НА ДВУХ ЯЗЫКАХ ==================
def get_text(key, language):
    texts = {
        'welcome': {
            'ru': "👋 Добро пожаловать в FootballKits.uz! Выберите язык:",
            'uz': "👋 FootballKits.uz ga xush kelibsiz! Tilni tanlang:"
        },
        'contact_request': {
            'ru': "📞 Для продолжения поделитесь контактом:",
            'uz': "📞 Davom etish uchun kontaktni ulashing:"
        },
        'phone_confirmation': {
            'ru': f"📱 Это ваш основной номер? Подтверждая эту информацию, вы соглашаетесь, что почта будет отправлена исключительно на этот номер для получения SMS от почтовой службы.",
            'uz': f"📱 Bu sizning asosiy raqamingizmi? Ushbu maʼlumotni tasdiqlasangiz, pochta xizmatidan SMS olish uchun pochta faqat shu raqamga yuborilishiga rozilik bildirasiz."
        },
        'region_request': {
            'ru': "🏙️ Выберите ваш регион:",
            'uz': "🏙️ Viloyatingizni tanlang:"
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
        'location_received': {
            'ru': "✅ Локация получена! Теперь вы можете выбирать товары:",
            'uz': "✅ Manzil qabul qilindi! Endi mahsulotlarni tanlashingiz mumkin:"
        },
        'post_office_received': {
            'ru': "✅ Отделение выбрано! Теперь вы можете выбирать товары:",
            'uz': "✅ Boʻlim tanlandi! Endi mahsulotlarni tanlashingiz mumkin:"
        },
        'no_contact': {
            'ru': "❌ Сначала поделитесь контактом!",
            'uz': "❌ Avval kontaktni ulashing!"
        },
        'no_region': {
            'ru': "❌ Сначала выберите регион!",
            'uz': "❌ Avval viloyatni tanlang!"
        },
        'help_text': {
            'ru': "🤝 Помощь\n\n📞 Служба поддержки: +998901234567\n📍 Адрес: Ташкент, Чорсу\n⏰ Время работы: 9:00-18:00\n\nВыберите категорию товаров:",
            'uz': "🤝 Yordam\n\n📞 Qo'llab-quvvatlash: +998901234567\n📍 Manzil: Toshkent, Chorsu\n⏰ Ish vaqti: 9:00-18:00\n\nMahsulot toifasini tanlang:"
        },
        'order_cancelled': {
            'ru': "❌ Заказ отменен",
            'uz': "❌ Buyurtma bekor qilindi"
        },
        'choose_size': {
            'ru': "📏 Выберите размер:",
            'uz': "📏 Oʻlchamni tanlang:"
        },
        'size_selected': {
            'ru': "✅ Размер выбран: ",
            'uz': "✅ Oʻlcham tanlandi: "
        }
    }
    return texts.get(key, {}).get(language, key)

# ================== БАЗА ДАННЫХ ==================
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

def save_order(user_id, phone, name, region, location, product_name, product_price, product_size=None, payment_method='cash'):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO orders (user_id, user_phone, user_name, user_region, user_location, product_name, product_price, product_size, payment_method) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, phone, name, region, location, product_name, product_price, product_size, payment_method)
        )
        order_id = cursor.lastrowid
        conn.commit()
        return order_id

def get_user_orders(user_id, language):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT product_name, product_price, status, payment_method, created_at 
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
    """Отправляет красивую карточку товара"""
    product_id, name, price, image_url, description, sizes = product
    
    if language == 'ru':
        caption = (
            f"🏷️ <b>{name}</b>\n\n"
            f"📝 {description}\n\n"
            f"📏 {sizes}\n\n"
            f"💵 <b>{format_price(price, language)}</b>\n\n"
            f"🆔 ID: <code>{product_id}</code>\n\n"
            f"✨ Чтобы заказать, напишите номер товара"
        )
    else:
        caption = (
            f"🏷️ <b>{name}</b>\n\n"
            f"📝 {description}\n\n"
            f"📏 {sizes}\n\n"
            f"💵 <b>{format_price(price, language)}</b>\n\n"
            f"🆔 ID: <code>{product_id}</code>\n\n"
            f"✨ Buyurtma berish uchun mahsulot raqamini yozing"
        )
    
    try:
        # Пытаемся отправить с фото
        await bot.send_photo(
            chat_id=chat_id,
            photo=image_url,
            caption=caption,
            parse_mode='HTML',
            reply_markup=get_back_menu(language)
        )
    except Exception as e:
        # Если фото не загружается, отправляем текстом
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
    
    user_sessions[user_id]['step'] = 'phone_confirmation'
    user_sessions[user_id]['phone'] = phone
    user_sessions[user_id]['name'] = name
    
    await message.answer(get_text('contact_received', language))
    await message.answer(get_text('phone_confirmation', language), reply_markup=get_phone_confirmation_keyboard(language))

# ПОДТВЕРЖДЕНИЕ НОМЕРА
@dp.message(F.text.in_(["✅ Да, это мой номер", "✅ Ha, bu mening raqamim", "❌ Нет, изменить номер", "❌ Yoʻq, raqamni oʻzgartirish"]))
async def handle_phone_confirmation(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    
    if session.get('step') != 'phone_confirmation':
        return
    
    language = session.get('language', 'ru')
    phone = session.get('phone')
    name = session.get('name')
    
    if message.text in ["✅ Да, это мой номер", "✅ Ha, bu mening raqamim"]:
        # Подтвердили номер
        save_user(user_id, phone, name, language)
        user_sessions[user_id]['step'] = 'region'
        
        await message.answer(get_text('region_request', language), reply_markup=get_region_keyboard(language))
    else:
        # Хотят изменить номер
        user_sessions[user_id]['step'] = 'contact'
        await message.answer(get_text('contact_request', language), reply_markup=get_contact_keyboard(language))

# ВЫБОР РЕГИОНА
@dp.message(F.text)
async def handle_region(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    
    if session.get('step') != 'region':
        return await handle_text_messages(message)
    
    language = session.get('language', 'ru')
    text = message.text
    
    # Определяем выбранный регион
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
    
    # Сохраняем регион пользователя
    save_user(user_id, session['phone'], session['name'], language, selected_region)
    
    if selected_region == 'tashkent':
        # Для Ташкента запрашиваем локацию
        await message.answer(get_text('location_request_tashkent', language), 
                           reply_markup=get_location_keyboard(language))
    else:
        # Для других регионов показываем список почтовых отделений
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
    
    # Проверяем, что выбранное отделение есть в списке для региона
    offices = POST_OFFICES.get(region, {}).get(language, [])
    if message.text not in offices:
        await message.answer("❌ Пожалуйста, выберите отделение из списка")
        return
    
    # Сохраняем выбранное отделение как локацию
    location = message.text
    save_user(user_id, session['phone'], session['name'], language, region, location)
    
    user_sessions[user_id]['step'] = 'main_menu'
    user_sessions[user_id]['location'] = location
    
    await message.answer(get_text('post_office_received', language), 
                       reply_markup=get_main_menu(language))

# ПОЛУЧЕНИЕ ЛОКАЦИИ (только для Ташкента)
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
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала завершите регистрацию через /start")
        return
    
    phone, name, language, region, location = user
    
    # Обработка отмены
    if message.text in ["❌ Отмена", "❌ Bekor qilish"]:
        if message.from_user.id in user_selections:
            del user_selections[message.from_user.id]
        if message.from_user.id in user_sessions:
            user_sessions[message.from_user.id].pop('waiting_receipt', None)
        
        await message.answer(get_text('order_cancelled', language), 
                           reply_markup=get_main_menu(language))
        return
    
    await message.answer("❌ Не понимаю команду. Используйте кнопки меню.", 
                       reply_markup=get_main_menu(language))

# ОБРАБОТЧИКИ КАТЕГОРИЙ
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
    await message.answer(get_text('help_text', language), reply_markup=get_main_menu(language))

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
        text = get_text('no_location', language)
        await message.answer(text)
        return
        
    products = get_products_by_category(category_ru, language)
    
    if products:
        category_name = category_ru if language == 'ru' else category_uz
        if language == 'ru':
            await message.answer(f"🏷️ {category_name}:\n\n👇 Вот наши товары:")
        else:
            await message.answer(f"🏷️ {category_name}:\n\n👇 Bizning mahsulotlarimiz:")
            
        # Отправляем каждый товар красивой карточкой
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
            user_selections[message.from_user.id] = {
                'product_id': product_id,
                'product_name': product_name, 
                'product_price': product_price,
                'image_url': image_url
            }
            
            # Запрашиваем размер
            if language == 'ru':
                text = f"🛒 Вы выбрали:\n\n📦 {product_name}\n💵 {format_price(product_price, language)}\n\n{get_text('choose_size', language)}"
            else:
                text = f"🛒 Siz tanladingiz:\n\n📦 {product_name}\n💵 {format_price(product_price, language)}\n\n{get_text('choose_size', language)}"
                
            await message.answer(text, reply_markup=get_size_keyboard(language))
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

# ВЫБОР РАЗМЕРА
@dp.callback_query(F.data.startswith('size_'))
async def handle_size_selection(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user or callback.from_user.id not in user_selections:
        await callback.answer("❌ Сначала выберите товар")
        return
    
    language = user[2]
    size = callback.data.replace('size_', '')
    
    user_selections[callback.from_user.id]['size'] = size
    
    await callback.message.edit_text(
        f"{callback.message.text}\n\n{get_text('size_selected', language)}{size}",
        reply_markup=None
    )
    
    if language == 'ru':
        text = f"✅ Размер {size} выбран!\n\nВыберите способ оплаты:"
    else:
        text = f"✅ {size} oʻlcham tanlandi!\n\nTo'lov usulini tanlang:"
        
    await callback.message.answer(text, reply_markup=get_payment_menu(language))
    await callback.answer()

# ВЫБОР ОПЛАТЫ
@dp.message(F.text.in_(["💳 Перевод на карту", "💳 Karta orqali to'lash", "💵 Наличные", "💵 Naqd pul"]))
async def handle_payment(message: types.Message):
    user = get_user(message.from_user.id)
    if not user or message.from_user.id not in user_selections:
        if user:
            language = user[2]
            if language == 'ru':
                await message.answer("❌ Сначала выберите товар")
            else:
                await message.answer("❌ Avval mahsulotni tanlang")
        return
    
    selection = user_selections[message.from_user.id]
    product_name = selection['product_name']
    product_price = selection['product_price']
    product_size = selection.get('size', 'Не указан')
    phone, name, language, region, location = user
    
    is_card = message.text in ["💳 Перевод на карту", "💳 Karta orqali to'lash"]
    
    if is_card:
        order_id = save_order(message.from_user.id, phone, name, region, location, product_name, product_price, product_size, 'card_pending')
        
        if language == 'ru':
            text = (
                f"💳 Перевод на карту\n\n"
                f"📦 Заказ: {product_name}\n"
                f"📏 Размер: {product_size}\n"
                f"💵 Сумма: {format_price(product_price, language)}\n\n"
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
                f"💵 Summa: {format_price(product_price, language)}\n\n"
                f"🔄 Kartaga o'tkazing:\n"
                f"<code>{CARD_NUMBER}</code>\n\n"
                f"📸 O'tkazishdan so'ng chek skrinshotini yuboring\n"
                f"Buyurtmani 15 daqiqa ichida tasdiqlaymiz!"
            )
        
        await message.answer(text, parse_mode='HTML')
        user_sessions[message.from_user.id]['waiting_receipt'] = True
        user_sessions[message.from_user.id]['order_id'] = order_id
            
    else:  # Наличные
        order_id = save_order(message.from_user.id, phone, name, region, location, product_name, product_price, product_size, 'cash')
        if language == 'ru':
            text = f"✅ Заказ #{order_id} принят!\n\n📦 {product_name}\n📏 Размер: {product_size}\n💵 {format_price(product_price, language)}\n💵 Оплата: наличными при получении\n\nМы свяжемся с вами для подтверждения!"
        else:
            text = f"✅ #{order_id}-buyurtma qabul qilindi!\n\n📦 {product_name}\n📏 Oʻlcham: {product_size}\n💵 {format_price(product_price, language)}\n💵 To'lov: yetkazib berishda naqd pul\n\nTasdiqlash uchun siz bilan bog'lanamiz!"
        
        await message.answer(text, reply_markup=get_main_menu(language))
        
        # Уведомление админам о наличном заказе
        order_text = (
            f"🆕 НАЛИЧНЫЙ ЗАКАЗ #{order_id}\n\n"
            f"👤 {name} (@{message.from_user.username or 'N/A'})\n"
            f"📞 {phone}\n"
            f"🏙️ {REGIONS['ru'].get(region, region)}\n"
            f"📍 {location}\n"
            f"📦 {product_name}\n"
            f"📏 Размер: {product_size}\n"
            f"💵 {format_price(product_price, 'ru')}\n"
            f"💰 Наличные\n"
            f"🕒 {datetime.now().strftime('%H:%M %d.%m.%Y')}"
        )
        await notify_admins(order_text)
    
    # Очищаем выбор
    if not is_card and message.from_user.id in user_selections:
        del user_selections[message.from_user.id]

# ПРИЕМ СКРИНШОТОВ ЧЕКОВ (ПЕРЕСЫЛАЕТСЯ АДМИНАМ)
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
    order_id = session['order_id']
    selection = user_selections.get(user_id, {})
    product_size = selection.get('size', 'Не указан')
    
    # Сохраняем информацию о чеке
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE orders SET status = 'waiting_confirm', receipt_photo_id = ? WHERE id = ?",
            (message.photo[-1].file_id, order_id)
        )
        conn.commit()
    
    # Уведомление админам с ПЕРЕСЫЛКОЙ ФОТО ЧЕКА
    admin_text = (
        f"📸 ПОСТУПИЛ ЧЕК\n\n"
        f"🆔 Заказ: #{order_id}\n"
        f"👤 Клиент: {name} (@{message.from_user.username or 'N/A'})\n"
        f"📞 Телефон: {phone}\n"
        f"🏙️ Регион: {REGIONS['ru'].get(region, region)}\n"
        f"📍 Адрес: {location}\n"
        f"📦 Товар: {selection.get('product_name', 'N/A')}\n"
        f"📏 Размер: {product_size}\n"
        f"💵 Сумма: {format_price(selection.get('product_price', 0), 'ru')}\n\n"
        f"✅ Для подтверждения: /confirm_{order_id}\n"
        f"❌ Для отмены: /cancel_{order_id}"
    )
    
    # Пересылаем фото чека админам
    await notify_admins(admin_text, message.photo[-1].file_id)
    
    if language == 'ru':
        text = "✅ Чек получен! Ожидайте подтверждения в течение 15 минут."
    else:
        text = "✅ Chek qabul qilindi! 15 daqiqa ichida tasdiqlanishini kuting."
    
    await message.answer(text, reply_markup=get_main_menu(language))
    
    # Очищаем сессию
    user_sessions[user_id]['waiting_receipt'] = False
    if 'order_id' in user_sessions[user_id]:
        del user_sessions[user_id]['order_id']
    if user_id in user_selections:
        del user_selections[user_id]

# КОМАНДЫ ДЛЯ ПОДТВЕРЖДЕНИЯ АДМИНАМИ
@dp.message(F.text.startswith('/confirm_'))
async def confirm_order(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        order_id = int(message.text.split('_')[1])
        update_order_status(order_id, ORDER_CONFIRMED, message.from_user.id)
        
        # Получаем информацию о заказе
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
        
        # Уведомляем пользователя
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
            
        for i, (product_name, product_price, status, payment, created_at) in enumerate(orders, 1):
            status_icon = "✅" if status == "confirmed" else "🔄" if status == "waiting_confirm" else "🆕"
            payment_icon = "💳" if payment == "card_pending" else "💵"
            
            status_text = "Подтвержден" if status == "confirmed" else "Ожидает подтверждения" if status == "waiting_confirm" else "Новый"
            if language == 'uz':
                status_text = "Tasdiqlangan" if status == "confirmed" else "Tasdiqlanish kutilmoqda" if status == "waiting_confirm" else "Yangi"
            
            response += f"{i}. {product_name}\n"
            response += f"💵 {format_price(product_price, language)} {payment_icon}\n"
            response += f"{status_icon} {status_text}\n"
            response += f"📅 {created_at[:16]}\n\n"
    else:
        if language == 'ru':
            response = "📦 У вас еще нет заказов"
        else:
            response = "📦 Sizda hali buyurtmalar yo'q"
    
    await message.answer(response, reply_markup=get_main_menu(language))

# АДМИН КОМАНДЫ
@dp.message(Command("admin"))
async def admin_stats(message: types.Message):
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

@dp.message(Command("report"))
async def manual_report(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await send_monthly_report()

# ОБРАБОТКА ЛЮБЫХ СООБЩЕНИЙ
@dp.message()
async def handle_any_message(message: types.Message):
    await handle_text_messages(message)

# ================== ЗАПУСК ==================
async def main():
    try:
        setup_database()
        asyncio.create_task(scheduled_reports())
        print("🚀 Бот запущен!")
        print(f"👑 Админы: {ADMIN_IDS}")
        print(f"💳 Карта для оплаты: {CARD_NUMBER}")
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())