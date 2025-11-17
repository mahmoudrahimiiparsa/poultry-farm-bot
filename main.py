import telebot
from telebot import types
import threading
import re
import json
import os
from datetime import datetime

# ------------------ پیکربندی اولیه ------------------
BOT_TOKEN = os.getenv("8340248752:AAFNFLCEtNRedXiZqt89HPv06e_klrkFqgY")  # توکن را از محیط بخوان
if not BOT_TOKEN:
    raise ValueError("8340248752:AAFNFLCEtNRedXiZqt89HPv06e_klrkFqgY")

bot = telebot.TeleBot("8340248752:AAFNFLCEtNRedXiZqt89HPv06e_klrkFqgY")

# تنظیمات سالن‌ها و کاربران مجاز
HALLS = {
    "farm1": {"number": "+989011349879", "manager": 6356648014},
    "farm2": {"number": "+989053373970", "manager": 6356648014}
}

AUTHORIZED_USERS = [6356648014]
ADMIN_CHAT_ID = 6356648014

# وضعیت‌های داخلی
periodic_timer = None
user_context = {}

# ------------------ تنظیمات پایدار ------------------
SETTINGS_FILE = "settings.json"
AUTO_CHECK_ENABLED = False
CHECK_INTERVAL = 3600
CHECK_START_HOUR = 0
CHECK_END_HOUR = 23

def load_settings():
    global AUTO_CHECK_ENABLED, CHECK_INTERVAL, CHECK_START_HOUR, CHECK_END_HOUR
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            AUTO_CHECK_ENABLED = data.get("AUTO_CHECK_ENABLED", False)
            CHECK_INTERVAL = data.get("CHECK_INTERVAL", 3600)
            CHECK_START_HOUR = data.get("CHECK_START_HOUR", 0)
            CHECK_END_HOUR = data.get("CHECK_END_HOUR", 23)
    except:
        pass

def save_settings():
    data = {
        "AUTO_CHECK_ENABLED": AUTO_CHECK_ENABLED,
        "CHECK_INTERVAL": CHECK_INTERVAL,
        "CHECK_START_HOUR": CHECK_START_HOUR,
        "CHECK_END_HOUR": CHECK_END_HOUR
    }
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

load_settings()

# ------------------ توابع کمکی ------------------
def log_event(text):
    with open("log.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} - {text}\n")

def authorized(message):
    if message.chat.id not in AUTHORIZED_USERS:
        bot.reply_to(message, "❌ شما مجاز به استفاده از این ربات نیستید.")
        return False
    return True

def is_in_hour_window(now_hour, start_hour, end_hour):
    if start_hour <= end_hour:
        return start_hour <= now_hour <= end_hour
    return now_hour >= start_hour or now_hour <= end_hour

def schedule_periodic():
    global periodic_timer
    if periodic_timer:
        periodic_timer.cancel()
    periodic_timer = threading.Timer(CHECK_INTERVAL, periodic_check)
    periodic_timer.daemon = True
    periodic_timer.start()

def periodic_check():
    if AUTO_CHECK_ENABLED:
        current_hour = datetime.now().hour
        if is_in_hour_window(current_hour, CHECK_START_HOUR, CHECK_END_HOUR):
            for hall_name, hall_info in HALLS.items():
                manager_id = hall_info["manager"]
                number = hall_info["number"]
                bot.send_message(manager_id, f"/sendsms2 {number}\n?IOS")
                bot.send_message(manager_id, f"/sendsms2 {number}\n!!!")
    schedule_periodic()

def current_hall(chat_id):
    hall = user_context.get(chat_id, {}).get("hall")
    if hall and hall in HALLS:
        return hall
    return list(HALLS.keys())[0]

def set_hall(chat_id, hall_name):
    ctx = user_context.get(chat_id, {})
    ctx["hall"] = hall_name
    user_context[chat_id] = ctx

def send_sms_via_bot(chat_id, hall_name, payload_text):
    number = HALLS.get(hall_name, {}).get("number")
    if number:
        bot.send_message(chat_id, f"/sendsms {number}\n{payload_text}")

# ------------------ خلاصه و اخطار ------------------
def summarize_report(text):
    temp = re.search(r'دما:(\d+(\.\d+)?)\s+تنظيم:(\d+(\.\d+)?)', text)
    hum  = re.search(r'رطوبت:(\d+(\.\d+)?)\s+تنظيم:(\d+(\.\d+)?)%', text)
    vent = re.search(r'فن:(\d+(\.\d+)?)%', text)

    lines = ["📊 خلاصه گزارش:"]
    if temp: lines.append(f"🌡 دما فعلی: {temp.group(1)} / تنظیم: {temp.group(3)}")
    if hum:  lines.append(f"💧 رطوبت فعلی: {hum.group(1)}% / تنظیم: {hum.group(3)}%")
    if vent: lines.append(f"💨 تهویه: {vent.group(1)}%")

    eq = []
    for line in text.splitlines():
        if any(k in line for k in ["فن", "هیتر", "اینلت"]):
            eq.append(line.strip())
    if eq:
        lines.append("⚙ تجهیزات روشن: " + ", ".join(eq))
    return "\n".join(lines)

def check_equipment_consistency(text):
    alerts = []
    vent_pct = re.search(r'فن:(\d+(\.\d+)?)%', text)
    temp = re.search(r'دما:(\d+(\.\d+)?)\s+تنظيم:(\d+(\.\d+)?)', text)
    fan_on = any("فن" in l for l in text.splitlines())
    heater_on = any("هیتر" in l for l in text.splitlines())

    if vent_pct and float(vent_pct.group(1)) > 0 and not fan_on:
        alerts.append("❌ اخطار: تهویه تنظیم شده اما هیچ فن روشن نیست.")
    if temp and float(temp.group(1)) < float(temp.group(3)) and not heater_on:
        alerts.append("❌ اخطار: دما زیر مقدار تنظیم است اما هیتر روشن نیست.")
    return alerts

# ------------------ منوی اصلی ------------------
def main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🏠 انتخاب سالن"),
        types.KeyboardButton("📊 گزارش‌گیری"),
        types.KeyboardButton("⚙ تنظیمات"),
        types.KeyboardButton("🔧 مدیریت"),
        types.KeyboardButton("ℹ راهنما")
    )
    sel_hall = current_hall(chat_id)
    bot.send_message(chat_id, f"لطفاً یکی از گزینه‌های زیر را انتخاب کن 👇\nسالن جاری: {sel_hall}", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):
    if not authorized(message): return
    if message.chat.id not in user_context:
        user_context[message.chat.id] = {"hall": list(HALLS.keys())[0]}
    main_menu(message.chat.id)

# سایر هندلرها مشابه قبل

@bot.message_handler(func=lambda m: m.text == "🏠 انتخاب سالن")
def hall_select_menu(message):
    if not authorized(message): return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for hall in HALLS.keys():
        markup.add(f"سالن: {hall}")
    markup.add("🔙 بازگشت")
    bot.send_message(message.chat.id, "یکی از سالن‌ها را انتخاب کن:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text and m.text.startswith("سالن: "))
def hall_selected(message):
    if not authorized(message): return
    hall_name = message.text.replace("سالن: ", "").strip()
    if hall_name in HALLS:
        set_hall(message.chat.id, hall_name)
        bot.reply_to(message, f"✅ سالن جاری تنظیم شد: {hall_name}")
        main_menu(message.chat.id)
    else:
        bot.reply_to(message, "❌ سالن نامعتبر است.")

@bot.message_handler(func=lambda m: m.text == "📊 گزارش‌گیری")
def report_menu(message):
    if not authorized(message): return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    markup.add("!", "!!", "!!!", "?IOS", "?Sensors", "?Tahvieh", "?Joojeh", "?Dan", "🔙 بازگشت")
    bot.send_message(message.chat.id, "📊 دستورات گزارش‌گیری:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in ["!", "!!", "!!!", "?IOS", "?Sensors", "?Tahvieh", "?Joojeh", "?Dan"])
def report_cmds(message):
    if not authorized(message): return
    hall = current_hall(message.chat.id)
    send_sms_via_bot(message.chat.id, hall, message.text)
    bot.reply_to(message, f"📨 گزارش ارسال شد: {message.text}")

@bot.message_handler(func=lambda m: m.text == "⚙ تنظیمات")
def settings_menu(message):
    if not authorized(message): return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🌡 تنظیم دما", "💧 تنظیم رطوبت", "💨 تهویه Min", "🚀 سرعت Max",
               "Tahvieh Daemi", "Tahvieh Timer", "Tahvieh Auto", "🔙 بازگشت")
    bot.send_message(message.chat.id, "⚙ دستورات تنظیم:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🌡 تنظیم دما")
def ask_dama(message):
    if not authorized(message): return
    user_context.setdefault(message.chat.id, {})["await"] = "dama"
    bot.send_message(message.chat.id, "عدد دما (بین 16 تا 38) را وارد کن. مثال: 26.5")

@bot.message_handler(func=lambda m: m.text == "💧 تنظیم رطوبت")
def ask_rot(message):
    if not authorized(message): return
    user_context.setdefault(message.chat.id, {})["await"] = "rot"
    bot.send_message(message.chat.id, "درصد رطوبت (بین 20 تا 80) را وارد کن. مثال: 56.4")

@bot.message_handler(func=lambda m: m.text == "💨 تهویه Min")
def ask_min(message):
    if not authorized(message): return
    user_context.setdefault(message.chat.id, {})["await"] = "min"
    bot.send_message(message.chat.id, "مقدار تهویه حداقلی (فن) را وارد کن. مثال: 1.2")

@bot.message_handler(func=lambda m: m.text == "🚀 سرعت Max")
def ask_max(message):
    if not authorized(message): return
    user_context.setdefault(message.chat.id, {})["await"] = "max"
    bot.send_message(message.chat.id, "حداکثر سرعت مجاز (m/s) را وارد کن. مثال: 1.4")

@bot.message_handler(func=lambda m: m.text == "Tahvieh Daemi")
def tahvieh_daemi(message):
    if not authorized(message): return
    hall = current_hall(message.chat.id)
    send_sms_via_bot(message.chat.id, hall, "Tahvieh Daemi")
    bot.reply_to(message, "✅ تهویه حداقلی روی حالت دائمی تنظیم شد.")

@bot.message_handler(func=lambda m: m.text == "Tahvieh Timer")
def tahvieh_timer(message):
    if not authorized(message): return
    user_context.setdefault(message.chat.id, {})["await"] = "timer"
    bot.send_message(message.chat.id, "⏳ مدت تایمر (دقیقه) را وارد کن. حداقل 2 و حداکثر 100. مثال: 5")

@bot.message_handler(func=lambda m: m.text == "Tahvieh Auto")
def tahvieh_auto(message):
    if not authorized(message): return
    hall = current_hall(message.chat.id)
    send_sms_via_bot(message.chat.id, hall, "Tahvieh Auto")
    bot.reply_to(message, "✅ تهویه حداقلی روی حالت اتوماتیک تنظیم شد.")

@bot.message_handler(func=lambda m: m.text == "🔧 مدیریت")
def manage_menu(message):
    if not authorized(message): return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("✅ فعال‌سازی چک", "❌ غیرفعال‌سازی چک", "⏳ تنظیم فاصله چک", "🕒 تنظیم ساعت چک", "🔙 بازگشت")
    bot.send_message(message.chat.id, "🔧 مدیریت ربات:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "✅ فعال‌سازی چک")
def enable_check_button(message):
    if not authorized(message): return
    global AUTO_CHECK_ENABLED
    AUTO_CHECK_ENABLED = True
    save_settings()
    bot.reply_to(message, "✅ چک خودکار تجهیزات فعال شد.")
    log_event("چک دوره‌ای فعال شد")
    schedule_periodic()

@bot.message_handler(func=lambda m: m.text == "❌ غیرفعال‌سازی چک")
def disable_check_button(message):
    if not authorized(message): return
    global AUTO_CHECK_ENABLED
    AUTO_CHECK_ENABLED = False
    save_settings()
    bot.reply_to(message, "❌ چک خودکار تجهیزات غیرفعال شد.")
    log_event("چک دوره‌ای غیرفعال شد")
    if periodic_timer:
        periodic_timer.cancel()

@bot.message_handler(func=lambda m: m.text == "⏳ تنظیم فاصله چک")
def ask_interval(message):
    if not authorized(message): return
    user_context.setdefault(message.chat.id, {})["await"] = "interval"
    bot.send_message(message.chat.id, "⏳ لطفاً فاصله چک (به دقیقه) را وارد کن. مثال: 30")

@bot.message_handler(func=lambda m: m.text == "🕒 تنظیم ساعت چک")
def ask_hours(message):
    if not authorized(message): return
    user_context.setdefault(message.chat.id, {})["await"] = "hours"
    bot.send_message(message.chat.id, "🕒 لطفاً بازه ساعت را وارد کن. مثال: 22 6")

@bot.message_handler(func=lambda m: m.text == "ℹ راهنما")
def help_menu(message):
    if not authorized(message): return
    help_text = (
        "📋 لیست دستورها\n\n"
        "🔧 مدیریتی:\n"
        "از منوی مدیریت استفاده کنید.\n\n"
        "📊 گزارش‌ها:\n"
        "از منوی گزارش‌گیری استفاده کنید.\n\n"
        "⚙ تنظیمات:\n"
        "از منوی تنظیمات استفاده کنید.\n\n"
        "🏠 انتخاب سالن:\n"
        "از منوی انتخاب سالن استفاده کنید."
    )
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(func=lambda m: m.text == "🔙 بازگشت")
def go_back(message):
    main_menu(message.chat.id)

# ------------------ پردازش ورودی‌های عددی ------------------
@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    if not authorized(message): return
    text = (message.text or "").strip()

    # اگر گزارش کامل باشد، خلاصه و اخطارها را ارسال کن
    if "دما:" in text and "رطوبت:" in text:
        bot.send_message(ADMIN_CHAT_ID, summarize_report(text))
        for alert in check_equipment_consistency(text):
            bot.send_message(ADMIN_CHAT_ID, alert)
            log_event(alert)
        return

    ctx = user_context.get(message.chat.id, {})
    awaiting = ctx.get("await")

    if awaiting == "dama":
        try:
            val = float(text)
            if not (16 <= val <= 38):
                bot.reply_to(message, "❌ مقدار دما باید بین 16 تا 38 باشد.")
            else:
                hall = current_hall(message.chat.id)
                send_sms_via_bot(message.chat.id, hall, f"{val} Dama")
                bot.reply_to(message, f"✅ دما تنظیم شد: {val}")
            ctx["await"] = None
        except:
            bot.reply_to(message, "❌ عدد معتبر وارد کنید. مثال: 26.5")

    elif awaiting == "rot":
        try:
            val = float(text)
            if not (20 <= val <= 80):
                bot.reply_to(message, "❌ مقدار رطوبت باید بین 20 تا 80 باشد.")
            else:
                hall = current_hall(message.chat.id)
                send_sms_via_bot(message.chat.id, hall, f"{val} Rot")
                bot.reply_to(message, f"✅ رطوبت تنظیم شد: {val}%")
            ctx["await"] = None
        except:
            bot.reply_to(message, "❌ عدد معتبر وارد کنید. مثال: 56.4")

    elif awaiting == "min":
        try:
            val = float(text)
            if val <= 0:
                bot.reply_to(message, "❌ مقدار باید مثبت باشد.")
            else:
                hall = current_hall(message.chat.id)
                send_sms_via_bot(message.chat.id, hall, f"{val} Min")
                bot.reply_to(message, f"✅ تهویه حداقلی تنظیم شد: {val} فن")
            ctx["await"] = None
        except:
            bot.reply_to(message, "❌ عدد معتبر وارد کنید. مثال: 1.2")

    elif awaiting == "max":
        try:
            val = float(text)
            if val <= 0:
                bot.reply_to(message, "❌ مقدار باید مثبت باشد.")
            else:
                hall = current_hall(message.chat.id)
                send_sms_via_bot(message.chat.id, hall, f"{val} Max")
                bot.reply_to(message, f"✅ حداکثر سرعت مجاز تنظیم شد: {val} m/s")
            ctx["await"] = None
        except:
            bot.reply_to(message, "❌ عدد معتبر وارد کنید. مثال: 1.4")

    elif awaiting == "timer":
        try:
            minutes = int(text)
            if not (2 <= minutes <= 100):
                bot.reply_to(message, "❌ مدت تایمر باید بین 2 تا 100 دقیقه باشد.")
            else:
                hall = current_hall(message.chat.id)
                send_sms_via_bot(message.chat.id, hall, f"{minutes} Tahvieh Timer")
                bot.reply_to(message, f"✅ تهویه تایمر تنظیم شد: {minutes} دقیقه")
            ctx["await"] = None
        except:
            bot.reply_to(message, "❌ عدد معتبر وارد کنید. مثال: 5")

    elif awaiting == "interval":
        try:
            minutes = int(text)
            global CHECK_INTERVAL
            CHECK_INTERVAL = minutes * 60
            save_settings()
            bot.reply_to(message, f"✅ چک هر {minutes} دقیقه انجام می‌شود.")
            log_event(f"بازه چک دوره‌ای تغییر کرد به {minutes} دقیقه")
            schedule_periodic()
            ctx["await"] = None
            manage_menu(message)
        except:
            bot.reply_to(message, "❌ عدد دقیقه معتبر وارد کن. مثال: 30")

    elif awaiting == "hours":
        try:
            parts = text.split()
            start_h, end_h = int(parts[0]), int(parts[1])
            global CHECK_START_HOUR, CHECK_END_HOUR
            CHECK_START_HOUR, CHECK_END_HOUR = start_h, end_h
            save_settings()
            bot.reply_to(message, f"✅ چک فقط بین {start_h} تا {end_h} انجام می‌شود.")
            log_event(f"بازه ساعت چک دوره‌ای شد: {start_h}-{end_h}")
            ctx["await"] = None
            manage_menu(message)
        except:
            bot.reply_to(message, "❌ فرمت درست: 22 6")

# ------------------ اجرای ربات ------------------
if __name__ == "__main__":
    print("ربات شروع به کار کرد...")
    if AUTO_CHECK_ENABLED:
        schedule_periodic()
    bot.infinity_polling(timeout=10, long_polling_timeout=5)