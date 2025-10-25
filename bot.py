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

def get_location_keyboard(language):
    text = "📍 Отправить локацию" if language == 'ru' else "📍 Manzilni yuborish"
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text, request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
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
        builder.add(KeyboardButton(text="💵 Наличные"))
        builder.add(KeyboardButton(text="❌ Отмена"))
    else:
        builder.add(KeyboardButton(text="💳 Karta orqali to'lash"))
        builder.add(KeyboardButton(text="💵 Naqd pul"))
        builder.add(KeyboardButton(text="❌ Bekor qilish"))
    
    builder.adjust(2, 1)
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
        'region_request': {
            'ru': "🏙️ Выберите ваш регион для доставки:",
            'uz': "🏙️ Yetkazib berish uchun viloyatingizni tanlang:"
        },
        'location_request_tashkent': {
            'ru': "📍 Теперь поделитесь вашим местоположением для доставки:",
            'uz': "📍 Endi yetkazib berish uchun manzilingizni ulashing:"
        },
        'post_office_info': {
            'ru': "📮 Информация о почтовых отделениях:\n\n",
            'uz': "📮 Pochta bo'limlari haqida ma'lumot:\n\n"
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

# ================== ИНФОРМАЦИЯ О ПОЧТОВЫХ ОТДЕЛЕНИЯХ ==================
def get_post_offices_info(region, language):
    post_offices_info = {
        'tashkent': {
            'ru': """📮 ПОЧТОВЫЕ ОТДЕЛЕНИЯ ТАШКЕНТА:

• 📍 Чиланзарское ОПС
  🗺️ Яндекс: https://yandex.uz/maps/10335/tashkent/?ll=69.240562%2C41.311151&z=13
  🗺️ Google: https://goo.gl/maps/example1

• 📍 Юнусабадское ОПС  
  🗺️ Яндекс: https://yandex.uz/maps/10335/tashkent/?ll=69.280562%2C41.351151&z=13
  🗺️ Google: https://goo.gl/maps/example2

• 📍 Мирзо-Улугбекское ОПС
  🗺️ Яндекс: https://yandex.uz/maps/10335/tashkent/?ll=69.260562%2C41.331151&z=13
  🗺️ Google: https://goo.gl/maps/example3

Выберите ближайшее отделение и сообщите нам при оформлении заказа.""",
            'uz': """📮 TOSHKENT Pochta Bo'limlari:

• 📍 Chilanzar OПХ
  🗺️ Yandex: https://yandex.uz/maps/10335/tashkent/?ll=69.240562%2C41.311151&z=13
  🗺️ Google: https://goo.gl/maps/example1

• 📍 Yunusobod OПХ
  🗺️ Yandex: https://yandex.uz/maps/10335/tashkent/?ll=69.280562%2C41.351151&z=13  
  🗺️ Google: https://goo.gl/maps/example2

• 📍 Mirzo-Ulugʻbek OПХ
  🗺️ Yandex: https://yandex.uz/maps/10335/tashkent/?ll=69.260562%2C41.331151&z=13
  🗺️ Google: https://goo.gl/maps/example3

Eng yaqin bo'limni tanlang va buyurtma berishda bizga xabar bering."""
        },
        'samarkand': {
            'ru': """📮 ПОЧТОВЫЕ ОТДЕЛЕНИЯ САМАРКАНДА:

• 📍 Самаркандское ОПС
  🗺️ Яндекс: https://yandex.uz/maps/10336/samarkand/?ll=66.959727%2C39.655146&z=13
  🗺️ Google: https://goo.gl/maps/example4

• 📍 ОПС Сиаб
  🗺️ Яндекс: https://yandex.uz/maps/10336/samarkand/?ll=66.939727%2C39.635146&z=13
  🗺️ Google: https://goo.gl/maps/example5

• 📍 ОПС Регистан
  🗺️ Яндекс: https://yandex.uz/maps/10336/samarkand/?ll=66.979727%2C39.675146&z=13
  🗺️ Google: https://goo.gl/maps/example6""",
            'uz': """📮 SAMARQAND Pochta Bo'limlari:

• 📍 Samarqand OПХ
  🗺️ Yandex: https://yandex.uz/maps/10336/samarkand/?ll=66.959727%2C39.655146&z=13
  🗺️ Google: https://goo.gl/maps/example4

• 📍 Siob OПХ
  🗺️ Yandex: https://yandex.uz/maps/10336/samarkand/?ll=66.939727%2C39.635146&z=13
  🗺️ Google: https://goo.gl/maps/example5

• 📍 Registon OПХ
  🗺️ Yandex: https://yandex.uz/maps/10336/samarkand/?ll=66.979727%2C39.675146&z=13
  🗺️ Google: https://goo.gl/maps/example6"""
        }
    }
    
    return post_offices_info.get(region, {}).get(language, 
        "📮 Выберите ближайшее почтовое отделение и сообщите нам при оформлении заказа." if language == 'ru' 
        else "📮 Eng yaqin pochta bo'limini tanlang va buyurtma berishda bizga xabar bering.")

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
        return
    
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
async def handle_region_selection(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    
    if session.get('step') != 'region':
        return await handle_main_menu(message)
    
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
    
    user_sessions[user_id]['step'] = 'location'
    user_sessions[user_id]['region'] = selected_region
    
    save_user(user_id, session['phone'], session['name'], language, selected_region)
    
    if selected_region == 'tashkent':
        await message.answer(get_text('location_request_tashkent', language), 
                           reply_markup=get_location_keyboard(language))
    else:
        # Для других регионов отправляем информацию о почтовых отделениях
        post_info = get_post_offices_info(selected_region, language)
        await message.answer(post_info)
        
        if language == 'ru':
            await message.answer("📍 После выбора отделения отправьте свою геолокацию или напишите название отделения:")
        else:
            await message.answer("📍 Bo'limni tanlaganingizdan so'ng, o'zingizning geolokatsiyangizni yuboring yoki bo'lim nomini yozing:")
        
        user_sessions[user_id]['waiting_location'] = True

# ПОЛУЧЕНИЕ ЛОКАЦИИ ИЛИ НАЗВАНИЯ ОТДЕЛЕНИЯ
@dp.message(F.text)
async def handle_location_input(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    
    if not session.get('waiting_location'):
        return await handle_main_menu(message)
    
    language = session.get('language', 'ru')
    location = message.text
    
    save_user(user_id, session['phone'], session['name'], language, session['region'], location)
    
    user_sessions[user_id]['step'] = 'main_menu'
    user_sessions[user_id]['location'] = location
    user_sessions[user_id]['waiting_location'] = False
    
    await message.answer(get_text('post_office_received', language), 
                       reply_markup=get_main_menu(language))

# ПОЛУЧЕНИЕ ГЕОЛОКАЦИИ
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

# ОБРАБОТКА ГЛАВНОГО МЕНЮ
async def handle_main_menu(message: types.Message):
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
    elif text in ["🛒 Корзина", "🛒 Savat"]:
        await show_cart_command(message)
    elif text in ["➕ Добавить еще товар", "➕ Yana mahsulot qo'shish"]:
        await add_more_products(message)
    elif text in ["💳 Оформить заказ", "💳 Buyurtma berish"]:
        await checkout_cart(message)
    elif text in ["🗑️ Очистить корзину", "🗑️ Savatni tozalash"]:
        await clear_cart(message)
    elif text in ["💳 Перевод на карту", "💳 Karta orqali to'lash"]:
        await handle_payment(message)
    elif text in ["💵 Наличные", "💵 Naqd pul"]:
        await handle_payment(message)
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
async def show_forms_menu(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала завершите регистрацию через /start")
        return
    
    phone, name, language, region, location = user
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
    
    phone, name, language, region, location = user
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
        return
    
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

@dp.message(F.text)
async def handle_review_text(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_sessions or not user_sessions[user_id].get('waiting_review'):
        return await handle_main_menu(message)
    
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

# МОИ ЗАКАЗЫ
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

# ОБРАБОТКА ВСЕХ СООБЩЕНИЙ
@dp.message()
async def handle_all_messages(message: types.Message):
    # Проверяем, не находится ли пользователь в процессе регистрации
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    
    if session.get('step') in ['language', 'contact', 'manual_phone', 'region', 'location']:
        # Если пользователь в процессе регистрации, пропускаем обычную обработку
        return
    
    # Обрабатываем как основное меню
    await handle_main_menu(message)

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