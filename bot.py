import asyncio
import logging
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.filters import Command
from dotenv import load_dotenv
import os

load_dotenv()

# ================== НАСТРОЙКИ ==================
API_TOKEN = os.getenv('API_TOKEN')
ADMIN_IDS = [5009858379, 587180281, 1225271746]  # 👈 ЗДЕСЬ МОЖНО МЕНЯТЬ АДМИНОВ

# 👇 ЗДЕСЬ МЕНЯЙ НОМЕР КАРТЫ НА СВОЙ
CARD_NUMBER = "8600 1234 5678 9012"  # 🎯 ЗАМЕНИ НА РЕАЛЬНУЮ КАРТУ

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
            location TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_ru TEXT NOT NULL,
            name_uz TEXT NOT NULL,
            price TEXT NOT NULL,
            category_ru TEXT NOT NULL,
            category_uz TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_phone TEXT NOT NULL,
            user_name TEXT,
            user_location TEXT,
            product_name TEXT NOT NULL,
            product_price TEXT NOT NULL,
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
            ('Бутсы Nike Mercurial', 'Nike Mercurial futbolka', '350,000 UZS', 'Бутсы', 'Futbolkalar'),
            ('Форма Пахтакора 2024', 'Paxtakor 2024 formasi', '150,000 UZS', 'Формы', 'Formalar'),
            ('Ретро форма Узбекистан 1994', 'Oʻzbekiston 1994 retro formasi', '200,000 UZS', 'Ретро', 'Retro'),
            ('Форма Насафа 2024', 'Nasaf 2024 formasi', '140,000 UZS', 'Формы', 'Formalar'),
            ('Бутсы Adidas Predator', 'Adidas Predator futbolka', '320,000 UZS', 'Бутсы', 'Futbolkalar'),
            ('🔥 АКЦИЯ: Форма + бутсы', '🔥 AKSIYA: Forma + futbolka', '450,000 UZS', 'Акции', 'Aksiyalar')
        ]
        cursor.executemany("INSERT INTO products (name_ru, name_uz, price, category_ru, category_uz) VALUES (?, ?, ?, ?, ?)", test_products)
    
    conn.commit()
    conn.close()
    print("✅ База данных готова")

# ================== ХРАНЕНИЕ ДАННЫХ ПОЛЬЗОВАТЕЛЕЙ ==================
user_sessions = {}
user_selections = {}

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
        builder.add(KeyboardButton(text="⚽ Бутсы"))
        builder.add(KeyboardButton(text="👕 Формы")) 
        builder.add(KeyboardButton(text="🕰️ Ретро"))
        builder.add(KeyboardButton(text="🔥 Акции"))
        builder.add(KeyboardButton(text="📦 Мои заказы"))
        builder.add(KeyboardButton(text="ℹ️ Помощь"))
    else:
        builder.add(KeyboardButton(text="⚽ Futbolkalar"))
        builder.add(KeyboardButton(text="👕 Formalar")) 
        builder.add(KeyboardButton(text="🕰️ Retro"))
        builder.add(KeyboardButton(text="🔥 Aksiyalar"))
        builder.add(KeyboardButton(text="📦 Mening buyurtmalarim"))
        builder.add(KeyboardButton(text="ℹ️ Yordam"))
    
    builder.adjust(2, 2, 2)
    return builder.as_markup(resize_keyboard=True)

def get_payment_menu(language):
    builder = ReplyKeyboardBuilder()
    
    if language == 'ru':
        builder.add(KeyboardButton(text="💳 Перевод на карту"))
        builder.add(KeyboardButton(text="💵 Наличные"))
        builder.add(KeyboardButton(text="↩️ Назад в меню"))
    else:
        builder.add(KeyboardButton(text="💳 Karta orqali to'lash"))
        builder.add(KeyboardButton(text="💵 Naqd pul"))
        builder.add(KeyboardButton(text="↩️ Menyuga qaytish"))
    
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)

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
        'location_request': {
            'ru': "📍 Теперь поделитесь вашим местоположением для доставки:",
            'uz': "📍 Endi yetkazib berish uchun manzilingizni ulashing:"
        },
        'contact_received': {
            'ru': "✅ Контакт получен!",
            'uz': "✅ Kontakt qabul qilindi!"
        },
        'location_received': {
            'ru': "✅ Локация получена! Теперь вы можете выбирать товары:",
            'uz': "✅ Manzil qabul qilindi! Endi mahsulotlarni tanlashingiz mumkin:"
        },
        'no_contact': {
            'ru': "❌ Сначала поделитесь контактом!",
            'uz': "❌ Avval kontaktni ulashing!"
        },
        'no_location': {
            'ru': "❌ Сначала поделитесь локацией!",
            'uz': "❌ Avval manzilni ulashing!"
        },
        'help_text': {
            'ru': "🤝 Помощь\n\n📞 Служба поддержки: +998901234567\n📍 Адрес: Ташкент, Чорсу\n⏰ Время работы: 9:00-18:00\n\nВыберите категорию товаров:",
            'uz': "🤝 Yordam\n\n📞 Qo'llab-quvvatlash: +998901234567\n📍 Manzil: Toshkent, Chorsu\n⏰ Ish vaqti: 9:00-18:00\n\nMahsulot toifasini tanlang:"
        }
    }
    return texts.get(key, {}).get(language, key)

# ================== БАЗА ДАННЫХ ==================
def get_db_connection():
    return sqlite3.connect('football_shop.db', check_same_thread=False)

def save_user(user_id, phone, name, language, location=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO users (user_id, phone, name, language, location) VALUES (?, ?, ?, ?, ?)",
        (user_id, phone, name, language, location)
    )
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT phone, name, language, location FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_products_by_category(category, language):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if language == 'ru':
        cursor.execute("SELECT id, name_ru, price FROM products WHERE category_ru = ?", (category,))
    else:
        cursor.execute("SELECT id, name_uz, price FROM products WHERE category_uz = ?", (category,))
        
    products = cursor.fetchall()
    conn.close()
    return products

def get_product_by_id(product_id, language):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if language == 'ru':
        cursor.execute("SELECT name_ru, price FROM products WHERE id = ?", (product_id,))
    else:
        cursor.execute("SELECT name_uz, price FROM products WHERE id = ?", (product_id,))
        
    product = cursor.fetchone()
    conn.close()
    return product

def save_order(user_id, phone, name, location, product_name, product_price, payment_method='cash'):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO orders (user_id, user_phone, user_name, user_location, product_name, product_price, payment_method) 
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, phone, name, location, product_name, product_price, payment_method)
    )
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return order_id

def get_user_orders(user_id, language):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT product_name, product_price, status, payment_method, created_at 
        FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 5""",
        (user_id,)
    )
    orders = cursor.fetchall()
    conn.close()
    return orders

def update_order_status(order_id, status, admin_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if admin_id:
        cursor.execute("UPDATE orders SET status = ?, confirmed_by = ?, confirmed_at = CURRENT_TIMESTAMP WHERE id = ?", 
                      (status, admin_id, order_id))
    else:
        cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()

# ================== УВЕДОМЛЕНИЯ АДМИНАМ ==================
async def notify_admins(order_text):
    for admin_id in ADMIN_IDS:  # 👈 ОТПРАВЛЯЕТ ВСЕМ АДМИНАМ ИЗ СПИСКА
        try:
            await bot.send_message(admin_id, order_text)
        except Exception as e:
            logging.error(f"Ошибка отправки админу {admin_id}: {e}")

# ================== ОТЧЕТЫ ==================
async def send_monthly_report():
    """Автоматическая отправка отчета 1-го числа"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*), 
                   SUM(CAST(REPLACE(REPLACE(product_price, ' UZS', ''), ',', '') AS INTEGER)) 
            FROM orders 
            WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now', '-1 month')
            AND status = 'confirmed'
        """)
        result = cursor.fetchone()
        month_orders = result[0] or 0
        month_revenue = result[1] or 0
        
        cursor.execute("""
            SELECT product_name, COUNT(*) as order_count 
            FROM orders 
            WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now', '-1 month')
            AND status = 'confirmed'
            GROUP BY product_name 
            ORDER BY order_count DESC 
            LIMIT 3
        """)
        popular_products = cursor.fetchall()
        
        conn.close()
        
        report_text = (
            f"📊 МЕСЯЧНЫЙ ОТЧЕТ\n\n"
            f"📦 Подтвержденных заказов: {month_orders}\n"
            f"💰 Выручка: {month_revenue:,} UZS\n\n"
            f"🏆 Популярные товары:\n"
        )
        
        for product, count in popular_products:
            report_text += f"• {product} - {count} зак.\n"
        
        report_text += f"\n📅 {datetime.now().strftime('%B %Y')}"
        
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, report_text)
            except Exception as e:
                logging.error(f"Ошибка отправки отчета админу {admin_id}: {e}")
                
    except Exception as e:
        logging.error(f"Ошибка генерации отчета: {e}")

async def scheduled_reports():
    """Фоновая задача для отчетов"""
    while True:
        now = datetime.now()
        if now.day == 1 and now.hour == 9 and now.minute == 0:
            await send_monthly_report()
        await asyncio.sleep(60)

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
    
    save_user(user_id, phone, name, language)
    user_sessions[user_id]['step'] = 'location'
    user_sessions[user_id]['phone'] = phone
    user_sessions[user_id]['name'] = name
    
    await message.answer(get_text('contact_received', language))
    await message.answer(get_text('location_request', language), reply_markup=get_location_keyboard(language))

# ПОЛУЧЕНИЕ ЛОКАЦИИ
@dp.message(F.location)
async def handle_location(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    
    if session.get('step') != 'location':
        return
    
    language = session.get('language', 'ru')
    location = f"{message.location.latitude},{message.location.longitude}"
    
    save_user(user_id, session['phone'], session['name'], language, location)
    user_sessions[user_id]['step'] = 'main_menu'
    
    await message.answer(get_text('location_received', language), reply_markup=get_main_menu(language))

# ОБРАБОТЧИКИ КАТЕГОРИЙ
@dp.message(F.text.in_(["⚽ Бутсы", "⚽ Futbolkalar"]))
async def show_boots(message: types.Message):
    await show_category_products(message, "Бутсы", "Futbolkalar")

@dp.message(F.text.in_(["👕 Формы", "👕 Formalar"]))
async def show_forms(message: types.Message):
    await show_category_products(message, "Формы", "Formalar")

@dp.message(F.text.in_(["🕰️ Ретро", "🕰️ Retro"]))
async def show_retro(message: types.Message):
    await show_category_products(message, "Ретро", "Retro")

@dp.message(F.text.in_(["🔥 Акции", "🔥 Aksiyalar"]))
async def show_sales(message: types.Message):
    await show_category_products(message, "Акции", "Aksiyalar")

@dp.message(F.text.in_(["ℹ️ Помощь", "ℹ️ Yordam"]))
async def show_help(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала завершите регистрацию через /start")
        return
    
    phone, name, language, location = user
    await message.answer(get_text('help_text', language), reply_markup=get_main_menu(language))

async def show_category_products(message: types.Message, category_ru: str, category_uz: str):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала завершите регистрацию через /start")
        return
    
    phone, name, language, location = user
    
    if not location:
        text = get_text('no_location', language)
        await message.answer(text)
        return
        
    products = get_products_by_category(category_ru, language)
    
    if products:
        if language == 'ru':
            response = f"🏷️ {category_ru}:\n\n"
        else:
            response = f"🏷️ {category_uz}:\n\n"
            
        for product_id, name, price in products:
            response += f"🆔 {product_id}. {name}\n💵 {price}\n\n"
        
        if language == 'ru':
            response += "Чтобы заказать, напишите номер товара"
        else:
            response += "Buyurtma berish uchun mahsulot raqamini yozing"
            
        await message.answer(response, reply_markup=get_back_menu(language))
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
    
    phone, name, language, location = user
    
    try:
        product_id = int(message.text)
        product = get_product_by_id(product_id, language)
        
        if product:
            product_name, product_price = product
            user_selections[message.from_user.id] = {
                'product_id': product_id,
                'product_name': product_name, 
                'product_price': product_price
            }
            
            if language == 'ru':
                text = f"🛒 Вы выбрали:\n\n📦 {product_name}\n💵 {product_price}\n\nВыберите способ оплаты:"
            else:
                text = f"🛒 Siz tanladingiz:\n\n📦 {product_name}\n💵 {product_price}\n\nTo'lov usulini tanlang:"
                
            await message.answer(text, reply_markup=get_payment_menu(language))
        else:
            if language == 'ru':
                await message.answer("❌ Товар не найден")
            else:
                await message.answer("❌ Mahsulot topilmadi")
            
    except Exception as e:
        if language == 'ru':
            await message.answer("❌ Ошибка выбора товара")
        else:
            await message.answer("❌ Mahsulotni tanlashda xato")

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
    phone, name, language, location = user
    
    is_card = message.text in ["💳 Перевод на карту", "💳 Karta orqali to'lash"]
    
    if is_card:
        order_id = save_order(message.from_user.id, phone, name, location, product_name, product_price, 'card_pending')
        
        if language == 'ru':
            text = (
                f"💳 Перевод на карту\n\n"
                f"📦 Заказ: {product_name}\n"
                f"💵 Сумма: {product_price}\n\n"
                f"🔄 Переведите на карту:\n"
                f"<code>{CARD_NUMBER}</code>\n\n"
                f"📸 После перевода отправьте скриншот чека\n"
                f"Мы подтвердим заказ в течение 15 минут!"
            )
        else:
            text = (
                f"💳 Karta orqali to'lash\n\n"
                f"📦 Buyurtma: {product_name}\n"
                f"💵 Summa: {product_price}\n\n"
                f"🔄 Kartaga o'tkazing:\n"
                f"<code>{CARD_NUMBER}</code>\n\n"
                f"📸 O'tkazishdan so'ng chek skrinshotini yuboring\n"
                f"Buyurtmani 15 daqiqa ichida tasdiqlaymiz!"
            )
        
        await message.answer(text, parse_mode='HTML')
        user_sessions[message.from_user.id]['waiting_receipt'] = True
        user_sessions[message.from_user.id]['order_id'] = order_id
            
    else:  # Наличные
        order_id = save_order(message.from_user.id, phone, name, location, product_name, product_price, 'cash')
        if language == 'ru':
            text = f"✅ Заказ #{order_id} принят!\n\n📦 {product_name}\n💵 {product_price}\n💵 Оплата: наличными при получении\n\nМы свяжемся с вами для подтверждения!"
        else:
            text = f"✅ #{order_id}-buyurtma qabul qilindi!\n\n📦 {product_name}\n💵 {product_price}\n💵 To'lov: yetkazib berishda naqd pul\n\nTasdiqlash uchun siz bilan bog'lanamiz!"
        
        await message.answer(text, reply_markup=get_main_menu(language))
        
        # Уведомление админам о наличном заказе
        order_text = (
            f"🆕 НАЛИЧНЫЙ ЗАКАЗ #{order_id}\n\n"
            f"👤 {name} (@{message.from_user.username or 'N/A'})\n"
            f"📞 {phone}\n"
            f"📍 {location}\n"
            f"📦 {product_name}\n"
            f"💵 {product_price}\n"
            f"💰 Наличные\n"
            f"🕒 {datetime.now().strftime('%H:%M %d.%m.%Y')}"
        )
        await notify_admins(order_text)
    
    # Очищаем выбор
    if not is_card and message.from_user.id in user_selections:
        del user_selections[message.from_user.id]

# ПРИЕМ СКРИНШОТОВ ЧЕКОВ
@dp.message(F.photo)
async def handle_receipt_photo(message: types.Message):
    user_id = message.from_user.id
    session = user_sessions.get(user_id, {})
    
    if not session.get('waiting_receipt'):
        return
    
    user = get_user(user_id)
    if not user:
        return
    
    phone, name, language, location = user
    order_id = session['order_id']
    
    # Сохраняем информацию о чеке
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE orders SET status = 'waiting_confirm', receipt_photo_id = ? WHERE id = ?",
        (message.photo[-1].file_id, order_id)
    )
    conn.commit()
    conn.close()
    
    # Уведомление админам для подтверждения
    admin_text = (
        f"📸 ПОСТУПИЛ ЧЕК\n\n"
        f"🆔 Заказ: #{order_id}\n"
        f"👤 Клиент: {name} (@{message.from_user.username or 'N/A'})\n"
        f"📞 Телефон: {phone}\n"
        f"📍 Локация: {location}\n\n"
        f"✅ Для подтверждения: /confirm_{order_id}\n"
        f"❌ Для отмены: /cancel_{order_id}"
    )
    
    await notify_admins(admin_text)
    
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
    if message.from_user.id not in ADMIN_IDS:  # 👈 ПРОВЕРКА АДМИНА
        return
    
    try:
        order_id = int(message.text.split('_')[1])
        update_order_status(order_id, 'confirmed', message.from_user.id)
        
        # Получаем информацию о заказе
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, product_name, product_price FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        conn.close()
        
        if order:
            user_id, product_name, product_price = order
            user = get_user(user_id)
            if user:
                phone, name, language, location = user
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
    if message.from_user.id not in ADMIN_IDS:  # 👈 ПРОВЕРКА АДМИНА
        return
    
    try:
        order_id = int(message.text.split('_')[1])
        update_order_status(order_id, 'cancelled')
        
        # Уведомляем пользователя
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        conn.close()
        
        if order:
            user_id = order[0]
            user = get_user(user_id)
            if user:
                phone, name, language, location = user
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
    
    phone, name, language, location = user
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
            response += f"💵 {product_price} {payment_icon}\n"
            response += f"{status_icon} {status_text}\n"
            response += f"📅 {created_at[:16]}\n\n"
    else:
        if language == 'ru':
            response = "📦 У вас еще нет заказов"
        else:
            response = "📦 Sizda hali buyurtmalar yo'q"
    
    await message.answer(response, reply_markup=get_main_menu(language))

# НАЗАД В МЕНЮ
@dp.message(F.text.in_(["↩️ Назад", "↩️ Orqaga", "↩️ Назад в меню", "↩️ Menyuga qaytish"]))
async def back_to_menu(message: types.Message):
    user = get_user(message.from_user.id)
    if user:
        language = user[2]
        if language == 'ru':
            text = "📋 Главное меню:"
        else:
            text = "📋 Asosiy menyu:"
        await message.answer(text, reply_markup=get_main_menu(language))

# АДМИН КОМАНДЫ
@dp.message(Command("admin"))
async def admin_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:  # 👈 ПРОВЕРКА АДМИНА
        return
        
    conn = get_db_connection()
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
    
    conn.close()
    
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