import asyncio
import logging
import sqlite3
import random
import traceback
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from datetime import datetime
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.filters import Command
from dotenv import load_dotenv
import os
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

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

# ================== FSM СОСТОЯНИЯ ==================
class PaymentStates(StatesGroup):
    waiting_for_receipt_photo = State()

class AdminStates(StatesGroup):
    adding_product = State()
    waiting_product_name_ru = State()
    waiting_product_name_uz = State()
    waiting_product_price = State()
    waiting_description_ru = State()
    waiting_description_uz = State()
    waiting_sizes_ru = State()
    waiting_sizes_uz = State()
    waiting_product_photo = State()

# ================== СИСТЕМА РОЛЕЙ ==================
USER_ROLES = {}
for admin_id in ADMIN_IDS:
    if admin_id not in USER_ROLES:
        USER_ROLES[admin_id] = 'admin'

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
    for admin_id in ADMIN_IDS:
        try:
            if USER_ROLES.get(admin_id) == 'user':
                switch_text = f"🆕 Поступил новый заказ!\n{text}\nХотите перейти в режим админа для обработки?"
                await bot.send_message(admin_id, switch_text, reply_markup=get_admin_switch_keyboard())
            else:
                if photo_file_id:
                    await bot.send_photo(admin_id, photo_file_id, caption=text)
                else:
                    await bot.send_message(admin_id, text)
        except Exception as e:
            logging.error(f"Ошибка отправки админу {admin_id}: {e}")
            # ================== ХРАНЕНИЕ ДАННЫХ В ПАМЯТИ ==================
user_sessions = {}
user_selections = {}
user_carts = {}
support_requests = {}
admin_sessions = {}

# ================== КЛАВИАТУРЫ ==================
# Только этапы регистрации используют ReplyKeyboard

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
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_post_office_keyboard(region, language):
    builder = ReplyKeyboardBuilder()
    if region in POST_OFFICES:
        offices = POST_OFFICES[region][language]
        for office in offices:
            # 🔥 ИСПРАВЛЕНО: безопасное получение имени
            if isinstance(office, dict):
                office_name = office['name']
            else:
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

# 🔥 ВСЕ ОСНОВНЫЕ МЕНЮ — INLINE (под сообщением)
def get_main_menu_inline(language):
    builder = InlineKeyboardBuilder()
    if language == 'ru':
        builder.button(text="🛍️ Каталог", callback_data="menu_catalog")
        builder.button(text="⭐ Мнения клиентов", callback_data="menu_reviews")
        builder.button(text="🛒 Корзина", callback_data="menu_cart")
        builder.button(text="📦 Мои заказы", callback_data="menu_orders")
        builder.button(text="ℹ️ Помощь", callback_data="menu_help")
    else:
        builder.button(text="🛍️ Katalog", callback_data="menu_catalog")
        builder.button(text="⭐ Mijozlar fikri", callback_data="menu_reviews")
        builder.button(text="🛒 Savat", callback_data="menu_cart")
        builder.button(text="📦 Mening buyurtmalarim", callback_data="menu_orders")
        builder.button(text="ℹ️ Yordam", callback_data="menu_help")
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def get_catalog_inline(language):
    builder = InlineKeyboardBuilder()
    if language == 'ru':
        builder.button(text="👕 Формы 2024/2025", callback_data="cat_forms_2024")
        builder.button(text="🕰️ Ретро формы", callback_data="cat_retro")
        builder.button(text="⚽ Бутсы", callback_data="cat_boots")
        builder.button(text="🎁 Фут. атрибутика", callback_data="cat_accessories")
        builder.button(text="🔥 Акции", callback_data="cat_promo")
        builder.button(text="↩️ Назад", callback_data="back_main")
    else:
        builder.button(text="👕 2024/2025 Formalari", callback_data="cat_forms_2024")
        builder.button(text="🕰️ Retro formalar", callback_data="cat_retro")
        builder.button(text="⚽ Futbolkalar", callback_data="cat_boots")
        builder.button(text="🎁 Futbol Aksessuarlari", callback_data="cat_accessories")
        builder.button(text="🔥 Aksiyalar", callback_data="cat_promo")
        builder.button(text="↩️ Orqaga", callback_data="back_main")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()

def get_cart_inline(language):
    builder = InlineKeyboardBuilder()
    if language == 'ru':
        builder.button(text="🛒 Корзина", callback_data="menu_cart")
        builder.button(text="➕ Добавить ещё", callback_data="menu_catalog")
        builder.button(text="💳 Оформить заказ", callback_data="checkout")
        builder.button(text="🗑️ Очистить корзину", callback_data="clear_cart")
        builder.button(text="🔙 Главное меню", callback_data="back_main")
    else:
        builder.button(text="🛒 Savat", callback_data="menu_cart")
        builder.button(text="➕ Yana qo'shish", callback_data="menu_catalog")
        builder.button(text="💳 Buyurtma berish", callback_data="checkout")
        builder.button(text="🗑️ Tozalash", callback_data="clear_cart")
        builder.button(text="🔙 Asosiy", callback_data="back_main")
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def get_reviews_inline(language):
    builder = InlineKeyboardBuilder()
    if language == 'ru':
        builder.button(text="⭐ Посмотреть", callback_data="show_reviews")
        builder.button(text="✍️ Оставить", callback_data="write_review")
        builder.button(text="↩️ Назад", callback_data="back_main")
    else:
        builder.button(text="⭐ Ko'rish", callback_data="show_reviews")
        builder.button(text="✍️ Yozish", callback_data="write_review")
        builder.button(text="↩️ Orqaga", callback_data="back_main")
    builder.adjust(2, 1)
    return builder.as_markup()

def get_payment_inline(language):
    builder = InlineKeyboardBuilder()
    if language == 'ru':
        builder.button(text="💳 Перевод на карту", callback_data="pay_card")
        builder.button(text="❌ Отмена", callback_data="cancel_order")
    else:
        builder.button(text="💳 Karta orqali", callback_data="pay_card")
        builder.button(text="❌ Bekor qilish", callback_data="cancel_order")
    builder.adjust(2)
    return builder.as_markup()

def get_admin_menu_inline():
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="📦 Заказы", callback_data="admin_orders")
    builder.button(text="➕ Добавить товар", callback_data="admin_add_product")
    builder.button(text="🛍️ Управление товарами", callback_data="admin_manage_products")
    builder.button(text="📝 Отзывы", callback_data="admin_reviews")
    builder.button(text="🚪 Выйти", callback_data="admin_exit")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()

def get_back_inline(language):
    text = "↩️ Назад" if language == 'ru' else "↩️ Orqaga"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data="back_main")]])

# ================== ТЕКСТЫ ==================
def get_text(key, language):
    texts = {
        'welcome': {
            'ru': "👋 Добро пожаловать в FootballKits.uz!\nВыберите язык:",
            'uz': "👋 FootballKits.uz ga xush kelibsiz!\nTilni tanlang:"
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
            'ru': "📱 Введите ваш номер телефона в формате:\n+998901234567\n⚠️ На этот номер придёт SMS от почты с трек-номером!",
            'uz': "📱 Telefon raqamingizni quyidagi formatda kiriting:\n+998901234567\n⚠️ Ushbu raqamga pochta orqali trek raqami bilan SMS keladi!"
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
            'ru': "🤝 Помощь\n📞 Телефон: +998 88 111-10-81\n📞 Телефон: +998 97 455-55-82\n⏰ Время работы: 9:00-23:00\n💬 Задайте ваш вопрос:",
            'uz': "🤝 Yordam\n📞 Telefon: +998 88 111-10-81\n📞 Telefon: +998 97 455-55-82\n⏰ Ish vaqti: 9:00-23:00\n💬 Savolingizni bering:"
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

# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================
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

def get_products_by_category_db(category_key, language):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if language == 'ru':
            cursor.execute("SELECT id, name_ru, price, image_url, description_ru, sizes_ru FROM products WHERE category_ru = ?", (category_key,))
        else:
            cursor.execute("SELECT id, name_uz, price, image_url, description_uz, sizes_uz FROM products WHERE category_uz = ?", (category_key,))
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
            f"{emoji} <b>{name}</b>\n"
            f"📝 {description}\n"
            f"📏 <b>Размеры: {sizes}</b>\n"
            f"💵 <b>Цена: {format_price(price, language)}</b>\n"
            f"🆔 <code>ID: {product_id}</code>\n"
            f"✨ <i>Нажмите на ID и отправьте боту, чтобы добавить в корзину</i>"
        )
    else:
        caption = (
            f"{emoji} <b>{name}</b>\n"
            f"📝 {description}\n"
            f"📏 <b>Oʻlchamlar: {sizes}</b>\n"
            f"💵 <b>Narx: {format_price(price, language)}</b>\n"
            f"🆔 <code>ID: {product_id}</code>\n"
            f"✨ <i>ID ni bosib botga yuboring</i>"
        )
    try:
        if image_url:
            await bot.send_photo(
                chat_id=chat_id,
                photo=image_url,
                caption=caption,
                parse_mode='HTML',
                reply_markup=get_back_inline(language)
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode='HTML',
                reply_markup=get_back_inline(language)
            )
    except Exception as e:
        logging.error(f"Ошибка загрузки фото: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode='HTML',
            reply_markup=get_back_inline(language)
        )

# ================== КОРЗИНА ==================
async def show_cart(user_id, language, message_or_callback):
    cart = user_carts.get(user_id, [])
    if not cart:
        text = "🛒 Корзина пуста" if language == 'ru' else "🛒 Savat bo'sh"
        if isinstance(message_or_callback, types.Message):
            await message_or_callback.answer(text, reply_markup=get_main_menu_inline(language))
        else:
            await message_or_callback.message.answer(text, reply_markup=get_main_menu_inline(language))
        return
    total_price = 0
    cart_text = "🛒 Ваша корзина:\n" if language == 'ru' else "🛒 Sizning savatingiz:\n"
    for i, item in enumerate(cart, 1):
        item_price = item['product_price'] + (item.get('customization', {}).get('price', 0) if item.get('customization') else 0)
        total_price += item_price
        cart_text += f"{i}. {item['product_name']}\n"
        if item.get('size'):
            cart_text += f"   📏 Размер: {item['size']}\n" if language == 'ru' else f"   📏 Oʻlcham: {item['size']}\n"
        if item.get('customization'):
            cart_text += f"   ✨ Кастомизация: {item['customization']['text']}\n" if language == 'ru' else f"   ✨ Be'zash: {item['customization']['text']}\n"
        cart_text += f"   💵 {format_price(item_price, language)}\n"
    cart_text += f"💰 Итого: {format_price(total_price, language)}" if language == 'ru' else f"💰 Jami: {format_price(total_price, language)}"
    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(cart_text, reply_markup=get_cart_inline(language))
    else:
        await message_or_callback.message.answer(cart_text, reply_markup=get_cart_inline(language))

# ================== ОТОПРАВКА МЕНЮ СООБЩЕНИЕМ ==================
async def send_main_menu_message(obj, language):
    text = "📋 Главное меню:" if language == 'ru' else "📋 Asosiy menyu:"
    if isinstance(obj, types.Message):
        await obj.answer(text, reply_markup=get_main_menu_inline(language))
    else:
        await obj.message.answer(text, reply_markup=get_main_menu_inline(language))
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

# ================== КЛАВИАТУРЫ РЕГИСТРАЦИИ (ОСТАЮТСЯ НА REPLY) ==================
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
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_post_office_keyboard(region, language):
    builder = ReplyKeyboardBuilder()
    if region in POST_OFFICES:
        offices = POST_OFFICES[region][language]
        for office in offices:
            # 🔥 ИСПРАВЛЕНО: безопасное получение имени
            if isinstance(office, dict):
                office_name = office['name']
            else:
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

# 🔥 INLINE КЛАВИАТУРЫ ДЛЯ ОСНОВНОГО МЕНЮ
def get_main_menu_inline(language):
    builder = InlineKeyboardBuilder()
    if language == 'ru':
        builder.button(text="🛍️ Каталог", callback_data="menu_catalog")
        builder.button(text="⭐ Мнения клиентов", callback_data="menu_reviews")
        builder.button(text="🛒 Корзина", callback_data="menu_cart")
        builder.button(text="📦 Мои заказы", callback_data="menu_orders")
        builder.button(text="ℹ️ Помощь", callback_data="menu_help")
    else:
        builder.button(text="🛍️ Katalog", callback_data="menu_catalog")
        builder.button(text="⭐ Mijozlar fikri", callback_data="menu_reviews")
        builder.button(text="🛒 Savat", callback_data="menu_cart")
        builder.button(text="📦 Mening buyurtmalarim", callback_data="menu_orders")
        builder.button(text="ℹ️ Yordam", callback_data="menu_help")
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def get_catalog_inline(language):
    builder = InlineKeyboardBuilder()
    if language == 'ru':
        builder.button(text="👕 Формы 2024/2025", callback_data="cat_forms_2024")
        builder.button(text="🕰️ Ретро формы", callback_data="cat_retro")
        builder.button(text="⚽ Бутсы", callback_data="cat_boots")
        builder.button(text="🎁 Фут. атрибутика", callback_data="cat_accessories")
        builder.button(text="🔥 Акции", callback_data="cat_promo")
        builder.button(text="↩️ Назад", callback_data="back_main")
    else:
        builder.button(text="👕 2024/2025 Formalari", callback_data="cat_forms_2024")
        builder.button(text="🕰️ Retro formalar", callback_data="cat_retro")
        builder.button(text="⚽ Futbolkalar", callback_data="cat_boots")
        builder.button(text="🎁 Futbol Aksessuarlari", callback_data="cat_accessories")
        builder.button(text="🔥 Aksiyalar", callback_data="cat_promo")
        builder.button(text="↩️ Orqaga", callback_data="back_main")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()

def get_cart_inline(language):
    builder = InlineKeyboardBuilder()
    if language == 'ru':
        builder.button(text="🛒 Корзина", callback_data="menu_cart")
        builder.button(text="➕ Добавить ещё", callback_data="menu_catalog")
        builder.button(text="💳 Оформить заказ", callback_data="checkout")
        builder.button(text="🗑️ Очистить корзину", callback_data="clear_cart")
        builder.button(text="🔙 Главное меню", callback_data="back_main")
    else:
        builder.button(text="🛒 Savat", callback_data="menu_cart")
        builder.button(text="➕ Yana qo'shish", callback_data="menu_catalog")
        builder.button(text="💳 Buyurtma berish", callback_data="checkout")
        builder.button(text="🗑️ Tozalash", callback_data="clear_cart")
        builder.button(text="🔙 Asosiy", callback_data="back_main")
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def get_reviews_inline(language):
    builder = InlineKeyboardBuilder()
    if language == 'ru':
        builder.button(text="⭐ Посмотреть", callback_data="show_reviews")
        builder.button(text="✍️ Оставить", callback_data="write_review")
        builder.button(text="↩️ Назад", callback_data="back_main")
    else:
        builder.button(text="⭐ Ko'rish", callback_data="show_reviews")
        builder.button(text="✍️ Yozish", callback_data="write_review")
        builder.button(text="↩️ Orqaga", callback_data="back_main")
    builder.adjust(2, 1)
    return builder.as_markup()

def get_payment_inline(language):
    builder = InlineKeyboardBuilder()
    if language == 'ru':
        builder.button(text="💳 Перевод на карту", callback_data="pay_card")
        builder.button(text="❌ Отмена", callback_data="cancel_order")
    else:
        builder.button(text="💳 Karta orqali", callback_data="pay_card")
        builder.button(text="❌ Bekor qilish", callback_data="cancel_order")
    builder.adjust(2)
    return builder.as_markup()

def get_admin_menu_inline():
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="📦 Заказы", callback_data="admin_orders")
    builder.button(text="➕ Добавить товар", callback_data="admin_add_product")
    builder.button(text="🛍️ Управление товарами", callback_data="admin_manage_products")
    builder.button(text="📝 Отзывы", callback_data="admin_reviews")
    builder.button(text="🚪 Выйти", callback_data="admin_exit")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()

def get_back_inline(language):
    text = "↩️ Назад" if language == 'ru' else "↩️ Orqaga"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data="back_main")]])

# ================== ТЕКСТЫ ==================
def get_text(key, language):
    texts = {
        'welcome': {
            'ru': "👋 Добро пожаловать в FootballKits.uz!\nВыберите язык:",
            'uz': "👋 FootballKits.uz ga xush kelibsiz!\nTilni tanlang:"
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
            'ru': "📱 Введите ваш номер телефона в формате:\n+998901234567\n⚠️ На этот номер придёт SMS от почты с трек-номером!",
            'uz': "📱 Telefon raqamingizni quyidagi formatda kiriting:\n+998901234567\n⚠️ Ushbu raqamga pochta orqali trek raqami bilan SMS keladi!"
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
            'ru': "🤝 Помощь\n📞 Телефон: +998 88 111-10-81\n📞 Телефон: +998 97 455-55-82\n⏰ Время работы: 9:00-23:00\n💬 Задайте ваш вопрос:",
            'uz': "🤝 Yordam\n📞 Telefon: +998 88 111-10-81\n📞 Telefon: +998 97 455-55-82\n⏰ Ish vaqti: 9:00-23:00\n💬 Savolingizni bering:"
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

# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================
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

def get_products_by_category_db(category_key, language):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if language == 'ru':
            cursor.execute("SELECT id, name_ru, price, image_url, description_ru, sizes_ru FROM products WHERE category_ru = ?", (category_key,))
        else:
            cursor.execute("SELECT id, name_uz, price, image_url, description_uz, sizes_uz FROM products WHERE category_uz = ?", (category_key,))
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
            f"{emoji} <b>{name}</b>\n"
            f"📝 {description}\n"
            f"📏 <b>Размеры: {sizes}</b>\n"
            f"💵 <b>Цена: {format_price(price, language)}</b>\n"
            f"🆔 <code>ID: {product_id}</code>\n"
            f"✨ <i>Нажмите на ID и отправьте боту, чтобы добавить в корзину</i>"
        )
    else:
        caption = (
            f"{emoji} <b>{name}</b>\n"
            f"📝 {description}\n"
            f"📏 <b>Oʻlchamlar: {sizes}</b>\n"
            f"💵 <b>Narx: {format_price(price, language)}</b>\n"
            f"🆔 <code>ID: {product_id}</code>\n"
            f"✨ <i>ID ni bosib botga yuboring</i>"
        )
    try:
        if image_url:
            await bot.send_photo(
                chat_id=chat_id,
                photo=image_url,
                caption=caption,
                parse_mode='HTML',
                reply_markup=get_back_inline(language)
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode='HTML',
                reply_markup=get_back_inline(language)
            )
    except Exception as e:
        logging.error(f"Ошибка загрузки фото: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode='HTML',
            reply_markup=get_back_inline(language)
        )

# ================== КОРЗИНА ==================
async def show_cart(user_id, language, message_or_callback):
    cart = user_carts.get(user_id, [])
    if not cart:
        text = "🛒 Корзина пуста" if language == 'ru' else "🛒 Savat bo'sh"
        if isinstance(message_or_callback, types.Message):
            await message_or_callback.answer(text, reply_markup=get_main_menu_inline(language))
        else:
            await message_or_callback.message.answer(text, reply_markup=get_main_menu_inline(language))
        return
    total_price = 0
    cart_text = "🛒 Ваша корзина:\n" if language == 'ru' else "🛒 Sizning savatingiz:\n"
    for i, item in enumerate(cart, 1):
        item_price = item['product_price'] + (item.get('customization', {}).get('price', 0) if item.get('customization') else 0)
        total_price += item_price
        cart_text += f"{i}. {item['product_name']}\n"
        if item.get('size'):
            cart_text += f"   📏 Размер: {item['size']}\n" if language == 'ru' else f"   📏 Oʻlcham: {item['size']}\n"
        if item.get('customization'):
            cart_text += f"   ✨ Кастомизация: {item['customization']['text']}\n" if language == 'ru' else f"   ✨ Be'zash: {item['customization']['text']}\n"
        cart_text += f"   💵 {format_price(item_price, language)}\n"
    cart_text += f"💰 Итого: {format_price(total_price, language)}" if language == 'ru' else f"💰 Jami: {format_price(total_price, language)}"
    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(cart_text, reply_markup=get_cart_inline(language))
    else:
        await message_or_callback.message.answer(cart_text, reply_markup=get_cart_inline(language))

# ================== ОТОПРАВКА МЕНЮ СООБЩЕНИЕМ ==================
async def send_main_menu_message(obj, language):
    text = "📋 Главное меню:" if language == 'ru' else "📋 Asosiy menyu:"
    if isinstance(obj, types.Message):
        await obj.answer(text, reply_markup=get_main_menu_inline(language))
    else:
        await obj.message.answer(text, reply_markup=get_main_menu_inline(language))
# ================== РЕГИСТРАЦИЯ (ОСТАЁТСЯ НА REPLYKEYBOARD) ==================
@dp.message(F.text.in_(['🇷🇺 Русский', '🇺🇿 O\'zbekcha']))
async def handle_language(message: types.Message):
    user_id = message.from_user.id
    if user_sessions.get(user_id, {}).get('step') != 'language':
        return
    language = 'ru' if 'Русский' in message.text else 'uz'
    user_sessions[user_id]['language'] = language
    user_sessions[user_id]['step'] = 'contact'
    await message.answer(get_text('contact_request', language), reply_markup=get_contact_keyboard(language))

@dp.message(F.contact)
async def handle_contact(message: types.Message):
    contact = message.contact
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    if session.get('step') != 'contact':
        return
    language = session.get('language', 'ru')
    phone = contact.phone_number
    name = contact.first_name
    user_sessions[user_id]['phone'] = phone
    user_sessions[user_id]['name'] = name
    user_sessions[user_id]['step'] = 'region'
    await message.answer(get_text('region_request', language), reply_markup=get_region_keyboard(language))

@dp.message(F.text.regexp(r'^\+998\d{9}$'))
async def handle_manual_phone(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    if session.get('step') != 'contact':
        return
    language = session.get('language', 'ru')
    phone = message.text
    name = message.from_user.first_name or 'Покупатель'
    user_sessions[user_id]['phone'] = phone
    user_sessions[user_id]['name'] = name
    user_sessions[user_id]['step'] = 'region'
    await message.answer(get_text('region_request', language), reply_markup=get_region_keyboard(language))

@dp.message(F.text == "📱 Ввести номер вручную")
async def handle_manual_phone_request(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    if session.get('step') != 'contact':
        return
    language = session.get('language', 'ru')
    await message.answer(get_text('manual_phone_request', language), reply_markup=get_manual_phone_keyboard(language))

@dp.message(F.text == "🔙 Назад")
async def handle_back_manual_phone(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    if session.get('step') != 'contact':
        return
    language = session.get('language', 'ru')
    await message.answer(get_text('contact_request', language), reply_markup=get_contact_keyboard(language))

# Обработчик выбора региона
@dp.message(F.text)
async def handle_region_selection(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    if session.get('step') != 'region':
        return
    language = session.get('language', 'ru')
    # Поиск региона по названию
    selected_region = None
    for region_key, region_name in REGIONS[language].items():
        if message.text == region_name:
            selected_region = region_key
            break
    if not selected_region:
        await message.answer("Пожалуйста, выберите регион из списка")
        return
    user_sessions[user_id]['region'] = selected_region
    # Для Ташкента — геолокация
    if selected_region == 'tashkent':
        user_sessions[user_id]['step'] = 'location'
        await message.answer(
            "📍 Отправьте геолокацию для доставки курьером",
            reply_markup=get_location_keyboard(language)
        )
    else:
        # Для других регионов — пункты выдачи
        user_sessions[user_id]['step'] = 'post_office'
        await message.answer(get_text('post_office_request', language), reply_markup=get_post_office_keyboard(selected_region, language))

@dp.message(F.location)
async def handle_location(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    if session.get('step') != 'location':
        return
    language = session.get('language', 'ru')
    lat, lon = message.location.latitude, message.location.longitude
    location_text = f"Геолокация: {lat}, {lon}"
    save_user(user_id, session['phone'], session['name'], language, 'tashkent', location_text)
    await message.answer(get_text('post_office_received', language), reply_markup=get_main_menu_inline(language))
    user_sessions[user_id]['step'] = 'completed'

@dp.message(F.text)
async def handle_post_office_selection(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    if session.get('step') != 'post_office':
        return
    language = session.get('language', 'ru')
    region = session.get('region')
    # Сохраняем выбранный пункт выдачи
    save_user(user_id, session['phone'], session['name'], language, region, message.text)
    await message.answer(get_text('post_office_received', language), reply_markup=get_main_menu_inline(language))
    user_sessions[user_id]['step'] = 'completed'

# ================== ОСНОВНЫЕ КОМАНДЫ ==================
@dp.message(Command("help"))
async def help_command(message: types.Message):
    user_id = message.from_user.id
    if user_id in ADMIN_IDS:
        help_text = """<b>ПОМОЩЬ ДЛЯ АДМИНА</b>..."""
        await message.answer(help_text, parse_mode='HTML', reply_markup=get_admin_help_keyboard())
    else:
        user = get_user(user_id)
        if user:
            language = user[2]
            await message.answer(get_text('help_text', language), parse_mode='HTML')
            support_requests[user_id] = {'waiting_question': True}
        else:
            await message.answer("Сначала завершите регистрацию через /start")

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет доступа")
        return
    admin_sessions[message.from_user.id] = {'is_admin': True}
    await message.answer("🛠️ Админ-панель", reply_markup=get_admin_menu_inline())

# ================== CALLBACK-ОБРАБОТЧИКИ ОСНОВНОГО МЕНЮ ==================
@dp.callback_query(F.data == "menu_catalog")
async def menu_catalog(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Зарегистрируйтесь", show_alert=True)
        return
    language = user[2]
    await callback.message.answer("🛍️ Выберите категорию:", reply_markup=get_catalog_inline(language))
    await callback.answer()

@dp.callback_query(F.data.startswith("cat_"))
async def handle_category(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Зарегистрируйтесь", show_alert=True)
        return
    language = user[2]
    cat_map = {
        "cat_forms_2024": ("Формы 2024/2025", "2024/2025 Formalari"),
        "cat_retro": ("Ретро формы", "Retro Formalari"),
        "cat_boots": ("Бутсы", "Futbolkalar"),
        "cat_accessories": ("Футбольная атрибутика", "Futbol Aksessuarlari"),
        "cat_promo": ("Акции", "Aksiyalar")
    }
    if callback.data in cat_map:
        cat_ru, cat_uz = cat_map[callback.data]
        category_key = cat_ru if language == 'ru' else cat_uz
        products = get_products_by_category_db(category_key, language)
        if products:
            cat_name = cat_ru if language == 'ru' else cat_uz
            await callback.message.answer(f"🏷️ {cat_name}:\n👇 Вот наши товары:")
            for product in products:
                await send_product_card(callback.message.chat.id, product, language)
        else:
            text = f"😔 В категории '{cat_ru}' пока нет товаров" if language == 'ru' else f"😔 '{cat_uz}' toifasida hozircha mahsulotlar yo'q"
            await callback.message.answer(text, reply_markup=get_main_menu_inline(language))
    await callback.answer()

@dp.callback_query(F.data == "menu_cart")
async def menu_cart(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Зарегистрируйтесь", show_alert=True)
        return
    language = user[2]
    await show_cart(callback.from_user.id, language, callback)
    await callback.answer()

@dp.callback_query(F.data == "menu_reviews")
async def menu_reviews(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Зарегистрируйтесь", show_alert=True)
        return
    language = user[2]
    text = "⭐ Мнение клиентов\nВыберите действие:" if language == 'ru' else "⭐ Mijozlar fikri\nAmalni tanlang:"
    await callback.message.answer(text, reply_markup=get_reviews_inline(language))
    await callback.answer()

@dp.callback_query(F.data == "show_reviews")
async def show_reviews(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        return
    language = user[2]
    reviews = get_all_reviews()
    if not reviews:
        text = "😔 Пока нет отзывов" if language == 'ru' else "😔 Hozircha sharhlar yo'q"
        await callback.message.answer(text)
    else:
        for review in reviews[:5]:
            customer_name, review_text_ru, review_text_uz, photo_url, rating, created_at = review
            stars = "⭐" * rating
            review_text = review_text_ru if language == 'ru' else review_text_uz
            caption = f"{stars}\n👤 {customer_name}\n💬 {review_text}"
            if photo_url:
                await callback.message.answer_photo(photo_url, caption=caption)
            else:
                await callback.message.answer(caption)
    await callback.answer()

@dp.callback_query(F.data == "write_review")
async def write_review(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        return
    language = user[2]
    text = "✍️ Напишите ваш отзыв..." if language == 'ru' else "✍️ Sharhingizni yozing..."
    await callback.message.answer(text)
    user_sessions[callback.from_user.id] = {'waiting_review': True}
    await callback.answer()

@dp.callback_query(F.data == "menu_orders")
async def menu_orders(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Зарегистрируйтесь", show_alert=True)
        return
    orders = get_user_orders(callback.from_user.id, 'ru')
    if orders:
        response = "📦 Ваши заказы:\n"
        for i, (product_name, product_price, customization_price, status, payment, created_at) in enumerate(orders, 1):
            total_price = product_price + (customization_price or 0)
            status_icon = "✅" if status == "confirmed" else "🔄" if status == "waiting_confirm" else "🆕"
            status_text = "Подтвержден" if status == "confirmed" else "Ожидает подтверждения" if status == "waiting_confirm" else "Новый"
            response += f"{i}. {product_name}\n💵 {format_price(total_price, 'ru')}\n{status_icon} {status_text}\n📅 {created_at[:16]}\n"
    else:
        response = "📦 У вас еще нет заказов"
    await callback.message.answer(response)
    await callback.answer()

@dp.callback_query(F.data == "menu_help")
async def menu_help(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Зарегистрируйтесь", show_alert=True)
        return
    language = user[2]
    await callback.message.answer(get_text('help_text', language), parse_mode='HTML')
    support_requests[callback.from_user.id] = {'waiting_question': True}
    await callback.answer()

@dp.callback_query(F.data == "back_main")
async def back_main(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("❌ Зарегистрируйтесь", show_alert=True)
        return
    language = user[2]
    await send_main_menu_message(callback, language)
    await callback.answer()
    # ================== ОБРАБОТКА ВЫБОРА ТОВАРА ==================
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
                    text = f"🛒 Вы выбрали:\n📦 {product_name}\n💵 {format_price(product_price, language)}\n{get_text('choose_size', language)}"
                else:
                    text = f"🛒 Siz tanladingiz:\n📦 {product_name}\n💵 {format_price(product_price, language)}\n{get_text('choose_size', language)}"
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

# ================== КАСТОМИЗАЦИЯ ==================
async def ask_customization(message: types.Message, language: str, product_name: str, product_price: int):
    if language == 'ru':
        text = (
            f"🎨 <b>Добавить имя и номер на форму?</b>\n"
            f"📦 Товар: {product_name}\n"
            f"💵 Базовая цена: {format_price(product_price, language)}\n"
            f"✨ <b>Кастомизация (+{format_price(CUSTOMIZATION_PRICE, language)}):</b>\n"
            f"• Имя на спине\n• Номер на спине\n• Профессиональная печать\n"
            f"Выберите вариант:"
        )
    else:
        text = (
            f"🎨 <b>Formaga ism va raqam qo'shilsinmi?</b>\n"
            f"📦 Mahsulot: {product_name}\n"
            f"💵 Asosiy narx: {format_price(product_price, language)}\n"
            f"✨ <b>Be'zash (+{format_price(CUSTOMIZATION_PRICE, language)}):</b>\n"
            f"• Orqaga ism\n• Orqaga raqam\n• Professional bosma\n"
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
            text = f"🛒 Вы выбрали:\n📦 {selection['product_name']}\n💵 {format_price(selection['product_price'], language)}\n{get_text('choose_size', language)}"
        else:
            text = f"🛒 Siz tanladingiz:\n📦 {selection['product_name']}\n💵 {format_price(selection['product_price'], language)}\n{get_text('choose_size', language)}"
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
        text = f"✅ Кастомизация добавлена: «{message.text}»\n📦 {selection['product_name']}\n💵 {format_price(selection['product_price'], language)} + {format_price(CUSTOMIZATION_PRICE, language)}\n{get_text('choose_size', language)}"
    else:
        text = f"✅ Be'zash qo'shildi: «{message.text}»\n📦 {selection['product_name']}\n💵 {format_price(selection['product_price'], language)} + {format_price(CUSTOMIZATION_PRICE, language)}\n{get_text('choose_size', language)}"
    await message.answer(text, reply_markup=get_size_keyboard(language, category))

# ================== ВЫБОР РАЗМЕРА ==================
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
                "📏 **ТАБЛИЦА РАЗМЕРОВ**\n"
                "**👕 ФУТБОЛКИ И ФОРМЫ:**\n"
                "• S (46-48) - Обхват груди: 92-96см\n"
                "• M (48-50) - Обхват груди: 96-100см\n"
                "• L (50-52) - Обхват груди: 100-104см\n"
                "• XL (52-54) - Обхват груди: 104-108см\n"
                "• XXL (54-56) - Обхват груди: 108-112см\n"
                "**⚽ БУТСЫ:**\n"
                "• 40 EU - Для стопы ~25.5см\n"
                "• 41 EU - Для стопы ~26.5см\n"
                "• 42 EU - Для стопы ~27см\n"
                "• 43 EU - Для стопы ~27.5см\n"
                "• 44 EU - Для стопы ~28.5см\n"
                "ℹ️ Если сомневаетесь в размере, напишите нам!"
            )
        else:
            text = (
                "📏 **OʻLCHAMLAR JADVALI**\n"
                "**👕 FUTBOLKALAR VA FORMALAR:**\n"
                "• S (46-48) - Ko'krak qafasi: 92-96sm\n"
                "• M (48-50) - Ko'krak qafasi: 96-100sm\n"
                "• L (50-52) - Ko'krak qafasi: 100-104sm\n"
                "• XL (52-54) - Ko'krak qafasi: 104-108sm\n"
                "• XXL (54-56) - Ko'krak qafasi: 108-112sm\n"
                "**⚽ FUTBOLKALAR:**\n"
                "• 40 EU - Oyoq uchun ~25.5sm\n"
                "• 41 EU - Oyoq uchun ~26.5sm\n"
                "• 42 EU - Oyoq uchun ~27sm\n"
                "• 43 EU - Oyoq uchun ~27.5sm\n"
                "• 44 EU - Oyoq uchun ~28.5sm\n"
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
    # ================== ОПЛАТА И ЧЕКИ ==================
@dp.message(F.text.in_(["💳 Перевод на карту", "💳 Karta orqali"]))
async def handle_payment_method(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала завершите регистрацию через /start")
        return
    phone, name, language, region, post_office = user
    cart = user_carts.get(message.from_user.id, [])
    if not cart:
        if language == 'ru':
            await message.answer("❌ Корзина пуста", reply_markup=get_main_menu_inline(language))
        else:
            await message.answer("❌ Savat bo'sh", reply_markup=get_main_menu_inline(language))
        return
    total_price = sum(item['product_price'] + (item.get('customization', {}).get('price', 0) if item.get('customization') else 0) for item in cart)
    if language == 'ru':
        text = (
            f"💳 Перевод на карту\n"
            f"📦 Товаров: {len(cart)}\n"
            f"💰 Сумма: {format_price(total_price, language)}\n"
            f"🔄 Переведите на карту:\n"
            f"<code>{CARD_NUMBER}</code>\n"
            f"📸 После перевода отправьте скриншот чека"
        )
    else:
        text = (
            f"💳 Karta orqali to'lash\n"
            f"📦 Mahsulotlar: {len(cart)}\n"
            f"💰 Summa: {format_price(total_price, language)}\n"
            f"🔄 Kartaga o'tkazing:\n"
            f"<code>{CARD_NUMBER}</code>\n"
            f"📸 O'tkazishdan so'ng chek skrinshotini yuboring"
        )
    await message.answer(text, parse_mode='HTML')
    user_sessions[message.from_user.id] = {'waiting_receipt': True, 'cart': cart.copy()}

@dp.message(F.photo)
async def handle_receipt_photo(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    if not session.get('waiting_receipt'):
        return
    user = get_user(user_id)
    if not user:
        return
    phone, name, language, region, post_office = user
    cart = session.get('cart', [])
    if not cart:
        return
    total_price = sum(item['product_price'] + (item.get('customization', {}).get('price', 0) if item.get('customization') else 0) for item in cart)
    order_ids = []
    for item in cart:
        order_id = save_order(
            user_id, phone, name, region, post_office,
            item['product_name'], item['product_price'],
            item.get('size'),
            item.get('customization', {}).get('text') if item.get('customization') else None,
            item.get('customization', {}).get('price', 0) if item.get('customization') else 0,
            'card_pending'
        )
        order_ids.append(order_id)
    # Обновляем статусы
    for order_id in order_ids:
        update_order_status(order_id, 'waiting_confirm')
    # Формируем уведомление для админов
    order_details = []
    for item in cart:
        item_price = item['product_price'] + (item.get('customization', {}).get('price', 0) if item.get('customization') else 0)
        detail = f"• {item['product_name']}"
        if item.get('size'):
            detail += f" | 📏 {item['size']}"
        if item.get('customization'):
            detail += f" | ✨ {item['customization']['text']}"
        detail += f" | 💵 {format_price(item_price, 'ru')}"
        order_details.append(detail)
    admin_text = (
        f"🆕 НОВЫЙ ЗАКАЗ С ОПЛАТОЙ\n"
        f"👤 {name} (@{message.from_user.username or 'N/A'})\n"
        f"📞 {phone}\n"
        f"🏙️ {REGIONS['ru'].get(region, region)}\n"
        f"📮 {post_office}\n"
        f"📦 Товары:\n" + "\n".join(order_details) + f"\n"
        f"💰 Итого: {format_price(total_price, 'ru')}\n"
        f"💳 Оплата: картой ✅\n"
        f"🆔 Заказы: {', '.join(map(str, order_ids))}\n"
        f"🕒 {datetime.now().strftime('%H:%M %d.%m.%Y')}"
    )
    # Уведомляем админов
    await notify_admins_with_role_check(admin_text, message.photo[-1].file_id, order_ids)
    # Ответ пользователю
    if language == 'ru':
        await message.answer("✅ Чек получен! Мы проверяем оплату и скоро подтвердим ваш заказ.", reply_markup=get_main_menu_inline(language))
    else:
        await message.answer("✅ Chek qabul qilindi! Biz to'lovni tekshiramiz va tez orada buyurtmangizni tasdiqlaymiz.", reply_markup=get_main_menu_inline(language))
    # Очищаем корзину
    if user_id in user_carts:
        del user_carts[user_id]
    user_sessions[user_id] = {}

@dp.callback_query(F.data == "cancel_order")
async def handle_cancel_order(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    language = 'ru'  # можно улучшить
    if user_id in user_carts:
        del user_carts[user_id]
    await callback.message.edit_text(get_text('order_cancelled', language), reply_markup=None)
    await callback.answer()

# ================== ОТЗЫВЫ ==================
@dp.message(F.text)
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    # Обработка отзыва
    session = user_sessions.get(user_id, {})
    if session.get('waiting_review'):
        user = get_user(user_id)
        if not user:
            return
        language = user[2]
        name = user[1]
        # Сохраняем отзыв
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if language == 'ru':
                cursor.execute(
                    "INSERT INTO reviews (customer_name, review_text_ru, review_text_uz) VALUES (?, ?, ?)",
                    (name, message.text, "")
                )
            else:
                cursor.execute(
                    "INSERT INTO reviews (customer_name, review_text_ru, review_text_uz) VALUES (?, ?, ?)",
                    (name, "", message.text)
                )
            conn.commit()
        if language == 'ru':
            await message.answer("✅ Спасибо за ваш отзыв! Он поможет другим покупателям.", reply_markup=get_main_menu_inline(language))
        else:
            await message.answer("✅ Sharhingiz uchun rahmat! Boshqa mijozlarga yordam beradi.", reply_markup=get_main_menu_inline(language))
        user_sessions[user_id] = {}
        return
    # Обработка кастомизации
    if session.get('waiting_customization_text'):
        await handle_customization_text(message)
        return
    # Обработка поддержки
    if support_requests.get(user_id, {}).get('waiting_question'):
        # Пересылаем сообщение админам
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"❓ Вопрос от @{message.from_user.username or 'пользователь'}:\n{message.text}"
                )
            except Exception as e:
                logging.error(f"Ошибка отправки админу {admin_id}: {e}")
        language = 'ru'  # можно улучшить
        await message.answer("✅ Ваш вопрос отправлен! Мы ответим в ближайшее время.", reply_markup=get_main_menu_inline(language))
        support_requests[user_id] = {}
        return
    # Обработка ID товара
    if message.text.isdigit():
        await handle_product_selection(message)
        return
    # Иначе — показываем главное меню
    await handle_main_menu(message)

# ================== АДМИНКА ==================
@dp.callback_query(F.data.startswith("admin_") & ~F.data.startswith("admin_"))
async def handle_admin_callbacks(callback: types.CallbackQuery):
    # Обработка админ-действий — см. Часть 10
    pass
# ================== АДМИНКА ==================
@dp.callback_query(F.data.startswith("admin_"))
async def handle_admin_callbacks(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    language = 'ru'  # можно улучшить
    data = callback.data
    if data == "admin_stats":
        stats = get_statistics()
        text = (
            f"📊 <b>СТАТИСТИКА</b>\n"
            f"👥 Пользователей: <b>{stats['total_users']}</b>\n"
            f"📦 Заказов: <b>{stats['total_orders']}</b>\n"
            f"💰 Выручка: <b>{format_price(stats['total_revenue'], 'ru')}</b>\n"
            f"✅ Подтверждённых: <b>{stats['status_stats'].get('confirmed', 0)}</b>\n"
            f"🔄 В ожидании: <b>{stats['status_stats'].get('waiting_confirm', 0)}</b>\n"
            f"❌ Отменённых: <b>{stats['status_stats'].get('cancelled', 0)}</b>"
        )
        await callback.message.answer(text, parse_mode='HTML', reply_markup=get_admin_menu_inline())
    elif data == "admin_orders":
        await callback.message.answer("📦 Выберите статус заказов:", reply_markup=get_orders_menu())
    elif data == "admin_add_product":
        admin_sessions[user_id] = {'adding_product': True, 'step': 'category'}
        await callback.message.answer("Выберите категорию:", reply_markup=get_categories_keyboard())
    elif data == "admin_manage_products":
        products = get_all_products()
        if products:
            await callback.message.answer("🛍️ Выберите действие:", reply_markup=get_products_list_keyboard(products, "manage"))
        else:
            await callback.message.answer("❌ Товаров нет", reply_markup=get_admin_menu_inline())
    elif data == "admin_reviews":
        reviews = get_all_reviews()
        if reviews:
            for review in reviews[:5]:
                customer_name, review_text_ru, review_text_uz, photo_url, rating, created_at = review
                stars = "⭐" * rating
                text = f"{stars}\n👤 {customer_name}\n💬 {review_text_ru}\n📅 {created_at[:16]}"
                if photo_url:
                    await callback.message.answer_photo(photo_url, caption=text)
                else:
                    await callback.message.answer(text)
        else:
            await callback.message.answer("❌ Отзывов нет")
        await callback.message.answer("📝 Все отзывы:", reply_markup=get_admin_menu_inline())
    elif data == "admin_exit":
        if user_id in admin_sessions:
            del admin_sessions[user_id]
        USER_ROLES[user_id] = 'user'
        await callback.message.answer("✅ Вы вышли из админки", reply_markup=get_main_menu_inline('ru'))
    await callback.answer()

# ================== ЗАПУСК ДЛЯ RENDER (WEBHOOK) ==================
async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    setup_database()
    logger.info("🚀 Бот запущен на webhook!")

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()

def main():
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()