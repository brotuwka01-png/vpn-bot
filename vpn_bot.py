import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ==============================
# НАСТРОЙКИ
# ==============================
import os
BOT_TOKEN = os.environ.get("7914467697:AAFkkbxqE1LHI4GirRMTuy3QfzcSzqCgTzk", "")        # вставь свой токен от @BotFather
ADMIN_ID = 8706308967
CARD_NUMBER = "2202 2083 1522 4080"
PRICE = 200
MANAGER = "@SIKI_OFFICIAL"
# ==============================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WAIT_RECEIPT = 1

def init_db():
    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            full_name TEXT,
            status TEXT DEFAULT 'pending',
            receipt TEXT,
            vpn_key TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_order(user_id, username, full_name):
    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO orders (user_id, username, full_name, created_at) VALUES (?,?,?,?)",
        (user_id, username or "нет", full_name, datetime.now().strftime("%d.%m.%Y %H:%M"))
    )
    order_id = c.lastrowid
    conn.commit()
    conn.close()
    return order_id

def update_receipt(order_id, receipt):
    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute("UPDATE orders SET receipt=?, status='waiting_admin' WHERE id=?", (receipt, order_id))
    conn.commit()
    conn.close()

def set_vpn_key(order_id, key):
    conn = sqlite3.connect("vpn_bot.db")
    c = conn.cursor()
    c.execute("UPDATE orders SET vpn_key=?, status='done' WHERE id=?", (key, order_id))
    row = c.execute("SELECT user_id FROM orders WHERE id=?", (order_id,)).fetchone()
    conn.commit()
    conn.close()
    return row[0] if row else None

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🛒 Купить VPN на 1 месяц — 200 руб", callback_data="buy")],
        [InlineKeyboardButton("💬 Написать менеджеру", url="https://t.me/SIKI_OFFICIAL")],
    ]
    await update.message.reply_text(
        "👋 Привет! Это VPN-бот.\n\n"
        "🔐 Мы продаём быстрый и надёжный VPN.\n"
        "📅 1 месяц — *200 рублей*\n"
        "⚡ Выдача ключа в течение нескольких минут после оплаты.\n\n"
        "Нажми кнопку ниже чтобы купить:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def buy_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    order_id = add_order(user.id, user.username, user.full_name)
    ctx.user_data["order_id"] = order_id
    await query.edit_message_text(
        f"💳 *Оплата заказа #{order_id}*\n\n"
        f"Переведи *{PRICE} рублей* на карту Сбербанк:\n"
        f"`{CARD_NUMBER}`\n\n"
        f"После оплаты отправь сюда *скриншот или номер чека*.",
        parse_mode="Markdown"
    )
    return WAIT_RECEIPT

async def receipt_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    order_id = ctx.user_data.get("order_id")
    if not order_id:
        await update.message.reply_text("Напиши /start чтобы начать заново.")
        return ConversationHandler.END
    receipt_text = update.message.text or update.message.caption or "скриншот"
    update_receipt(order_id, receipt_text)
    await update.message.reply_text(
        "✅ Чек получен! Ожидай — выдадим ключ в течение нескольких минут."
    )
    mention = f"@{user.username}" if user.username else user.full_name
    kb = [[InlineKeyboardButton(f"✅ Выдать ключ для заказа #{order_id}", callback_data=f"give_{order_id}")]]
    msg = (
        f"🔔 *Новый заказ #{order_id}*\n\n"
        f"👤 Пользователь: {mention} (`{user.id}`)\n"
        f"💰 Сумма: {PRICE} руб\n"
        f"📋 Чек: {receipt_text}\n\n"
        f"👉 Зайди в @trustvpn_official_bot, купи ключ за 149 руб и нажми кнопку ниже."
    )
    await ctx.bot.send_message(ADMIN_ID, msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    return ConversationHandler.END

async def photo_receipt_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    update.message.text = update.message.caption or "фото чека"
    await receipt_handler(update, ctx)

async def give_key_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        await query.answer("Нет доступа.", show_alert=True)
        return
    order_id = int(query.data.split("_")[1])
    ctx.user_data["giving_order"] = order_id
    await query.edit_message_text(f"📨 Введи VPN-ключ для заказа #{order_id}:")
    return WAIT_RECEIPT

async def admin_key_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    order_id = ctx.user_data.get("giving_order")
    if not order_id:
        await update.message.reply_text("Нажми кнопку 'Выдать ключ' из уведомления.")
        return ConversationHandler.END
    key = update.message.text.strip()
    user_id = set_vpn_key(order_id, key)
    if user_id:
        await ctx.bot.send_message(
            user_id,
            f"🎉 *Твой VPN ключ готов!*\n\n"
            f"```\n{key}\n```\n\n"
            f"📌 Вставь этот ключ в приложение и готово! 🚀",
            parse_mode="Markdown"
        )
        await update.message.reply_text(f"✅ Ключ для заказа #{order_id} отправлен клиенту!")
    else:
        await update.message.reply_text("❌ Заказ не найден.")
    ctx.user_data.pop("giving_order", None)
    return ConversationHandler.END

async def orders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect("vpn_bot.db")
    rows = conn.execute("SELECT id, full_name, status, created_at FROM orders ORDER BY id DESC LIMIT 10").fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("Заказов пока нет.")
        return
    text = "📋 *Последние 10 заказов:*\n\n"
    for r in rows:
        text += f"#{r[0]} | {r[1]} | {r[2]} | {r[3]}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено. Напиши /start чтобы начать заново.")
    return ConversationHandler.END

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    buy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_handler, pattern="^buy$")],
        states={WAIT_RECEIPT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receipt_handler),
            MessageHandler(filters.PHOTO, photo_receipt_handler),
        ]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    give_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(give_key_start, pattern="^give_")],
        states={WAIT_RECEIPT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(ADMIN_ID), admin_key_input)
        ]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("orders", orders))
    app.add_handler(buy_conv)
    app.add_handler(give_conv)
    print("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
