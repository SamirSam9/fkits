import asyncio
import logging
import sqlite3
import os
import json
from datetime import datetime, timedelta
from decimal import Decimal

from dotenv import load_dotenv
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import KeyboardButton, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, BufferedInputFile
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# ================== НАСТРОЙКИ ==================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
CARD_NUMBER = os.getenv('CARD_NUMBER', '6262 4700 5534 4787')
ADMIN_IDS = [5009858379, 587180281, 1225271746] 
DB_FILENAME = 'football_shop.db'
PORT = int(os.getenv("PORT", 10000))

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ================== ДАННЫЕ ==================
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

ORDER_STATUSES = {
    'pending': {'ru': '⏳ Ожидает оплаты', 'uz': '⏳ To\'lov kutilmoqda'},
    'waiting_confirm': {'ru': '🔄 Проверяется', 'uz': '🔄 Tekshirilmoqda'},
    'confirmed': {'ru': '✅ Подтвержден', 'uz': '✅ Tasdiqlandi'},
    'shipping': {'ru': '🚚 Доставляется', 'uz': '🚚 Yetkazilmoqda'},
    'delivered': {'ru': '📦 Доставлен', 'uz': '📦 Yetkazib berildi'},
    'cancelled': {'ru': '❌ Отменен', 'uz': '❌ Bekor qilindi'}
}

# ================== МАШИНА СОСТОЯНИЙ ==================
class OrderFlow(StatesGroup):
    # Регистрация
    choosing_lang = State()
    entering_phone = State()
    choosing_region = State()
    choosing_post = State()
    entering_phone_manually = State()  # Для ручного ввода номера
    entering_name_manually = State()   # Для ручного ввода имени
    
    # Основное
    main_menu = State()
    choosing_category = State()
    viewing_cart = State()
    viewing_orders = State()
    waiting_receipt = State()

    # Отзывы
    viewing_reviews = State()
    writing_review = State()
    rating_product = State()
    
    # Админка
    admin_home = State()
    admin_adding_product_name = State()
    admin_adding_product_price = State()
    admin_adding_product_category = State()  # ДОБАВЛЕНО НОВОЕ СОСТОЯНИЕ
    admin_adding_product_photo = State()
    admin_managing_products = State()
    admin_editing_product = State()
    admin_editing_price = State()
    admin_editing_photo = State()
    admin_viewing_orders = State()
    admin_updating_order = State()
    admin_statistics = State()
    admin_viewing_reviews = State()
    admin_managing_reviews = State()

# ================== РАБОТА С БД ==================
def get_db_connection():
    conn = sqlite3.connect(DB_FILENAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def setup_database():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, phone TEXT, name TEXT, 
            language TEXT DEFAULT 'ru', region TEXT, post_office TEXT, 
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            name_ru TEXT, name_uz TEXT, price INTEGER,
            category_ru TEXT, category_uz TEXT, image_url TEXT, 
            description_ru TEXT, description_uz TEXT, sizes TEXT,
            is_active INTEGER DEFAULT 1)''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            quantity INTEGER DEFAULT 1,
            size TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id))''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER,
            items TEXT,  -- JSON список товаров
            total_price INTEGER,
            status TEXT DEFAULT 'pending',
            receipt_photo_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            product_id INTEGER,
            rating INTEGER CHECK(rating >= 1 AND rating <= 5),
            review_text TEXT,
            is_approved INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )''')
        conn.commit()

def save_user(user_id, phone, name, language, region=None, post_office=None):
    with get_db_connection() as conn:
        conn.execute("""INSERT OR REPLACE INTO users (user_id, phone, name, language, region, post_office) 
                        VALUES (?, ?, ?, ?, ?, ?)""", (user_id, phone, name, language, region, post_office))
        conn.commit()

def get_user(user_id):
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

def add_product(name, price, category_ru, category_uz, image_url):
    with get_db_connection() as conn:
        conn.execute("""INSERT INTO products (name_ru, name_uz, price, category_ru, category_uz, image_url, description_ru, description_uz, sizes) 
                        VALUES (?, ?, ?, ?, ?, ?, 'Описание товара', 'Mahsulot tavsifi', 'S, M, L, XL')""", 
                        (name, name, price, category_ru, category_uz, image_url))
        conn.commit()

def update_product(product_id, field, value):
    with get_db_connection() as conn:
        conn.execute(f"UPDATE products SET {field} = ? WHERE id = ?", (value, product_id))
        conn.commit()

def delete_product(product_id):
    with get_db_connection() as conn:
        conn.execute("UPDATE products SET is_active = 0 WHERE id = ?", (product_id,))
        conn.commit()

def get_all_products():
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM products WHERE is_active = 1 ORDER BY id DESC")
        return cursor.fetchall()

def get_product_by_id(pid):
    with get_db_connection() as conn:
        return conn.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()

def get_products_by_category(category, lang):
    col = 'category_ru' if lang == 'ru' else 'category_uz'
    with get_db_connection() as conn:
        cursor = conn.execute(f"SELECT * FROM products WHERE {col} = ? AND is_active = 1", (category,))
        return cursor.fetchall()

def add_to_cart(user_id, product_id, quantity=1, size=None):
    with get_db_connection() as conn:
        existing = conn.execute("SELECT * FROM cart_items WHERE user_id = ? AND product_id = ?", 
                                (user_id, product_id)).fetchone()
        if existing:
            conn.execute("UPDATE cart_items SET quantity = quantity + ? WHERE id = ?", (quantity, existing['id']))
        else:
            conn.execute("""INSERT INTO cart_items (user_id, product_id, quantity, size) 
                            VALUES (?, ?, ?, ?)""", (user_id, product_id, quantity, size))
        conn.commit()

def remove_from_cart(user_id, product_id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM cart_items WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        conn.commit()

def get_cart_items(user_id):
    with get_db_connection() as conn:
        cursor = conn.execute("""SELECT ci.*, p.name_ru, p.name_uz, p.price, p.image_url 
                                 FROM cart_items ci 
                                 JOIN products p ON ci.product_id = p.id 
                                 WHERE ci.user_id = ?""", (user_id,))
        return cursor.fetchall()

def clear_cart(user_id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
        conn.commit()

def create_order(user_id, items, total_price, status='pending'):
    with get_db_connection() as conn:
        cursor = conn.execute("""INSERT INTO orders (user_id, items, total_price, status) 
                                 VALUES (?, ?, ?, ?) RETURNING id""", 
                                 (user_id, json.dumps(items), total_price, status))
        conn.commit()
        return cursor.fetchone()[0]

def update_order_status(order_id, status):
    with get_db_connection() as conn:
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        conn.commit()

def update_order_receipt(order_id, photo_id):
    with get_db_connection() as conn:
        conn.execute("UPDATE orders SET receipt_photo_id = ?, status = 'waiting_confirm' WHERE id = ?", (photo_id, order_id))
        conn.commit()

def get_user_orders(user_id):
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        return cursor.fetchall()

def get_all_orders():
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM orders ORDER BY created_at DESC")
        return cursor.fetchall()

def get_order_by_id(order_id):
    with get_db_connection() as conn:
        return conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()

def get_monthly_statistics(year=None, month=None):
    with get_db_connection() as conn:
        if year and month:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_orders,
                    SUM(CASE WHEN status = 'delivered' THEN total_price ELSE 0 END) as total_revenue,
                    SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) as delivered_orders,
                    AVG(CASE WHEN status = 'delivered' THEN total_price ELSE NULL END) as avg_order_value
                FROM orders 
                WHERE strftime('%Y', created_at) = ? AND strftime('%m', created_at) = ?
            """, (str(year), str(month).zfill(2)))
        else:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_orders,
                    SUM(CASE WHEN status = 'delivered' THEN total_price ELSE 0 END) as total_revenue,
                    SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) as delivered_orders,
                    AVG(CASE WHEN status = 'delivered' THEN total_price ELSE NULL END) as avg_order_value
                FROM orders 
                WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
            """)
        return cursor.fetchone()

def get_product_statistics():
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT p.name_ru, COUNT(ci.id) as times_ordered, SUM(ci.quantity) as total_quantity
            FROM cart_items ci
            JOIN products p ON ci.product_id = p.id
            JOIN orders o ON o.items LIKE '%' || p.id || '%'
            WHERE o.status = 'delivered'
            GROUP BY p.id
            ORDER BY total_quantity DESC
            LIMIT 10
        """)

def add_review(user_id, user_name, product_id, rating, review_text):
    with get_db_connection() as conn:
        conn.execute("""INSERT INTO reviews (user_id, user_name, product_id, rating, review_text) 
                        VALUES (?, ?, ?, ?, ?)""", 
                     (user_id, user_name, product_id, rating, review_text))
        conn.commit()

def get_product_reviews(product_id, approved_only=True):
    with get_db_connection() as conn:
        if approved_only:
            cursor = conn.execute("""SELECT * FROM reviews 
                                     WHERE product_id = ? AND is_approved = 1 
                                     ORDER BY created_at DESC""", (product_id,))
        else:
            cursor = conn.execute("""SELECT * FROM reviews 
                                     WHERE product_id = ? 
                                     ORDER BY created_at DESC""", (product_id,))
        return cursor.fetchall()

def get_user_reviews(user_id):
    with get_db_connection() as conn:
        cursor = conn.execute("""SELECT r.*, p.name_ru 
                                 FROM reviews r 
                                 JOIN products p ON r.product_id = p.id 
                                 WHERE r.user_id = ? 
                                 ORDER BY r.created_at DESC""", (user_id,))
        return cursor.fetchall()

def approve_review(review_id):
    with get_db_connection() as conn:
        conn.execute("UPDATE reviews SET is_approved = 1 WHERE id = ?", (review_id,))
        conn.commit()

def delete_review(review_id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
        conn.commit()

def get_average_rating(product_id):
    with get_db_connection() as conn:
        cursor = conn.execute("""SELECT AVG(rating) as avg_rating, COUNT(*) as review_count 
                                 FROM reviews 
                                 WHERE product_id = ? AND is_approved = 1""", (product_id,))
        result = cursor.fetchone()
        if result and result['avg_rating']:
            return float(result['avg_rating']), result['review_count'] or 0
        return 0, 0

def get_pending_reviews():
    with get_db_connection() as conn:
        cursor = conn.execute("""SELECT r.*, p.name_ru, u.name 
                                 FROM reviews r 
                                 JOIN products p ON r.product_id = p.id 
                                 JOIN users u ON r.user_id = u.user_id 
                                 WHERE r.is_approved = 0 
                                 ORDER BY r.created_at DESC""")
        return cursor.fetchall()
    

# ================== КЛАВИАТУРЫ ==================
def get_language_keyboard():
    return ReplyKeyboardBuilder().add(KeyboardButton(text="🇷🇺 Русский"), KeyboardButton(text="🇺🇿 O'zbekcha")).as_markup(resize_keyboard=True)

def get_contact_keyboard(lang):
    builder = ReplyKeyboardBuilder()
    text_send = "📞 Отправить контакт" if lang == 'ru' else "📞 Kontaktni yuborish"
    text_manual = "📝 Ввести вручную" if lang == 'ru' else "📝 Qo'lda kiritish"
    
    builder.add(KeyboardButton(text=text_send, request_contact=True))
    builder.add(KeyboardButton(text=text_manual))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

def get_region_keyboard(lang):
    builder = ReplyKeyboardBuilder()
    for key in REGIONS:
        builder.add(KeyboardButton(text=REGIONS[key][lang]))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_post_keyboard(region_key, lang):
    builder = ReplyKeyboardBuilder()
    offices = POST_OFFICES.get(region_key, {}).get(lang, [])
    for office in offices:
        builder.add(KeyboardButton(text=office))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

def get_main_menu(lang):
    menu = ["🛍️ Каталог", "🛒 Корзина", "📦 Мои заказы", "⭐ Отзывы", "ℹ️ Помощь"] if lang == 'ru' else ["🛍️ Katalog", "🛒 Savat", "📦 Buyurtmalarim", "⭐ Sharhlar", "ℹ️ Yordam"]
    builder = ReplyKeyboardBuilder()
    for item in menu: builder.add(KeyboardButton(text=item))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_catalog_keyboard(lang):
    cats = ["👕 Формы 2024/2025", "⚽ Бутсы", "🔙 Назад"] if lang == 'ru' else ["👕 2024/2025 Formalari", "⚽ Butsalar", "🔙 Orqaga"]
    builder = ReplyKeyboardBuilder()
    for cat in cats: builder.add(KeyboardButton(text=cat))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_cart_keyboard(lang, cart_items):
    builder = InlineKeyboardBuilder()
    for item in cart_items:
        builder.add(InlineKeyboardButton(
            text=f"❌ {item['name_ru']}" if lang == 'ru' else f"❌ {item['name_uz']}",
            callback_data=f"remove_{item['product_id']}"
        ))
    builder.add(InlineKeyboardButton(
        text="✅ Оформить заказ" if lang == 'ru' else "✅ Buyurtma berish",
        callback_data="checkout"
    ))
    builder.add(InlineKeyboardButton(
        text="🧹 Очистить корзину" if lang == 'ru' else "🧹 Savatni tozalash",
        callback_data="clear_cart"
    ))
    builder.adjust(1)
    return builder.as_markup()

def get_admin_kb():
    builder = ReplyKeyboardBuilder()
    buttons = ["➕ Добавить товар", "📦 Управление товарами", "📊 Статистика", "📋 Все заказы", "🔙 Выход"]
    for btn in buttons:
        builder.add(KeyboardButton(text=btn))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_products_management_kb():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_products"))
    builder.add(InlineKeyboardButton(text="🗑️ Удалить", callback_data="delete_products"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin"))
    builder.adjust(2)
    return builder.as_markup()

def get_products_list_kb(products, action):
    builder = InlineKeyboardBuilder()
    for product in products:
        builder.add(InlineKeyboardButton(
            text=f"{product['name_ru']} - {product['price']} UZS",
            callback_data=f"{action}_{product['id']}"
        ))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_manage"))
    builder.adjust(1)
    return builder.as_markup()

def get_order_status_kb(order_id):
    builder = InlineKeyboardBuilder()
    statuses = ['waiting_confirm', 'confirmed', 'shipping', 'delivered', 'cancelled']
    for status in statuses:
        builder.add(InlineKeyboardButton(
            text=ORDER_STATUSES[status]['ru'],
            callback_data=f"setstatus_{order_id}_{status}"
        ))
    builder.adjust(1)
    return builder.as_markup()

def get_statistics_kb():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="📊 Текущий месяц", callback_data="stats_current"))
    builder.add(InlineKeyboardButton(text="📈 Продажи по товарам", callback_data="stats_products"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin"))
    builder.adjust(1)

def get_reviews_keyboard(lang, product_id=None):
    builder = InlineKeyboardBuilder()
    
    if lang == 'ru':
        if product_id:
            builder.add(InlineKeyboardButton(text="⭐ Написать отзыв", callback_data=f"write_review_{product_id}"))
        builder.add(InlineKeyboardButton(text="📝 Мои отзывы", callback_data="my_reviews"))
        builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
    else:
        if product_id:
            builder.add(InlineKeyboardButton(text="⭐ Sharh yozish", callback_data=f"write_review_{product_id}"))
        builder.add(InlineKeyboardButton(text="📝 Mening sharhlarim", callback_data="my_reviews"))
        builder.add(InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main"))
    
    builder.adjust(1)
    return builder.as_markup()

def get_rating_keyboard(lang):
    builder = InlineKeyboardBuilder()
    
    if lang == 'ru':
        buttons = [
            ("⭐ 1", "rating_1"),
            ("⭐⭐ 2", "rating_2"),
            ("⭐⭐⭐ 3", "rating_3"),
            ("⭐⭐⭐⭐ 4", "rating_4"),
            ("⭐⭐⭐⭐⭐ 5", "rating_5")
        ]
    else:
        buttons = [
            ("⭐ 1", "rating_1"),
            ("⭐⭐ 2", "rating_2"),
            ("⭐⭐⭐ 3", "rating_3"),
            ("⭐⭐⭐⭐ 4", "rating_4"),
            ("⭐⭐⭐⭐⭐ 5", "rating_5")
        ]
    
    for text, callback in buttons:
        builder.add(InlineKeyboardButton(text=text, callback_data=callback))
    builder.adjust(5)
    return builder.as_markup()

def get_reviews_admin_kb():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="👁️ Просмотр отзывов", callback_data="view_reviews_admin"))
    builder.add(InlineKeyboardButton(text="✅ Модерация", callback_data="moderate_reviews"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin"))
    builder.adjust(2)
    return builder.as_markup()
    

# ================== ЛОГИКА: СТАРТ И РЕГИСТРАЦИЯ ==================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user = get_user(message.from_user.id)
    if user:
        await message.answer("👋 С возвращением!" if user['language'] == 'ru' else "👋 Xush kelibsiz!", 
                           reply_markup=get_main_menu(user['language']))
        await state.set_state(OrderFlow.main_menu)
    else:
        await message.answer("👋 Добро пожаловать! / Xush kelibsiz!\nВыберите язык / Tilni tanlang:", 
                           reply_markup=get_language_keyboard())
        await state.set_state(OrderFlow.choosing_lang)

@dp.message(OrderFlow.choosing_lang)
async def lang_chosen(message: types.Message, state: FSMContext):
    lang = 'ru' if 'Русский' in message.text else 'uz'
    await state.update_data(lang=lang)
    await message.answer("📱 Поделитесь контактом / Kontakt yuboring:", 
                       reply_markup=get_contact_keyboard(lang))
    await state.set_state(OrderFlow.entering_phone)

@dp.message(OrderFlow.entering_phone, F.text.in_(["📝 Ввести вручную", "📝 Qo'lda kiritish"]))
async def manual_phone_entry(message: types.Message, state: FSMContext):
    data = await state.get_data()
    lang = data['lang']
    
    text = "📱 Введите ваш номер телефона в формате:\n+998901234567\nили 901234567" if lang == 'ru' else \
           "📱 Telefon raqamingizni quyidagi ko'rinishda kiriting:\n+998901234567\nyoki 901234567"
    
    await message.answer(text, reply_markup=ReplyKeyboardRemove())
    await state.set_state(OrderFlow.entering_phone_manually)

@dp.message(OrderFlow.entering_phone_manually)
async def phone_entered_manually(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    
    # Проверка формата номера
    if not (phone.startswith('+998') or phone.startswith('998') or (len(phone) == 9 and phone.isdigit())):
        data = await state.get_data()
        lang = data['lang']
        error_text = "❌ Неверный формат номера. Пример: +998901234567" if lang == 'ru' else \
                    "❌ Raqam formati noto'g'ri. Masalan: +998901234567"
        return await message.answer(error_text)
    
    # Нормализация номера
    if phone.startswith('+998'):
        normalized_phone = phone
    elif phone.startswith('998'):
        normalized_phone = '+' + phone
    elif len(phone) == 9 and phone.isdigit():
        normalized_phone = '+998' + phone
    else:
        normalized_phone = phone
    
    await state.update_data(phone=normalized_phone)
    
    data = await state.get_data()
    lang = data['lang']
    
    text = "👤 Теперь введите ваше имя и фамилию:" if lang == 'ru' else \
           "👤 Endi ism va familiyangizni kiriting:"
    
    await message.answer(text)
    await state.set_state(OrderFlow.entering_name_manually)

@dp.message(OrderFlow.entering_name_manually)
async def name_entered_manually(message: types.Message, state: FSMContext):
    name = message.text.strip()
    
    if len(name) < 2:
        data = await state.get_data()
        lang = data['lang']
        error_text = "❌ Имя должно содержать минимум 2 символа" if lang == 'ru' else \
                    "❌ Ism kamida 2 belgidan iborat bo'lishi kerak"
        return await message.answer(error_text)
    
    await state.update_data(name=name)
    
    data = await state.get_data()
    lang = data['lang']
    
    await message.answer("🏙 Выберите регион / Viloyatni tanlang:", 
                       reply_markup=get_region_keyboard(lang))
    await state.set_state(OrderFlow.choosing_region)

@dp.message(OrderFlow.choosing_region)
async def region_chosen(message: types.Message, state: FSMContext):
    data = await state.get_data()
    found_key = None
    for key, vals in REGIONS.items():
        if message.text in vals.values():
            found_key = key
            break
    
    if not found_key:
        return await message.answer("❌ Выберите из списка / Ro'yxatdan tanlang")

    await state.update_data(region=found_key)
    await message.answer("📮 Выберите почту / Pochta tanlang:", 
                       reply_markup=get_post_keyboard(found_key, data['lang']))
    await state.set_state(OrderFlow.choosing_post)

@dp.message(OrderFlow.choosing_post)
async def post_chosen(message: types.Message, state: FSMContext):
    data = await state.get_data()
    save_user(message.from_user.id, data['phone'], data['name'], data['lang'], data['region'], message.text)
    await message.answer("✅ Регистрация завершена! / Ro'yxatdan o'tish tugadi!", 
                       reply_markup=get_main_menu(data['lang']))
    await state.set_state(OrderFlow.main_menu)

# ================== ЛОГИКА: МАГАЗИН ==================
@dp.message(OrderFlow.main_menu, F.text.in_(["🛍️ Каталог", "🛍️ Katalog"]))
async def show_catalog(message: types.Message, state: FSMContext):
    user = get_user(message.from_user.id)
    await message.answer("📂 Категории / Bo'limlar:", 
                       reply_markup=get_catalog_keyboard(user['language']))
    await state.set_state(OrderFlow.choosing_category)

@dp.message(OrderFlow.main_menu, F.text.in_(["🛒 Корзина", "🛒 Savat"]))
async def show_cart(message: types.Message, state: FSMContext):
    user = get_user(message.from_user.id)
    cart_items = get_cart_items(message.from_user.id)
    
    if not cart_items:
        await message.answer("🛒 Корзина пуста / Savat bo'sh" if user['language'] == 'ru' else "🛒 Savat bo'sh")
        return
    
    total = sum(item['price'] * item['quantity'] for item in cart_items)
    text = "🛒 Ваша корзина:\n\n" if user['language'] == 'ru' else "🛒 Sizning savatingiz:\n\n"
    
    for item in cart_items:
        name = item['name_ru'] if user['language'] == 'ru' else item['name_uz']
        text += f"• {name} x{item['quantity']} = {item['price'] * item['quantity']} UZS\n"
    
    text += f"\n💵 Итого: {total} UZS" if user['language'] == 'ru' else f"\n💵 Jami: {total} UZS"
    
    await message.answer(text, reply_markup=get_cart_keyboard(user['language'], cart_items))
    await state.set_state(OrderFlow.viewing_cart)

@dp.message(OrderFlow.main_menu, F.text.in_(["📦 Мои заказы", "📦 Buyurtmalarim"]))
async def show_my_orders(message: types.Message, state: FSMContext):
    user = get_user(message.from_user.id)
    orders = get_user_orders(message.from_user.id)
    
    if not orders:
        await message.answer("📦 У вас пока нет заказов / Hozircha buyurtmalaringiz yo'q")
        return
    
    text = "📦 Ваши заказы:\n\n" if user['language'] == 'ru' else "📦 Sizning buyurtmalaringiz:\n\n"
    
    for order in orders:
        status_text = ORDER_STATUSES.get(order['status'], {}).get(user['language'], order['status'])
        text += f"📦 Заказ #{order['id']}\n"
        text += f"💰 Сумма: {order['total_price']} UZS\n"
        text += f"📊 Статус: {status_text}\n"
        text += f"📅 Дата: {order['created_at'][:10]}\n\n"
    
    await message.answer(text)
    await state.set_state(OrderFlow.viewing_orders)

@dp.message(OrderFlow.main_menu, F.text.in_(["ℹ️ Помощь", "ℹ️ Yordam"]))
async def show_help(message: types.Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user['language']
    
    if lang == 'ru':
        text = """ℹ️ **Помощь по использованию бота:**
        
🛍️ **Каталог** - просмотр и выбор товаров
🛒 **Корзина** - управление выбранными товарами
📦 **Мои заказы** - отслеживание статусов заказов

📞 **Поддержка:** @footballkitsuz7

💳 **Оплата:** только через банковскую карту
🚚 **Доставка:** через почтовые отделения
        
❓ **Частые вопросы:**
Q: Как оплатить заказ?
A: После оформления вы получите номер карты для оплаты.

Q: Сколько времени занимает доставка?
A: 1-3 дней в зависимости от региона."""
    else:
        text = """ℹ️ **Botdan foydalanish bo'yicha yordam:**
        
🛍️ **Katalog** - mahsulotlarni ko'rish va tanlash
🛒 **Savat** - tanlangan mahsulotlarni boshqarish
📦 **Buyurtmalarim** - buyurtma holatini kuzatish

📞 **Qo'llab-quvvatlash:** @footballkitsuz7

💳 **To'lov:** faqat bank kartasi orqali
🚚 **Yetkazib berish:** pochta bo'limlari orqali
        
❓ **Tez-tez so'raladigan savollar:**
S: Buyurtmani qanday to'lash mumkin?
J: Buyurtmani rasmiylashtirgandan so'ng to'lov uchun karta raqamini olasiz.

S: Yetkazib berish qancha vaqt oladi?
J: Viloyatga qarab 1-3 kun."""
    
    await message.answer(text, parse_mode="Markdown")

@dp.message(OrderFlow.choosing_category)
async def show_products(message: types.Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user['language']
    
    if "Назад" in message.text or "Orqaga" in message.text:
        await message.answer("🏠 Меню", reply_markup=get_main_menu(lang))
        return await state.set_state(OrderFlow.main_menu)

    products = get_products_by_category(message.text, lang)
    if not products:
        await message.answer("😕 Пока пусто / Hozircha bo'sh")
        return

    for prod in products:
        # Получаем рейтинг товара
        avg_rating, review_count = get_average_rating(prod['id'])
        rating_text = ""
        
        if avg_rating > 0:
            stars = "⭐" * int(round(avg_rating))
            if lang == 'ru':
                rating_text = f"⭐ Рейтинг: {avg_rating:.1f} {stars} ({review_count} отзывов)\n"
            else:
                rating_text = f"⭐ Reyting: {avg_rating:.1f} {stars} ({review_count} sharh)\n"
        else:
            if lang == 'ru':
                rating_text = "⭐ Ещё нет отзывов\n"
            else:
                rating_text = "⭐ Hozircha sharhlar yo'q\n"
        
        # Формируем описание товара
        caption = f"👕 <b>{prod['name_ru'] if lang == 'ru' else prod['name_uz']}</b>\n{rating_text}💸 {prod['price']} UZS"
        
        # Создаём клавиатуру с двумя кнопками
        kb = InlineKeyboardBuilder()
        if lang == 'ru':
            kb.add(InlineKeyboardButton(text="🛒 Добавить в корзину", callback_data=f"addtocart_{prod['id']}"))
            kb.add(InlineKeyboardButton(text="⭐ Отзывы", callback_data=f"show_reviews_{prod['id']}"))
        else:
            kb.add(InlineKeyboardButton(text="🛒 Savatga qo'shish", callback_data=f"addtocart_{prod['id']}"))
            kb.add(InlineKeyboardButton(text="⭐ Sharhlar", callback_data=f"show_reviews_{prod['id']}"))
        kb.adjust(2)
        
        try:
            await message.answer_photo(prod['image_url'], caption=caption, parse_mode="HTML", reply_markup=kb.as_markup())
        except:
            await message.answer(caption, parse_mode="HTML", reply_markup=kb.as_markup())

            # ================== ЛОГИКА: ОТЗЫВЫ ==================

@dp.message(OrderFlow.main_menu, F.text.in_(["⭐ Отзывы", "⭐ Sharhlar"]))
async def show_reviews_menu(message: types.Message, state: FSMContext):
    user = get_user(message.from_user.id)
    lang = user['language']
    
    if lang == 'ru':
        text = "⭐ **Отзывы о товарах**\n\nЗдесь вы можете:\n• Написать отзыв о товаре\n• Посмотреть свои отзывы\n• Увидеть отзывы других покупателей"
    else:
        text = "⭐ **Mahsulotlarga sharhlar**\n\nBu yerda siz quyidagilarni qilishingiz mumkin:\n• Mahsulot haqida sharh yozish\n• O'z sharhlaringizni ko'rish\n• Boshiga xaridorlarning sharhlarini ko'rish"
    
    await message.answer(text, parse_mode="Markdown", reply_markup=get_reviews_keyboard(lang))
    await state.set_state(OrderFlow.viewing_reviews)

# Показ отзывов о конкретном товаре (при просмотре товара добавьте кнопку)
# Обновите функцию show_products - добавьте кнопку "Отзывы" рядом с "Добавить в корзину"

@dp.callback_query(F.data.startswith("show_reviews_"))
async def show_product_reviews(callback: types.CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[2])
    user = get_user(callback.from_user.id)
    lang = user['language']
    
    reviews = get_product_reviews(product_id, approved_only=True)
    avg_rating, review_count = get_average_rating(product_id)
    product = get_product_by_id(product_id)
    
    product_name = product['name_ru'] if lang == 'ru' else product['name_uz']
    
    if lang == 'ru':
        text = f"⭐ **Отзывы о товаре:** {product_name}\n\n"
        text += f"📊 **Средний рейтинг:** {avg_rating:.1f} ⭐ ({review_count} отзывов)\n\n"
    else:
        text = f"⭐ **Mahsulot sharhlari:** {product_name}\n\n"
        text += f"📊 **O'rtacha reyting:** {avg_rating:.1f} ⭐ ({review_count} sharh)\n\n"
    
    if not reviews:
        if lang == 'ru':
            text += "😔 Пока нет отзывов. Будьте первым!"
        else:
            text += "😔 Hozircha sharhlar yo'q. Birinchi bo'ling!"
    else:
        for i, review in enumerate(reviews[:10], 1):  # Показываем последние 10
            stars = "⭐" * review['rating']
            if lang == 'ru':
                text += f"{i}. **{review['user_name']}** {stars}\n"
                text += f"   {review['review_text']}\n"
                text += f"   📅 {review['created_at'][:10]}\n\n"
            else:
                text += f"{i}. **{review['user_name']}** {stars}\n"
                text += f"   {review['review_text']}\n"
                text += f"   📅 {review['created_at'][:10]}\n\n"
    
    await callback.message.answer(text, parse_mode="Markdown", 
                                reply_markup=get_reviews_keyboard(lang, product_id))
    await callback.answer()

@dp.callback_query(F.data.startswith("write_review_"))
async def start_writing_review(callback: types.CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[2])
    user = get_user(callback.from_user.id)
    lang = user['language']
    
    # Проверяем, покупал ли пользователь этот товар
    orders = get_user_orders(callback.from_user.id)
    has_purchased = False
    
    for order in orders:
        if order['status'] == 'delivered':  # Только доставленные заказы
            try:
                items = json.loads(order['items'])
                for item in items:
                    if item['product_id'] == product_id:
                        has_purchased = True
                        break
            except:
                pass
    
    if not has_purchased:
        if lang == 'ru':
            await callback.answer("❌ Вы можете оставить отзыв только на купленные товары")
        else:
            await callback.answer("❌ Faqat sotib olgan mahsulotlaringizga sharh qoldirishingiz mumkin")
        return
    
    await state.update_data(review_product_id=product_id)
    
    if lang == 'ru':
        text = "⭐ **Оцените товар:**\n\nВыберите количество звезд от 1 до 5:"
    else:
        text = "⭐ **Mahsulotni baholang:**\n\n1 dan 5 gacha yulduz sonini tanlang:"
    
    await callback.message.answer(text, reply_markup=get_rating_keyboard(lang))
    await state.set_state(OrderFlow.rating_product)
    await callback.answer()

@dp.callback_query(OrderFlow.rating_product, F.data.startswith("rating_"))
async def set_review_rating(callback: types.CallbackQuery, state: FSMContext):
    rating = int(callback.data.split("_")[1])
    user = get_user(callback.from_user.id)
    lang = user['language']
    
    await state.update_data(review_rating=rating)
    
    if lang == 'ru':
        text = f"⭐ Вы выбрали: {rating} звезд\n\nТеперь напишите текст отзыва:"
    else:
        text = f"⭐ Siz tanladingiz: {rating} yulduz\n\nEndi sharh matnini yozing:"
    
    await callback.message.answer(text)
    await state.set_state(OrderFlow.writing_review)
    await callback.answer()

@dp.message(OrderFlow.writing_review)
async def save_review_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user = get_user(message.from_user.id)
    lang = user['language']
    
    review_text = message.text.strip()
    
    if len(review_text) < 5:
        if lang == 'ru':
            await message.answer("❌ Отзыв должен содержать минимум 5 символов")
        else:
            await message.answer("❌ Sharh kamida 5 belgidan iborat bo'lishi kerak")
        return
    
    if len(review_text) > 1000:
        if lang == 'ru':
            await message.answer("❌ Отзыв не должен превышать 1000 символов")
        else:
            await message.answer("❌ Sharh 1000 belgidan oshmasligi kerak")
        return
    
    # Сохраняем отзыв
    add_review(
        user_id=message.from_user.id,
        user_name=user['name'],
        product_id=data['review_product_id'],
        rating=data['review_rating'],
        review_text=review_text
    )
    
    if lang == 'ru':
        text = "✅ Спасибо за ваш отзыв!\n\nОтзыв отправлен на модерацию. После проверки он появится на странице товара."
    else:
        text = "✅ Sharhingiz uchun rahmat!\n\nSharh moderatsiyaga yuborildi. Tekshiruvdan so'ng u mahsulot sahifasida paydo bo'ladi."
    
    await message.answer(text, reply_markup=get_main_menu(lang))
    await state.set_state(OrderFlow.main_menu)

@dp.callback_query(F.data == "my_reviews")
async def show_my_reviews(callback: types.CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    lang = user['language']
    reviews = get_user_reviews(callback.from_user.id)
    
    if lang == 'ru':
        text = "📝 **Мои отзывы:**\n\n"
    else:
        text = "📝 **Mening sharhlarim:**\n\n"
    
    if not reviews:
        if lang == 'ru':
            text += "😔 У вас пока нет отзывов."
        else:
            text += "😔 Hozircha sharhlaringiz yo'q."
    else:
        for i, review in enumerate(reviews, 1):
            stars = "⭐" * review['rating']
            status = "✅ Одобрен" if review['is_approved'] else "⏳ На модерации"
            status_uz = "✅ Tasdiqlangan" if review['is_approved'] else "⏳ Moderatsiyada"
            
            if lang == 'ru':
                text += f"{i}. **{review['name_ru']}** {stars}\n"
                text += f"   {review['review_text']}\n"
                text += f"   📅 {review['created_at'][:10]} | {status}\n\n"
            else:
                text += f"{i}. **{review['name_ru']}** {stars}\n"
                text += f"   {review['review_text']}\n"
                text += f"   📅 {review['created_at'][:10]} | {status_uz}\n\n"
    
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_from_reviews(callback: types.CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    await callback.message.answer("🏠 Меню" if user['language'] == 'ru' else "🏠 Menu", 
                                reply_markup=get_main_menu(user['language']))
    await state.set_state(OrderFlow.main_menu)
    await callback.answer()

@dp.callback_query(F.data.startswith("addtocart_"))
async def add_to_cart_handler(callback: types.CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[1])
    user = get_user(callback.from_user.id)
    
    add_to_cart(callback.from_user.id, product_id)
    
    await callback.answer("✅ Добавлено в корзину" if user['language'] == 'ru' else "✅ Savatga qo'shildi")
    await callback.message.edit_reply_markup(reply_markup=None)

@dp.callback_query(F.data.startswith("remove_"))
async def remove_from_cart_handler(callback: types.CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[1])
    user = get_user(callback.from_user.id)
    
    remove_from_cart(callback.from_user.id, product_id)
    
    cart_items = get_cart_items(callback.from_user.id)
    if cart_items:
        total = sum(item['price'] * item['quantity'] for item in cart_items)
        text = "🛒 Ваша корзина:\n\n"
        for item in cart_items:
            name = item['name_ru'] if user['language'] == 'ru' else item['name_uz']
            text += f"• {name} x{item['quantity']} = {item['price'] * item['quantity']} UZS\n"
        text += f"\n💵 Итого: {total} UZS"
        
        await callback.message.edit_text(text, reply_markup=get_cart_keyboard(user['language'], cart_items))
    else:
        await callback.message.edit_text("🛒 Корзина пуста")
    
    await callback.answer("✅ Удалено из корзины" if user['language'] == 'ru' else "✅ Savatdan olib tashlandi")

@dp.callback_query(F.data == "clear_cart")
async def clear_cart_handler(callback: types.CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    clear_cart(callback.from_user.id)
    await callback.message.edit_text("🧹 Корзина очищена" if user['language'] == 'ru' else "🧹 Savat tozalandi")
    await callback.answer()

@dp.callback_query(F.data == "checkout")
async def checkout_handler(callback: types.CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    cart_items = get_cart_items(callback.from_user.id)
    
    if not cart_items:
        await callback.answer("❌ Корзина пуста")
        return
    
    total = sum(item['price'] * item['quantity'] for item in cart_items)
    
    await state.update_data(cart_items=[dict(item) for item in cart_items])
    
    await callback.message.answer(
        f"💰 К оплате: {total} UZS\n\n"
        f"💳 Карта для оплаты: `{CARD_NUMBER}`\n\n"
        f"📸 После оплаты отправьте скриншот чека.\n"
        f"Укажите в комментарии к переводу: Заказ от @{callback.from_user.username}",
        parse_mode="Markdown"
    )
    await state.set_state(OrderFlow.waiting_receipt)
    await callback.answer()

@dp.message(OrderFlow.waiting_receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cart_items = data.get('cart_items', [])
    
    if not cart_items:
        await message.answer("❌ Ошибка: корзина пуста")
        return
    
    user = get_user(message.from_user.id)
    total = sum(item['price'] * item['quantity'] for item in cart_items)
    
    order_items = []
    for item in cart_items:
        order_items.append({
            'product_id': item['product_id'],
            'name': item['name_ru'] if user['language'] == 'ru' else item['name_uz'],
            'quantity': item['quantity'],
            'price': item['price']
        })
    
    order_id = create_order(message.from_user.id, order_items, total, status='waiting_confirm')
    update_order_receipt(order_id, message.photo[-1].file_id)
    
    clear_cart(message.from_user.id)
    
    for admin_id in ADMIN_IDS:
        try:
            items_text = "\n".join([f"• {item['name']} x{item['quantity']}" for item in order_items])
            await bot.send_photo(
                admin_id, 
                message.photo[-1].file_id, 
                caption=f"🆕 НОВЫЙ ЗАКАЗ #{order_id}\n"
                       f"👤 Пользователь: {message.from_user.id} (@{message.from_user.username})\n"
                       f"📦 Товары:\n{items_text}\n"
                       f"💰 Сумма: {total} UZS\n"
                       f"📊 Статус: Ожидает подтверждения"
            )
        except Exception as e:
            logger.error(f"Error sending to admin {admin_id}: {e}")

    await message.answer(
        "✅ Чек принят! Заказ ожидает подтверждения.\n"
        "Статус можно отслеживать в разделе 'Мои заказы'.",
        reply_markup=get_main_menu(user['language'])
    )
    await state.set_state(OrderFlow.main_menu)

# ================== ЛОГИКА: АДМИНКА ==================
@dp.message(Command("admin"))
async def admin_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: 
        return
    await message.answer("🛠 Админ-панель", reply_markup=get_admin_kb())
    await state.set_state(OrderFlow.admin_home)

@dp.message(OrderFlow.admin_home, F.text == "➕ Добавить товар")
async def admin_add_prod(message: types.Message, state: FSMContext):
    await message.answer("Введите название товара (RU):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(OrderFlow.admin_adding_product_name)

@dp.message(OrderFlow.admin_home, F.text == "📦 Управление товарами")
async def admin_manage_products(message: types.Message, state: FSMContext):
    await message.answer("Выберите действие:", reply_markup=get_products_management_kb())
    await state.set_state(OrderFlow.admin_managing_products)

@dp.message(OrderFlow.admin_home, F.text == "📋 Все заказы")
async def admin_view_orders(message: types.Message, state: FSMContext):
    orders = get_all_orders()
    if not orders:
        await message.answer("📦 Заказов пока нет")
        return
    
    text = "📋 Все заказы:\n\n"
    for order in orders[:10]:
        user_info = get_user(order['user_id'])
        username = f"@{user_info['name']}" if user_info else f"ID: {order['user_id']}"
        status_text = ORDER_STATUSES.get(order['status'], {}).get('ru', order['status'])
        
        text += f"📦 Заказ #{order['id']}\n"
        text += f"👤 {username}\n"
        text += f"💰 {order['total_price']} UZS\n"
        text += f"📊 {status_text}\n"
        text += f"📅 {order['created_at'][:10]}\n"
        text += f"📝 Управление: /order_{order['id']}\n\n"
    
    await message.answer(text)
    await state.set_state(OrderFlow.admin_viewing_orders)

@dp.message(OrderFlow.admin_home, F.text == "📊 Статистика")
async def admin_statistics(message: types.Message, state: FSMContext):
    await message.answer("📊 Выберите тип статистики:", reply_markup=get_statistics_kb())
    await state.set_state(OrderFlow.admin_statistics)

@dp.message(OrderFlow.admin_home, F.text == "🔙 Выход")
async def admin_exit(message: types.Message, state: FSMContext):
    await message.answer("👋 Выход из админки", reply_markup=ReplyKeyboardRemove())
    await state.clear()

# ИСПРАВЛЕННАЯ ЦЕПОЧКА ДОБАВЛЕНИЯ ТОВАРА
@dp.message(OrderFlow.admin_adding_product_name)
async def admin_prod_name(message: types.Message, state: FSMContext):
    await state.update_data(new_prod_name=message.text)
    await message.answer("Введите цену (только цифры):")
    await state.set_state(OrderFlow.admin_adding_product_price)

@dp.message(OrderFlow.admin_adding_product_price)
async def admin_prod_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): 
        return await message.answer("❌ Только цифры!")
    
    await state.update_data(new_prod_price=int(message.text))
    
    await message.answer("Выберите категорию:", reply_markup=ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👕 Формы 2024/2025"), KeyboardButton(text="⚽ Бутсы")]
        ],
        resize_keyboard=True
    ))
    await state.set_state(OrderFlow.admin_adding_product_category)  # ИСПРАВЛЕНО

@dp.message(OrderFlow.admin_adding_product_category)
async def admin_prod_category(message: types.Message, state: FSMContext):
    category_map = {
        "👕 Формы 2024/2025": ("👕 Формы 2024/2025", "👕 2024/2025 Formalari"),
        "⚽ Бутсы": ("⚽ Бутсы", "⚽ Butsalar")
    }
    
    if message.text not in category_map:
        return await message.answer("❌ Выберите из предложенных категорий")
    
    category_ru, category_uz = category_map[message.text]
    await state.update_data(category_ru=category_ru, category_uz=category_uz)
    await message.answer("Отправьте фото товара:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(OrderFlow.admin_adding_product_photo)

@dp.message(OrderFlow.admin_adding_product_photo, F.photo)
async def admin_prod_finish(message: types.Message, state: FSMContext):
    data = await state.get_data()
    add_product(
        data['new_prod_name'], 
        data['new_prod_price'], 
        data['category_ru'], 
        data['category_uz'], 
        message.photo[-1].file_id
    )
    
    await message.answer("✅ Товар добавлен!", reply_markup=get_admin_kb())
    await state.set_state(OrderFlow.admin_home)

# Управление товарами
@dp.callback_query(OrderFlow.admin_managing_products, F.data == "edit_products")
async def edit_products_list(callback: types.CallbackQuery, state: FSMContext):
    products = get_all_products()
    if not products:
        await callback.message.edit_text("📦 Товаров нет")
        return
    
    await callback.message.edit_text(
        "📝 Выберите товар для редактирования:",
        reply_markup=get_products_list_kb(products, "edit")
    )

@dp.callback_query(OrderFlow.admin_managing_products, F.data == "delete_products")
async def delete_products_list(callback: types.CallbackQuery, state: FSMContext):
    products = get_all_products()
    if not products:
        await callback.message.edit_text("📦 Товаров нет")
        return
    
    await callback.message.edit_text(
        "🗑️ Выберите товар для удаления:",
        reply_markup=get_products_list_kb(products, "delete")
    )

@dp.callback_query(OrderFlow.admin_managing_products, F.data.startswith("edit_"))
async def edit_product(callback: types.CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[1])
    product = get_product_by_id(product_id)
    
    if not product:
        await callback.answer("❌ Товар не найден")
        return
    
    await state.update_data(editing_product_id=product_id)
    
    text = f"📝 Редактирование товара:\n\n"
    text += f"Название (RU): {product['name_ru']}\n"
    text += f"Цена: {product['price']} UZS\n\n"
    text += "Отправьте новое название или новую цену цифрами"
    
    await callback.message.edit_text(text)
    await state.set_state(OrderFlow.admin_editing_product)

@dp.message(OrderFlow.admin_editing_product)
async def process_edit_product(message: types.Message, state: FSMContext):
    data = await state.get_data()
    product_id = data['editing_product_id']
    
    if message.text.isdigit():
        update_product(product_id, 'price', int(message.text))
        await message.answer(f"✅ Цена обновлена: {message.text} UZS", reply_markup=get_admin_kb())
        await state.set_state(OrderFlow.admin_home)
    else:
        update_product(product_id, 'name_ru', message.text)
        update_product(product_id, 'name_uz', message.text)
        await message.answer(f"✅ Название обновлено", reply_markup=get_admin_kb())
        await state.set_state(OrderFlow.admin_home)

@dp.callback_query(OrderFlow.admin_managing_products, F.data.startswith("delete_"))
async def delete_product_handler(callback: types.CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[1])
    delete_product(product_id)
    
    await callback.message.edit_text("✅ Товар удален (скрыт из каталога)")
    await callback.answer()

@dp.callback_query(OrderFlow.admin_managing_products, F.data == "back_to_admin")
async def back_to_admin_from_manage(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🛠 Админ-панель")
    await callback.message.answer("Выберите действие:", reply_markup=get_admin_kb())
    await state.set_state(OrderFlow.admin_home)

@dp.callback_query(OrderFlow.admin_statistics, F.data == "back_to_admin")
async def back_to_admin_from_stats(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🛠 Админ-панель")
    await callback.message.answer("Выберите действие:", reply_markup=get_admin_kb())
    await state.set_state(OrderFlow.admin_home)

# Управление заказами
@dp.message(F.text.startswith("/order_"))
async def manage_order_command(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        order_id = int(message.text.split("_")[1])
    except:
        await message.answer("❌ Неверный формат команды")
        return
    
    order = get_order_by_id(order_id)
    if not order:
        await message.answer("❌ Заказ не найден")
        return
    
    user_info = get_user(order['user_id'])
    username = f"@{user_info['name']}" if user_info else f"ID: {order['user_id']}"
    status_text = ORDER_STATUSES.get(order['status'], {}).get('ru', order['status'])
    
    try:
        items = json.loads(order['items'])
        items_text = "\n".join([f"• {item['name']} x{item['quantity']} ({item['price']} UZS)" for item in items])
    except:
        items_text = order['items']
    
    text = f"📦 Заказ #{order_id}\n"
    text += f"👤 Пользователь: {username}\n"
    text += f"📅 Дата: {order['created_at']}\n"
    text += f"💰 Сумма: {order['total_price']} UZS\n"
    text += f"📊 Текущий статус: {status_text}\n\n"
    text += f"📦 Товары:\n{items_text}\n\n"
    text += "🔄 Выберите новый статус:"
    
    await message.answer(text, reply_markup=get_order_status_kb(order_id))

@dp.callback_query(F.data.startswith("setstatus_"))
async def set_order_status(callback: types.CallbackQuery, state: FSMContext):
    _, order_id, new_status = callback.data.split("_")
    order_id = int(order_id)
    
    update_order_status(order_id, new_status)
    status_text = ORDER_STATUSES.get(new_status, {}).get('ru', new_status)
    
    order = get_order_by_id(order_id)
    if order:
        user = get_user(order['user_id'])
        if user:
            lang = user['language']
            status_user_text = ORDER_STATUSES.get(new_status, {}).get(lang, new_status)
            try:
                await bot.send_message(
                    order['user_id'],
                    f"📦 Статус вашего заказа #{order_id} изменен:\n\n"
                    f"🔄 Новый статус: {status_user_text}\n"
                    f"💰 Сумма: {order['total_price']} UZS"
                )
            except:
                pass
    
    await callback.message.edit_text(f"✅ Статус заказа #{order_id} изменен на: {status_text}")
    await callback.answer()

# Статистика
@dp.callback_query(OrderFlow.admin_statistics, F.data == "stats_current")
async def show_current_stats(callback: types.CallbackQuery, state: FSMContext):
    stats = get_monthly_statistics()
    
    if not stats or stats['total_orders'] == 0:
        await callback.message.edit_text("📊 Нет данных за текущий месяц")
        return
    
    text = f"📊 Статистика за текущий месяц:\n\n"
    text += f"📦 Всего заказов: {stats['total_orders']}\n"
    text += f"✅ Доставлено заказов: {stats['delivered_orders']}\n"
    text += f"💰 Общая выручка: {stats['total_revenue'] or 0} UZS\n"
    text += f"📈 Средний чек: {int(stats['avg_order_value'] or 0)} UZS"
    
    await callback.message.edit_text(text)

@dp.callback_query(OrderFlow.admin_statistics, F.data == "stats_products")
async def show_product_stats(callback: types.CallbackQuery, state: FSMContext):
    stats = get_product_statistics()
    
    if not stats:
        await callback.message.edit_text("📦 Нет данных по продажам товаров")
        return
    
    text = "📈 Топ товаров по продажам:\n\n"
    for i, item in enumerate(stats, 1):
        text += f"{i}. {item['name_ru']}\n"
        text += f"   📦 Продано: {item['total_quantity']} шт.\n"
        text += f"   🛒 Заказов: {item['times_ordered']}\n\n"
    
    await callback.message.edit_text(text)

# ================== WEB SERVER ==================
async def handle_ping(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

# ================== ЗАПУСК ==================
async def main():
    setup_database()
    await start_web_server()
    
    print("🚀 Бот запущен...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())