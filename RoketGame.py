import sqlite3
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import random
import datetime
import logging
import re
from threading import Lock
import uuid
import asyncio

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("rocket_war_final.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

TOKEN = " "
DB_FILE = "rocket_war_final.db"
ADMIN_IDS = [ ]
CHAT_ID_FOR_LUCKY_BOX = -1002817956837 # این متغیر در حال حاضر استفاده نمی‌شود، اما در صورت نیاز برای ارسال به یک چت خاص می‌تواند مفید باشد.

# --- Game Data (Optimized for direct access) ---
MISSILES = {
    "فاتح": {"name": "🪖 فاتح", "damage": 85, "cost": 450, "cooldown": 3000, "required_level": 1, "emoji": "🪖", "type": "بالستیک"},
    "عماد": {"name": "⚡ عماد", "damage": 70, "cost": 350, "cooldown": 2000, "required_level": 1, "emoji": "⚡", "type": "بالستیک"},
    "سجیل": {"name": "🔥 سجیل", "damage": 95, "cost": 550, "cooldown": 4000, "required_level": 2, "emoji": "🔥", "type": "بالستیک"},
    "خیبرشکن": {"name": "💥 خیبرشکن", "damage": 110, "cost": 700, "cooldown": 5000, "required_level": 2, "emoji": "💥", "type": "بالستیک"},
    "خرمشهر": {"name": "🌪️ خرمشهر", "damage": 90, "cost": 600, "cooldown": 3800, "required_level": 2, "emoji": "🌪️", "type": "کروز"},
    "ذوالفقار": {"name": "⚔️ ذوالفقار", "damage": 75, "cost": 400, "cooldown": 2800, "required_level": 1, "emoji": "⚔️", "type": "کروز"},
    "شهاب": {"name": "☄️ شهاب", "damage": 120, "cost": 900, "cooldown": 5500, "required_level": 3, "emoji": "☄️", "type": "بالستیک"},
    "قدر": {"name": "🌟 قدر", "damage": 150, "cost": 1100, "cooldown": 6500, "required_level": 5, "emoji": "🌟", "type": "بالستیک"},
    "هسته‌ای": {"name": "☢️ هسته‌ای", "damage": 300, "cost": 2200, "cooldown": 12000, "required_level": 8, "emoji": "☢️", "type": "استراتژیک", "special": "آسیب به کل منطقه"},
    "قادر": {"name": "🌊 قادر", "damage": 100, "cost": 750, "cooldown": 3500, "required_level": 4, "emoji": "🌊", "type": "کروز ضدکشتی"},
    "یا علی": {"name": "🚀 یا علی", "damage": 110, "cost": 850, "cooldown": 4000, "required_level": 5, "emoji": "🚀", "type": "کروز زمین به دریا"},
    "هویزه": {"name": "🛣️ هویزه", "damage": 120, "cost": 950, "cooldown": 4500, "required_level": 6, "emoji": "🛣️", "type": "کروز زمینی"},
    "خلیج فارس": {"name": "⚓ خلیج فارس", "damage": 130, "cost": 1000, "cooldown": 5000, "required_level": 7, "emoji": "⚓", "type": "بالستیک ضدکشتی"},
    "طوفان": {"name": "🌪️ طوفان", "damage": 60, "cost": 280, "cooldown": 1500, "required_level": 1, "emoji": "🌪️", "type": "ضدزره"},
    "الماس": {"name": "💎 الماس", "damage": 70, "cost": 380, "cooldown": 1800, "required_level": 2, "emoji": "💎", "type": "ضدزره هواپرتاب"},
    "ابومهدی": {"name": "🚢 ابومهدی", "damage": 140, "cost": 1100, "cooldown": 5500, "required_level": 8, "emoji": "🚢", "type": "کروز دریایی"},
    "دهلاویه": {"name": "🎯 دهلاویه", "damage": 80, "cost": 480, "cooldown": 2200, "required_level": 3, "emoji": "🎯", "type": "ضدزره"}
}

DEFENSE_SYSTEMS = {
    "پدافند": {"name": "🛡️ پدافند", "protection": 30, "cost": 500, "max_level": 5, "emoji": "🛡️", "upgrade_cost": 250, "salary": 50},
    "رادار": {"name": "📡 رادار", "detection": 0.4, "cost": 350, "max_level": 4, "emoji": "📡", "upgrade_cost": 180, "salary": 40},
    "سامانه": {"name": "🚀 سامانه", "intercept": 0.5, "cost": 700, "max_level": 4, "emoji": "🚀", "upgrade_cost": 350, "salary": 70},
    "گنبد": {"name": "🕌 گنبد آهنین", "protection": 50, "cost": 1000, "max_level": 5, "emoji": "🕌", "upgrade_cost": 500, "salary": 100},
    "پدافند هوایی": {"name": "✈️ پدافند هوایی", "protection": 40, "cost": 800, "max_level": 5, "emoji": "✈️", "upgrade_cost": 400, "salary": 80},
    "پدافند ساحلی": {"name": "⚓ پدافند ساحلی", "protection": 35, "cost": 600, "max_level": 5, "emoji": "⚓", "upgrade_cost": 300, "salary": 60}
}

CYBER_DEFENSES = {
    "فایروال": {"name": "🧱 فایروال", "protection_chance": 0.3, "cost": 700, "max_level": 3, "emoji": "🧱", "upgrade_cost": 350, "salary": 70},
    "آنتی‌ویروس": {"name": "🦠 آنتی‌ویروس", "protection_value": 0.2, "cost": 600, "max_level": 3, "emoji": "🦠", "upgrade_cost": 300, "salary": 60}
}

TANKS = {
    "تی-72": {"name": "🇷🇺 تی-72", "damage": 60, "cost": 700, "cooldown": 1500, "required_level": 2, "emoji": "🇷🇺", "type": "متوسط", "max_health": 100, "repair_cost_per_hp": 5},
    "آبرامز": {"name": "🇺🇸 آبرامز", "damage": 80, "cost": 1100, "cooldown": 2000, "required_level": 4, "emoji": "🇺🇸", "type": "سنگین", "max_health": 120, "repair_cost_per_hp": 6},
    "چلنجر": {"name": "🇬🇧 چلنجر", "damage": 75, "cost": 1000, "cooldown": 1800, "required_level": 3, "emoji": "🇬🇧", "type": "سنگین", "max_health": 110, "repair_cost_per_hp": 5},
    "مرکاوا": {"name": "🇮🇱 مرکاوا", "damage": 70, "cost": 900, "cooldown": 1700, "required_level": 2, "emoji": "🇮🇱", "type": "متوسط", "max_health": 105, "repair_cost_per_hp": 5},
    "ذوالفقار": {"name": "🇮🇷 ذوالفقار", "damage": 85, "cost": 1200, "cooldown": 2200, "required_level": 5, "emoji": "🇮🇷", "type": "سنگین", "max_health": 130, "repair_cost_per_hp": 7},
    "سبلان": {"name": "🇮🇷 سبلان", "damage": 70, "cost": 800, "cooldown": 1900, "required_level": 3, "emoji": "🇮🇷", "type": "متوسط", "max_health": 95, "repair_cost_per_hp": 4}
}

FIGHTERS = {
    "اف-16": {"name": "🇺🇸 اف-16", "damage": 70, "cost": 900, "cooldown": 2000, "required_level": 3, "emoji": "🇺🇸", "type": "چندمنظوره", "max_health": 80, "repair_cost_per_hp": 7},
    "سوخو-35": {"name": "🇷🇺 سوخو-35", "damage": 85, "cost": 1300, "cooldown": 3000, "required_level": 5, "emoji": "🇷🇺", "type": "برتری هوایی", "max_health": 90, "repair_cost_per_hp": 8},
    "میراژ-2000": {"name": "🇫🇷 میراژ-2000", "damage": 65, "cost": 800, "cooldown": 1800, "required_level": 2, "emoji": "🇫🇷", "type": "رهگیر", "max_health": 75, "repair_cost_per_hp": 6},
    "کوثر": {"name": "🇮🇷 کوثر", "damage": 75, "cost": 1000, "cooldown": 2200, "required_level": 4, "emoji": "🇮🇷", "type": "جنگنده سبک", "max_health": 85, "repair_cost_per_hp": 7},
    "صاعقه": {"name": "🇮🇷 صاعقه", "damage": 80, "cost": 1100, "cooldown": 2400, "required_level": 4, "emoji": "🇮🇷", "type": "جنگنده بمب‌افکن", "max_health": 88, "repair_cost_per_hp": 7},
    "آذرخش": {"name": "🇮🇷 آذرخش", "damage": 70, "cost": 900, "cooldown": 2000, "required_level": 3, "emoji": "🇮🇷", "type": "جنگنده پشتیبانی", "max_health": 78, "repair_cost_per_hp": 6},
    "یاک-۱۳۰": {"name": "🇷🇺 یاک-۱۳۰", "damage": 60, "cost": 700, "cooldown": 1700, "required_level": 2, "emoji": "🇷🇺", "type": "جنگنده آموزشی", "max_health": 70, "repair_cost_per_hp": 5},
    "کمان-۲۲": {"name": "🇮🇷 کمان-۲۲", "damage": 90, "cost": 1600, "cooldown": 3500, "required_level": 6, "emoji": "🇮🇷", "type": "پهپاد رزمی", "max_health": 95, "repair_cost_per_hp": 9}
}

WARSHIPS = {
    "ناوچه": {"name": "🚢 ناوچه", "damage": 90, "cost": 1600, "cooldown": 4000, "required_level": 6, "emoji": "🚢", "type": "سطحی", "max_health": 150, "repair_cost_per_hp": 4},
    "ناوشکن": {"name": "⚓ ناوشکن", "damage": 110, "cost": 2200, "cooldown": 5000, "required_level": 8, "emoji": "⚓", "type": "سطحی", "max_health": 180, "repair_cost_per_hp": 5},
    "زیردریایی": {"name": "🚤 زیردریایی", "damage": 130, "cost": 2700, "cooldown": 6000, "required_level": 10, "emoji": "🚤", "type": "پنهان‌کار", "max_health": 130, "repair_cost_per_hp": 6},
    "جماران": {"name": "🇮🇷 جماران", "damage": 95, "cost": 1700, "cooldown": 4200, "required_level": 7, "emoji": "🇮🇷", "type": "ناوچه موشک‌انداز", "max_health": 160, "repair_cost_per_hp": 4},
    "دنا": {"name": "🇮🇷 دنا", "damage": 100, "cost": 1900, "cooldown": 4700, "required_level": 7, "emoji": "🇮🇷", "type": "ناوچه", "max_health": 170, "repair_cost_per_hp": 4},
    "شهید سلیمانی": {"name": "🇮🇷 شهید سلیمانی", "damage": 120, "cost": 2500, "cooldown": 5500, "required_level": 9, "emoji": "🇮🇷", "type": "شناور موشک‌انداز", "max_health": 190, "repair_cost_per_hp": 5},
    "کمان": {"name": "🇮🇷 کمان", "damage": 80, "cost": 1400, "cooldown": 3500, "required_level": 5, "emoji": "🇮🇷", "type": "قایق موشک‌انداز", "max_health": 140, "repair_cost_per_hp": 3},
    "خارک": {"name": "🇮🇷 خارک", "damage": 50, "cost": 900, "cooldown": 2500, "required_level": 4, "emoji": "🇮🇷", "type": "ناو لجستیکی", "max_health": 200, "repair_cost_per_hp": 2}
}

DRONES = {
    "شاهد-136": {"name": "💥 شاهد-136", "damage": 70, "cost": 800, "cooldown": 2000, "required_level": 3, "emoji": "💥", "type": "انتحاری", "max_health": 60, "repair_cost_per_hp": 8},
    "آرش": {"name": "🚀 آرش", "damage": 85, "cost": 1100, "cooldown": 2500, "required_level": 4, "emoji": "🚀", "type": "انتحاری", "max_health": 70, "repair_cost_per_hp": 9},
    "کمان-12": {"name": "🎯 کمان-12", "damage": 60, "cost": 700, "cooldown": 1800, "required_level": 2, "emoji": "🎯", "type": "شناسایی-رزمی", "max_health": 55, "repair_cost_per_hp": 7}
}

CYBER_ATTACKS = {
    "هک اطلاعات": {"name": "🕵️‍♂️ هک اطلاعات", "cost": 1000, "cooldown": 7200, "required_level": 5, "emoji": "🕵️‍♂️", "type": "اطلاعاتی", "effect": "disrupt_defense", "salary": 100},
    "هک مالی": {"name": "💸 هک مالی", "cost": 1500, "cooldown": 10800, "required_level": 7, "emoji": "💸", "type": "مالی", "effect": "steal_toman", "salary": 150}
}

RESOURCES = {
    "تومان": {"name": "💰 تومان", "default": 5000, "emoji": "💰"},
    "جام": {"name": "🏆 جام", "default": 100, "emoji": "🏆"},
    "یاقوت": {"name": "💎 یاقوت", "default": 50, "emoji": "💎"}
}

RUBY_TO_TOMAN_RATE = 350

# Combine all defense systems for easier lookup
ALL_DEFENSES = {**DEFENSE_SYSTEMS, **CYBER_DEFENSES}

# --- Global State & Locks ---
db_lock = Lock()
# user_panel_messages = {} # این دیکشنری برای مدیریت پیام‌های پنل کاربر استفاده می‌شد و باعث مشکل "منقضی شدن" می‌شد.
# به جای آن، هر بار که یک پنل جدید باز می‌شود، پیام قبلی ویرایش می‌شود یا یک پیام جدید ارسال می‌شود.
local_storage = asyncio.Lock() # For async DB access

# --- Database Operations ---
def get_db_connection_sync():
    """Establishes a synchronous SQLite connection."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

async def execute_db_operation(operation_func, *args):
    """
    Executes a database operation asynchronously, ensuring thread safety.
    The actual DB interaction (operation_func) is synchronous but wrapped.
    """
    async with local_storage:
        conn = get_db_connection_sync()
        try:
            cursor = conn.cursor()
            result = operation_func(cursor, *args)
            conn.commit()
            return result
        except Exception as e:
            conn.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            conn.close()

def init_db():
    """Initializes the database schema."""
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, level INTEGER DEFAULT 1,
            experience INTEGER DEFAULT 0, health INTEGER DEFAULT 100, base_health INTEGER DEFAULT 100,
            shield INTEGER DEFAULT 0, last_attack TEXT, last_treatment TEXT, last_login TEXT,
            created_at TEXT, is_admin BOOLEAN DEFAULT FALSE, notification_enabled BOOLEAN DEFAULT TRUE,
            last_daily_bonus TEXT, cyber_defense_disrupted_until TEXT, last_bank_withdrawal TEXT,
            base_health_level INTEGER DEFAULT 1, shield_level INTEGER DEFAULT 1, mine_ruby_level INTEGER DEFAULT 1)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS resources (
            player_id INTEGER, type TEXT, amount INTEGER, PRIMARY KEY (player_id, type))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS missiles (
            player_id INTEGER, type TEXT, count INTEGER DEFAULT 0, last_used TEXT, PRIMARY KEY (player_id, type))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS defenses (
            player_id INTEGER, type TEXT, level INTEGER DEFAULT 0, health INTEGER DEFAULT 100, last_paid TEXT, PRIMARY KEY (player_id, type))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS battles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, attacker_id INTEGER, defender_id INTEGER, weapon_type TEXT,
            result TEXT, damage INTEGER, resources_stolen TEXT, timestamp TEXT, attack_mode TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS tanks (
            player_id INTEGER, type TEXT, count INTEGER DEFAULT 0, last_used TEXT, health INTEGER DEFAULT 100, PRIMARY KEY (player_id, type))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS fighters (
            player_id INTEGER, type TEXT, count INTEGER DEFAULT 0, last_used TEXT, health INTEGER DEFAULT 100, PRIMARY KEY (player_id, type))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS warships (
            player_id INTEGER, type TEXT, count INTEGER DEFAULT 0, last_used TEXT, health INTEGER DEFAULT 100, PRIMARY KEY (player_id, type))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS drones (
            player_id INTEGER, type TEXT, count INTEGER DEFAULT 0, last_used TEXT, health INTEGER DEFAULT 100, PRIMARY KEY (player_id, type))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS cyber_attacks (
            player_id INTEGER, type TEXT, last_used TEXT, last_paid TEXT, PRIMARY KEY (player_id, type))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY, chat_title TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS mines (
            player_id INTEGER, type TEXT, last_collected TEXT, level INTEGER DEFAULT 1, PRIMARY KEY (player_id, type))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS attack_cooldowns (
            attacker_id INTEGER, defender_id INTEGER, attack_count INTEGER DEFAULT 0, last_attack_time TEXT, cooldown_until TEXT, PRIMARY KEY (attacker_id, defender_id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS active_lucky_boxes (
            lucky_box_id TEXT PRIMARY KEY, chat_id INTEGER, message_id INTEGER, opened_by INTEGER DEFAULT NULL, opened_at TEXT DEFAULT NULL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS gift_codes (
            code TEXT PRIMARY KEY, reward_type TEXT, min_amount INTEGER, max_amount INTEGER,
            ruby_amount INTEGER, exp_amount INTEGER, uses_left INTEGER, max_uses INTEGER)''')

        cursor.execute('DROP TABLE IF EXISTS missions') # Clean up old tables

        for admin_id in ADMIN_IDS:
            cursor.execute('INSERT OR IGNORE INTO players (id, username, is_admin) VALUES (?, ?, ?)', (admin_id, "Admin", True))
            for res_type, res_info in RESOURCES.items():
                cursor.execute('INSERT OR IGNORE INTO resources (player_id, type, amount) VALUES (?, ?, ?)',
                             (admin_id, res_type, res_info["default"] * 10))
        conn.commit()
        conn.close()
        logger.info("پایگاه داده با موفقیت مقداردهی اولیه شد.")

# --- Player Management ---
async def add_experience(player_id, amount):
    def _add_experience_db(cursor, player_id, amount):
        cursor.execute('SELECT level, experience FROM players WHERE id = ?', (player_id,))
        player_data = cursor.fetchone()
        if not player_data:
            logger.warning(f"بازیکن {player_id} یافت نشد. امکان افزودن تجربه وجود ندارد.")
            return ""
        current_level, current_exp = player_data['level'], player_data['experience']

        new_exp = current_exp + amount
        required_exp_for_next_level = current_level * 1000

        level_up_message = ""
        if new_exp >= required_exp_for_next_level:
            new_level = current_level + 1
            new_exp -= required_exp_for_next_level
            cursor.execute('UPDATE players SET level = ?, experience = ? WHERE id = ?', (new_level, new_exp, player_id))
            level_up_message = f"🎉 تبریک می‌گوییم، فرمانده! شما به سطح {new_level} رسیدید! 🚀"
        else:
            cursor.execute('UPDATE players SET experience = ? WHERE id = ?', (new_exp, player_id))
        return level_up_message
    return await execute_db_operation(_add_experience_db, player_id, amount)

async def remove_experience(player_id, amount):
    def _remove_experience_db(cursor, player_id, amount):
        cursor.execute('SELECT level, experience FROM players WHERE id = ?', (player_id,))
        player_data = cursor.fetchone()
        if not player_data:
            logger.warning(f"بازیکن {player_id} یافت نشد. امکان کسر تجربه وجود ندارد.")
            return ""
        current_level, current_exp = player_data['level'], player_data['experience']

        new_exp = max(0, current_exp - amount)
        level_down_message = ""
        while current_level > 1 and new_exp < (current_level - 1) * 1000:
            current_level -= 1
            new_exp += current_level * 1000
            level_down_message = f"📉 متاسفانه، شما به سطح {current_level} سقوط کردید!"

        cursor.execute('UPDATE players SET level = ?, experience = ? WHERE id = ?', (current_level, new_exp, player_id))
        return level_down_message
    return await execute_db_operation(_remove_experience_db, player_id, amount)

async def get_or_create_player(user_id, username, first_name):
    def _get_or_create_player_db(cursor, user_id, username, first_name):
        cursor.execute('SELECT * FROM players WHERE id = ?', (user_id,))
        player = cursor.fetchone()
        now = datetime.datetime.now().isoformat()
        if not player:
            cursor.execute('INSERT INTO players (id, username, first_name, created_at, last_login) VALUES (?, ?, ?, ?, ?)',
                (user_id, username, first_name, now, now))
            for res_type, res_info in RESOURCES.items():
                cursor.execute('INSERT INTO resources (player_id, type, amount) VALUES (?, ?, ?)',
                             (user_id, res_type, res_info["default"]))
            cursor.execute('INSERT OR IGNORE INTO missiles (player_id, type, count) VALUES (?, "فاتح", 2)', (user_id,))
            cursor.execute('INSERT OR IGNORE INTO missiles (player_id, type, count) VALUES (?, "عماد", 1)', (user_id,))
            cursor.execute('INSERT OR IGNORE INTO defenses (player_id, type, level, health, last_paid) VALUES (?, "پدافند", 1, 100, ?)', (user_id, now))
            cursor.execute('INSERT OR IGNORE INTO mines (player_id, type, last_collected, level) VALUES (?, "یاقوت", ?, 1)', (user_id, now))
            logger.info(f"کاربر جدید ایجاد شد: {username} ({user_id})")
        cursor.execute('UPDATE players SET last_login = ? WHERE id = ?', (now, user_id))
        return True
    return await execute_db_operation(_get_or_create_player_db, user_id, username, first_name)

def is_admin(user_id):
    return user_id in ADMIN_IDS

# --- Utility Functions ---
async def get_target_info(text, reply_to_message):
    target_id = None
    target_username = "ناشناس"

    if reply_to_message:
        target_user = reply_to_message.from_user
        target_id = target_user.id
        target_username = target_user.username or target_user.first_name
    else:
        target_match = re.search(r'به\s+@?([\w\u0600-\u06FF]+)', text)
        if target_match:
            target_username_from_text = target_match.group(1)
            def _get_target_id_db(cursor, username_or_name):
                cursor.execute('SELECT id, username, first_name FROM players WHERE username = ? OR first_name = ?', (username_or_name, username_or_name))
                return cursor.fetchone()
            result = await execute_db_operation(_get_target_id_db, target_username_from_text, target_username_from_text)
            if result:
                target_id = result['id']
                target_username = result['username'] or result['first_name']
    return target_id, target_username

async def send_attack_notification(context, target_id, attacker_id, weapon_type, attack_result, attack_mode):
    try:
        def _get_player_info_db(cursor, player_id):
            cursor.execute('SELECT username, first_name, level, notification_enabled FROM players WHERE id = ?', (player_id,))
            return cursor.fetchone()

        attacker_info = await execute_db_operation(_get_player_info_db, attacker_id)
        if not attacker_info:
            logger.error(f"اطلاعات مهاجم {attacker_id} یافت نشد. امکان ارسال اعلان وجود ندارد.")
            return

        attacker_name = attacker_info['username'] or attacker_info['first_name'] or "یک فرمانده"
        attacker_level = attacker_info['level']

        target_player_data = await execute_db_operation(_get_player_info_db, target_id)
        if not target_player_data or not target_player_data['notification_enabled']:
            if not target_player_data:
                logger.warning(f"بازیکن هدف {target_id} یافت نشد یا ربات را مسدود کرده است. اعلان ارسال نشد.")
            return

        stolen_toman = attack_result['stolen'].get('تومان', 0)
        stolen_cups = attack_result['stolen'].get('جام', 0)

        weapon_name = "ناشناس"
        weapon_damage = "نامشخص"
        attack_emoji = "❓"

        if attack_mode == "موشکی":
            weapon_info = MISSILES.get(weapon_type)
            if weapon_info:
                weapon_name = weapon_info['name']
                weapon_damage = weapon_info['damage']
                attack_emoji = "🚀"
        elif attack_mode == "زمینی":
            weapon_info = TANKS.get(weapon_type)
            if weapon_info:
                weapon_name = weapon_info['name']
                weapon_damage = weapon_info['damage']
                attack_emoji = "⚔️"
        elif attack_mode == "هوایی":
            weapon_info = FIGHTERS.get(weapon_type)
            if weapon_info:
                weapon_name = weapon_info['name']
                weapon_damage = weapon_info['damage']
                attack_emoji = "✈️"
        elif attack_mode == "دریایی":
            weapon_info = WARSHIPS.get(weapon_type)
            if weapon_info:
                weapon_name = weapon_info['name']
                weapon_damage = weapon_info['damage']
                attack_emoji = "🚢"
        elif attack_mode == "پهپادی":
            weapon_info = DRONES.get(weapon_type)
            if weapon_info:
                weapon_name = weapon_info['name']
                weapon_damage = weapon_info['damage']
                attack_emoji = "🚁"
        elif attack_mode == "سایبری":
            weapon_info = CYBER_ATTACKS.get(weapon_type)
            if weapon_info:
                weapon_name = weapon_info['name']
                weapon_damage = "نامشخص"
                attack_emoji = "💻"

        attack_message = (
            f"*🚨 شما مورد حمله قرار گرفتید! 🚨*\n\n"
            f"*⚔️ مهاجم:* {attacker_name} (سطح {attacker_level})\n"
            f"*{attack_emoji} حمله {attack_mode} دریافت شده:* {weapon_name} (میزان آسیب: {weapon_damage})\n"
        )
        if stolen_toman > 0:
            attack_message += f"*💰 تومان از دست رفته:* {stolen_toman} 💰\n"
        if stolen_cups > 0:
            attack_message += f"*🏆 جام از دست رفته:* {stolen_cups}\n"

        if attack_mode != "سایبری":
            attack_message += f"*❤️ سلامت فعلی پایگاه:* {attack_result['remaining_health']}\n\n"

        if attack_result.get('effect_applied'):
            attack_message += f"*✨ اثر حمله: {attack_result['effect_applied']}*\n\n"

        attack_message += f"*🩹 برای درمان سریع از دستور /treat استفاده کنید!*"

        await context.bot.send_message(chat_id=target_id, text=attack_message, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        if "blocked" in str(e).lower():
            logger.warning(f"کاربر {target_id} ربات را مسدود کرده است. اعلان ارسال نشد.")
        else:
            logger.error(f"خطا در ارسال اعلان حمله به {target_id}: {e}")

# --- Core Game Logic (Attacks) ---
async def handle_attack_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, attack_type_map, attack_mode_name, execute_attack_func):
    user_id = update.effective_user.id
    text = update.message.text

    target_id, target_username = await get_target_info(text, update.message.reply_to_message)

    if not target_id:
        await update.message.reply_text(f"*❌ کاربر هدف یافت نشد! به پیام او پاسخ دهید یا از فرمت '{attack_mode_name} [نوع] به [نام کاربری]' استفاده کنید.*", parse_mode=constants.ParseMode.MARKDOWN)
        return

    weapon_type_match = next((w for w in attack_type_map if w in text), None)
    if not weapon_type_match:
        await update.message.reply_text(f"*❌ نوع {attack_mode_name} مشخص نشده است! لطفاً نام صحیح را وارد کنید.*", parse_mode=constants.ParseMode.MARKDOWN)
        return
    weapon_type = weapon_type_match

    if target_id == user_id:
        await update.message.reply_text("*😂 فرمانده، شما نمی‌توانید به خودتان حمله کنید!*", parse_mode=constants.ParseMode.MARKDOWN)
        return

    def _check_admin_status_db(cursor, user_id_to_check):
        cursor.execute('SELECT is_admin FROM players WHERE id = ?', (user_id_to_check,))
        result = cursor.fetchone()
        return result['is_admin'] if result else False

    is_attacker_admin = await execute_db_operation(_check_admin_status_db, user_id)
    is_defender_admin = await execute_db_operation(_check_admin_status_db, target_id)

    if is_defender_admin and not is_attacker_admin:
        await update.message.reply_text("*🛡️ شما جرات حمله به یک ادمین را ندارید!*", parse_mode=constants.ParseMode.MARKDOWN)
        return

    def _get_attack_cooldown_db(cursor, attacker_id, defender_id):
        cursor.execute('SELECT attack_count, cooldown_until FROM attack_cooldowns WHERE attacker_id = ? AND defender_id = ?', (attacker_id, defender_id))
        return cursor.fetchone()

    cooldown_data = await execute_db_operation(_get_attack_cooldown_db, user_id, target_id)

    if cooldown_data:
        cooldown_until_str = cooldown_data['cooldown_until']
        if cooldown_until_str:
            cooldown_until = datetime.datetime.fromisoformat(cooldown_until_str)
            if datetime.datetime.now() < cooldown_until:
                remaining_seconds = int((cooldown_until - datetime.datetime.now()).total_seconds())
                remaining_minutes = remaining_seconds // 60
                await update.message.reply_text(f"*❌ شما نمی‌توانید تا {remaining_minutes} دقیقه دیگر به {target_username} حمله کنید!*", parse_mode=constants.ParseMode.MARKDOWN)
                return

    success, result = await execute_attack_func(user_id, target_id, weapon_type, context)

    if success:
        def _update_attack_cooldown_db(cursor, attacker_id, defender_id, new_attack_count, cooldown_until_iso):
            cursor.execute('REPLACE INTO attack_cooldowns (attacker_id, defender_id, attack_count, last_attack_time, cooldown_until) VALUES (?, ?, ?, ?, ?)',
                           (attacker_id, defender_id, new_attack_count, datetime.datetime.now().isoformat(), cooldown_until_iso))

        new_attack_count = (cooldown_data['attack_count'] + 1) if cooldown_data else 1
        cooldown_until = None
        if new_attack_count >= 5: # Limit to 1 attack in a row, then 15 min cooldown
            cooldown_until = (datetime.datetime.now() + datetime.timedelta(seconds=5)).isoformat()
            new_attack_count = 0

        await execute_db_operation(_update_attack_cooldown_db, user_id, target_id, new_attack_count, cooldown_until)

        await send_attack_notification(context, target_id, user_id, weapon_type, result, attack_mode_name)
        stolen_toman = result['stolen'].get('تومان', 0)
        stolen_cups = result['stolen'].get('جام', 0)

        weapon_info = attack_type_map.get(weapon_type, {})
        weapon_emoji = weapon_info.get('emoji', '❓')
        weapon_display_name = weapon_info.get('name', weapon_type)

        result_text = (
            f"*🔥 نتیجه حمله {attack_mode_name} به {target_username} 🔥*\n\n"
            f"*{weapon_emoji} {weapon_display_name} شلیک شد:*\n"
            f"*💥 آسیب وارد شده:* *{result['damage']}*\n"
            f"*❤️ سلامت باقی‌مانده هدف:* *{result['remaining_health']}*\n\n"
            f"*💰 غنایم جنگی:*\n"
            f"*{RESOURCES['تومان']['emoji']} تومان:* *{stolen_toman}*\n"
            f"*{RESOURCES['جام']['emoji']} جام:* *{stolen_cups}*\n\n"
            f"*✅ ماموریت با موفقیت انجام شد، فرمانده!*"
        )
        if result.get('effect_applied'):
            result_text += f"\n\n*✨ اثر حمله سایبری: {result['effect_applied']}*"

        await update.message.reply_text(result_text, parse_mode=constants.ParseMode.MARKDOWN)

        exp_gain = 0
        cup_gain = 0
        if attack_mode_name == "موشکی": exp_gain, cup_gain = 50, 10
        elif attack_mode_name == "زمینی": exp_gain, cup_gain = 30, 5
        elif attack_mode_name == "هوایی": exp_gain, cup_gain = 40, 7
        elif attack_mode_name == "دریایی": exp_gain, cup_gain = 60, 12
        elif attack_mode_name == "پهپادی": exp_gain, cup_gain = 35, 6
        elif attack_mode_name == "سایبری": exp_gain, cup_gain = 25, 4

        level_up_msg_attacker = await add_experience(user_id, exp_gain)
        if level_up_msg_attacker:
            await update.message.reply_text(level_up_msg_attacker, parse_mode=constants.ParseMode.MARKDOWN)

        def _add_cups_db(cursor, player_id, amount):
            cursor.execute('UPDATE resources SET amount = amount + ? WHERE player_id = ? AND type = "جام"', (amount, player_id))
        await execute_db_operation(_add_cups_db, user_id, cup_gain)

        exp_loss = exp_gain // 2
        cup_loss = cup_gain // 2
        await remove_experience(target_id, exp_loss)
        def _remove_cups_db(cursor, player_id, amount):
            cursor.execute('UPDATE resources SET amount = MAX(0, amount - ?) WHERE player_id = ? AND type = "جام"', (amount, player_id))
        await execute_db_operation(_remove_cups_db, target_id, cup_loss)

    else:
        await update.message.reply_text(f"*❌ اوه! حمله {attack_mode_name} شکست خورد! ❌*\n\n*دلیل: {result}*", parse_mode=constants.ParseMode.MARKDOWN)

async def execute_missile_attack(attacker_id, defender_id, missile_type, context):
    def _execute_missile_attack_db(cursor, attacker_id, defender_id, missile_type):
        attacker_player_data = cursor.execute('SELECT level, is_admin FROM players WHERE id = ?', (attacker_id,)).fetchone()
        if not attacker_player_data: return False, "اطلاعات مهاجم یافت نشد!"
        attacker_level, is_attacker_admin = attacker_player_data['level'], attacker_player_data['is_admin']

        missile_info = MISSILES[missile_type]

        if not is_attacker_admin:
            missile_data = cursor.execute('SELECT count, last_used FROM missiles WHERE player_id = ? AND type = ?', (attacker_id, missile_type)).fetchone()
            if not missile_data or missile_data['count'] <= 0: return False, "فرمانده، موشک کافی ندارید!"

            if missile_data['last_used']:
                last_time = datetime.datetime.fromisoformat(missile_data['last_used'])
                cooldown = datetime.timedelta(seconds=missile_info["cooldown"])
                if datetime.datetime.now() - last_time < cooldown:
                    remaining = int((last_time + cooldown - datetime.datetime.now()).total_seconds() / 60)
                    return False, f"موشک در حال شارژ مجدد است! {remaining} دقیقه دیگر تلاش کنید. ⏳"

            if attacker_level < missile_info["required_level"]:
                return False, f"برای استفاده از این موشک باید به سطح {missile_info['required_level']} برسید! 📈"

        defender_data = cursor.execute('SELECT health, base_health, shield, cyber_defense_disrupted_until FROM players WHERE id = ?', (defender_id,)).fetchone()
        if not defender_data: return False, "کاربر هدف (مدافع) یافت نشد! 🕵️‍♂️"
        defender_health, base_health, shield, cyber_disrupted_until = defender_data['health'], defender_data['base_health'], defender_data['shield'], defender_data['cyber_defense_disrupted_until']

        is_cyber_disrupted = cyber_disrupted_until and datetime.datetime.now() < datetime.datetime.fromisoformat(cyber_disrupted_until)

        defenses_raw = cursor.execute('SELECT type, level, health, last_paid FROM defenses WHERE player_id = ? AND level > 0', (defender_id,)).fetchall()
        defenses = {row['type']: {'level': row['level'], 'health': row['health'], 'last_paid': row['last_paid']} for row in defenses_raw}

        total_protection = shield
        defense_chance = 0

        if not is_cyber_disrupted:
            for def_type, def_info in defenses.items():
                if def_type in DEFENSE_SYSTEMS and datetime.datetime.now() - datetime.datetime.fromisoformat(def_info['last_paid']) < datetime.timedelta(hours=24):
                    if def_type == "پدافند": total_protection += DEFENSE_SYSTEMS["پدافند"]["protection"] * def_info["level"]
                    elif def_type == "گنبد": total_protection += DEFENSE_SYSTEMS["گنبد"]["protection"] * def_info["level"]
                    elif def_type == "رادار": defense_chance += DEFENSE_SYSTEMS["رادار"]["detection"] * def_info["level"]
                    elif def_type == "سامانه": defense_chance += DEFENSE_SYSTEMS["سامانه"]["intercept"] * def_info["level"]

        if random.random() < defense_chance: return False, "حمله شما توسط سیستم‌های دفاعی دشمن شناسایی و خنثی شد! 🛡️📡🚀"

        damage = max(missile_info["damage"] - total_protection, 10)
        if defender_health <= 0: damage *= 1.5

        if missile_type == "هسته‌ای":
            damage *= 1.5
            for def_type in defenses:
                if def_type in DEFENSE_SYSTEMS:
                    new_health = max(defenses[def_type]['health'] - 50, 0)
                    cursor.execute('UPDATE defenses SET health = ? WHERE player_id = ? AND type = ?', (new_health, defender_id, def_type))

        defender_resources_raw = cursor.execute('SELECT type, amount FROM resources WHERE player_id = ?', (defender_id,)).fetchall()
        defender_resources = {row['type']: row['amount'] for row in defender_resources_raw}

        stolen_resources = {}
        for res_type in ["تومان", "جام"]:
            steal_amount = int(min(defender_resources.get(res_type, 0) * 0.3, 750))
            stolen_resources[res_type] = steal_amount

        new_health = max(defender_health - damage, 0)
        cursor.execute('UPDATE players SET health = ? WHERE id = ?', (new_health, defender_id))
        for res_type, amount in stolen_resources.items():
            cursor.execute('UPDATE resources SET amount = amount - ? WHERE player_id = ? AND type = ?', (amount, defender_id, res_type))
            cursor.execute('UPDATE resources SET amount = amount + ? WHERE player_id = ? AND type = ?', (amount, attacker_id, res_type))

        if not is_attacker_admin:
            cursor.execute('UPDATE missiles SET count = count - 1, last_used = ? WHERE player_id = ? AND type = ?', (datetime.datetime.now().isoformat(), attacker_id, missile_type))

        cursor.execute('INSERT INTO battles (attacker_id, defender_id, weapon_type, result, damage, resources_stolen, timestamp, attack_mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (attacker_id, defender_id, missile_type, "success", damage, json.dumps(stolen_resources), datetime.datetime.now().isoformat(), "موشکی"))

        return True, {"damage": damage, "stolen": stolen_resources, "remaining_health": new_health}
    return await execute_db_operation(_execute_missile_attack_db, attacker_id, defender_id, missile_type)

async def execute_ground_attack(attacker_id, defender_id, tank_type, context):
    def _execute_ground_attack_db(cursor, attacker_id, defender_id, tank_type):
        attacker_player_data = cursor.execute('SELECT level, is_admin FROM players WHERE id = ?', (attacker_id,)).fetchone()
        if not attacker_player_data: return False, "اطلاعات مهاجم یافت نشد!"
        attacker_level, is_attacker_admin = attacker_player_data['level'], attacker_player_data['is_admin']

        tank_info = TANKS[tank_type]

        if not is_attacker_admin:
            tank_data = cursor.execute('SELECT count, last_used, health FROM tanks WHERE player_id = ? AND type = ?', (attacker_id, tank_type)).fetchone()
            if not tank_data or tank_data['count'] <= 0 or tank_data['health'] <= 0: return False, "فرمانده، تانک کافی یا سالم ندارید! شاید نیاز به تعمیر دارد."

            if tank_data['last_used']:
                last_time = datetime.datetime.fromisoformat(tank_data['last_used'])
                cooldown = datetime.timedelta(seconds=tank_info["cooldown"])
                if datetime.datetime.now() - last_time < cooldown:
                    remaining = int((last_time + cooldown - datetime.datetime.now()).total_seconds() / 60)
                    return False, f"تانک در حال تعمیر است! {remaining} دقیقه دیگر تلاش کنید. ⏳"

            if attacker_level < tank_info["required_level"]:
                return False, f"برای استفاده از این تانک باید به سطح {tank_info['required_level']} برسید! 📈"

        defender_data = cursor.execute('SELECT health, base_health, shield, cyber_defense_disrupted_until FROM players WHERE id = ?', (defender_id,)).fetchone()
        if not defender_data: return False, "کاربر هدف (مدافع) یافت نشد! 🕵️‍♂️"
        defender_health, base_health, shield, cyber_disrupted_until = defender_data['health'], defender_data['base_health'], defender_data['shield'], defender_data['cyber_defense_disrupted_until']

        is_cyber_disrupted = cyber_disrupted_until and datetime.datetime.now() < datetime.datetime.fromisoformat(cyber_disrupted_until)

        defenses_raw = cursor.execute('SELECT type, level, health, last_paid FROM defenses WHERE player_id = ? AND level > 0', (defender_id,)).fetchall()
        defenses = {row['type']: {'level': row['level'], 'health': row['health'], 'last_paid': row['last_paid']} for row in defenses_raw}

        total_protection = shield
        defense_chance = 0
        if not is_cyber_disrupted:
            for def_type, def_info in defenses.items():
                if def_type in DEFENSE_SYSTEMS and datetime.datetime.now() - datetime.datetime.fromisoformat(def_info['last_paid']) < datetime.timedelta(hours=24):
                    if def_type == "پدافند": total_protection += DEFENSE_SYSTEMS["پدافند"]["protection"] * def_info["level"] * 0.5
                    elif def_type == "گنبد": total_protection += DEFENSE_SYSTEMS["گنبد"]["protection"] * def_info["level"] * 0.3
                    elif def_type == "رادار": defense_chance += DEFENSE_SYSTEMS["رادار"]["detection"] * def_info["level"] * 0.1
                    elif def_type == "سامانه": defense_chance += DEFENSE_SYSTEMS["سامانه"]["intercept"] * def_info["level"] * 0.1

        if random.random() < defense_chance: return False, "حمله شما توسط سیستم‌های دفاعی دشمن شناسایی و خنثی شد! 🛡️📡🚀"

        damage = max(tank_info["damage"] - total_protection, 5)
        if defender_health <= 0: damage *= 1.2

        defender_resources_raw = cursor.execute('SELECT type, amount FROM resources WHERE player_id = ?', (defender_id,)).fetchall()
        defender_resources = {row['type']: row['amount'] for row in defender_resources_raw}

        stolen_resources = {
            "تومان": int(min(defender_resources.get("تومان", 0) * 0.2, 400)),
            "جام": int(min(defender_resources.get("جام", 0) * 0.1, 100))
        }

        new_health = max(defender_health - damage, 0)
        cursor.execute('UPDATE players SET health = ? WHERE id = ?', (new_health, defender_id))
        for res_type, amount in stolen_resources.items():
            cursor.execute('UPDATE resources SET amount = amount - ? WHERE player_id = ? AND type = ?', (amount, defender_id, res_type))
            cursor.execute('UPDATE resources SET amount = amount + ? WHERE player_id = ? AND type = ?', (amount, attacker_id, res_type))

        if not is_attacker_admin:
            tank_current_health = tank_data['health']
            damage_to_tank = random.randint(10, 30)
            new_tank_health = max(0, tank_current_health - damage_to_tank)
            cursor.execute('UPDATE tanks SET last_used = ?, health = ? WHERE player_id = ? AND type = ?', (datetime.datetime.now().isoformat(), new_tank_health, attacker_id, tank_type))

        cursor.execute('INSERT INTO battles (attacker_id, defender_id, weapon_type, result, damage, resources_stolen, timestamp, attack_mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (attacker_id, defender_id, tank_type, "success", damage, json.dumps(stolen_resources), datetime.datetime.now().isoformat(), "زمینی"))

        return True, {"damage": damage, "stolen": stolen_resources, "remaining_health": new_health}
    return await execute_db_operation(_execute_ground_attack_db, attacker_id, defender_id, tank_type)

async def execute_air_attack(attacker_id, defender_id, fighter_type, context):
    def _execute_air_attack_db(cursor, attacker_id, defender_id, fighter_type):
        attacker_player_data = cursor.execute('SELECT level, is_admin FROM players WHERE id = ?', (attacker_id,)).fetchone()
        if not attacker_player_data: return False, "اطلاعات مهاجم یافت نشد!"
        attacker_level, is_attacker_admin = attacker_player_data['level'], attacker_player_data['is_admin']

        fighter_info = FIGHTERS[fighter_type]

        if not is_attacker_admin:
            fighter_data = cursor.execute('SELECT count, last_used, health FROM fighters WHERE player_id = ? AND type = ?', (attacker_id, fighter_type)).fetchone()
            if not fighter_data or fighter_data['count'] <= 0 or fighter_data['health'] <= 0: return False, "فرمانده، جنگنده کافی یا سالم ندارید! شاید نیاز به تعمیر دارد."

            if fighter_data['last_used']:
                last_time = datetime.datetime.fromisoformat(fighter_data['last_used'])
                cooldown = datetime.timedelta(seconds=fighter_info["cooldown"])
                if datetime.datetime.now() - last_time < cooldown:
                    remaining = int((last_time + cooldown - datetime.datetime.now()).total_seconds() / 60)
                    return False, f"جنگنده در حال سوخت‌گیری است! {remaining} دقیقه دیگر تلاش کنید. ⏳"

            if attacker_level < fighter_info["required_level"]:
                return False, f"برای استفاده از این جنگنده باید به سطح {fighter_info['required_level']} برسید! 📈"

        defender_data = cursor.execute('SELECT health, base_health, shield, cyber_defense_disrupted_until FROM players WHERE id = ?', (defender_id,)).fetchone()
        if not defender_data: return False, "کاربر هدف (مدافع) یافت نشد! 🕵️‍♂️"
        defender_health, base_health, shield, cyber_disrupted_until = defender_data['health'], defender_data['base_health'], defender_data['shield'], defender_data['cyber_defense_disrupted_until']

        is_cyber_disrupted = cyber_disrupted_until and datetime.datetime.now() < datetime.datetime.fromisoformat(cyber_disrupted_until)

        defenses_raw = cursor.execute('SELECT type, level, health, last_paid FROM defenses WHERE player_id = ? AND level > 0', (defender_id,)).fetchall()
        defenses = {row['type']: {'level': row['level'], 'health': row['health'], 'last_paid': row['last_paid']} for row in defenses_raw}

        total_protection = shield
        defense_chance = 0
        if not is_cyber_disrupted:
            for def_type, def_info in defenses.items():
                if def_type in DEFENSE_SYSTEMS and datetime.datetime.now() - datetime.datetime.fromisoformat(def_info['last_paid']) < datetime.timedelta(hours=24):
                    if def_type == "پدافند هوایی": total_protection += DEFENSE_SYSTEMS["پدافند هوایی"]["protection"] * def_info["level"]
                    elif def_type == "گنبد": total_protection += DEFENSE_SYSTEMS["گنبد"]["protection"] * def_info["level"] * 0.7
                    elif def_type == "رادار": defense_chance += DEFENSE_SYSTEMS["رادار"]["detection"] * def_info["level"] * 0.2
                    elif def_type == "سامانه": defense_chance += DEFENSE_SYSTEMS["سامانه"]["intercept"] * def_info["level"] * 0.3

        if random.random() < defense_chance: return False, "حمله شما توسط سیستم‌های دفاع هوایی دشمن شناسایی و خنثی شد! ✈️📡🚀"

        damage = max(fighter_info["damage"] - total_protection, 8)
        if defender_health <= 0: damage *= 1.3

        defender_resources_raw = cursor.execute('SELECT type, amount FROM resources WHERE player_id = ?', (defender_id,)).fetchall()
        defender_resources = {row['type']: row['amount'] for row in defender_resources_raw}

        stolen_resources = {
            "تومان": int(min(defender_resources.get("تومان", 0) * 0.25, 600)),
            "جام": int(min(defender_resources.get("جام", 0) * 0.15, 120))
        }

        new_health = max(defender_health - damage, 0)
        cursor.execute('UPDATE players SET health = ? WHERE id = ?', (new_health, defender_id))
        for res_type, amount in stolen_resources.items():
            cursor.execute('UPDATE resources SET amount = amount - ? WHERE player_id = ? AND type = ?', (amount, defender_id, res_type))
            cursor.execute('UPDATE resources SET amount = amount + ? WHERE player_id = ? AND type = ?', (amount, attacker_id, res_type))

        if not is_attacker_admin:
            fighter_current_health = fighter_data['health']
            damage_to_fighter = random.randint(15, 35)
            new_fighter_health = max(0, fighter_current_health - damage_to_fighter)
            cursor.execute('UPDATE fighters SET last_used = ?, health = ? WHERE player_id = ? AND type = ?', (datetime.datetime.now().isoformat(), new_fighter_health, attacker_id, fighter_type))

        cursor.execute('INSERT INTO battles (attacker_id, defender_id, weapon_type, result, damage, resources_stolen, timestamp, attack_mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (attacker_id, defender_id, fighter_type, "success", damage, json.dumps(stolen_resources), datetime.datetime.now().isoformat(), "هوایی"))

        return True, {"damage": damage, "stolen": stolen_resources, "remaining_health": new_health}
    return await execute_db_operation(_execute_air_attack_db, attacker_id, defender_id, fighter_type)

async def execute_naval_attack(attacker_id, defender_id, warship_type, context):
    def _execute_naval_attack_db(cursor, attacker_id, defender_id, warship_type):
        attacker_player_data = cursor.execute('SELECT level, is_admin FROM players WHERE id = ?', (attacker_id,)).fetchone()
        if not attacker_player_data: return False, "اطلاعات مهاجم یافت نشد!"
        attacker_level, is_attacker_admin = attacker_player_data['level'], attacker_player_data['is_admin']

        warship_info = WARSHIPS[warship_type]

        if not is_attacker_admin:
            warship_data = cursor.execute('SELECT count, last_used, health FROM warships WHERE player_id = ? AND type = ?', (attacker_id, warship_type)).fetchone()
            if not warship_data or warship_data['count'] <= 0 or warship_data['health'] <= 0: return False, "فرمانده، کشتی جنگی کافی یا سالم ندارید! شاید نیاز به تعمیر دارد."

            if warship_data['last_used']:
                last_time = datetime.datetime.fromisoformat(warship_data['last_used'])
                cooldown = datetime.timedelta(seconds=warship_info["cooldown"])
                if datetime.datetime.now() - last_time < cooldown:
                    remaining = int((last_time + cooldown - datetime.datetime.now()).total_seconds() / 60)
                    return False, f"کشتی جنگی در حال تعمیر است! {remaining} دقیقه دیگر تلاش کنید. ⏳"

            if attacker_level < warship_info["required_level"]:
                return False, f"برای استفاده از این کشتی جنگی باید به سطح {warship_info['required_level']} برسید! 📈"

        defender_data = cursor.execute('SELECT health, base_health, shield, cyber_defense_disrupted_until FROM players WHERE id = ?', (defender_id,)).fetchone()
        if not defender_data: return False, "کاربر هدف (مدافع) یافت نشد! 🕵️‍♂️"
        defender_health, base_health, shield, cyber_disrupted_until = defender_data['health'], defender_data['base_health'], defender_data['shield'], defender_data['cyber_defense_disrupted_until']

        is_cyber_disrupted = cyber_disrupted_until and datetime.datetime.now() < datetime.datetime.fromisoformat(cyber_disrupted_until)

        defenses_raw = cursor.execute('SELECT type, level, health, last_paid FROM defenses WHERE player_id = ? AND level > 0', (defender_id,)).fetchall()
        defenses = {row['type']: {'level': row['level'], 'health': row['health'], 'last_paid': row['last_paid']} for row in defenses_raw}

        total_protection = shield
        defense_chance = 0
        if not is_cyber_disrupted:
            for def_type, def_info in defenses.items():
                if def_type in DEFENSE_SYSTEMS and datetime.datetime.now() - datetime.datetime.fromisoformat(def_info['last_paid']) < datetime.timedelta(hours=24):
                    if def_type == "پدافند ساحلی": total_protection += DEFENSE_SYSTEMS["پدافند ساحلی"]["protection"] * def_info["level"]
                    elif def_type == "پدافند": total_protection += DEFENSE_SYSTEMS["پدافند"]["protection"] * def_info["level"] * 0.4
                    elif def_type == "رادار": defense_chance += DEFENSE_SYSTEMS["رادار"]["detection"] * def_info["level"] * 0.15
                    elif def_type == "سامانه": defense_chance += DEFENSE_SYSTEMS["سامانه"]["intercept"] * def_info["level"] * 0.15

        if random.random() < defense_chance: return False, "حمله شما توسط سیستم‌های دفاع دریایی دشمن شناسایی و خنثی شد! ⚓📡🚀"

        damage = max(warship_info["damage"] - total_protection, 15)
        if defender_health <= 0: damage *= 1.4

        defender_resources_raw = cursor.execute('SELECT type, amount FROM resources WHERE player_id = ?', (defender_id,)).fetchall()
        defender_resources = {row['type']: row['amount'] for row in defender_resources_raw}

        stolen_resources = {
            "تومان": int(min(defender_resources.get("تومان", 0) * 0.35, 800)),
            "جام": int(min(defender_resources.get("جام", 0) * 0.2, 150))
        }

        new_health = max(defender_health - damage, 0)
        cursor.execute('UPDATE players SET health = ? WHERE id = ?', (new_health, defender_id))
        for res_type, amount in stolen_resources.items():
            cursor.execute('UPDATE resources SET amount = amount - ? WHERE player_id = ? AND type = ?', (amount, defender_id, res_type))
            cursor.execute('UPDATE resources SET amount = amount + ? WHERE player_id = ? AND type = ?', (amount, attacker_id, res_type))

        if not is_attacker_admin:
            warship_current_health = warship_data['health']
            damage_to_warship = random.randint(20, 40)
            new_warship_health = max(0, warship_current_health - damage_to_warship)
            cursor.execute('UPDATE warships SET last_used = ?, health = ? WHERE player_id = ? AND type = ?', (datetime.datetime.now().isoformat(), new_warship_health, attacker_id, warship_type))

        cursor.execute('INSERT INTO battles (attacker_id, defender_id, weapon_type, result, damage, resources_stolen, timestamp, attack_mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (attacker_id, defender_id, warship_type, "success", damage, json.dumps(stolen_resources), datetime.datetime.now().isoformat(), "دریایی"))

        return True, {"damage": damage, "stolen": stolen_resources, "remaining_health": new_health}
    return await execute_db_operation(_execute_naval_attack_db, attacker_id, defender_id, warship_type)

async def execute_drone_attack(attacker_id, defender_id, drone_type, context):
    def _execute_drone_attack_db(cursor, attacker_id, defender_id, drone_type):
        attacker_player_data = cursor.execute('SELECT level, is_admin FROM players WHERE id = ?', (attacker_id,)).fetchone()
        if not attacker_player_data: return False, "اطلاعات مهاجم یافت نشد!"
        attacker_level, is_attacker_admin = attacker_player_data['level'], attacker_player_data['is_admin']

        drone_info = DRONES[drone_type]

        if not is_attacker_admin:
            drone_data = cursor.execute('SELECT count, last_used, health FROM drones WHERE player_id = ? AND type = ?', (attacker_id, drone_type)).fetchone()
            if not drone_data or drone_data['count'] <= 0 or drone_data['health'] <= 0: return False, "فرمانده، پهپاد کافی یا سالم ندارید! شاید نیاز به تعمیر دارد."

            if drone_data['last_used']:
                last_time = datetime.datetime.fromisoformat(drone_data['last_used'])
                cooldown = datetime.timedelta(seconds=drone_info["cooldown"])
                if datetime.datetime.now() - last_time < cooldown:
                    remaining = int((last_time + cooldown - datetime.datetime.now()).total_seconds() / 60)
                    return False, f"پهپاد در حال آماده‌سازی است! {remaining} دقیقه دیگر تلاش کنید. ⏳"

            if attacker_level < drone_info["required_level"]:
                return False, f"برای استفاده از این پهپاد باید به سطح {drone_info['required_level']} برسید! 📈"

        defender_data = cursor.execute('SELECT health, base_health, shield, cyber_defense_disrupted_until FROM players WHERE id = ?', (defender_id,)).fetchone()
        if not defender_data: return False, "کاربر هدف (مدافع) یافت نشد! 🕵️‍♂️"
        defender_health, base_health, shield, cyber_disrupted_until = defender_data['health'], defender_data['base_health'], defender_data['shield'], defender_data['cyber_defense_disrupted_until']

        is_cyber_disrupted = cyber_disrupted_until and datetime.datetime.now() < datetime.datetime.fromisoformat(cyber_disrupted_until)

        defenses_raw = cursor.execute('SELECT type, level, health, last_paid FROM defenses WHERE player_id = ? AND level > 0', (defender_id,)).fetchall()
        defenses = {row['type']: {'level': row['level'], 'health': row['health'], 'last_paid': row['last_paid']} for row in defenses_raw}

        total_protection = shield
        defense_chance = 0
        if not is_cyber_disrupted:
            for def_type, def_info in defenses.items():
                if def_type in DEFENSE_SYSTEMS and datetime.datetime.now() - datetime.datetime.fromisoformat(def_info['last_paid']) < datetime.timedelta(hours=24):
                    if def_type == "پدافند هوایی": total_protection += DEFENSE_SYSTEMS["پدافند هوایی"]["protection"] * def_info["level"] * 0.8
                    elif def_type == "سامانه": total_protection += DEFENSE_SYSTEMS["سامانه"]["intercept"] * def_info["level"] * 0.6
                    elif def_type == "رادار": defense_chance += DEFENSE_SYSTEMS["رادار"]["detection"] * def_info["level"] * 0.3
                    elif def_type == "سامانه": defense_chance += DEFENSE_SYSTEMS["سامانه"]["intercept"] * def_info["level"] * 0.4

        if random.random() < defense_chance: return False, "حمله شما توسط دفاع پهپادی دشمن شناسایی و خنثی شد! 🚁🛡️"

        damage = max(drone_info["damage"] - total_protection, 10)
        if defender_health <= 0: damage *= 1.3

        defender_resources_raw = cursor.execute('SELECT type, amount FROM resources WHERE player_id = ?', (defender_id,)).fetchall()
        defender_resources = {row['type']: row['amount'] for row in defender_resources_raw}

        stolen_resources = {
            "تومان": int(min(defender_resources.get("تومان", 0) * 0.2, 500)),
            "جام": int(min(defender_resources.get("جام", 0) * 0.1, 80))
        }

        new_health = max(defender_health - damage, 0)
        cursor.execute('UPDATE players SET health = ? WHERE id = ?', (new_health, defender_id))
        for res_type, amount in stolen_resources.items():
            cursor.execute('UPDATE resources SET amount = amount - ? WHERE player_id = ? AND type = ?', (amount, defender_id, res_type))
            cursor.execute('UPDATE resources SET amount = amount + ? WHERE player_id = ? AND type = ?', (amount, attacker_id, res_type))

        if not is_attacker_admin:
            drone_current_health = drone_data['health']
            damage_to_drone = random.randint(10, 25)
            new_drone_health = max(0, drone_current_health - damage_to_drone)
            cursor.execute('UPDATE drones SET last_used = ?, health = ? WHERE player_id = ? AND type = ?', (datetime.datetime.now().isoformat(), new_drone_health, attacker_id, drone_type))

        cursor.execute('INSERT INTO battles (attacker_id, defender_id, weapon_type, result, damage, resources_stolen, timestamp, attack_mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (attacker_id, defender_id, drone_type, "success", damage, json.dumps(stolen_resources), datetime.datetime.now().isoformat(), "پهپادی"))

        return True, {"damage": damage, "stolen": stolen_resources, "remaining_health": new_health}
    return await execute_db_operation(_execute_drone_attack_db, attacker_id, defender_id, drone_type)

async def execute_cyber_attack(attacker_id, defender_id, cyber_attack_type, context):
    def _execute_cyber_attack_db(cursor, attacker_id, defender_id, cyber_attack_type):
        attacker_player_data = cursor.execute('SELECT level, is_admin FROM players WHERE id = ?', (attacker_id,)).fetchone()
        if not attacker_player_data: return False, "اطلاعات مهاجم یافت نشد!"
        attacker_level, is_attacker_admin = attacker_player_data['level'], attacker_player_data['is_admin']

        cyber_attack_info = CYBER_ATTACKS[cyber_attack_type]

        if not is_attacker_admin:
            cyber_attack_data = cursor.execute('SELECT last_used, last_paid FROM cyber_attacks WHERE player_id = ? AND type = ?', (attacker_id, cyber_attack_type)).fetchone()

            last_paid = cyber_attack_data['last_paid'] if cyber_attack_data else None
            if not last_paid or datetime.datetime.now() - datetime.datetime.fromisoformat(last_paid) > datetime.timedelta(hours=24):
                return False, "حقوق هکرها پرداخت نشده است! ابتدا حقوق را پرداخت کنید."

            if cyber_attack_data and cyber_attack_data['last_used']:
                last_time = datetime.datetime.fromisoformat(cyber_attack_data['last_used'])
                cooldown = datetime.timedelta(seconds=cyber_attack_info["cooldown"])
                if datetime.datetime.now() - last_time < cooldown:
                    remaining = int((last_time + cooldown - datetime.datetime.now()).total_seconds() / 60)
                    return False, f"حمله سایبری در حال خنک شدن است! {remaining} دقیقه دیگر تلاش کنید. ⏳"

            if attacker_level < cyber_attack_info["required_level"]:
                return False, f"برای استفاده از این حمله سایبری باید به سطح {cyber_attack_info['required_level']} برسید! 📈"

        defender_data = cursor.execute('SELECT health, base_health FROM players WHERE id = ?', (defender_id,)).fetchone()
        if not defender_data: return False, "کاربر هدف (مدافع) یافت نشد! 🕵️‍♂️"
        defender_health, base_health = defender_data['health'], defender_data['base_health']

        cyber_defenses_raw = cursor.execute('SELECT type, level, last_paid FROM defenses WHERE player_id = ? AND type IN ("فایروال", "آنتی‌ویروس") AND level > 0', (defender_id,)).fetchall()
        cyber_defenses = {row['type']: {'level': row['level'], 'last_paid': row['last_paid']} for row in cyber_defenses_raw}

        success_chance = 1.0
        stolen_toman = 0
        effect_applied = None

        for def_type, def_info in cyber_defenses.items():
            if datetime.datetime.now() - datetime.datetime.fromisoformat(def_info['last_paid']) < datetime.timedelta(hours=24):
                if def_type == "فایروال": success_chance -= CYBER_DEFENSES["فایروال"]["protection_chance"] * def_info["level"]

        success_chance = max(0.1, success_chance)
        if random.random() > success_chance: return False, "حمله سایبری توسط سیستم‌های دفاعی دشمن خنثی شد! 🧱🦠"

        if cyber_attack_type == "هک اطلاعات":
            disruption_duration_hours = 1
            if "آنتی‌ویروس" in cyber_defenses and datetime.datetime.now() - datetime.datetime.fromisoformat(cyber_defenses["آنتی‌ویروس"]['last_paid']) < datetime.timedelta(hours=24):
                disruption_duration_hours *= (1 - CYBER_DEFENSES["آنتی‌ویروس"]["protection_value"] * cyber_defenses["آنتی‌ویروس"]["level"])

            disruption_time = datetime.datetime.now() + datetime.timedelta(hours=disruption_duration_hours)
            cursor.execute('UPDATE players SET cyber_defense_disrupted_until = ? WHERE id = ?', (disruption_time.isoformat(), defender_id))
            effect_applied = f"سیستم‌های دفاعی به مدت {int(disruption_duration_hours * 60)} دقیقه مختل شدند!"

        elif cyber_attack_type == "هک مالی":
            defender_toman = cursor.execute('SELECT amount FROM resources WHERE player_id = ? AND type = "تومان"', (defender_id,)).fetchone()
            defender_toman = defender_toman['amount'] if defender_toman else 0

            steal_percentage = 0.1
            max_steal = 1000
            if "آنتی‌ویروس" in cyber_defenses and datetime.datetime.now() - datetime.datetime.fromisoformat(cyber_defenses["آنتی‌ویروس"]['last_paid']) < datetime.timedelta(hours=24):
                steal_percentage *= (1 - CYBER_DEFENSES["آنتی‌ویروس"]["protection_value"] * cyber_defenses["آنتی‌ویروس"]["level"])
                max_steal *= (1 - CYBER_DEFENSES["آنتی‌ویروس"]["protection_value"] * cyber_defenses["آنتی‌ویروس"]["level"])

            stolen_toman = int(min(defender_toman * steal_percentage, max_steal))
            cursor.execute('UPDATE resources SET amount = amount - ? WHERE player_id = ? AND type = "تومان"', (stolen_toman, defender_id))
            cursor.execute('UPDATE resources SET amount = amount + ? WHERE player_id = ? AND type = "تومان"', (stolen_toman, attacker_id))
            effect_applied = f"{stolen_toman} تومان به سرقت رفت!"

        if not is_attacker_admin:
            cursor.execute('UPDATE cyber_attacks SET last_used = ? WHERE player_id = ? AND type = ?', (datetime.datetime.now().isoformat(), attacker_id, cyber_attack_type))

        cursor.execute('INSERT INTO battles (attacker_id, defender_id, weapon_type, result, damage, resources_stolen, timestamp, attack_mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (attacker_id, defender_id, cyber_attack_type, "success", 0, json.dumps({"تومان": stolen_toman}), datetime.datetime.now().isoformat(), "سایبری"))

        return True, {"damage": 0, "stolen": {"تومان": stolen_toman}, "remaining_health": defender_health, "effect_applied": effect_applied}
    return await execute_db_operation(_execute_cyber_attack_db, attacker_id, defender_id, cyber_attack_type)

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await get_or_create_player(user.id, user.username, user.first_name):
        await (update.callback_query or update.message).reply_text("❌ خطا در شروع بازی. لطفاً دوباره تلاش کنید.", parse_mode=constants.ParseMode.MARKDOWN)
        return

    if update.message and update.message.chat.type in ['group', 'supergroup']:
        def _save_chat_db(cursor, chat_id, chat_title):
            cursor.execute('INSERT OR IGNORE INTO chats (chat_id, chat_title) VALUES (?, ?)', (chat_id, chat_title))
        await execute_db_operation(_save_chat_db, update.message.chat.id, update.message.chat.title)

    welcome_text = (
        f"*سلام، فرمانده {user.first_name}! 🇮🇷*\n\n"
        f"*به مرکز فرماندهی 'جنگ موشکی' خوش آمدید. 🚀*\n"
        f"*اینجا میدان نبرد اراده‌هاست و شما ستون فقرات مقاومت هستید! 💥*\n\n"
        f"*برای مشاهده لیست دستورات، از /help استفاده کنید. 📜*"
    )
    keyboard = [
        [InlineKeyboardButton("🎖️ زرادخانه من 🎖️", callback_data="show_arsenal")],
        [InlineKeyboardButton(" 💰 فروشگاه 💰 ", callback_data="shop_main")],
        [InlineKeyboardButton("🏆 رتبه‌بندی 🏆", callback_data="show_ranking")],
        [InlineKeyboardButton("📊 وضعیت من", callback_data="show_status")]
    ]
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton("🛠️ پنل ادمین 🛠️", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        f"*📜 لیست دستورات اصلی:*\n"
        f"*/arsenal* 🎖️ - *مشاهده وضعیت پایگاه و تجهیزات*\n"
        f"*/treat* 🩹 - *درمان و تعمیر پایگاه*\n"
        f"*/shop* 🛒 - *خرید موشک، تانک، جنگنده و کشتی جنگی*\n"
        f"*/upgrade_defense [نوع]* 🛡️ - *ارتقاء سیستم‌های دفاعی*\n"
        f"*/ranking* 🏆 - *مشاهده برترین فرماندهان*\n"
        f"*/status* 📊 - *گزارش کامل وضعیت منابع*\n"
        f"*/mine_ruby* 💎 - *استخراج یاقوت*\n"
        f"*/daily_bonus* 🎁 - *دریافت پاداش روزانه از بانک*\n"
        f"*/admin* 🛠️ - *پنل ادمین (فقط برای ادمین‌ها)*\n"
        f"*/broadcast [پیام]* 📢 - *ارسال پیام همگانی (فقط برای ادمین‌ها)*\n"
        f"*/redeem [کد_هدیه]* 🎁 - *استفاده از کد هدیه*\n\n"
        f"*🎯 برای حمله به دشمن، به پیام او پاسخ دهید یا از دستورات زیر استفاده کنید:*\n"
        f"`شلیک موشک [نوع_موشک] به [نام_کاربری/پاسخ]`\n"
        f"  _مثال: شلیک موشک فاتح به @username_\n"
        f"`شلیک تانک [نوع_تانک] به [نام_کاربری/پاسخ]`\n"
        f"  _مثال: شلیک تانک تی-72 به @username_\n"
        f"`حمله هوایی [نوع_جنگنده] به [نام_کاربری/پاسخ]`\n"
        f"  _مثال: حمله هوایی اف-16 به @username_\n"
        f"`حمله دریایی [نوع_کشتی_جنگی] به [نام_کاربری/پاسخ]`\n"
        f"  _مثال: حمله دریایی ناوچه به @username_\n"
        f"`حمله پهپادی [نوع_پهپاد] به [نام_کاربری/پاسخ]`\n"
        f"  _مثال: حمله پهپادی شاهد-136 به @username_\n"
        f"`حمله سایبری [نوع_حمله_سایبری] به [نام_کاربری/پاسخ]`\n"
        f"  _مثال: حمله سایبری هک مالی به @username_\n\n"
        f"*⚠️ توجه: برای حملات، می‌توانید به پیام کاربر هدف پاسخ دهید یا مستقیماً نام کاربری او را وارد کنید.*"
    )
    await update.message.reply_text(help_text, parse_mode=constants.ParseMode.MARKDOWN)

async def handle_missile_attack_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_attack_logic(update, context, MISSILES, "موشکی", execute_missile_attack)

async def handle_ground_attack_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_attack_logic(update, context, TANKS, "زمینی", execute_ground_attack)

async def handle_air_attack_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_attack_logic(update, context, FIGHTERS, "هوایی", execute_air_attack)

async def handle_naval_attack_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_attack_logic(update, context, WARSHIPS, "دریایی", execute_naval_attack)

async def handle_drone_attack_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_attack_logic(update, context, DRONES, "پهپادی", execute_drone_attack)

async def handle_cyber_attack_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_attack_logic(update, context, CYBER_ATTACKS, "سایبری", execute_cyber_attack)

async def treat_base(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    def _treat_base_db(cursor, user_id):
        player_health_data = cursor.execute('SELECT health, base_health, is_admin FROM players WHERE id = ?', (user_id,)).fetchone()
        if not player_health_data: return "❌ اطلاعات بازیکن یافت نشد. لطفاً دوباره تلاش کنید."
        health, base_health, is_admin_user = player_health_data['health'], player_health_data['base_health'], player_health_data['is_admin']

        if health >= base_health: return "💚 فرمانده، پایگاه در وضعیت عالی قرار دارد و نیازی به تعمیر ندارد! ✨"

        treatment_cost = 200
        toman = cursor.execute('SELECT amount FROM resources WHERE player_id = ? AND type = "تومان"', (user_id,)).fetchone()
        toman = toman['amount'] if toman else 0

        if not is_admin_user and toman < treatment_cost:
            return f"❌ تومان کافی برای تعمیر ندارید! مورد نیاز: {treatment_cost} 💰"

        new_health = min(health + 30, base_health)
        cursor.execute('UPDATE players SET health = ? WHERE id = ?', (new_health, user_id))
        if not is_admin_user:
            cursor.execute('UPDATE resources SET amount = amount - ? WHERE player_id = ? AND type = "تومان"', (treatment_cost, user_id))

        return (
            f"*🩹 پایگاه با موفقیت تعمیر شد! 🩹*\n\n"
            f"*❤️ سلامت جدید:* {new_health}/{base_health}\n"
            f"*💰 هزینه تعمیر:* {treatment_cost if not is_admin_user else 0}"
        )
    try:
        result_text = await execute_db_operation(_treat_base_db, user_id)
        if update.callback_query:
            await update.callback_query.answer(result_text, show_alert=True) if result_text.startswith("❌") or result_text.startswith("💚") else \
                await update.callback_query.edit_message_text(result_text, parse_mode=constants.ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(result_text, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در درمان پایگاه: {e}")
        text = "*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*"
        await (update.callback_query or update.message).reply_text(text, parse_mode=constants.ParseMode.MARKDOWN)

async def upgrade_defense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    def_type = context.args[0] if context.args else None

    if not def_type:
        await (update.callback_query or update.message).reply_text("*❌ نوع سیستم دفاعی مشخص نشده است! مثال: /upgrade_defense پدافند*", parse_mode=constants.ParseMode.MARKDOWN)
        return

    if def_type not in ALL_DEFENSES:
        await (update.callback_query or update.message).reply_text("*❌ این سیستم دفاعی وجود ندارد! 🧐*", parse_mode=constants.ParseMode.MARKDOWN)
        return

    selected_defense_info = ALL_DEFENSES[def_type]

    def _upgrade_defense_db(cursor, user_id, def_type, selected_defense_info):
        player_info = cursor.execute('SELECT is_admin FROM players WHERE id = ?', (user_id,)).fetchone()
        if not player_info: return "*❌ اطلاعات بازیکن یافت نشد. لطفاً دوباره تلاش کنید.*"
        is_admin_user = player_info['is_admin']

        current_level = cursor.execute('SELECT level FROM defenses WHERE player_id = ? AND type = ?', (user_id, def_type)).fetchone()
        current_level = current_level['level'] if current_level else 0

        if current_level >= selected_defense_info["max_level"]:
            return f"*❌ این سیستم به حداکثر سطح ({selected_defense_info['max_level']}) رسیده است! 🌟*"

        upgrade_cost = selected_defense_info["cost"] if current_level == 0 else selected_defense_info["upgrade_cost"] * (current_level + 1)

        toman = cursor.execute('SELECT amount FROM resources WHERE player_id = ? AND type = "تومان"', (user_id,)).fetchone()
        toman = toman['amount'] if toman else 0

        if not is_admin_user and toman < upgrade_cost:
            return f"*❌ تومان کافی برای ارتقاء ندارید! مورد نیاز: {upgrade_cost} 💰*"

        now = datetime.datetime.now().isoformat()
        if current_level == 0:
            cursor.execute('INSERT INTO defenses (player_id, type, level, health, last_paid) VALUES (?, ?, 1, 100, ?)', (user_id, def_type, now))
        else:
            cursor.execute('UPDATE defenses SET level = level + 1 WHERE player_id = ? AND type = ?', (user_id, def_type))

        if not is_admin_user:
            cursor.execute('UPDATE resources SET amount = amount - ? WHERE player_id = ? AND type = "تومان"', (upgrade_cost, user_id))

        return (
            f"*✅ {selected_defense_info['name']} با موفقیت به سطح {current_level + 1} ارتقاء یافت! 🛡️*\n"
            f"*💰 هزینه:* {upgrade_cost if not is_admin_user else 0}"
        )
    try:
        msg = await execute_db_operation(_upgrade_defense_db, user_id, def_type, selected_defense_info)
        if update.callback_query:
            await update.callback_query.answer(msg, show_alert=True) if msg.startswith("❌") else \
                await update.callback_query.edit_message_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در ارتقاء دفاع: {e}")
        msg = "*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*"
        await (update.callback_query or update.message).reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)

async def upgrade_player_stat(update: Update, context: ContextTypes.DEFAULT_TYPE, stat_type):
    user_id = update.effective_user.id

    def _upgrade_player_stat_db(cursor, user_id, stat_type):
        player_data = cursor.execute(f'SELECT {stat_type}_level, level, is_admin FROM players WHERE id = ?', (user_id,)).fetchone()
        if not player_data: return "*❌ اطلاعات بازیکن یافت نشد. لطفاً دوباره تلاش کنید.*"
        current_stat_level, player_level, is_admin_user = player_data[f'{stat_type}_level'], player_data['level'], player_data['is_admin']

        max_level = 5
        if stat_type == "mine_ruby": max_level = 10

        if current_stat_level >= max_level:
            return f"*❌ {stat_type} شما به حداکثر سطح ({max_level}) رسیده است! 🌟*"

        upgrade_cost = (current_stat_level + 1) * (500 if stat_type != "mine_ruby" else 300)

        toman = cursor.execute('SELECT amount FROM resources WHERE player_id = ? AND type = "تومان"', (user_id,)).fetchone()
        toman = toman['amount'] if toman else 0

        if not is_admin_user and toman < upgrade_cost:
            return f"*❌ تومان کافی برای ارتقاء {stat_type} ندارید! مورد نیاز: {upgrade_cost} 💰*"

        new_stat_level = current_stat_level + 1
        cursor.execute(f'UPDATE players SET {stat_type}_level = ? WHERE id = ?', (new_stat_level, user_id))

        if stat_type == "base_health": cursor.execute('UPDATE players SET base_health = base_health + 50 WHERE id = ?', (user_id,))
        elif stat_type == "shield": cursor.execute('UPDATE players SET shield = shield + 10 WHERE id = ?', (user_id,))

        if not is_admin_user:
            cursor.execute('UPDATE resources SET amount = amount - ? WHERE player_id = ? AND type = "تومان"', (upgrade_cost, user_id))

        return (
            f"*✅ {stat_type} شما با موفقیت به سطح {new_stat_level} ارتقاء یافت! 📈*\n"
            f"*💰 هزینه:* {upgrade_cost if not is_admin_user else 0}"
        )
    try:
        msg = await execute_db_operation(_upgrade_player_stat_db, user_id, stat_type)
        if update.callback_query:
            await update.callback_query.answer(msg, show_alert=True) if msg.startswith("❌") else \
                await update.callback_query.edit_message_text(msg, parse_mode=constants.ParseMode.MARKDOWN,
                                                              reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به وضعیت من", callback_data="show_status")]]))
        else:
            await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در ارتقاء {stat_type}: {e}")
        msg = "*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*"
        await (update.callback_query or update.message).reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)

async def upgrade_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    def _upgrade_level_db(cursor, user_id):
        player_level_data = cursor.execute('SELECT level, experience, is_admin FROM players WHERE id = ?', (user_id,)).fetchone()
        if not player_level_data: return "*❌ اطلاعات بازیکن یافت نشد. لطفاً دوباره تلاش کنید.*"
        current_level, current_exp, is_admin_user = player_level_data['level'], player_level_data['experience'], player_level_data['is_admin']

        upgrade_cost = (current_level + 1) * 1250

        toman = cursor.execute('SELECT amount FROM resources WHERE player_id = ? AND type = "تومان"', (user_id,)).fetchone()
        toman = toman['amount'] if toman else 0

        if not is_admin_user and toman < upgrade_cost:
            return f"*❌ تومان کافی برای ارتقاء سطح ندارید! مورد نیاز: {upgrade_cost} 💰*"

        new_level = current_level + 1
        cursor.execute('UPDATE players SET level = ?, experience = 0 WHERE id = ?', (new_level, user_id))
        if not is_admin_user:
            cursor.execute('UPDATE resources SET amount = amount - ? WHERE player_id = ? AND type = "تومان"', (upgrade_cost, user_id))

        return (
            f"*🎉 تبریک می‌گوییم، فرمانده! شما با موفقیت به سطح {new_level} ارتقاء یافتید! 🚀*\n"
            f"*💰 هزینه ارتقاء:* {upgrade_cost if not is_admin_user else 0}"
        )
    try:
        msg = await execute_db_operation(_upgrade_level_db, user_id)
        if update.callback_query:
            await update.callback_query.answer(msg, show_alert=True) if msg.startswith("❌") else \
                await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]]), parse_mode=constants.ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در ارتقاء سطح: {e}")
        msg = "*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*"
        await (update.callback_query or update.message).reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)

async def mine_ruby(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    def _mine_ruby_db(cursor, user_id):
        mine_data = cursor.execute('SELECT last_collected, level FROM mines WHERE player_id = ? AND type = "یاقوت"', (user_id,)).fetchone()

        now = datetime.datetime.now()
        last_collected = datetime.datetime.fromisoformat(mine_data['last_collected']) if mine_data and mine_data['last_collected'] else None
        mine_level = mine_data['level'] if mine_data else 1

        cooldown_hours = 6
        if last_collected and (now - last_collected).total_seconds() < cooldown_hours * 3600:
            remaining_seconds = int((last_collected + datetime.timedelta(hours=cooldown_hours) - now).total_seconds())
            remaining_minutes = remaining_seconds // 60
            remaining_hours = remaining_minutes // 60
            remaining_minutes %= 60
            return f"*❌ برای استخراج یاقوت خیلی زود است! ⏳*\n*زمان باقی‌مانده: {remaining_hours} ساعت و {remaining_minutes} دقیقه.*"

        ruby_amount = random.randint(5 + (mine_level - 1) * 2, 15 + (mine_level - 1) * 3)
        cursor.execute('INSERT OR REPLACE INTO mines (player_id, type, last_collected, level) VALUES (?, ?, ?, ?)', (user_id, "یاقوت", now.isoformat(), mine_level))
        cursor.execute('UPDATE resources SET amount = amount + ? WHERE player_id = ? AND type = "یاقوت"', (ruby_amount, user_id))

        return f"*✅ {ruby_amount} 💎 یاقوت از معدن استخراج شد!*"
    try:
        msg = await execute_db_operation(_mine_ruby_db, user_id)
        if update.callback_query:
            await update.callback_query.answer(msg, show_alert=True) if msg.startswith("❌") else \
                await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به وضعیت من", callback_data="show_status")]]), parse_mode=constants.ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در استخراج یاقوت برای بازیکن {user_id}: {e}")
        error_msg = "*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*"
        await (update.callback_query or update.message).reply_text(error_msg, parse_mode=constants.ParseMode.MARKDOWN)

async def bank_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    def _bank_withdrawal_db(cursor, user_id):
        player_data = cursor.execute('SELECT last_bank_withdrawal FROM players WHERE id = ?', (user_id,)).fetchone()

        now = datetime.datetime.now()
        last_withdrawal_time = datetime.datetime.fromisoformat(player_data['last_bank_withdrawal']) if player_data and player_data['last_bank_withdrawal'] else None

        cooldown_hours = 6
        if last_withdrawal_time and (now - last_withdrawal_time).total_seconds() < cooldown_hours * 3600:
            remaining_seconds = int((last_withdrawal_time + datetime.timedelta(hours=cooldown_hours) - now).total_seconds())
            remaining_minutes = remaining_seconds // 60
            remaining_hours = remaining_minutes // 60
            remaining_minutes %= 60
            return f"*❌ برای برداشت از بانک خیلی زود است! ⏳*\n*زمان باقی‌مانده: {remaining_hours} ساعت و {remaining_minutes} دقیقه.*"

        toman_amount = random.randint(500, 1500)
        cursor.execute('UPDATE resources SET amount = amount + ? WHERE player_id = ? AND type = "تومان"', (toman_amount, user_id))
        cursor.execute('UPDATE players SET last_bank_withdrawal = ? WHERE id = ?', (now.isoformat(), user_id))

        return f"*✅ {toman_amount} 💰 تومان از بانک برداشت شد!*"
    try:
        msg = await execute_db_operation(_bank_withdrawal_db, user_id)
        if update.callback_query:
            await update.callback_query.answer(msg, show_alert=True) if msg.startswith("❌") else \
                await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به وضعیت من", callback_data="show_status")]]), parse_mode=constants.ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در برداشت از بانک برای بازیکن {user_id}: {e}")
        error_msg = "*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*"
        await (update.callback_query or update.message).reply_text(error_msg, parse_mode=constants.ParseMode.MARKDOWN)

async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    def _daily_bonus_db(cursor, user_id):
        player_data = cursor.execute('SELECT last_daily_bonus FROM players WHERE id = ?', (user_id,)).fetchone()

        now = datetime.datetime.now()
        last_bonus_time = datetime.datetime.fromisoformat(player_data['last_daily_bonus']) if player_data and player_data['last_daily_bonus'] else None

        cooldown_hours = 24
        if last_bonus_time and (now - last_bonus_time).total_seconds() < cooldown_hours * 3600:
            remaining_seconds = int((last_bonus_time + datetime.timedelta(hours=cooldown_hours) - now).total_seconds())
            remaining_minutes = remaining_seconds // 60
            remaining_hours = remaining_minutes // 60
            remaining_minutes %= 60
            return f"*❌ برای دریافت پاداش روزانه خیلی زود است! ⏳*\n*زمان باقی‌مانده: {remaining_hours} ساعت و {remaining_minutes} دقیقه.*"

        toman_amount = 5000
        ruby_amount = random.randint(2, 7)

        cursor.execute('UPDATE resources SET amount = amount + ? WHERE player_id = ? AND type = "تومان"', (toman_amount, user_id))
        cursor.execute('UPDATE resources SET amount = amount + ? WHERE player_id = ? AND type = "یاقوت"', (ruby_amount, user_id))
        cursor.execute('UPDATE players SET last_daily_bonus = ? WHERE id = ?', (now.isoformat(), user_id))

        return (
            f"*🎉 پاداش روزانه شما دریافت شد! 🎉*\n"
            f"*{toman_amount} 💰 تومان*\n"
            f"*{ruby_amount} 💎 یاقوت*"
        )
    try:
        msg = await execute_db_operation(_daily_bonus_db, user_id)
        if update.callback_query:
            await update.callback_query.answer(msg, show_alert=True) if msg.startswith("❌") else \
                await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به وضعیت من", callback_data="show_status")]]), parse_mode=constants.ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در دریافت پاداش روزانه برای بازیکن {user_id}: {e}")
        error_msg = "*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*"
        await (update.callback_query or update.message).reply_text(error_msg, parse_mode=constants.ParseMode.MARKDOWN)

async def convert_ruby_to_toman(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    def _convert_ruby_to_toman_db(cursor, user_id):
        ruby_data = cursor.execute('SELECT amount FROM resources WHERE player_id = ? AND type = "یاقوت"', (user_id,)).fetchone()
        current_ruby = ruby_data['amount'] if ruby_data else 0

        if current_ruby <= 0: return "*❌ یاقوت کافی برای تبدیل ندارید! 💎*"

        toman_gain = current_ruby * RUBY_TO_TOMAN_RATE

        cursor.execute('UPDATE resources SET amount = 0 WHERE player_id = ? AND type = "یاقوت"', (user_id,))
        cursor.execute('UPDATE resources SET amount = amount + ? WHERE player_id = ? AND type = "تومان"', (toman_gain, user_id))

        return f"*✅ {current_ruby} 💎 یاقوت شما به {toman_gain} 💰 تومان تبدیل شد!*"
    try:
        msg = await execute_db_operation(_convert_ruby_to_toman_db, user_id)
        if update.callback_query:
            await update.callback_query.answer(msg, show_alert=True) if msg.startswith("❌") else \
                await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به فروشگاه", callback_data="shop_main")]]), parse_mode=constants.ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در تبدیل یاقوت به تومان برای بازیکن {user_id}: {e}")
        error_msg = "*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*"
        await (update.callback_query or update.message).reply_text(error_msg, parse_mode=constants.ParseMode.MARKDOWN)

async def repair_equipment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    parts = query.data.split('_')
    equipment_type = parts[1]
    equipment_name = parts[2]

    equipment_data_map = {
        "tank": TANKS, "fighter": FIGHTERS, "warship": WARSHIPS, "drone": DRONES
    }
    table_name_map = {
        "tank": "tanks", "fighter": "fighters", "warship": "warships", "drone": "drones"
    }

    equipment_data = equipment_data_map.get(equipment_type)
    table_name = table_name_map.get(equipment_type)

    if not equipment_data or equipment_name not in equipment_data:
        await query.answer("❌ نوع یا نام تجهیزات نامعتبر است!", show_alert=True)
        return

    def _repair_equipment_db(cursor, user_id, equipment_type, equipment_name, equipment_data, table_name):
        eq_info = cursor.execute(f'SELECT health, count FROM {table_name} WHERE player_id = ? AND type = ?', (user_id, equipment_name)).fetchone()
        if not eq_info or eq_info['count'] <= 0: return "❌ شما این تجهیزات را ندارید یا تعداد آن صفر است!"

        current_health = eq_info['health']
        max_health = equipment_data[equipment_name]["max_health"]
        repair_cost_per_hp = equipment_data[equipment_name]["repair_cost_per_hp"]

        if current_health >= max_health: return "✅ این تجهیزات کاملاً سالم است و نیازی به تعمیر ندارد!"

        health_needed = max_health - current_health
        total_repair_cost = health_needed * repair_cost_per_hp

        toman = cursor.execute('SELECT amount FROM resources WHERE player_id = ? AND type = "تومان"', (user_id,)).fetchone()
        toman = toman['amount'] if toman else 0

        is_admin_user = cursor.execute('SELECT is_admin FROM players WHERE id = ?', (user_id,)).fetchone()['is_admin']

        if not is_admin_user and toman < total_repair_cost:
            return f"❌ تومان کافی برای تعمیر ندارید! مورد نیاز: {total_repair_cost} 💰"

        cursor.execute(f'UPDATE {table_name} SET health = ? WHERE player_id = ? AND type = ?', (max_health, user_id, equipment_name))
        if not is_admin_user:
            cursor.execute('UPDATE resources SET amount = amount - ? WHERE player_id = ? AND type = "تومان"', (total_repair_cost, user_id))

        return (
            f"*✅ {equipment_data[equipment_name]['emoji']} {equipment_name} با موفقیت تعمیر شد!*\n"
            f"*💰 هزینه تعمیر:* {total_repair_cost if not is_admin_user else 0}"
        )
    try:
        msg = await execute_db_operation(_repair_equipment_db, user_id, equipment_type, equipment_name, equipment_data, table_name)
        if msg.startswith("❌") or msg.startswith("✅ این تجهیزات کاملاً سالم است"):
            await query.answer(msg, show_alert=True)
        else:
            await query.edit_message_text(
                msg,
                parse_mode=constants.ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به زرادخانه", callback_data="show_arsenal")]])
            )
    except Exception as e:
        logger.error(f"خطا در تعمیر تجهیزات {equipment_type} {equipment_name} برای بازیکن {user_id}: {e}")
        await query.answer("*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*", show_alert=True)

async def pay_salaries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    parts = query.data.split('_')
    salary_type = parts[1]
    item_name = parts[2]

    def _pay_salaries_db(cursor, user_id, salary_type, item_name):
        total_salary_cost = 0
        now = datetime.datetime.now().isoformat()

        is_admin_user = cursor.execute('SELECT is_admin FROM players WHERE id = ?', (user_id,)).fetchone()['is_admin']

        if salary_type == "cyber_attack":
            if item_name not in CYBER_ATTACKS: return "❌ حمله سایبری نامعتبر است!"
            total_salary_cost = CYBER_ATTACKS[item_name]["salary"]
            cursor.execute('UPDATE cyber_attacks SET last_paid = ? WHERE player_id = ? AND type = ?', (now, user_id, item_name))
        elif salary_type == "defense":
            if item_name not in ALL_DEFENSES: return "❌ سیستم دفاعی نامعتبر است!"
            total_salary_cost = ALL_DEFENSES[item_name]["salary"]
            cursor.execute('UPDATE defenses SET last_paid = ? WHERE player_id = ? AND type = ?', (now, user_id, item_name))
        else:
            return "❌ نوع حقوق نامعتبر است!"

        toman = cursor.execute('SELECT amount FROM resources WHERE player_id = ? AND type = "تومان"', (user_id,)).fetchone()
        toman = toman['amount'] if toman else 0

        if not is_admin_user and toman < total_salary_cost:
            return f"❌ تومان کافی برای پرداخت حقوق ندارید! مورد نیاز: {total_salary_cost} 💰"

        if not is_admin_user:
            cursor.execute('UPDATE resources SET amount = amount - ? WHERE player_id = ? AND type = "تومان"', (total_salary_cost, user_id))

        return (
            f"*✅ حقوق {item_name} با موفقیت پرداخت شد!*\n"
            f"*💰 هزینه:* {total_salary_cost if not is_admin_user else 0}"
        )
    try:
        msg = await execute_db_operation(_pay_salaries_db, user_id, salary_type, item_name)
        if msg.startswith("❌"):
            await query.answer(msg, show_alert=True)
        else:
            await query.edit_message_text(
                msg,
                parse_mode=constants.ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به زرادخانه", callback_data="show_arsenal")]])
            )
    except Exception as e:
        logger.error(f"خطا در پرداخت حقوق برای {salary_type} {item_name} برای بازیکن {user_id}: {e}")
        await query.answer("*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*", show_alert=True)

async def show_arsenal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # if update.callback_query: user_panel_messages[user_id] = update.callback_query.message.message_id # این خط حذف شد

    def _show_arsenal_db(cursor, user_id):
        p_info = cursor.execute('SELECT level, experience, health, base_health, shield FROM players WHERE id = ?', (user_id,)).fetchone()
        if not p_info: return "*❌ اطلاعات بازیکن یافت نشد. لطفاً دوباره تلاش کنید.*", None

        missiles = cursor.execute('SELECT type, count FROM missiles WHERE player_id = ? AND count > 0', (user_id,)).fetchall()
        tanks = cursor.execute('SELECT type, count, health FROM tanks WHERE player_id = ? AND count > 0', (user_id,)).fetchall()
        fighters = cursor.execute('SELECT type, count, health FROM fighters WHERE player_id = ? AND count > 0', (user_id,)).fetchall()
        warships = cursor.execute('SELECT type, count, health FROM warships WHERE player_id = ? AND count > 0', (user_id,)).fetchall()
        drones = cursor.execute('SELECT type, count, health FROM drones WHERE player_id = ? AND count > 0', (user_id,)).fetchall()
        defenses = cursor.execute('SELECT type, level, health, last_paid FROM defenses WHERE player_id = ? AND level > 0', (user_id,)).fetchall()
        cyber_attacks_owned = cursor.execute('SELECT type, last_paid FROM cyber_attacks WHERE player_id = ?', (user_id,)).fetchall()

        arsenal_text = (
            f"*🎖️✨ زرادخانه و پایگاه شما ✨🎖️*\n\n"
            f"*📊 سطح:* {p_info['level']} | *⭐ تجربه:* {p_info['experience']}\n"
            f"*❤️ سلامت پایگاه:* {p_info['health']}/{p_info['base_health']}\n"
            f"*🛡️ سپر دفاعی:* {p_info['shield']}\n"
            f"*{'─'*20}*\n"
            f"*🚀 موشک‌های آماده:*\n"
        )
        arsenal_text += "".join([f"*{MISSILES[m['type']]['emoji']} {m['type']}:* {m['count']} واحد\n" for m in missiles]) if missiles else "*خالی! از فروشگاه موشک بخرید. 🛒*\n"

        arsenal_text += f"*{'─'*20}*\n*⚔️ تانک‌های آماده:*\n"
        arsenal_text += "".join([f"*{TANKS[t['type']]['emoji']} {t['type']}:* {t['count']} واحد (سلامت: {t['health']}/{TANKS[t['type']]['max_health']})\n" for t in tanks]) if tanks else "*تانکی ندارید! از فروشگاه تانک بخرید. 🛒*\n"

        arsenal_text += f"*{'─'*20}*\n*✈️ جنگنده‌های آماده:*\n"
        arsenal_text += "".join([f"*{FIGHTERS[f['type']]['emoji']} {f['type']}:* {f['count']} واحد (سلامت: {f['health']}/{FIGHTERS[f['type']]['max_health']})\n" for f in fighters]) if fighters else "*جنگنده‌ای ندارید! از فروشگاه جنگنده بخرید. 🛒*\n"

        arsenal_text += f"*{'─'*20}*\n*🚢 کشتی‌های جنگی آماده:*\n"
        arsenal_text += "".join([f"*{WARSHIPS[w['type']]['emoji']} {w['type']}:* {w['count']} واحد (سلامت: {w['health']}/{WARSHIPS[w['type']]['max_health']})\n" for w in warships]) if warships else "*کشتی جنگی ندارید! از فروشگاه کشتی جنگی بخرید. 🛒*\n"

        arsenal_text += f"*{'─'*20}*\n*🚁 پهپادهای آماده:*\n"
        arsenal_text += "".join([f"*{DRONES[d['type']]['emoji']} {d['type']}:* {d['count']} واحد (سلامت: {d['health']}/{DRONES[d['type']]['max_health']})\n" for d in drones]) if drones else "*پهپادی ندارید! از فروشگاه پهپاد بخرید. 🛒*\n"

        arsenal_text += f"*{'─'*20}*\n*🛡️ سیستم‌های دفاعی فعال:*\n"
        if defenses:
            for d in defenses:
                last_paid = datetime.datetime.fromisoformat(d['last_paid']) if d['last_paid'] else datetime.datetime.min
                salary_status = "✅ فعال" if datetime.datetime.now() - last_paid < datetime.timedelta(hours=24) else "❌ حقوق پرداخت نشده"
                if d['type'] in DEFENSE_SYSTEMS:
                    arsenal_text += f"*{DEFENSE_SYSTEMS[d['type']]['emoji']} {d['type']}:* سطح {d['level']} (سلامت: {d['health']}, وضعیت: {salary_status})\n"
                elif d['type'] in CYBER_DEFENSES:
                    arsenal_text += f"*{CYBER_DEFENSES[d['type']]['emoji']} {d['type']}:* سطح {d['level']} (وضعیت: {salary_status})\n"
        else:
            arsenal_text += "*سیستم دفاعی فعالی ندارید! 😔*\n"

        arsenal_text += f"*{'─'*20}*\n*💻 حملات سایبری فعال:*\n"
        if cyber_attacks_owned:
            for ca in cyber_attacks_owned:
                last_paid = datetime.datetime.fromisoformat(ca['last_paid']) if ca['last_paid'] else datetime.datetime.min
                salary_status = "✅ فعال" if datetime.datetime.now() - last_paid < datetime.timedelta(hours=24) else "❌ حقوق پرداخت نشده"
                arsenal_text += f"*{CYBER_ATTACKS[ca['type']]['emoji']} {ca['type']}:* (وضعیت: {salary_status})\n"
        else:
            arsenal_text += "*حمله سایبری فعالی ندارید! 😔*\n"

        keyboard = [
            [InlineKeyboardButton("🩹 تعمیر پایگاه", callback_data="treat_base")],
            [InlineKeyboardButton("🛠️ تعمیر تجهیزات", callback_data="repair_equipment_menu")],
            [InlineKeyboardButton("💰 پرداخت حقوق", callback_data="pay_salaries_menu")],
            [InlineKeyboardButton("🛡️ ارتقاء دفاع", callback_data="shop_defenses")],
            [InlineKeyboardButton("📈 ارتقاء سطح", callback_data="upgrade_level")],
            [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]
        ]
        return arsenal_text, InlineKeyboardMarkup(keyboard)
    try:
        arsenal_text, reply_markup = await execute_db_operation(_show_arsenal_db, user_id)
        if update.callback_query:
            await update.callback_query.edit_message_text(arsenal_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(arsenal_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در نمایش زرادخانه: {e}")
        await (update.callback_query or update.message).reply_text("*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*", parse_mode=constants.ParseMode.MARKDOWN)

async def repair_equipment_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    def _repair_equipment_menu_db(cursor, user_id):
        repair_options = []
        for eq_type, eq_map, table_name in [("tank", TANKS, "tanks"), ("fighter", FIGHTERS, "fighters"), ("warship", WARSHIPS, "warships"), ("drone", DRONES, "drones")]:
            for item in cursor.execute(f'SELECT type, health FROM {table_name} WHERE player_id = ? AND count > 0', (user_id,)).fetchall():
                max_health = eq_map[item['type']]["max_health"]
                if item['health'] < max_health:
                    repair_options.append(InlineKeyboardButton(f"🛠️ {eq_map[item['type']]['emoji']} {item['type']} ({item['health']}/{max_health})", callback_data=f"repair_{eq_type}_{item['type']}"))
        return repair_options
    try:
        repair_options = await execute_db_operation(_repair_equipment_menu_db, user_id)

        if not repair_options:
            await query.answer("✅ هیچ تجهیزات آسیب‌دیده‌ای برای تعمیر وجود ندارد!", show_alert=True)
            return

        keyboard = [[option] for option in repair_options]
        keyboard.append([InlineKeyboardButton("🔙 بازگشت به زرادخانه", callback_data="show_arsenal")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "*🛠️ تجهیزات آسیب‌دیده شما:*\n\n*روی تجهیزاتی که می‌خواهید تعمیر کنید کلیک کنید:*",
            reply_markup=reply_markup,
            parse_mode=constants.ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"خطا در نمایش منوی تعمیر تجهیزات برای بازیکن {user_id}: {e}")
        await query.answer("*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*", show_alert=True)

async def pay_salaries_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    def _pay_salaries_menu_db(cursor, user_id):
        salary_options = []
        now = datetime.datetime.now()
        salary_cooldown = datetime.timedelta(hours=24)

        for ca in cursor.execute('SELECT type, last_paid FROM cyber_attacks WHERE player_id = ?', (user_id,)).fetchall():
            last_paid = datetime.datetime.fromisoformat(ca['last_paid']) if ca['last_paid'] else datetime.datetime.min
            if now - last_paid > salary_cooldown:
                salary_cost = CYBER_ATTACKS[ca['type']]["salary"]
                salary_options.append(InlineKeyboardButton(f"💰 حقوق {CYBER_ATTACKS[ca['type']]['emoji']} {ca['type']} ({salary_cost} 💰)", callback_data=f"pay_cyber_attack_{ca['type']}"))

        for d in cursor.execute('SELECT type, last_paid FROM defenses WHERE player_id = ? AND level > 0', (user_id,)).fetchall():
            last_paid = datetime.datetime.fromisoformat(d['last_paid']) if d['last_paid'] else datetime.datetime.min
            if now - last_paid > salary_cooldown:
                if d['type'] in ALL_DEFENSES:
                    salary_cost = ALL_DEFENSES[d['type']]["salary"]
                    salary_options.append(InlineKeyboardButton(f"💰 حقوق {ALL_DEFENSES[d['type']]['emoji']} {d['type']} ({salary_cost} 💰)", callback_data=f"pay_defense_{d['type']}"))
        return salary_options
    try:
        salary_options = await execute_db_operation(_pay_salaries_menu_db, user_id)

        if not salary_options:
            await query.answer("✅ هیچ حقوقی برای پرداخت وجود ندارد!", show_alert=True)
            return

        keyboard = [[option] for option in salary_options]
        keyboard.append([InlineKeyboardButton("🔙 بازگشت به زرادخانه", callback_data="show_arsenal")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "*💰 پرداخت حقوق و نگهداری سیستم‌ها:*\n\n*روی گزینه مورد نظر برای پرداخت حقوق کلیک کنید:*",
            reply_markup=reply_markup,
            parse_mode=constants.ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"خطا در نمایش منوی پرداخت حقوق برای بازیکن {user_id}: {e}")
        await query.answer("*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*", show_alert=True)

async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # if update.callback_query: user_panel_messages[user_id] = update.callback_query.message.message_id # این خط حذف شد

    def _show_status_db(cursor, user_id):
        status = cursor.execute('''SELECT p.level, p.experience, p.health, p.base_health, p.shield,
                             r.amount as toman, r2.amount as cups, r3.amount as gems,
                             p.cyber_defense_disrupted_until, p.last_bank_withdrawal,
                             p.base_health_level, p.shield_level, m.level as mine_ruby_level
                             FROM players p
                             LEFT JOIN resources r ON p.id = r.player_id AND r.type = 'تومان'
                             LEFT JOIN resources r2 ON p.id = r2.player_id AND r2.type = 'جام'
                             LEFT JOIN resources r3 ON p.id = r3.player_id AND r3.type = 'یاقوت'
                             LEFT JOIN mines m ON p.id = m.player_id AND m.type = 'یاقوت'
                             WHERE p.id = ?''', (user_id,)).fetchone()
        if not status: return "*❌ اطلاعات بازیکن یافت نشد. لطفاً دوباره تلاش کنید.*", None

        disruption_status = ""
        if status['cyber_defense_disrupted_until']:
            disruption_time = datetime.datetime.fromisoformat(status['cyber_defense_disrupted_until'])
            if datetime.datetime.now() < disruption_time:
                remaining_seconds = int((disruption_time - datetime.datetime.now()).total_seconds())
                remaining_minutes = remaining_seconds // 60
                disruption_status = f" (مختل شده برای {remaining_minutes} دقیقه دیگر)"

        status_text = (
            f"*📊 وضعیت فرمانده {update.effective_user.first_name}:*\n\n"
            f"*📈 سطح:* {status['level']}\n"
            f"*⭐ تجربه:* {status['experience']}\n"
            f"*❤️ سلامت پایگاه:* {status['health']}/{status['base_health']} (سطح: {status['base_health_level']})\n"
            f"*🛡️ سپر دفاعی:* {status['shield']} (سطح: {status['shield_level']})\n"
            f"*{RESOURCES['تومان']['emoji']} تومان:* {status['toman'] if status['toman'] is not None else 0}\n"
            f"*{RESOURCES['جام']['emoji']} جام:* {status['cups'] if status['cups'] is not None else 0}\n"
            f"*{RESOURCES['یاقوت']['emoji']} یاقوت:* {status['gems'] if status['gems'] is not None else 0} (سطح معدن: {status['mine_ruby_level']})\n"
            f"*💻 دفاع سایبری:* فعال{disruption_status}\n"
        )
        keyboard = [
            [InlineKeyboardButton("🩹 تعمیر پایگاه", callback_data="treat_base")],
            [InlineKeyboardButton("📈 ارتقاء سطح", callback_data="upgrade_level")],
            [InlineKeyboardButton("❤️ ارتقاء سلامت پایگاه", callback_data="upgrade_player_stat_base_health")],
            [InlineKeyboardButton("🛡️ ارتقاء سپر دفاعی", callback_data="upgrade_player_stat_shield")],
            [InlineKeyboardButton("💎 استخراج یاقوت (معدن)", callback_data="mine_ruby_btn")],
            [InlineKeyboardButton("⛏️ ارتقاء معدن یاقوت", callback_data="upgrade_player_stat_mine_ruby")],
            [InlineKeyboardButton("🏦 برداشت از بانک", callback_data="bank_withdrawal_btn")],
            [InlineKeyboardButton("🎁 پاداش روزانه", callback_data="daily_bonus_btn")],
            [InlineKeyboardButton("🔄 تبدیل یاقوت به تومان", callback_data="convert_ruby_to_toman_btn")],
            [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]
        ]
        return status_text, InlineKeyboardMarkup(keyboard)
    try:
        status_text, reply_markup = await execute_db_operation(_show_status_db, user_id)
        if update.callback_query:
            await update.callback_query.edit_message_text(status_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(status_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در نمایش وضعیت: {e}")
        await (update.callback_query or update.message).reply_text("*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*", parse_mode=constants.ParseMode.MARKDOWN)

async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    def _ranking_db(cursor):
        top_players = cursor.execute('SELECT username, first_name, level FROM players ORDER BY level DESC, experience DESC LIMIT 10').fetchall()
        rank_text = "*🏆 👑 ۱۰ فرمانده برتر 👑 🏆*\n\n"
        emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        if top_players:
            for i, player in enumerate(top_players):
                name = player['username'] or player['first_name'] or "ناشناس"
                rank_text += f"*{emojis[i]} {name} - سطح {player['level']}*\n"
        else:
            rank_text += "*هنوز بازیکنی در رتبه‌بندی نیست! اولین نفر باشید!*"
        return rank_text
    try:
        rank_text = await execute_db_operation(_ranking_db)
        keyboard = [[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(rank_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(rank_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در نمایش رتبه‌بندی: {e}")
        await (update.callback_query or update.message).reply_text("*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*", parse_mode=constants.ParseMode.MARKDOWN)

# --- Shop Handlers ---
async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"*🛒 به فروشگاه بزرگ جنگ موشکی خوش آمدید! 🛒*\n\n"
        f"*فرمانده، هر آنچه برای نبردی سهمگین نیاز دارید اینجا موجود است. چه می‌خواهید؟ 🛍️*"
    )
    keyboard = [
        [InlineKeyboardButton("🚀 خرید موشک", callback_data="shop_missiles")],
        [InlineKeyboardButton("🛡️ خرید و ارتقاء دفاع", callback_data="shop_defenses")],
        [InlineKeyboardButton("⚔️ خرید تانک", callback_data="shop_tanks")],
        [InlineKeyboardButton("✈️ خرید جنگنده", callback_data="shop_fighters")],
        [InlineKeyboardButton("🚢 خرید کشتی جنگی", callback_data="shop_warships")],
        [InlineKeyboardButton("🚁 خرید پهپاد", callback_data="shop_drones")],
        [InlineKeyboardButton("💻 خرید حملات سایبری", callback_data="shop_cyber_attacks")],
        [InlineKeyboardButton("🔄 تبدیل یاقوت به تومان", callback_data="convert_ruby_to_toman_btn")],
        [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)

async def show_missiles_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    shop_text = (
        f"*🚀 فروشگاه موشک‌های مرگبار 🚀*\n\n"
        f"*فرمانده، موشک مورد نظر خود را انتخاب کنید:*\n"
        f"*{'─'*20}*\n"
    )
    for missile, info in MISSILES.items():
        shop_text += (
            f"*{info['emoji']} {missile}*\n"
            f"*💥 آسیب:* {info['damage']}\n"
            f"*💰 قیمت:* {info['cost']} تومان\n"
            f"*📊 سطح مورد نیاز:* {info['required_level']}\n"
            f"*⏰ زمان خنک شدن:* {info['cooldown']//60} دقیقه\n"
            f"*🎯 نوع:* {info['type']}\n"
        )
        if 'special' in info: shop_text += f"*✨ ویژگی خاص:* {info['special']}\n"
        shop_text += f"*{'─'*20}*\n"

    keyboard = [[InlineKeyboardButton(f"خرید {m}", callback_data=f"buy_missile_{m}")] for m in MISSILES]
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به فروشگاه", callback_data="shop_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(shop_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)

async def handle_missile_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    missile_type = query.data.replace("buy_missile_", "")

    if missile_type not in MISSILES:
        await query.message.reply_text("*❌ موشک نامعتبر است! لطفاً یکی از موشک‌های موجود را انتخاب کنید. 🧐*", parse_mode=constants.ParseMode.MARKDOWN)
        return

    def _handle_missile_purchase_db(cursor, user_id, missile_type):
        player_data = cursor.execute('SELECT level, is_admin FROM players WHERE id = ?', (user_id,)).fetchone()
        if not player_data: return "*❌ اطلاعات بازیکن یافت نشد. لطفاً دوباره تلاش کنید.*"
        user_level, is_admin_user = player_data['level'], player_data['is_admin']

        missile_info = MISSILES[missile_type]

        if not is_admin_user:
            if user_level < missile_info["required_level"]:
                return (
                    f"*❌ سطح شما برای خرید {missile_info['name']} کافی نیست! 📈*\n"
                    f"*مورد نیاز: سطح {missile_info['required_level']}*"
                )

            toman = cursor.execute('SELECT amount FROM resources WHERE player_id = ? AND type = "تومان"', (user_id,)).fetchone()
            toman = toman['amount'] if toman else 0
            missile_cost = missile_info["cost"]
            if toman < missile_cost:
                return (
                    f"*❌ تومان کافی ندارید! 💰*\n*مورد نیاز: {missile_cost} 💰*"
                )
            cursor.execute('UPDATE resources SET amount = amount - ? WHERE player_id = ? AND type = "تومان"', (missile_cost, user_id))

        existing_missile = cursor.execute('SELECT count FROM missiles WHERE player_id = ? AND type = ?', (user_id, missile_type)).fetchone()
        if existing_missile:
            cursor.execute('UPDATE missiles SET count = count + 1 WHERE player_id = ? AND type = ?', (user_id, missile_type))
        else:
            cursor.execute('INSERT INTO missiles (player_id, type, count) VALUES (?, ?, 1)', (user_id, missile_type))

        return (
            f"*✅ خرید با موفقیت انجام شد! 🎉*\n\n*{missile_info['emoji']} {missile_type}* به زرادخانه شما اضافه شد! 🚀"
        )
    try:
        msg = await execute_db_operation(_handle_missile_purchase_db, user_id, missile_type)
        await query.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در خرید موشک: {e}")
        await query.message.reply_text("*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*", parse_mode=constants.ParseMode.MARKDOWN)

async def show_defenses_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    shop_text = (
        f"*🛡️ فروشگاه سیستم‌های دفاعی 🛡️*\n\n"
        f"*فرمانده، پایگاه خود را با این سیستم‌ها نفوذناپذیر کنید:*\n"
        f"*{'─'*20}*\n"
    )

    for def_type, info in ALL_DEFENSES.items():
        shop_text += (
            f"*{info['emoji']} {def_type}*\n"
            f"*💰 قیمت اولیه:* {info['cost']} تومان\n"
            f"*📈 حداکثر سطح:* {info['max_level']}\n"
            f"*💸 هزینه ارتقاء:* {info['upgrade_cost']} تومان به ازای هر سطح\n"
            f"*💵 حقوق روزانه:* {info['salary']} تومان\n"
            f"*{'─'*20}*\n"
        )

    keyboard = [[InlineKeyboardButton(f"خرید/ارتقاء {d}", callback_data=f"upgrade_defense_{d}")] for d in ALL_DEFENSES]
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به فروشگاه", callback_data="shop_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(shop_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)

async def handle_defense_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    def_type = query.data.replace("upgrade_defense_", "")
    context.args = [def_type]
    await upgrade_defense(update, context)

async def show_tanks_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    shop_text = (
        f"*⚔️ فروشگاه تانک‌های جنگی ⚔️*\n\n"
        f"*فرمانده، تانک مورد نظر خود را انتخاب کنید:*\n"
        f"*{'─'*20}*\n"
    )
    for tank, info in TANKS.items():
        shop_text += (
            f"*{info['emoji']} {tank}*\n"
            f"*💥 آسیب:* {info['damage']}\n"
            f"*❤️ سلامت اولیه:* {info['max_health']}\n"
            f"*💰 قیمت:* {info['cost']} تومان\n"
            f"*📊 سطح مورد نیاز:* {info['required_level']}\n"
            f"*⏰ زمان خنک شدن:* {info['cooldown']//60} دقیقه\n"
            f"*🎯 نوع:* {info['type']}\n"
        )
        shop_text += f"*{'─'*20}*\n"

    keyboard = [[InlineKeyboardButton(f"خرید {t}", callback_data=f"buy_tank_{t}")] for t in TANKS]
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به فروشگاه", callback_data="shop_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(shop_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)

async def handle_tank_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    tank_type = query.data.replace("buy_tank_", "")

    if tank_type not in TANKS:
        await query.message.reply_text("*❌ تانک نامعتبر است! لطفاً یکی از تانک‌های موجود را انتخاب کنید. 🧐*", parse_mode=constants.ParseMode.MARKDOWN)
        return

    def _handle_tank_purchase_db(cursor, user_id, tank_type):
        player_data = cursor.execute('SELECT level, is_admin FROM players WHERE id = ?', (user_id,)).fetchone()
        if not player_data: return "*❌ اطلاعات بازیکن یافت نشد. لطفاً دوباره تلاش کنید.*"
        user_level, is_admin_user = player_data['level'], player_data['is_admin']

        tank_info = TANKS[tank_type]

        if not is_admin_user:
            if user_level < tank_info["required_level"]:
                return (
                    f"*❌ سطح شما برای خرید {tank_info['name']} کافی نیست! 📈*\n"
                    f"*مورد نیاز: سطح {tank_info['required_level']}*"
                )

            toman = cursor.execute('SELECT amount FROM resources WHERE player_id = ? AND type = "تومان"', (user_id,)).fetchone()
            toman = toman['amount'] if toman else 0
            tank_cost = tank_info["cost"]
            if toman < tank_cost:
                return (
                    f"*❌ تومان کافی ندارید! 💰*\n*مورد نیاز: {tank_cost} 💰*"
                )
            cursor.execute('UPDATE resources SET amount = amount - ? WHERE player_id = ? AND type = "تومان"', (tank_cost, user_id))

        existing_tank = cursor.execute('SELECT count FROM tanks WHERE player_id = ? AND type = ?', (user_id, tank_type)).fetchone()
        if existing_tank:
            cursor.execute('UPDATE tanks SET count = count + 1, health = ? WHERE player_id = ? AND type = ?', (tank_info["max_health"], user_id, tank_type))
        else:
            cursor.execute('INSERT INTO tanks (player_id, type, count, health) VALUES (?, ?, 1, ?)', (user_id, tank_type, tank_info["max_health"]))

        return (
            f"*✅ خرید با موفقیت انجام شد! 🎉*\n\n*{tank_info['emoji']} {tank_type}* به زرادخانه شما اضافه شد! ⚔️"
        )
    try:
        msg = await execute_db_operation(_handle_tank_purchase_db, user_id, tank_type)
        await query.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در خرید تانک: {e}")
        await query.message.reply_text("*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*", parse_mode=constants.ParseMode.MARKDOWN)

async def show_fighters_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    shop_text = (
        f"*✈️ فروشگاه جنگنده‌های هوایی ✈️*\n\n"
        f"*فرمانده، جنگنده مورد نظر خود را انتخاب کنید:*\n"
        f"*{'─'*20}*\n"
    )
    for fighter, info in FIGHTERS.items():
        shop_text += (
            f"*{info['emoji']} {fighter}*\n"
            f"*💥 آسیب:* {info['damage']}\n"
            f"*❤️ سلامت اولیه:* {info['max_health']}\n"
            f"*💰 قیمت:* {info['cost']} تومان\n"
            f"*📊 سطح مورد نیاز:* {info['required_level']}\n"
            f"*⏰ زمان خنک شدن:* {info['cooldown']//60} دقیقه\n"
            f"*🎯 نوع:* {info['type']}\n"
        )
        shop_text += f"*{'─'*20}*\n"

    keyboard = [[InlineKeyboardButton(f"خرید {f}", callback_data=f"buy_fighter_{f}")] for f in FIGHTERS]
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به فروشگاه", callback_data="shop_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(shop_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)

async def handle_fighter_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    fighter_type = query.data.replace("buy_fighter_", "")

    if fighter_type not in FIGHTERS:
        await query.message.reply_text("*❌ جنگنده نامعتبر است! لطفاً یکی از جنگنده‌های موجود را انتخاب کنید. 🧐*", parse_mode=constants.ParseMode.MARKDOWN)
        return

    def _handle_fighter_purchase_db(cursor, user_id, fighter_type):
        player_data = cursor.execute('SELECT level, is_admin FROM players WHERE id = ?', (user_id,)).fetchone()
        if not player_data: return "*❌ اطلاعات بازیکن یافت نشد. لطفاً دوباره تلاش کنید.*"
        user_level, is_admin_user = player_data['level'], player_data['is_admin']

        fighter_info = FIGHTERS[fighter_type]

        if not is_admin_user:
            if user_level < fighter_info["required_level"]:
                return (
                    f"*❌ سطح شما برای خرید {fighter_info['name']} کافی نیست! 📈*\n"
                    f"*مورد نیاز: سطح {fighter_info['required_level']}*"
                )

            toman = cursor.execute('SELECT amount FROM resources WHERE player_id = ? AND type = "تومان"', (user_id,)).fetchone()
            toman = toman['amount'] if toman else 0
            fighter_cost = fighter_info["cost"]
            if toman < fighter_cost:
                return (
                    f"*❌ تومان کافی ندارید! 💰*\n*مورد نیاز: {fighter_cost} 💰*"
                )
            cursor.execute('UPDATE resources SET amount = amount - ? WHERE player_id = ? AND type = "تومان"', (fighter_cost, user_id))

        existing_fighter = cursor.execute('SELECT count FROM fighters WHERE player_id = ? AND type = ?', (user_id, fighter_type)).fetchone()
        if existing_fighter:
            cursor.execute('UPDATE fighters SET count = count + 1, health = ? WHERE player_id = ? AND type = ?', (fighter_info["max_health"], user_id, fighter_type))
        else:
            cursor.execute('INSERT INTO fighters (player_id, type, count, health) VALUES (?, ?, 1, ?)', (user_id, fighter_type, fighter_info["max_health"]))

        return (
            f"*✅ خرید با موفقیت انجام شد! 🎉*\n\n*{fighter_info['emoji']} {fighter_type}* به زرادخانه شما اضافه شد! ✈️"
        )
    try:
        msg = await execute_db_operation(_handle_fighter_purchase_db, user_id, fighter_type)
        await query.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در خرید جنگنده: {e}")
        await query.message.reply_text("*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*", parse_mode=constants.ParseMode.MARKDOWN)

async def show_warships_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    shop_text = (
        f"*🚢 فروشگاه کشتی‌های جنگی 🚢*\n\n"
        f"*فرمانده، کشتی جنگی مورد نظر خود را انتخاب کنید:*\n"
        f"*{'─'*20}*\n"
    )
    for warship, info in WARSHIPS.items():
        shop_text += (
            f"*{info['emoji']} {warship}*\n"
            f"*💥 آسیب:* {info['damage']}\n"
            f"*❤️ سلامت اولیه:* {info['max_health']}\n"
            f"*💰 قیمت:* {info['cost']} تومان\n"
            f"*📊 سطح مورد نیاز:* {info['required_level']}\n"
            f"*⏰ زمان خنک شدن:* {info['cooldown']//60} دقیقه\n"
            f"*🎯 نوع:* {info['type']}\n"
        )
        shop_text += f"*{'─'*20}*\n"

    keyboard = [[InlineKeyboardButton(f"خرید {w}", callback_data=f"buy_warship_{w}")] for w in WARSHIPS]
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به فروشگاه", callback_data="shop_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(shop_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)

async def handle_warship_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    warship_type = query.data.replace("buy_warship_", "")

    if warship_type not in WARSHIPS:
        await query.message.reply_text("*❌ کشتی جنگی نامعتبر است! لطفاً یکی از کشتی‌های جنگی موجود را انتخاب کنید. 🧐*", parse_mode=constants.ParseMode.MARKDOWN)
        return

    def _handle_warship_purchase_db(cursor, user_id, warship_type):
        player_data = cursor.execute('SELECT level, is_admin FROM players WHERE id = ?', (user_id,)).fetchone()
        if not player_data: return "*❌ اطلاعات بازیکن یافت نشد. لطفاً دوباره تلاش کنید.*"
        user_level, is_admin_user = player_data['level'], player_data['is_admin']

        warship_info = WARSHIPS[warship_type]

        if not is_admin_user:
            if user_level < warship_info["required_level"]:
                return (
                    f"*❌ سطح شما برای خرید {warship_info['name']} کافی نیست! 📈*\n"
                    f"*مورد نیاز: سطح {warship_info['required_level']}*"
                )

            toman = cursor.execute('SELECT amount FROM resources WHERE player_id = ? AND type = "تومان"', (user_id,)).fetchone()
            toman = toman['amount'] if toman else 0
            warship_cost = warship_info["cost"]
            if toman < warship_cost:
                return (
                    f"*❌ تومان کافی ندارید! 💰*\n*مورد نیاز: {warship_cost} 💰*"
                )
            cursor.execute('UPDATE resources SET amount = amount - ? WHERE player_id = ? AND type = "تومان"', (warship_cost, user_id))

        existing_warship = cursor.execute('SELECT count FROM warships WHERE player_id = ? AND type = ?', (user_id, warship_type)).fetchone()
        if existing_warship:
            cursor.execute('UPDATE warships SET count = count + 1, health = ? WHERE player_id = ? AND type = ?', (warship_info["max_health"], user_id, warship_type))
        else:
            cursor.execute('INSERT INTO warships (player_id, type, count, health) VALUES (?, ?, 1, ?)', (user_id, warship_type, warship_info["max_health"]))

        return (
            f"*✅ خرید با موفقیت انجام شد! 🎉*\n\n*{warship_info['emoji']} {warship_type}* به زرادخانه شما اضافه شد! 🚢"
        )
    try:
        msg = await execute_db_operation(_handle_warship_purchase_db, user_id, warship_type)
        await query.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در خرید کشتی جنگی: {e}")
        await query.message.reply_text("*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*", parse_mode=constants.ParseMode.MARKDOWN)

async def show_drones_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    shop_text = (
        f"*🚁 فروشگاه پهپادهای رزمی 🚁*\n\n"
        f"*فرمانده، پهپاد مورد نظر خود را انتخاب کنید:*\n"
        f"*{'─'*20}*\n"
    )
    for drone, info in DRONES.items():
        shop_text += (
            f"*{info['emoji']} {drone}*\n"
            f"*💥 آسیب:* {info['damage']}\n"
            f"*❤️ سلامت اولیه:* {info['max_health']}\n"
            f"*💰 قیمت:* {info['cost']} تومان\n"
            f"*📊 سطح مورد نیاز:* {info['required_level']}\n"
            f"*⏰ زمان خنک شدن:* {info['cooldown']//60} دقیقه\n"
            f"*🎯 نوع:* {info['type']}\n"
        )
        shop_text += f"*{'─'*20}*\n"

    keyboard = [[InlineKeyboardButton(f"خرید {d}", callback_data=f"buy_drone_{d}")] for d in DRONES]
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به فروشگاه", callback_data="shop_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(shop_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)

async def handle_drone_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    drone_type = query.data.replace("buy_drone_", "")

    if drone_type not in DRONES:
        await query.message.reply_text("*❌ پهپاد نامعتبر است! لطفاً یکی از پهپادهای موجود را انتخاب کنید. 🧐*", parse_mode=constants.ParseMode.MARKDOWN)
        return

    def _handle_drone_purchase_db(cursor, user_id, drone_type):
        player_data = cursor.execute('SELECT level, is_admin FROM players WHERE id = ?', (user_id,)).fetchone()
        if not player_data: return "*❌ اطلاعات بازیکن یافت نشد. لطفاً دوباره تلاش کنید.*"
        user_level, is_admin_user = player_data['level'], player_data['is_admin']

        drone_info = DRONES[drone_type]

        if not is_admin_user:
            if user_level < drone_info["required_level"]:
                return (
                    f"*❌ سطح شما برای خرید {drone_info['name']} کافی نیست! 📈*\n"
                    f"*مورد نیاز: سطح {drone_info['required_level']}*"
                )

            toman = cursor.execute('SELECT amount FROM resources WHERE player_id = ? AND type = "تومان"', (user_id,)).fetchone()
            toman = toman['amount'] if toman else 0
            drone_cost = drone_info["cost"]
            if toman < drone_cost:
                return (
                    f"*❌ تومان کافی ندارید! 💰*\n*مورد نیاز: {drone_cost} 💰*"
                )
            cursor.execute('UPDATE resources SET amount = amount - ? WHERE player_id = ? AND type = "تومان"', (drone_cost, user_id))

        existing_drone = cursor.execute('SELECT count FROM drones WHERE player_id = ? AND type = ?', (user_id, drone_type)).fetchone()
        if existing_drone:
            cursor.execute('UPDATE drones SET count = count + 1, health = ? WHERE player_id = ? AND type = ?', (drone_info["max_health"], user_id, drone_type))
        else:
            cursor.execute('INSERT INTO drones (player_id, type, count, health) VALUES (?, ?, 1, ?)', (user_id, drone_type, drone_info["max_health"]))

        return (
            f"*✅ خرید با موفقیت انجام شد! 🎉*\n\n*{drone_info['emoji']} {drone_type}* به زرادخانه شما اضافه شد! 🚁"
        )
    try:
        msg = await execute_db_operation(_handle_drone_purchase_db, user_id, drone_type)
        await query.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در خرید پهپاد: {e}")
        await query.message.reply_text("*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*", parse_mode=constants.ParseMode.MARKDOWN)

async def show_cyber_attacks_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    shop_text = (
        f"*💻 فروشگاه حملات سایبری 💻*\n\n"
        f"*فرمانده، حمله سایبری مورد نظر خود را انتخاب کنید:*\n"
        f"*{'─'*20}*\n"
    )
    for attack, info in CYBER_ATTACKS.items():
        shop_text += (
            f"*{info['emoji']} {attack}*\n"
            f"*💰 قیمت:* {info['cost']} تومان (خرید اولیه)\n"
            f"*💵 حقوق روزانه:* {info['salary']} تومان\n"
            f"*📊 سطح مورد نیاز:* {info['required_level']}\n"
            f"*⏰ زمان خنک شدن:* {info['cooldown']//60} دقیقه\n"
            f"*🎯 نوع:* {info['type']}\n"
        )
        shop_text += f"*{'─'*20}*\n"

    keyboard = [[InlineKeyboardButton(f"خرید {a}", callback_data=f"buy_cyber_attack_{a}")] for a in CYBER_ATTACKS]
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به فروشگاه", callback_data="shop_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(shop_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)

async def handle_cyber_attack_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    cyber_attack_type = query.data.replace("buy_cyber_attack_", "")

    if cyber_attack_type not in CYBER_ATTACKS:
        await query.message.reply_text("*❌ حمله سایبری نامعتبر است! لطفاً یکی از حملات موجود را انتخاب کنید. 🧐*", parse_mode=constants.ParseMode.MARKDOWN)
        return

    def _handle_cyber_attack_purchase_db(cursor, user_id, cyber_attack_type):
        player_data = cursor.execute('SELECT level, is_admin FROM players WHERE id = ?', (user_id,)).fetchone()
        if not player_data: return "*❌ اطلاعات بازیکن یافت نشد. لطفاً دوباره تلاش کنید.*"
        user_level, is_admin_user = player_data['level'], player_data['is_admin']

        cyber_attack_info = CYBER_ATTACKS[cyber_attack_type]

        if not is_admin_user:
            if user_level < cyber_attack_info["required_level"]:
                return (
                    f"*❌ سطح شما برای خرید {cyber_attack_info['name']} کافی نیست! 📈*\n"
                    f"*مورد نیاز: سطح {cyber_attack_info['required_level']}*"
                )

            toman = cursor.execute('SELECT amount FROM resources WHERE player_id = ? AND type = "تومان"', (user_id,)).fetchone()
            toman = toman['amount'] if toman else 0
            attack_cost = cyber_attack_info["cost"]
            if toman < attack_cost:
                return (
                    f"*❌ تومان کافی ندارید! 💰*\n*مورد نیاز: {attack_cost} 💰*"
                )
            cursor.execute('UPDATE resources SET amount = amount - ? WHERE player_id = ? AND type = "تومان"', (attack_cost, user_id))

        now = datetime.datetime.now().isoformat()
        cursor.execute('INSERT OR IGNORE INTO cyber_attacks (player_id, type, last_paid) VALUES (?, ?, ?)', (user_id, cyber_attack_type, now))

        return (
            f"*✅ خرید با موفقیت انجام شد! 🎉*\n\n*{cyber_attack_info['emoji']} {cyber_attack_type}* به لیست حملات سایبری شما اضافه شد! 💻"
        )
    try:
        msg = await execute_db_operation(_handle_cyber_attack_purchase_db, user_id, cyber_attack_type)
        await query.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در خرید حمله سایبری: {e}")
        await query.message.reply_text("*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*", parse_mode=constants.ParseMode.MARKDOWN)

# --- Admin Panel ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await (update.callback_query or update.message).reply_text("*⛔ شما ادمین نیستید، فرمانده! دسترسی به این بخش فقط برای ادمین‌هاست. 👮‍♂️*", parse_mode=constants.ParseMode.MARKDOWN)
        return

    text = (
        f"*👑 به پنل ادمین خوش آمدید، سرورم! 👑*\n\n"
        f"*چه کاری می‌توانم برای شما انجام دهم؟ 🛠️*"
    )
    keyboard = [
        [InlineKeyboardButton("➕ افزودن تومان", callback_data="admin_add_toman")],
        [InlineKeyboardButton("➕ افزودن موشک", callback_data="admin_add_missiles")],
        [InlineKeyboardButton("➕ افزودن یاقوت", callback_data="admin_add_ruby")],
        [InlineKeyboardButton("📊 آمار کلی", callback_data="admin_stats")],
        [InlineKeyboardButton("🎁 ارسال جعبه شانس", callback_data="admin_send_lucky_box")],
        [InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin_broadcast_message")],
        [InlineKeyboardButton("🔑 ایجاد کد هدیه", callback_data="admin_create_gift_code")],
        [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        # به جای بررسی user_panel_messages، مستقیماً پیام را ویرایش می‌کنیم.
        # این کار مشکل "منقضی شدن" را حل می‌کند.
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)

async def handle_admin_add_toman(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"*➕ افزودن تومان به کاربر 💰*\n\n*لطفاً شناسه کاربر و مقدار تومان را وارد کنید:*\n`/add_toman [شناسه] [مقدار]`",
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def admin_add_toman_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("*⛔ فقط ادمین‌ها می‌توانند از این دستور استفاده کنند! 👮‍♂️*", parse_mode=constants.ParseMode.MARKDOWN)
        return

    if len(context.args) < 2:
        await update.message.reply_text("*❌ فرمت اشتباه است! استفاده کنید:*\n`/add_toman [شناسه_بازیکن] [مقدار]`", parse_mode=constants.ParseMode.MARKDOWN)
        return

    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        if amount <= 0:
            await update.message.reply_text("*❌ مقدار تومان باید مثبت باشد! 🔢*", parse_mode=constants.ParseMode.MARKDOWN)
            return

        def _add_toman_db(cursor, target_id, amount):
            if not cursor.execute('SELECT id FROM players WHERE id = ?', (target_id,)).fetchone():
                return "*❌ کاربر یافت نشد! 🕵️‍♂️*"
            cursor.execute('UPDATE resources SET amount = amount + ? WHERE player_id = ? AND type = "تومان"', (amount, target_id))
            return f"*✅ {amount} تومان به کاربر {target_id} اضافه شد! 💰*"

        msg = await execute_db_operation(_add_toman_db, target_id, amount)
        await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("*❌ شناسه یا مقدار باید عدد باشد! 🔢*", parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در افزودن تومان: {e}")
        await update.message.reply_text("*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*", parse_mode=constants.ParseMode.MARKDOWN)

async def handle_admin_add_missiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"*➕ افزودن موشک به کاربر 🚀*\n\n*لطفاً شناسه کاربر، نوع موشک و تعداد را وارد کنید:*\n`/add_missile [شناسه] [نوع] [تعداد]`",
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def admin_add_missile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("*⛔ فقط ادمین‌ها می‌توانند از این دستور استفاده کنند! 👮‍♂️*", parse_mode=constants.ParseMode.MARKDOWN)
        return

    if len(context.args) < 3:
        await update.message.reply_text("*❌ فرمت اشتباه است! استفاده کنید:*\n`/add_missile [شناسه_بازیکن] [نوع] [تعداد]`", parse_mode=constants.ParseMode.MARKDOWN)
        return

    try:
        target_id = int(context.args[0])
        missile_type = context.args[1]
        count = int(context.args[2])
        if missile_type not in MISSILES:
            await update.message.reply_text("*❌ موشک نامعتبر است! یکی از موشک‌های موجود را انتخاب کنید. 🧐*", parse_mode=constants.ParseMode.MARKDOWN)
            return
        if count <= 0:
            await update.message.reply_text("*❌ تعداد موشک باید مثبت باشد! 🔢*", parse_mode=constants.ParseMode.MARKDOWN)
            return

        def _add_missile_db(cursor, target_id, missile_type, count):
            if not cursor.execute('SELECT id FROM players WHERE id = ?', (target_id,)).fetchone():
                return "*❌ کاربر یافت نشد! 🕵️‍♂️*"
            existing = cursor.execute('SELECT count FROM missiles WHERE player_id = ? AND type = ?', (target_id, missile_type)).fetchone()
            if existing:
                cursor.execute('UPDATE missiles SET count = count + ? WHERE player_id = ? AND type = ?', (count, target_id, missile_type))
            else:
                cursor.execute('INSERT INTO missiles (player_id, type, count) VALUES (?, ?, ?)', (target_id, missile_type, count))
            return (
                f"*✅ {count} موشک {MISSILES[missile_type]['name']} به کاربر {target_id} اضافه شد! 🚀*"
            )

        msg = await execute_db_operation(_add_missile_db, target_id, missile_type, count)
        await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("*❌ شناسه یا تعداد باید عدد باشد! 🔢*", parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در افزودن موشک: {e}")
        await update.message.reply_text("*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*", parse_mode=constants.ParseMode.MARKDOWN)

async def handle_admin_add_ruby(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"*➕ افزودن یاقوت به کاربر 💎*\n\n*لطفاً شناسه کاربر و مقدار یاقوت را وارد کنید:*\n`/add_ruby [شناسه] [مقدار]`",
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def admin_add_ruby_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("*⛔ فقط ادمین‌ها می‌توانند از این دستور استفاده کنند! 👮‍♂️*", parse_mode=constants.ParseMode.MARKDOWN)
        return

    if len(context.args) < 2:
        await update.message.reply_text("*❌ فرمت اشتباه است! استفاده کنید:*\n`/add_ruby [شناسه_بازیکن] [مقدار]`", parse_mode=constants.ParseMode.MARKDOWN)
        return

    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        if amount <= 0:
            await update.message.reply_text("*❌ مقدار یاقوت باید مثبت باشد! 🔢*", parse_mode=constants.ParseMode.MARKDOWN)
            return

        def _add_ruby_db(cursor, target_id, amount):
            if not cursor.execute('SELECT id FROM players WHERE id = ?', (target_id,)).fetchone():
                return "*❌ کاربر یافت نشد! 🕵️‍♂️*"
            cursor.execute('UPDATE resources SET amount = amount + ? WHERE player_id = ? AND type = "یاقوت"', (amount, target_id))
            return f"*✅ {amount} یاقوت به کاربر {target_id} اضافه شد! 💎*"

        msg = await execute_db_operation(_add_ruby_db, target_id, amount)
        await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("*❌ شناسه یا مقدار باید عدد باشد! 🔢*", parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در افزودن یاقوت: {e}")
        await update.message.reply_text("*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*", parse_mode=constants.ParseMode.MARKDOWN)

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.message.reply_text("*⛔ فقط ادمین‌ها می‌توانند آمار را مشاهده کنند! 👮‍♂️*", parse_mode=constants.ParseMode.MARKDOWN)
        return

    def _admin_stats_db(cursor):
        total_players = cursor.execute('SELECT COUNT(*) FROM players').fetchone()[0] or 0
        avg_level_raw = cursor.execute('SELECT AVG(level) FROM players').fetchone()[0]
        avg_level = round(avg_level_raw, 2) if avg_level_raw is not None else 0.0
        total_toman = cursor.execute('SELECT SUM(amount) FROM resources WHERE type = "تومان"').fetchone()[0] or 0
        total_battles = cursor.execute('SELECT COUNT(*) FROM battles').fetchone()[0] or 0
        top_players = cursor.execute('SELECT username, first_name, level FROM players ORDER BY level DESC, experience DESC LIMIT 5').fetchall()

        stats_text = (
            f"*📊 آمار کلی بازی 📊*\n\n"
            f"*👥 کل بازیکنان:* {total_players}\n"
            f"*📈 میانگین سطح بازیکنان:* {avg_level}\n"
            f"*💰 کل تومان در بازی:* {total_toman}\n"
            f"*⚔️ کل نبردها:* {total_battles}\n"
            f"*{'─'*20}*\n"
            f"*🏆 ۵ بازیکن برتر:*\n"
        )
        if top_players:
            for i, player in enumerate(top_players, 1):
                name = player['username'] or player['first_name'] or "ناشناس"
                stats_text += f"*{i}. {name} - سطح {player['level']}*\n"
        else:
            stats_text += "*هنوز بازیکنی در رتبه‌بندی نیست!*"
        return stats_text
    try:
        stats_text = await execute_db_operation(_admin_stats_db)
        keyboard = [
            [InlineKeyboardButton("🔙 بازگشت به پنل ادمین", callback_data="admin_panel")],
            [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(stats_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در نمایش آمار: {e}")
        await query.message.reply_text("*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*", parse_mode=constants.ParseMode.MARKDOWN)

# --- Lucky Box ---
async def send_lucky_box_message(context: ContextTypes.DEFAULT_TYPE):
    lucky_box_id = str(uuid.uuid4())
    text = (
        f"*🎁 جعبه شانس جدید! 🎁*\n\n"
        f"*فرماندهان، یک جعبه مرموز در میدان نبرد پیدا شده است! اولین نفری که روی دکمه زیر کلیک کند، جایزه را برنده می‌شود! 🏆*"
    )
    keyboard = [[InlineKeyboardButton("✨ باز کردن جعبه شانس ✨", callback_data=f"open_lucky_box_{lucky_box_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    def _get_chat_ids_db(cursor):
        cursor.execute('SELECT chat_id FROM chats')
        return [row['chat_id'] for row in cursor.fetchall()]

    all_chat_ids = await execute_db_operation(_get_chat_ids_db)

    for chat_id in all_chat_ids:
        try:
            delay = random.uniform(1, 10)
            await asyncio.sleep(delay)
            sent_message = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)

            def _save_active_lucky_box_db(cursor, lucky_box_id, chat_id, message_id):
                cursor.execute('INSERT INTO active_lucky_boxes (lucky_box_id, chat_id, message_id) VALUES (?, ?, ?)', (lucky_box_id, chat_id, message_id))
            await execute_db_operation(_save_active_lucky_box_db, lucky_box_id, chat_id, sent_message.message_id)

            logger.info(f"جعبه شانس {lucky_box_id} به چت {chat_id} با تاخیر {delay:.2f} ثانیه ارسال شد.")
        except Exception as e:
            logger.error(f"خطا در ارسال جعبه شانس به چت {chat_id}: {e}")

async def handle_open_lucky_box(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    lucky_box_id = query.data.replace("open_lucky_box_", "")
    chat_id = query.message.chat_id

    def _check_and_open_lucky_box_db(cursor, lucky_box_id, chat_id, user_id, now_iso):
        lucky_box_status = cursor.execute('SELECT opened_by FROM active_lucky_boxes WHERE lucky_box_id = ? AND chat_id = ?', (lucky_box_id, chat_id)).fetchone()

        if lucky_box_status and lucky_box_status['opened_by'] is not None:
            # اگر جعبه قبلاً باز شده باشد، پیام خطا را به کاربر فعلی نشان می‌دهیم
            # و پیام اصلی جعبه شانس را ویرایش نمی‌کنیم.
            opener_id = lucky_box_status['opened_by']
            opener_info = cursor.execute('SELECT username, first_name FROM players WHERE id = ?', (opener_id,)).fetchone()
            opener_name = opener_info['username'] or opener_info['first_name'] or "یک فرمانده"
            return False, f"❌ این جعبه قبلاً توسط {opener_name} در این گروه باز شده است! 😔", None

        # اگر جعبه باز نشده باشد، آن را برای کاربر فعلی باز می‌کنیم
        cursor.execute('UPDATE active_lucky_boxes SET opened_by = ?, opened_at = ? WHERE lucky_box_id = ? AND chat_id = ?', (user_id, now_iso, lucky_box_id, chat_id))
        return True, None, query.message.message_id # message_id را برمی‌گردانیم تا بتوانیم آن را ویرایش کنیم

    success, error_msg, original_message_id = await execute_db_operation(_check_and_open_lucky_box_db, lucky_box_id, chat_id, user_id, datetime.datetime.now().isoformat())

    if not success:
        await query.answer(error_msg, show_alert=True)
        return

    await query.answer("🎉 در حال باز کردن جعبه... 🎉")

    player_info = await execute_db_operation(lambda cursor, uid: cursor.execute('SELECT username, first_name FROM players WHERE id = ?', (uid,)).fetchone(), user_id)
    if not player_info:
        logger.error(f"بازیکن {user_id} برای جعبه شانس یافت نشد.")
        await query.edit_message_text("*❌ خطایی رخ داد: اطلاعات بازیکن یافت نشد.*", parse_mode=constants.ParseMode.MARKDOWN)
        return
    player_name = player_info['username'] or player_info['first_name'] or "فرمانده ناشناس"

    prize_message = f"*🎉 {player_name} جعبه شانس را باز کرد و جایزه را برد! 🎉*\n\n"

    prizes = [
        {"type": "resource", "name": "تومان", "amount": random.randint(2000, 7000), "emoji": RESOURCES["تومان"]["emoji"], "weight": 6},
        {"type": "resource", "name": "جام", "amount": random.randint(20, 100), "emoji": RESOURCES["جام"]["emoji"], "weight": 3},
        {"type": "resource", "name": "یاقوت", "amount": random.randint(5, 20), "emoji": RESOURCES["یاقوت"]["emoji"], "weight": 5},
        {"type": "missile", "name": random.choice(list(MISSILES.keys())), "amount": 1, "emoji": "🚀", "weight": 2},
        {"type": "tank", "name": random.choice(list(TANKS.keys())), "amount": 1, "emoji": "⚔️", "weight": 1},
        {"type": "fighter", "name": random.choice(list(FIGHTERS.keys())), "amount": 1, "emoji": "✈️", "weight": 1},
        {"type": "warship", "name": random.choice(list(WARSHIPS.keys())), "amount": 1, "emoji": "🚢", "weight": 0.5},
        {"type": "drone", "name": random.choice(list(DRONES.keys())), "amount": 1, "emoji": "🚁", "weight": 1},
        {"type": "defense", "name": random.choice(list(DEFENSE_SYSTEMS.keys())), "level": 1, "emoji": "🛡️", "weight": 1},
        {"type": "cyber_defense", "name": random.choice(list(CYBER_DEFENSES.keys())), "level": 1, "emoji": "💻", "weight": 0.8},
        {"type": "experience", "amount": random.randint(200, 1000), "emoji": "⭐", "weight": 2},
        {"type": "level_up", "emoji": "📈", "weight": 0.5},
        {"type": "health_boost", "amount": random.randint(20, 80), "emoji": "❤️", "weight": 1.5},
        {"type": "shield_boost", "amount": random.randint(10, 30), "emoji": "🛡️", "weight": 1}
    ]

    chosen_prize = random.choices(prizes, weights=[p['weight'] for p in prizes], k=1)[0]

    def _apply_lucky_box_prize_db(cursor, user_id, chosen_prize):
        prize_message_part = ""
        prize_type = chosen_prize["type"]
        prize_name = chosen_prize.get("name")
        amount = chosen_prize.get("amount")
        level = chosen_prize.get("level")

        if prize_type == "missile":
            cursor.execute('INSERT OR IGNORE INTO missiles (player_id, type, count) VALUES (?, ?, 0)', (user_id, prize_name))
            cursor.execute('UPDATE missiles SET count = count + ? WHERE player_id = ? AND type = ?', (amount, user_id, prize_name))
            prize_message_part = f"*جایزه شما: {amount} موشک {MISSILES[prize_name]['emoji']} {prize_name}! 🚀*"
        elif prize_type == "tank":
            cursor.execute('INSERT OR IGNORE INTO tanks (player_id, type, count, health) VALUES (?, ?, 0, ?)', (user_id, prize_name, TANKS[prize_name]["max_health"]))
            cursor.execute('UPDATE tanks SET count = count + ?, health = ? WHERE player_id = ? AND type = ?', (amount, TANKS[prize_name]["max_health"], user_id, prize_name))
            prize_message_part = f"*جایزه شما: {amount} تانک {TANKS[prize_name]['emoji']} {prize_name}! ⚔️*"
        elif prize_type == "fighter":
            cursor.execute('INSERT OR IGNORE INTO fighters (player_id, type, count, health) VALUES (?, ?, 0, ?)', (user_id, prize_name, FIGHTERS[prize_name]["max_health"]))
            cursor.execute('UPDATE fighters SET count = count + ?, health = ? WHERE player_id = ? AND type = ?', (amount, FIGHTERS[prize_name]["max_health"], user_id, prize_name))
            prize_message_part = f"*جایزه شما: {amount} جنگنده {FIGHTERS[prize_name]['emoji']} {prize_name}! ✈️*"
        elif prize_type == "warship":
            cursor.execute('INSERT OR IGNORE INTO warships (player_id, type, count, health) VALUES (?, ?, 0, ?)', (user_id, prize_name, WARSHIPS[prize_name]["max_health"]))
            cursor.execute('UPDATE warships SET count = count + ?, health = ? WHERE player_id = ? AND type = ?', (amount, WARSHIPS[prize_name]["max_health"], user_id, prize_name))
            prize_message_part = f"*جایزه شما: {amount} کشتی جنگی {WARSHIPS[prize_name]['emoji']} {prize_name}! 🚢*"
        elif prize_type == "drone":
            cursor.execute('INSERT OR IGNORE INTO drones (player_id, type, count, health) VALUES (?, ?, 0, ?)', (user_id, prize_name, DRONES[prize_name]["max_health"]))
            cursor.execute('UPDATE drones SET count = count + ?, health = ? WHERE player_id = ? AND type = ?', (amount, DRONES[prize_name]["max_health"], user_id, prize_name))
            prize_message_part = f"*جایزه شما: {amount} پهپاد {DRONES[prize_name]['emoji']} {prize_name}! 🚁*"
        elif prize_type == "defense" or prize_type == "cyber_defense":
            def_map = DEFENSE_SYSTEMS if prize_type == "defense" else CYBER_DEFENSES
            existing_defense = cursor.execute('SELECT level FROM defenses WHERE player_id = ? AND type = ?', (user_id, prize_name)).fetchone()
            now_iso = datetime.datetime.now().isoformat()
            if existing_defense:
                current_level = existing_defense['level']
                if current_level < def_map[prize_name]["max_level"]:
                    cursor.execute('UPDATE defenses SET level = level + 1, last_paid = ? WHERE player_id = ? AND type = ?', (now_iso, user_id, prize_name))
                    prize_message_part = f"*جایزه شما: ارتقاء {def_map[prize_name]['emoji']} {prize_name} به سطح {current_level + 1}! 🛡️*"
                else:
                    bonus_toman = 500 if prize_type == "defense" else 700
                    cursor.execute('UPDATE resources SET amount = amount + ? WHERE player_id = ? AND type = "تومان"', (bonus_toman, user_id))
                    prize_message_part = f"*جایزه شما: {def_map[prize_name]['emoji']} {prize_name} در حداکثر سطح است! شما {bonus_toman} تومان دریافت کردید! 💰*"
            else:
                cursor.execute('INSERT INTO defenses (player_id, type, level, health, last_paid) VALUES (?, ?, 1, 100, ?)', (user_id, prize_name, now_iso))
                prize_message_part = f"*جایزه شما: {def_map[prize_name]['emoji']} {prize_name} به پایگاه شما اضافه شد! 🛡️*"
        elif prize_type == "resource":
            cursor.execute('UPDATE resources SET amount = amount + ? WHERE player_id = ? AND type = ?', (amount, user_id, prize_name))
            prize_message_part = f"*جایزه شما: {amount} {chosen_prize['emoji']} {prize_name}! 💰*"
        elif prize_type == "experience":
            level_up_msg = asyncio.run(add_experience(user_id, amount)) # Direct call, careful with nested async
            prize_message_part = f"*جایزه شما: {amount} {chosen_prize['emoji']} تجربه! {level_up_msg}*"
        elif prize_type == "level_up":
            current_level = cursor.execute('SELECT level FROM players WHERE id = ?', (user_id,)).fetchone()['level']
            new_level = current_level + 1
            cursor.execute('UPDATE players SET level = ?, experience = 0 WHERE id = ?', (new_level, user_id))
            prize_message_part = f"*جایزه ویژه شما: یک ارتقاء سطح کامل! شما به سطح {new_level} رسیدید! 📈✨*"
        elif prize_type == "health_boost":
            health_data = cursor.execute('SELECT health, base_health FROM players WHERE id = ?', (user_id,)).fetchone()
            current_health, base_health = health_data['health'], health_data['base_health']
            new_health = min(current_health + amount, base_health)
            cursor.execute('UPDATE players SET health = ? WHERE id = ?', (new_health, user_id))
            prize_message_part = f"*جایزه شما: {amount} {chosen_prize['emoji']} افزایش سلامت پایگاه! ❤️ سلامت فعلی: {new_health}/{base_health}*"
        elif prize_type == "shield_boost":
            cursor.execute('UPDATE players SET shield = shield + ? WHERE id = ?', (amount, user_id))
            current_shield = cursor.execute('SELECT shield FROM players WHERE id = ?', (user_id,)).fetchone()['shield']
            prize_message_part = f"*جایزه شما: {amount} {chosen_prize['emoji']} افزایش سپر دفاعی! 🛡️ سپر فعلی: {current_shield}*"
        return prize_message_part

    try:
        prize_message_part = await execute_db_operation(_apply_lucky_box_prize_db, user_id, chosen_prize)
        prize_message += prize_message_part
    except Exception as e:
        logger.error(f"خطا در اعمال جایزه جعبه شانس برای بازیکن {user_id}: {e}")
        prize_message = "*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*"

    try:
        # پیام اصلی جعبه شانس را ویرایش می‌کنیم تا نتیجه را نشان دهد
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=original_message_id,
            text=prize_message,
            parse_mode=constants.ParseMode.MARKDOWN,
            reply_markup=None # دکمه را حذف می‌کنیم تا دیگر قابل کلیک نباشد
        )
        # نیازی به حذف پیام نیست، چون ویرایش شده است.
        # اگر می‌خواهید پیام بعد از مدتی حذف شود، می‌توانید یک تاخیر و سپس حذف را اضافه کنید.
        # def _delete_active_lucky_box_db(cursor, lucky_box_id, chat_id):
        #     cursor.execute('DELETE FROM active_lucky_boxes WHERE lucky_box_id = ? AND chat_id = ?', (lucky_box_id, chat_id))
        # await execute_db_operation(_delete_active_lucky_box_db, lucky_box_id, chat_id)

    except Exception as e:
        logger.error(f"خطا در ویرایش پیام جعبه شانس: {e}")
        # اگر ویرایش پیام اصلی با خطا مواجه شد، پیام جایزه را به صورت جدید ارسال می‌کنیم.
        await context.bot.send_message(chat_id=query.message.chat.id, text=prize_message, parse_mode=constants.ParseMode.MARKDOWN)

async def admin_send_lucky_box_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.message.reply_text("*⛔ فقط ادمین‌ها می‌توانند این کار را انجام دهند!*", parse_mode=constants.ParseMode.MARKDOWN)
        return

    await send_lucky_box_message(context)
    await query.message.reply_text("*✅ جعبه شانس با موفقیت به تمام گروه‌های ثبت شده ارسال شد! 🎁*", parse_mode=constants.ParseMode.MARKDOWN)

async def admin_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"*📢 ارسال پیام همگانی 📢*\n\n*لطفاً پیامی را که می‌خواهید ارسال کنید وارد کنید:*\n`/broadcast [پیام شما]`",
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def broadcast_message_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("*⛔ فقط ادمین‌ها می‌توانند از این دستور استفاده کنند! 👮‍♂️*", parse_mode=constants.ParseMode.MARKDOWN)
        return

    if not context.args:
        await update.message.reply_text("*❌ لطفاً پیامی برای ارسال وارد کنید! مثال:*\n`/broadcast سلام فرماندهان!`", parse_mode=constants.ParseMode.MARKDOWN)
        return

    message_to_send = " ".join(context.args)

    def _get_all_player_and_chat_ids_db(cursor):
        player_ids = [row['id'] for row in cursor.execute('SELECT id FROM players').fetchall()]
        chat_ids = [row['chat_id'] for row in cursor.execute('SELECT chat_id FROM chats').fetchall()]
        return player_ids, chat_ids

    player_ids, chat_ids = await execute_db_operation(_get_all_player_and_chat_ids_db)

    for player_id in player_ids:
        try:
            await context.bot.send_message(chat_id=player_id, text=f"*📢 پیام از ستاد فرماندهی مرکزی:*\n\n{message_to_send}", parse_mode=constants.ParseMode.MARKDOWN)
        except Exception as e:
            if "blocked" in str(e).lower():
                logger.warning(f"کاربر {player_id} ربات را مسدود کرده است. پیام همگانی ارسال نشد.")
            else:
                logger.error(f"خطا در ارسال پیام همگانی به کاربر {player_id}: {e}")

    for chat_id in chat_ids:
        try:
            await context.bot.send_message(chat_id=chat_id, text=f"*📢 پیام از ستاد فرماندهی مرکزی:*\n\n{message_to_send}", parse_mode=constants.ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"خطا در ارسال پیام همگانی به چت {chat_id}: {e}")

    await update.message.reply_text("*✅ پیام همگانی با موفقیت ارسال شد!*", parse_mode=constants.ParseMode.MARKDOWN)

async def admin_create_gift_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"*🔑 ایجاد کد هدیه جدید 🔑*\n\n"
        f"*لطفاً اطلاعات کد هدیه را در فرمت زیر وارد کنید:*\n"
        f"`/create_gift_code [نوع_جایزه] [حداقل_مقدار] [حداکثر_مقدار] [مقدار_یاقوت] [مقدار_تجربه] [حداکثر_تعداد_استفاده]`\n\n"
        f"*مثال:*\n"
        f"`/create_gift_code toman 20000 27000 0 0 10` (20 تا 27 هزار تومان، 10 بار استفاده)\n"
        f"`/create_gift_code ruby 0 0 10 0 5` (10 یاقوت، 5 بار استفاده)\n"
        f"`/create_gift_code exp 0 0 0 5000 20` (5000 تجربه، 20 بار استفاده)\n"
        f"`/create_gift_code mixed 10000 15000 5 2000 3` (10-15 هزار تومان، 5 یاقوت، 2000 تجربه، 3 بار استفاده)\n\n"
        f"*نوع_جایزه می‌تواند toman, ruby, exp یا mixed باشد. برای مقادیر نامربوط 0 وارد کنید.*",
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def create_gift_code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("*⛔ فقط ادمین‌ها می‌توانند کد هدیه ایجاد کنند! 👮‍♂️*", parse_mode=constants.ParseMode.MARKDOWN)
        return

    if len(context.args) != 6:
        await update.message.reply_text("*❌ فرمت اشتباه است! لطفاً راهنما را دوباره بخوانید.*", parse_mode=constants.ParseMode.MARKDOWN)
        return

    try:
        reward_type = context.args[0].lower()
        min_amount = int(context.args[1])
        max_amount = int(context.args[2])
        ruby_amount = int(context.args[3])
        exp_amount = int(context.args[4])
        max_uses = int(context.args[5])

        if reward_type not in ["toman", "ruby", "exp", "mixed"]:
            await update.message.reply_text("*❌ نوع جایزه نامعتبر است. (toman, ruby, exp, mixed)*", parse_mode=constants.ParseMode.MARKDOWN)
            return
        if min_amount < 0 or max_amount < 0 or ruby_amount < 0 or exp_amount < 0 or max_uses <= 0:
            await update.message.reply_text("*❌ مقادیر باید مثبت باشند و تعداد استفاده حداقل 1 باشد.*", parse_mode=constants.ParseMode.MARKDOWN)
            return
        if min_amount > max_amount and (reward_type == "toman" or reward_type == "mixed"):
            await update.message.reply_text("*❌ حداقل مقدار نمی‌تواند بیشتر از حداکثر مقدار باشد.*", parse_mode=constants.ParseMode.MARKDOWN)
            return

        code = str(uuid.uuid4())[:8].upper()

        def _create_gift_code_db(cursor, code, reward_type, min_amount, max_amount, ruby_amount, exp_amount, max_uses):
            cursor.execute('INSERT INTO gift_codes (code, reward_type, min_amount, max_amount, ruby_amount, exp_amount, uses_left, max_uses) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                           (code, reward_type, min_amount, max_amount, ruby_amount, exp_amount, max_uses, max_uses))
            return (
                f"*✅ کد هدیه `{code}` با موفقیت ایجاد شد!*\n"
                f"*نوع جایزه:* {reward_type}\n"
                f"*تومان:* {min_amount}-{max_amount}\n"
                f"*یاقوت:* {ruby_amount}\n"
                f"*تجربه:* {exp_amount}\n"
                f"*تعداد استفاده:* {max_uses}"
            )

        msg = await execute_db_operation(_create_gift_code_db, code, reward_type, min_amount, max_amount, ruby_amount, exp_amount, max_uses)
        await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)

    except ValueError:
        await update.message.reply_text("*❌ مقادیر عددی نامعتبر هستند!*", parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در ایجاد کد هدیه: {e}")
        await update.message.reply_text("*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*", parse_mode=constants.ParseMode.MARKDOWN)

async def redeem_gift_code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("*❌ فرمت اشتباه است! استفاده کنید:*\n`/redeem [کد_هدیه]`", parse_mode=constants.ParseMode.MARKDOWN)
        return

    code = context.args[0].upper()

    def _redeem_gift_code_db(cursor, user_id, code):
        gift_code_data = cursor.execute('SELECT * FROM gift_codes WHERE code = ?', (code,)).fetchone()

        if not gift_code_data: return "*❌ کد هدیه نامعتبر است!*", False
        if gift_code_data['uses_left'] <= 0: return "*❌ این کد هدیه منقضی شده است!*", False

        reward_type = gift_code_data['reward_type']
        min_amount = gift_code_data['min_amount']
        max_amount = gift_code_data['max_amount']
        ruby_amount = gift_code_data['ruby_amount']
        exp_amount = gift_code_data['exp_amount']

        reward_message = "*🎁 پاداش کد هدیه شما:*\n"

        if reward_type == "toman" or reward_type == "mixed":
            toman_reward = random.randint(min_amount, max_amount)
            cursor.execute('UPDATE resources SET amount = amount + ? WHERE player_id = ? AND type = "تومان"', (toman_reward, user_id))
            reward_message += f"*{toman_reward} 💰 تومان*\n"

        if reward_type == "ruby" or reward_type == "mixed":
            cursor.execute('UPDATE resources SET amount = amount + ? WHERE player_id = ? AND type = "یاقوت"', (ruby_amount, user_id))
            reward_message += f"*{ruby_amount} 💎 یاقوت*\n"

        if reward_type == "exp" or reward_type == "mixed":
            level_up_msg = asyncio.run(add_experience(user_id, exp_amount))
            reward_message += f"*{exp_amount} ⭐ تجربه! {level_up_msg}*\n"

        cursor.execute('UPDATE gift_codes SET uses_left = uses_left - 1 WHERE code = ?', (code,))
        return reward_message, True

    try:
        msg, success = await execute_db_operation(_redeem_gift_code_db, user_id, code)
        await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"خطا در استفاده از کد هدیه: {e}")
        await update.message.reply_text("*❌ خطایی رخ داد! لطفاً دوباره تلاش کنید. 🐛*", parse_mode=constants.ParseMode.MARKDOWN)

# --- Inline Button Handler ---
async def handle_inline_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    # این بخش برای جلوگیری از "منقضی شدن" پیام‌ها تغییر کرده است.
    # دیگر نیازی به بررسی user_panel_messages نیست، زیرا هر بار پیام ویرایش می‌شود.
    # اگر پیام از یک گروه باشد و کاربر ادمین نباشد، ممکن است بخواهیم محدودیت‌هایی اعمال کنیم.
    # اما برای پنل‌های شخصی، ویرایش مستقیم پیام بهترین راه حل است.

    handlers = {
        "main_menu": start,
        "show_arsenal": show_arsenal,
        "show_ranking": ranking,
        "show_status": show_status,
        "shop_main": shop,
        "shop_missiles": show_missiles_shop,
        "shop_defenses": show_defenses_shop,
        "shop_tanks": show_tanks_shop,
        "shop_fighters": show_fighters_shop,
        "shop_warships": show_warships_shop,
        "shop_drones": show_drones_shop,
        "shop_cyber_attacks": show_cyber_attacks_shop,
        "treat_base": treat_base,
        "upgrade_level": upgrade_level,
        "mine_ruby_btn": mine_ruby,
        "daily_bonus_btn": daily_bonus,
        "bank_withdrawal_btn": bank_withdrawal,
        "convert_ruby_to_toman_btn": convert_ruby_to_toman,
        "repair_equipment_menu": repair_equipment_menu,
        "pay_salaries_menu": pay_salaries_menu,
        "admin_panel": admin_panel,
        "admin_add_toman": handle_admin_add_toman,
        "admin_add_missiles": handle_admin_add_missiles,
        "admin_add_ruby": handle_admin_add_ruby,
        "admin_stats": admin_stats,
        "admin_send_lucky_box": admin_send_lucky_box_manual,
        "admin_broadcast_message": admin_broadcast_message,
        "admin_create_gift_code": admin_create_gift_code,
        "upgrade_player_stat_base_health": lambda u, c: upgrade_player_stat(u, c, "base_health"),
        "upgrade_player_stat_shield": lambda u, c: upgrade_player_stat(u, c, "shield"),
        "upgrade_player_stat_mine_ruby": lambda u, c: upgrade_player_stat(u, c, "mine_ruby"),
    }

    if data in handlers:
        await handlers[data](update, context)
    elif data.startswith("buy_missile_"): await handle_missile_purchase(update, context)
    elif data.startswith("upgrade_defense_"): await handle_defense_purchase(update, context)
    elif data.startswith("buy_tank_"): await handle_tank_purchase(update, context)
    elif data.startswith("buy_fighter_"): await handle_fighter_purchase(update, context)
    elif data.startswith("buy_warship_"): await handle_warship_purchase(update, context)
    elif data.startswith("buy_drone_"): await handle_drone_purchase(update, context)
    elif data.startswith("buy_cyber_attack_"): await handle_cyber_attack_purchase(update, context)
    elif data.startswith("open_lucky_box_"): await handle_open_lucky_box(update, context)
    elif data.startswith("repair_"): await repair_equipment(update, context)
    elif data.startswith("pay_"): await pay_salaries(update, context)
    else:
        await query.answer("*❌ این دکمه هنوز فعال نیست! به زودی اضافه خواهد شد. 🚧*", show_alert=True)

# --- Main Function ---
def main():
    init_db()
    application = Application.builder().token(TOKEN).build()

    # ارسال جعبه شانس هر 5 دقیقه (300 ثانیه)
    application.job_queue.run_repeating(send_lucky_box_message, interval=300, first=10)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("arsenal", show_arsenal))
    application.add_handler(CommandHandler("treat", treat_base))
    application.add_handler(CommandHandler("shop", shop))
    application.add_handler(CommandHandler("upgrade_defense", upgrade_defense))
    application.add_handler(CommandHandler("ranking", ranking))
    application.add_handler(CommandHandler("status", show_status))
    application.add_handler(CommandHandler("mine_ruby", mine_ruby))
    application.add_handler(CommandHandler("daily_bonus", daily_bonus))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("add_toman", admin_add_toman_command))
    application.add_handler(CommandHandler("add_missile", admin_add_missile_command))
    application.add_handler(CommandHandler("add_ruby", admin_add_ruby_command))
    application.add_handler(CommandHandler("broadcast", broadcast_message_command))
    application.add_handler(CommandHandler("create_gift_code", create_gift_code_command))
    application.add_handler(CommandHandler("redeem", redeem_gift_code_command))

    application.add_handler(MessageHandler(filters.Regex(r'شلیک موشک'), handle_missile_attack_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'شلیک تانک'), handle_ground_attack_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'حمله هوایی'), handle_air_attack_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'حمله دریایی'), handle_naval_attack_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'حمله پهپادی'), handle_drone_attack_cmd))
    application.add_handler(MessageHandler(filters.Regex(r'حمله سایبری'), handle_cyber_attack_cmd))
    application.add_handler(CallbackQueryHandler(handle_inline_buttons))

    logger.info("ربات جنگ موشکی با موفقیت راه‌اندازی شد... 🚀")
    application.run_polling()

if __name__ == "__main__":
    main()
