import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

SUB_URL = "https://raw.githubusercontent.com/alireza786786/Tahababa/main/subs/plain.txt"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def fetch_configs():
    try:
        res = requests.get(SUB_URL, timeout=10)
        if res.status_code == 200:
            lines = [l.strip() for l in res.text.splitlines() if l.strip()]
            return lines
    except Exception as e:
        print(f"Error fetching configs: {e}")
    return []

def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("⚡ دریافت ۵ کانفیگ برتر (پینگ زیر ۵۰۰ms)", callback_data="top5")],
        [
            InlineKeyboardButton("🌐 VLESS", callback_data="proto_vless"),
            InlineKeyboardButton("🚀 VMess", callback_data="proto_vmess"),
        ],
        [
            InlineKeyboardButton("🛡️ Trojan", callback_data="proto_trojan"),
            InlineKeyboardButton("⚡ Hysteria2", callback_data="proto_hy2"),
        ],
        [
            InlineKeyboardButton("📱 راهنمای برنامه‌ها", callback_data="apps_guide"),
            InlineKeyboardButton("📡 لینک سابسکریپشن", callback_data="sub_links"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_markup = get_main_keyboard()
    text = (
        "🤖 **به ربات هوشمند V2Ray خوش آمدید!**\n\n"
        "این ربات به صورت خودکار به مخزن کانفیگ‌های پاک‌سازی‌شده و تست‌شده متصل است.\n\n"
        "لطفا گزینه مورد نظر خود را از منوی زیر انتخاب کنید:"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def send_proto_configs(update: Update, proto: str):
    configs = fetch_configs()
    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]])
    
    if not configs:
        msg = "❌ خطایی در دریافت کانفیگ‌ها رخ داد. لطفاً دوباره تلاش کنید."
    else:
        filtered = [c for c in configs if c.startswith(f"{proto}://") or (proto == "hy2" and "hysteria2://" in c)]
        selected = filtered[:5] if filtered else []
        if selected:
            msg = f"📌 **۵ کانفیگ برتر پروتکل {proto.upper()}:**\n\n" + "\n\n".join(f"`{c}`" for c in selected)
        else:
            msg = f"⚠️ در حال حاضر کانفیگی برای پروتکل {proto.upper()} یافت نشد."
            
    if update.message:
        await update.message.reply_text(msg, reply_markup=back_button, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.edit_text(msg, reply_markup=back_button, parse_mode="Markdown")

async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    configs = fetch_configs()
    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]])
    if configs:
        msg = "⚡ **۵ کانفیگ برتر با پینگ زیر ۵۰۰ms:**\n\n" + "\n\n".join(f"`{c}`" for c in configs[:5])
    else:
        msg = "❌ خطایی در دریافت کانفیگ‌ها رخ داد."
    await update.message.reply_text(msg, reply_markup=back_button, parse_mode="Markdown")

async def cmd_vless(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_proto_configs(update, "vless")

async def cmd_vmess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_proto_configs(update, "vmess")

async def cmd_hy2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_proto_configs(update, "hy2")

async def cmd_trojan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_proto_configs(update, "trojan")

async def cmd_apps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📱 **نرم‌افزارهای پیشنهادی برای اتصال:**\n\n"
        "💻 **ویندوز / لینوکس:** Nekoray | V2rayN\n"
        "🤖 **اندروید:** v2rayNG | NekoBox | Hiddify | V2BOX\n"
        "🍎 **آیفون (iOS) / مک:** Streisand | ShadowRocket | V2BOX\n\n"
        "📋 **روش استفاده:** کافیست کانفیگ یا لینک سابسکریپشن را کپی کرده و در برنامه `Import` کنید."
    )
    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]])
    await update.message.reply_text(msg, reply_markup=back_button, parse_mode="Markdown")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "❓ **راهنمای استفاده از ربات:**\n\n"
        "۱. برای دریافت کانفیگ سریع از دستورات منو یا دکمه‌ها استفاده کنید.\n"
        "۲. کانفیگ‌های کپی شده را مستقیم در نرم‌افزار خود پیست (Import from Clipboard) کنید.\n"
        "۳. در صورت بروز مشکل، کانفیگ‌های جدیدتر را جایگزین کنید.\n\n"
        "📣 **کانال ما:** @Goodbaye_filtering"
    )
    back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]])
    await update.message.reply_text(msg, reply_markup=back_button, parse_mode="Markdown")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "main_menu":
        await start(update, context)
    elif data == "top5":
        configs = fetch_configs()
        back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]])
        msg = "⚡ **۵ کانفیگ برتر با پینگ زیر ۵۰۰ms:**\n\n" + "\n\n".join(f"`{c}`" for c in configs[:5]) if configs else "❌ خطایی رخ داد."
        await query.message.edit_text(msg, reply_markup=back_button, parse_mode="Markdown")
    elif data.startswith("proto_"):
        proto = data.replace("proto_", "")
        await send_proto_configs(update, proto)
    elif data == "apps_guide":
        await cmd_apps(update, context)
    elif data == "sub_links":
        back_button = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]])
        msg = (
            "📡 **لینک‌های سابسکریپشن آنلاین:**\n\n"
            "🔗 **لینک مستقیم (Base64):**\n`https://raw.githubusercontent.com/alireza786786/Tahababa/main/subs/sub.txt`\n\n"
            "📄 **لینک متنی (Plain Text):**\n`https://raw.githubusercontent.com/alireza786786/Tahababa/main/subs/plain.txt`"
        )
        await query.message.edit_text(msg, reply_markup=back_button, parse_mode="Markdown")

def main():
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN is not set.")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CommandHandler("vless", cmd_vless))
    app.add_handler(CommandHandler("vmess", cmd_vmess))
    app.add_handler(CommandHandler("hy2", cmd_hy2))
    app.add_handler(CommandHandler("trojan", cmd_trojan))
    app.add_handler(CommandHandler("apps", cmd_apps))
    app.add_handler(CommandHandler("help", cmd_help))
    
    app.add_handler(CallbackQueryHandler(button_click))
    
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
