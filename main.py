import os
import sqlite3
import logging
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ==================== ১. ক্লাউডে ২৪/৭ রাখার ওয়েব সার্ভার ====================
app = Flask('')

@app.route('/')
def home():
    return "Ultra OTP Bot with Fixed IDs & Advanced Demo Panel is Running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==================== ২. বটের মূল কনফিগারেশন ====================
BOT_TOKEN = "8955870337:AAE9yODdtPTVWeMlleiO_u2MjoBmWQjbmOk"  # আপনার বটের টোকেন
ADMIN_IDS = [8051276654]  # আপনার টেলিগ্রাম আইডি

# ==================== ৩. ডাটাবেজ সেটআপ ====================
conn = sqlite3.connect('master_otp.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS user_stats 
                  (user_id INTEGER PRIMARY KEY, total_numbers INTEGER DEFAULT 0, total_otps INTEGER DEFAULT 0)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, lang TEXT DEFAULT 'en')''')
cursor.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
conn.commit()

# ⚙️ আপনার দেওয়া ৩টি চ্যানেল/গ্রুপের আইডি ও লিংক এখানে নিখুঁতভাবে সেট করা হয়েছে
cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ch1_id', '-1003436812983')") # মেইন চ্যানেল আইডি
cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ch1_link', 'https://t.me/facboo578')")

cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ch2_id', '-1002797517003')") # ব্যাকআপ চ্যানেল আইডি
cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ch2_link', 'https://t.me/gsjggj98')")

cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ch3_id', '-1002414484554')") # ওটিপি গ্রুপ আইডিকে ৩ নম্বর লক হিসেবে রাখা হলো
cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ch3_link', 'https://t.me/gjifch743')")

# 📢 ওটিপি প্রুফ শেয়ার করার জন্য আপনার ওটিপি গ্রুপের আইডি সেট করা হলো
cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('otp_share_group', '-1002414484554')") 
conn.commit()

# Temporary storage for Admin Demo Session
admin_demo_data = {}

# ==================== ৪. নাম্বারের কান্ট্রি কোড ও লাস্ট ৪ ডিজিট মাস্কিং ফাংশন ====================
def mask_number(phone_number, country_code_str="🌍"):
    clean_num = phone_number.replace("+", "").replace(" ", "").strip()
    last_four = clean_num[-4:] if len(clean_num) >= 4 else clean_num
    return f"{country_code_str} XXXX {last_four}"

def get_service_header(service_name):
    srv = service_name.lower().strip()
    if "facebook" in srv or "fb" == srv: return "🔵 **FACEBOOK OTP RECEIVED** 🔵"
    elif "instagram" in srv or "ig" == srv: return "📸 **INSTAGRAM OTP RECEIVED** 📸"
    elif "telegram" in srv or "tg" == srv: return "✈️ **TELEGRAM OTP RECEIVED** ✈️"
    elif "whatsapp" in srv or "wa" == srv: return "🟢 **WHATSAPP OTP RECEIVED** 🟢"
    else: return f"📩 **{service_name.upper()} OTP RECEIVED** 📩"

# ==================== ৫. ৩টি চ্যানেল লক চেকিং ফাংশন (আইডি বেসড) ====================
async def is_subscribed_all(user_id, context):
    if user_id in ADMIN_IDS: return True
    cursor.execute("SELECT value FROM settings WHERE key IN ('ch1_id', 'ch2_id', 'ch3_id')")
    results = cursor.fetchall()
    for res in results:
        ch = res[0].strip()
        if ch:
            try:
                # এখানে ইন্টিজারে রূপান্তর করে প্রাইভেট চ্যাট আইডি চেক করা হচ্ছে
                member = await context.bot.get_chat_member(chat_id=int(ch), user_id=user_id)
                if member.status in ['left', 'kicked']: return False
            except Exception: return False
    return True

# ==================== ৬. বটের কমান্ড হ্যান্ডলারসমূহ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    cursor.execute("INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)", (user_id,))
    conn.commit()

    if not await is_subscribed_all(user_id, context):
        cursor.execute("SELECT key, value FROM settings WHERE key IN ('ch1_link', 'ch2_link', 'ch3_link')")
        links = dict(cursor.fetchall())
        keyboard = [
            [InlineKeyboardButton("📢 1. Join Main Channel", url=links.get('ch1_link', '#'))],
            [InlineKeyboardButton("🔄 2. Join Backup Channel", url=links.get('ch2_link', '#'))],
            [InlineKeyboardButton("📱 3. Join OTP Group", url=links.get('ch3_link', '#'))],
            [InlineKeyboardButton("✅ Check All Membership", callback_data="check_sub")]
        ]
        await update.message.reply_text("⚠️ **Access Denied!**\n\nবটটি ব্যবহার করতে আপনাকে অবশ্যই আমাদের নিচের ২টি চ্যানেল ও ওটিপি গ্রুপে জয়েন করতে হবে।", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    keyboard = [[InlineKeyboardButton("🇧🇩 বাংলা", callback_data="lang_bn"), InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]]
    await update.message.reply_text("👋 Choose Your Language / ভাষা সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS: return

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    keyboard = [
        [InlineKeyboardButton("📊 User Statistics", callback_data="view_user_stats")],
        [InlineKeyboardButton("🧪 Advanced Demo OTP Panel", callback_data="setup_demo_otp")]
    ]
    msg_target = update.message if update.message else update.callback_query.message
    await msg_target.reply_text(f"🛠️ **Welcome Admin!**\n\n📊 Total Active Users: {total_users}\n⚡ Control everything from below:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ==================== 🧪 ৭. অ্যাডভান্সড ডেমো ওটিপি সেটআপ ও বাটন হ্যান্ডলিং ====================
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == "check_sub":
        if await is_subscribed_all(user_id, context):
            await query.message.delete()
            keyboard = [[InlineKeyboardButton("🇧🇩 বাংলা", callback_data="lang_bn"), InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]]
            await context.bot.send_message(chat_id=query.message.chat_id, text="👋 Choose Your Language:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.message.reply_text("❌ আপনি এখনো সবগুলো চ্যানেল ও গ্রুপে জয়েন করেননি!")
            
    elif query.data in ["lang_bn", "lang_en"]:
        lang = "bn" if query.data == "lang_bn" else "en"
        cursor.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, user_id))
        conn.commit()
        msg = "🎉 স্বাগতম!" if lang == "bn" else "🎉 Welcome!"
        main_menu = [["📞 GET NUMBER", "💰 BALANCE"], ["👥 REFER & EARN", "📊 STATUS"]]
        await context.bot.send_message(chat_id=query.message.chat_id, text=msg, reply_markup=ReplyKeyboardMarkup(main_menu, resize_keyboard=True))

    elif query.data == "view_user_stats":
        if user_id not in ADMIN_IDS: return
        cursor.execute("SELECT user_id, total_numbers, total_otps FROM user_stats LIMIT 15")
        rows = cursor.fetchall()
        response_text = "📊 **User Statistics:**\n\n"
        for row in rows:
            response_text += f"👤 **User ID:** `{row[0]}`\n├ Ordered: {row[1]} | └ Success OTPs: {row[2]}\n\n"
        back_btn = [[InlineKeyboardButton("⬅️ Back to Panel", callback_data="back_to_admin")]]
        await query.message.edit_text(response_text, reply_markup=InlineKeyboardMarkup(back_btn), parse_mode="Markdown")

    elif query.data == "back_to_admin":
        if user_id not in ADMIN_IDS: return
        await query.message.delete()
        await admin_panel(update, context)

    elif query.data == "setup_demo_otp":
        if user_id not in ADMIN_IDS: return
        if user_id not in admin_demo_data:
            admin_demo_data[user_id] = {"phone": "", "service": "", "otp": "", "country": "🌍 Country", "delay": 0}
        await show_demo_settings_panel(query, user_id)

    elif query.data.startswith("set_demo_"):
        field = query.data.replace("set_demo_", "")
        if field == "country":
            keyboard = [
                [InlineKeyboardButton("🇧🇩 Bangladesh", callback_data="select_country_🇧🇩 +880"), InlineKeyboardButton("🇮🇳 India", callback_data="select_country_🇮🇳 +91")],
                [InlineKeyboardButton("🇺🇸 USA", callback_data="select_country_🇺🇸 +1"), InlineKeyboardButton("🇷🇺 Russia", callback_data="select_country_🇷🇺 +7")]
            ]
            await query.message.edit_text("🌍 সিলেক্ট করুন কোন দেশের নাম্বার:", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            admin_demo_data[user_id]["current_editing"] = field
            await query.message.reply_text(f"✏️ এখন চ্যাটে আপনার কাঙ্ক্ষিত **{field.upper()}** টাইপ করে পাঠান:")

    elif query.data.startswith("select_country_"):
        c_str = query.data.replace("select_country_", "")
        admin_demo_data[user_id]["country"] = c_str
        await show_demo_settings_panel(query, user_id)

    elif query.data == "run_demo_otp":
        data = admin_demo_data.get(user_id)
        if not data or not data["phone"] or not data["otp"]:
            await query.message.reply_text("❌ সব তথ্য পূরণ করা হয়নি! দয়া করে সম্পূর্ণ করুন।")
            return
        
        await query.message.reply_text(f"🚀 ডেমো ওটিপি প্রসেসিং শুরু হয়েছে। {data['delay']} সেকেন্ড পর ওটিপি গ্রুপে রিসিভ হবে...")
        asyncio.create_task(process_and_send_otp_to_group(context, data, user_id))

async def show_demo_settings_panel(query, user_id):
    data = admin_demo_data[user_id]
    text = (f"🧪 **Advanced Demo OTP Panel (Group Only)**\n\n"
            f"📱 Phone Number: `{data['phone']}`\n"
            f"🌍 Country Flag: `{data['country']}`\n"
            f"⚙️ Service Name: `{data['service']}`\n"
            f"🔑 OTP Code: `{data['otp']}`\n"
            f"⏳ Delay/Timer: `{data['delay']} Seconds`\n\n"
            f"👇 নিচের বাটনগুলোতে ক্লিক করে তথ্য পূরণ করুন:")
    
    keyboard = [
        [InlineKeyboardButton("📱 Set Phone", callback_data="set_demo_phone"), InlineKeyboardButton("🌍 Set Country Flag", callback_data="set_demo_country")],
        [InlineKeyboardButton("⚙️ Set Service", callback_data="set_demo_service"), InlineKeyboardButton("🔑 Set OTP Code", callback_data="set_demo_otp")],
        [InlineKeyboardButton("⏳ Set Delay (Sec)", callback_data="set_demo_delay")],
        [InlineKeyboardButton("🚀 RUN DEMO (গ্রুপে পাঠান)", callback_data="run_demo_otp")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_admin_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS or user_id not in admin_demo_data: return
    
    field = admin_demo_data[user_id].get("current_editing")
    if not field: return
    
    text_input = update.message.text
    if field == "delay":
        try: admin_demo_data[user_id][field] = int(text_input)
        except: await update.message.reply_text("❌ শুধুমাত্র সংখ্যা ইনপুট দিন!")
    else:
        admin_demo_data[user_id][field] = text_input
        
    admin_demo_data[user_id]["current_editing"] = None
    
    keyboard = [[InlineKeyboardButton("🔄 Refresh Panel", callback_data="setup_demo_otp")]]
    await update.message.reply_text("✅ ডাটা সেভ হয়েছে। প্যানেল রিফ্রেশ করুন:", reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== ⏳ ৮ম ধাপ: শুধুমাত্র ওটিপি গ্রুপে মেসেজ পাঠানো ====================
async def process_and_send_otp_to_group(context, data, admin_id):
    if data["delay"] > 0:
        await asyncio.sleep(data["delay"])
        
    header = get_service_header(data["service"])
    masked_phone = mask_number(data["phone"], data["country"])
    
    group_message = (f"📢 **LIVE OTP PROOF** 📢\n\n"
                     f"{header}\n\n"
                     f"📱 **Number:** `{masked_phone}`\n"
                     f"🔑 **OTP Code:** `{data['otp']}`\n\n"
                     f"⏳ *বটের ভেতর ওটিপিটি সফলভাবে রিসিভ হয়েছে!*")
    
    cursor.execute("SELECT value FROM settings WHERE key='otp_share_group'")
    group_res = cursor.fetchone()
    if group_res and group_res[0]:
        try:
            # চ্যাট আইডি সরাসরি ইন্টিজারে কনভার্ট করে গ্রুপে পাঠানো হচ্ছে
            await context.bot.send_message(chat_id=int(group_res[0]), text=group_message, parse_mode="Markdown")
            await context.bot.send_message(chat_id=admin_id, text="✅ সফল হয়েছে! ডেমো ওটিপিটি ওটিপি গ্রুপে পোস্ট করা হয়েছে।")
        except Exception as e:
            await context.bot.send_message(chat_id=admin_id, text=f"❌ গ্রুপে পাঠানো যায়নি। বটকে গ্রুপে অ্যাডমিন করেছেন তো? এরর: {e}")

# ==================== ৯. মেইন অ্যাপ্লিকেশন রান ====================
def main():
    keep_alive()
    app_bot = Application.builder().token(BOT_TOKEN).build()
    
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("admin", admin_panel))
    app_bot.add_handler(CallbackQueryHandler(button_click))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_inputs))
    
    print("🤖 All Fixed! Group-Only Demo Mode OTP Bot is Live!")
    app_bot.run_polling()

if __name__ == '__main__':
    main()
