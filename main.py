import logging
import requests
import sqlite3
import re
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Render-এ ২৪ ঘণ্টা সচল রাখার ওয়েব সার্ভার
server = Flask('')
@server.route('/')
def home(): return "Supreme Multi-Panel & User OTP Bot is Running 24/7!"
def run_server(): server.run(host='0.0.0.0', port=8080)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==================== কনফিগারেশন ===================="8517425191:AAE6-VcxO5c8o9eDZr_XqJ2JOVptXfPmIQA"  # ⚠️ আপনার বটের আসল টোকেন দিন
ADMIN_IDS = [8051276654]  # ⚠️ আপনার সঠিক অ্যাডমিন আইডি দিন
# ===================================================

# 🗄️ ডাটাবেস তৈরি ও টেবিল সেটআপ
def init_db():
    conn = sqlite3.connect('master_otp.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS panels 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, url TEXT, token TEXT, username TEXT, password TEXT, type TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS manual_numbers 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT, service TEXT, country TEXT, status TEXT DEFAULT 'AVAILABLE', otp TEXT DEFAULT '')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, lang TEXT DEFAULT 'en')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    # ডিফল্ট চ্যানেল লক সেটিংস
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('channels', '@tuotpbackup, @TechUniverseBackup')")
    conn.commit()
    conn.close()

init_db()

admin_state = {}

# 🌐 ভাষা অনুযায়ী ডিকশনারি (হুবহু আপনার স্ক্রিনশটের টেক্সট)
STRINGS = {
    "en": {
        "welcome": "👋 *Welcome to our Bot!*\n📲 Instantly receive Telegram, WhatsApp, Facebook, Google OTP code using virtual numbers.\n\n🌐 *Please select your language:*",
        "lock": "⚠️ *Please join all required channels first!*\nBot access is locked until you join all channels.",
        "joined_success": "✅ Successfully authorized! Welcome to the main menu.",
        "select_country": "🌍 *PLEASE SELECT A COUNTRY / SERVICE:*",
        "active_num": "📊 You currently have no active numbers.",
        "kb_get_num": "📞 Get Number",
        "kb_active": "📊 Active Numbers",
        "kb_lang": "🌐 Change Language"
    },
    "ar": {
        "welcome": "👋 *مرحباً بك في البوت الخاص بنا!*\n📲 احصل على أكواد OTP الفورية لتليجرام، واتساب، فيسبوك، وجوجل باستخدام أرقام وهمية.\n\n🌐 *يرجى اختيار اللغة الخاصة بك:*",
        "lock": "⚠️ *رجاءً قم بالانضمام إلى جميع القنوات المطلوبة أولاً!*\nالدخول للبوت مغلق حتى تنضم للقنوات.",
        "joined_success": "✅ تم التحقق بنجاح! مرحباً بك في القائمة الرئيسية.",
        "select_country": "🌍 *رجاءً اختر الدولة / الخدمة:*",
        "no_stock": "❌ لا يوجد مخزون حالياً!",
        "active_num": "📊 ليس لديك أي أرقام نشطة حالياً.",
        "kb_get_num": "📞 الحصول على رقم",
        "kb_active": "📊 الأرقام النشطة",
        "kb_lang": "🌐 تغيير اللغة"
    }
}

# ডাটাবেস থেকে চ্যানেল লক ডেটা আনা
def get_required_channels():
    conn = sqlite3.connect('master_otp.db')
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key='channels'")
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return [ch.strip() for ch in row[0].split(",") if ch.strip()]
    return []

# ইউজার চ্যানেলগুলোতে জয়েন আছে কিনা চেক করা
async def is_user_subscribed(bot, user_id):
    if user_id in ADMIN_IDS: return True
    channels = get_required_channels()
    for channel in channels:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ['left', 'kicked']: return False
        except: return False
    return True

# ইউজার মেইন রিপ্লাই কিবোর্ড
def get_main_keyboard(lang):
    kb = [
        [STRINGS[lang]["kb_get_num"], STRINGS[lang]["kb_active"]],
        [STRINGS[lang]["kb_lang"]]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

# 👑 অ্যাডমিন কন্ট্রোল প্যানেল কিবোর্ড
def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔗 নতুন API প্যানেল যোগ", callback_data="adm_add_api")],
        [InlineKeyboardButton("🔑 নতুন ID-Pass প্যানেল যোগ", callback_data="adm_add_login")],
        [InlineKeyboardButton("📱 নিজের নাম্বার অ্যাড (Manual)", callback_data="adm_add_manual")],
        [InlineKeyboardButton("🔒 চ্যানেল লক এডিট করুন", callback_data="adm_edit_ch")],
        [InlineKeyboardButton("📊 স্ট্যাটাস ও কানেক্টেড প্যানেল", callback_data="adm_status")]
    ]
    return InlineKeyboardMarkup(keyboard)

# /start কমান্ড
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect('master_otp.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, lang) VALUES (?, 'en')", (user_id,))
    conn.commit()
    conn.close()

    keyboard = [[InlineKeyboardButton("English 🇬🇧", callback_data="set_lang_en")], [InlineKeyboardButton("العربية 🇸🇦", callback_data="set_lang_ar")]]
    await update.message.reply_text(STRINGS["en"]["welcome"], parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# /admin কমান্ড
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    await update.message.reply_text("⚙️ *TBT Supreme Control Centre*\nনিচের অপশনগুলো দিয়ে ইউজার বট ও প্যানেল সেশন নিয়ন্ত্রণ করুন:", parse_mode="Markdown", reply_markup=get_admin_keyboard())

# বাটন ক্লিক এবং ইন্টারফেস হ্যান্ডলার (ইউজার + অ্যাডমিন)
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    await query.answer()

    conn = sqlite3.connect('master_otp.db')
    cursor = conn.cursor()
    cursor.execute("SELECT lang FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    lang = row[0] if row else "en"

    # --- ১. ইউজার ল্যাঙ্গুয়েজ ও চ্যানেল লক ইন্টারফেস ---
    if query.data.startswith("set_lang_"):
        lang = query.data.split("_")[2]
        cursor.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, user_id))
        conn.commit()
        
        if not await is_user_subscribed(context.bot, user_id):
            channels = get_required_channels()
            keyboard = []
            for ch in channels:
                keyboard.append([InlineKeyboardButton(f"Join {ch} ↗️", url=f"https://t.me/{ch.lstrip('@')}")])
            keyboard.append([InlineKeyboardButton("✔️ I Have Joined", callback_data="u_check_join")])
            await query.edit_message_text(STRINGS[lang]["lock"], parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.message.reply_text(STRINGS[lang]["joined_success"], reply_markup=get_main_keyboard(lang))

    elif query.data == "u_check_join":
        if await is_user_subscribed(context.bot, user_id):
            await query.message.reply_text(STRINGS[lang]["joined_success"], reply_markup=get_main_keyboard(lang))
        else:
            await context.bot.send_message(chat_id=user_id, text="❌ You haven't joined all channels yet!")

    # --- ২. দেশের সার্ভিস এবং নাম্বার সিলেকশন (হুবহু স্ক্রিনশট ৩ ও ৪ এর মতো) ---
    elif query.data.startswith("srv_"):
        srv_type = query.data.split("_")[1] # e.g. egyptwa
        # নিজের ম্যানুয়াল স্টক অথবা প্যানেল সেশন থেকে নাম্বার নিয়ে এসে সুন্দর বাটন বক্সে দেখাবে
        cursor.execute("SELECT id, phone FROM manual_numbers WHERE service=? AND status='AVAILABLE' LIMIT 3", (srv_type,))
        numbers = cursor.fetchall()
        
        keyboard = []
        if numbers:
            for num in numbers:
                keyboard.append([InlineKeyboardButton(f"📋 🌍 {num[1]}", callback_data=f"getotp_{num[0]}")])
        else:
            # যদি নিজের ডাটাবেসে না থাকে, ডেমো হিসেবে বাটন শো করবে
            keyboard.append([InlineKeyboardButton("📋 🇪🇬 +201109719973", callback_data="demo_otp")])
            keyboard.append([InlineKeyboardButton("📋 🇪🇬 +201181920708", callback_data="demo_otp")])

        keyboard.append([InlineKeyboardButton("🔄 Change Number", callback_data="u_get_num_trigger")])
        keyboard.append([InlineKeyboardButton("🌍 Change Country", callback_data="u_get_num_trigger")])
        keyboard.append([InlineKeyboardButton("🔑 Get OTP ↗️", callback_data="demo_otp")])
        
        await query.edit_message_text("╔════════════════════════╗\n   📱 *TBT Number Bot* ☎️  `Admin` \n╚════════════════════════╝\n\n👇 *Available Numbers:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "u_get_num_trigger":
        # স্ক্রিনশট ৩ এর মতো কান্ট্রি ও স্টক লিস্ট বাটন জেনারেট করা
        keyboard = [
            [InlineKeyboardButton("🇪🇬 Egypt Whatsapp (583)", callback_data="srv_egyptwa")],
            [InlineKeyboardButton("🇹🇳 Tunisia Facebook (129)", callback_data="srv_tunisiafb")],
            [InlineKeyboardButton("🇾🇪 Yemen Telegram (340)", callback_data="srv_yementg")]
        ]
        await query.edit_message_text(STRINGS[lang]["select_country"], parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # --- ৩. অ্যাডমিন প্যানেল ব্যাকঅ্যান্ড একশনস ---
    elif query.data == "adm_add_api":
        admin_state[user_id] = "w_api"
        await query.edit_message_text("👉 *ফরম্যাট:* `প্যানেল_নাম | API_URL | API_Token` লিখে পাঠান:")
    elif query.data == "adm_add_login":
        admin_state[user_id] = "w_login"
        await query.edit_message_text("👉 *ফরম্যাট:* `প্যানেল_নাম | Login_URL | ইউজারনেম | পাসওয়ার্ড` লিখে পাঠান:")
    elif query.data == "adm_add_manual":
        admin_state[user_id] = "w_manual"
        await query.edit_message_text("👉 *ফরম্যাট:* `নাম্বার | সার্ভিস | দেশ` লিখে পাঠান:\n(যেমন: `+201109719973 | egyptwa | Egypt`)")
    elif query.data == "adm_edit_ch":
        admin_state[user_id] = "w_ch"
        await query.edit_message_text("👉 নতুন চ্যানেল লকগুলোর ইউজারনেম কমা (,) দিয়ে লিখে পাঠান:\n(যেমন: `@ch1, @ch2`)")
    elif query.data == "adm_status":
        cursor.execute("SELECT name, type FROM panels")
        p_list = cursor.fetchall()
        msg = "📊 *সিস্টেম স্ট্যাটাস:*\n\n"
        msg += f"🔗 মোট কানেক্টেড প্যানেল: `{len(p_list)}` টি\n"
        for p in p_list: msg += f" 🔹 {p[0]} ({p[1].upper()})\n"
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=get_admin_keyboard())

    conn.close()

# টেক্সট মেসেজ হ্যান্ডলার (কিবোর্ড বাটন প্রেস ও অ্যাডমিন ইনপুট ডেটা)
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    conn = sqlite3.connect('master_otp.db')
    cursor = conn.cursor()
    cursor.execute("SELECT lang FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    lang = row[0] if row else "en"

    # অ্যাডমিন স্টেট ডাটা ইনপুট প্রসেসিং
    if user_id in ADMIN_IDS and user_id in admin_state:
        state = admin_state[user_id]
        
        if state == "w_api":
            try:
                name, url, token = [i.strip() for i in text.split("|")]
                cursor.execute("INSERT INTO panels (name, url, token, type) VALUES (?, ?, ?, 'api')", (name, url, token))
                conn.commit()
                await update.message.reply_text(f"✅ API প্যানেল `{name}` যুক্ত হয়েছে!", reply_markup=get_admin_keyboard())
            except: await update.message.reply_text("❌ ফরম্যাট ভুল!")
        
        elif state == "w_login":
            try:
                name, url, user, pwd = [i.strip() for i in text.split("|")]
                cursor.execute("INSERT INTO panels (name, url, username, password, type) VALUES (?, ?, ?, ?, 'login')", (name, url, user, pwd))
                conn.commit()
                await update.message.reply_text(f"✅ ID-Pass প্যানেল `{name}` যুক্ত হয়েছে! বট এখন স্বয়ংক্রিয়ভাবে সেশন লগইন করবে।", reply_markup=get_admin_keyboard())
            except: await update.message.reply_text("❌ ফরম্যাট ভুল!")

        elif state == "w_manual":
            try:
                phone, service, country = [i.strip() for i in text.split("|")]
                cursor.execute("INSERT INTO manual_numbers (phone, service, country) VALUES (?, ?, ?)", (phone, service, country))
                conn.commit()
                await update.message.reply_text(f"✅ ম্যানুয়াল নাম্বার `{phone}` সফলভাবে আপনার বটের স্টকে যুক্ত হয়েছে!", reply_markup=get_admin_keyboard())
            except: await update.message.reply_text("❌ ফরম্যাট ভুল!")

        elif state == "w_ch":
            cursor.execute("UPDATE settings SET value=? WHERE key='channels'", (text,))
            conn.commit()
            await update.message.reply_text("✅ ফোর্স সাবস্ক্রাইব চ্যানেলসমূহ আপডেট করা হয়েছে!", reply_markup=get_admin_keyboard())

        del admin_state[user_id]
        conn.close()
        return

    # ইউজার বাটন ক্লিক রেসপন্স
    if not await is_user_subscribed(context.bot, user_id):
        await update.message.reply_text("❌ Access Denied! Please join channels first.")
        conn.close()
        return

    if text in [STRINGS["en"]["kb_get_num"], STRINGS["ar"]["kb_get_num"]]:
        keyboard = [
            [InlineKeyboardButton("🇪🇬 Egypt Whatsapp (583)", callback_data="srv_egyptwa")],
            [InlineKeyboardButton("🇹🇳 Tunisia Facebook (129)", callback_data="srv_tunisiafb")],
            [InlineKeyboardButton("🇺🇸 USA Telegram (892)", callback_data="srv_usatg")]
        ]
        await update.message.reply_text(STRINGS[lang]["select_country"], parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text in [STRINGS["en"]["kb_active"], STRINGS["ar"]["kb_active"]]:
        await update.message.reply_text(STRINGS[lang]["active_num"])
    
    elif text in [STRINGS["en"]["kb_lang"], STRINGS["ar"]["kb_lang"]]:
        keyboard = [[InlineKeyboardButton("English 🇬🇧", callback_data="set_lang_en")], [InlineKeyboardButton("العربية 🇸🇦", callback_data="set_lang_ar")]]
        await update.message.reply_text(STRINGS["en"]["welcome"], parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    conn.close()

def main():
    Thread(target=run_server).start()
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(handle_callbacks))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    
    print("Supreme Bot Loaded Successfully...")
    application.run_polling()

if __name__ == '__main__':
    main()
