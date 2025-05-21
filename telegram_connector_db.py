#!/usr/bin/env python3
# Filename: telegram_connector_db.py
import asyncio
import sys
import mysql.connector
from datetime import datetime, timedelta
from pathlib import Path
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, JobQueue
)

ACCESS_FILE = "private/.mariadb_access"
BOT_TOKEN_FILE = "/private/.bot_token"
ADMIN_ID = 13709024
CONFIRM_TIMEOUT_MINUTES = 15


def read_token(path=BOT_TOKEN_FILE) -> str:
    token_path = Path(path)
    if not token_path.exists():
        print("❌ Bot-Token-Datei nicht gefunden.")
        sys.exit(1)
    return token_path.read_text().strip()


def load_db_credentials() -> dict:
    creds = {}
    with open(ACCESS_FILE) as f:
        for line in f:
            if "=" in line:
                key, value = line.strip().split("=", 1)
                creds[key.strip()] = value.strip()
    return {
        "host": creds.get("host"),
        "port": int(creds.get("port", 3306)),
        "user": creds.get("user"),
        "password": creds.get("password"),
        "database": creds.get("database"),
    }


class TelegramConnector:
    def __init__(self, token: str, admin_id: int):
        self.token = token
        self.admin_id = admin_id
        self.db_config = load_db_credentials()
        self.app = None
        self.pending_confirmations = {}  # user_id: (message_text, timestamp, dialog_id)

    async def send_replies(self, context: ContextTypes.DEFAULT_TYPE):
        conn = mysql.connector.connect(**self.db_config)
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT c.id, c.user_id, c.model_response
            FROM conversations c
            JOIN user_profile u ON c.user_id = u.user_id
            WHERE c.message_status = 'solved'
              AND c.processing_finished_at IS NOT NULL
              AND (c.response_sent IS NULL OR c.response_sent = 0)
        """)
        rows = cursor.fetchall()

        for row in rows:
            try:
                await context.bot.send_message(chat_id=row["user_id"], text=row["model_response"] or "(keine Antwort)")
                cursor.execute("UPDATE conversations SET response_sent = 1 WHERE id = %s", (row["id"],))
                conn.commit()
            except Exception as e:
                print(f"❌ Fehler beim Senden an {row['user_id']}: {e}")

        cursor.close()
        conn.close()

    def start(self):
        self.app = ApplicationBuilder().token(self.token).build()
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.app.add_handler(CommandHandler("start", self.handle_start))

        job_queue = self.app.job_queue
        job_queue.run_repeating(self.send_replies, interval=5)
        job_queue.run_repeating(self.cleanup_confirmations, interval=60)

        self.app.run_polling()

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("👋 Hallo! Sende mir einfach eine Nachricht, um zu starten.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_id = user.id
        msg_text = update.message.text.strip()
        now = datetime.now()

        if user_id in self.pending_confirmations:
            old_msg, timestamp, old_dialog_id = self.pending_confirmations[user_id]
            if msg_text.lower() == "ja":
                await self.save_message(user_id, old_msg, old_dialog_id)
                await update.message.reply_text("🔄 Fortsetzung bestätigt. Nachricht wurde verarbeitet.")
            elif msg_text.lower() == "nein":
                await self.save_message(user_id, old_msg, None)
                await update.message.reply_text("🆕 Neuer Dialog gestartet.")
            else:
                await update.message.reply_text("❓ Bitte antworte mit 'ja' oder 'nein', um fortzufahren.")
                return

            del self.pending_confirmations[user_id]
            return

        conn = mysql.connector.connect(**self.db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM user_profile WHERE user_id = %s", (user_id,))
        profile = cursor.fetchone()

        if not profile:
            cursor.execute("""
                INSERT INTO user_profile (user_id, first_name, last_name, messenger_id, last_active)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                user_id,
                user.first_name or "",
                user.last_name or "",
                user.username or None,
                now,
            ))
            conn.commit()
            await update.message.reply_text("👤 Dein Account wurde registriert. Bitte warte auf Freischaltung.")
            cursor.close()
            conn.close()
            return

        if profile["role"] == "disabled":
            await update.message.reply_text("🚫 Dein Zugriff wurde deaktiviert.")
            cursor.close()
            conn.close()
            return

        # Letzte Konversation prüfen
        cursor.execute("""
            SELECT id, dialog_id, timestamp FROM conversations
            WHERE user_id = %s AND message_status = 'solved'
            ORDER BY timestamp DESC LIMIT 1
        """, (user_id,))
        last = cursor.fetchone()

        if last:
            delta = now - last["timestamp"]
            if delta.total_seconds() > CONFIRM_TIMEOUT_MINUTES * 60:
                self.pending_confirmations[user_id] = (msg_text, now, last["dialog_id"])
                await update.message.reply_text("🤔 Möchtest Du unser letztes Gespräch fortsetzen? Antworte bitte mit ja oder nein.")
                cursor.close()
                conn.close()
                return

        # Fortsetzung oder erster Eintrag
        dialog_id = last["dialog_id"] if last else None
        await self.save_message(user_id, msg_text, dialog_id)
        #await update.message.reply_text("✅ Deine Nachricht wurde entgegengenommen.")
        cursor.close()
        conn.close()

    async def save_message(self, user_id, message, dialog_id):
        conn = mysql.connector.connect(**self.db_config)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO conversations (user_id, user_message, message_status, timestamp, dialog_id)
            VALUES (%s, %s, 'new', %s, %s)
        """, (user_id, message, datetime.now(), dialog_id))
        conn.commit()
        cursor.close()
        conn.close()

    async def cleanup_confirmations(self, context: ContextTypes.DEFAULT_TYPE):
        now = datetime.now()
        expired = [uid for uid, (_, ts, _) in self.pending_confirmations.items()
                   if (now - ts).total_seconds() > CONFIRM_TIMEOUT_MINUTES * 60]
        for uid in expired:
            del self.pending_confirmations[uid]

    async def send_test_message(self):
        await self.app.initialize()
        await self.app.bot.send_message(chat_id=self.admin_id, text="✅ Telegram-Verbindung erfolgreich (Testnachricht).")
        await self.app.shutdown()


# === Direkt ausführbar ===
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Telegram Bot Connector mit Datenbankintegration")
    parser.add_argument("--test", action="store_true", help="Sende Testnachricht an Admin")
    args = parser.parse_args()

    connector = TelegramConnector(token=read_token(), admin_id=ADMIN_ID)
    if args.test:
        asyncio.run(connector.send_test_message())
    else:
        connector.start()
