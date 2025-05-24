#!/usr/bin/env python3
# Filename: ollama_agent_light.py

import os
import time
import logging
import socket
import subprocess
import mysql.connector
import requests
import uuid
from configparser import ConfigParser
from datetime import datetime, timedelta
import threading

# === Konfiguration ===
ACCESS_FILE = "private/.mariadb_access"
OLLAMA_URL = "http://localhost:11434/api/chat"
AGENT_NAME = socket.gethostname()
CHECK_INTERVAL = 3  # Sekunden

# === Logging ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# === DB-Konfiguration laden ===
def load_db_config():
    config = ConfigParser()
    config.read(ACCESS_FILE)
    client = config["client"]
    return {
        "host": client.get("host", "127.0.0.1"),
        "port": int(client.get("port", 3306)),
        "user": client.get("user"),
        "password": client.get("password"),
        "database": client.get("database")
    }

def find_best_prompt_id_by_tags(cursor, user_text):
    cursor.execute("SELECT id, tags FROM prompts WHERE is_active = 1 AND role = 'pre' AND tags IS NOT NULL")
    prompts = cursor.fetchall()
    user_words = [w.strip(",.!?").lower() for w in user_text.split()]
    max_hits = 0
    best_id = None
    for prompt in prompts:
        tag_words = [tag.strip().lower() for tag in prompt["tags"].split(",") if tag.strip()]
        hits = sum(1 for word in user_words if word in tag_words)
        if hits > max_hits:
            max_hits = hits
            best_id = prompt["id"]
    return best_id

def build_chat_history(cursor, dialog_id, new_prompt):
    cursor.execute("""
        SELECT user_message, model_response FROM conversations
        WHERE dialog_id = %s AND message_status = 'solved'
        ORDER BY timestamp ASC
    """, (dialog_id,))
    rows = cursor.fetchall()
    history = []
    for row in rows:
        if row["user_message"]:
            history.append({"role": "user", "content": row["user_message"]})
        if row["model_response"]:
            history.append({"role": "assistant", "content": row["model_response"]})
    history.append({"role": "user", "content": new_prompt})
    return history

def query_ollama(messages: list, model: str) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=300)
        if response.ok:
            return response.json().get("message", {}).get("content", "")
        logging.error("Fehlerhafte Antwort von Ollama: %s", response.text)
    except Exception as e:
        logging.exception("Fehler bei Anfrage an Ollama: %s", e)
    return "❌ Fehler bei der Modellanfrage."

def get_or_create_dialog_id(cursor, user_id):
    cursor.execute("""
        SELECT dialog_id, MAX(timestamp) AS ts FROM conversations
        WHERE user_id = %s AND dialog_id IS NOT NULL
        GROUP BY dialog_id ORDER BY ts DESC LIMIT 1
    """, (user_id,))
    last = cursor.fetchone()
    if last and last["ts"]:
        if datetime.now() - last["ts"] < timedelta(minutes=15):
            return last["dialog_id"]
    return str(uuid.uuid4())

def is_model_supported_by_agent(cursor, agent_name: str, model_name: str) -> bool:
    cursor.execute("SELECT * FROM model_catalog WHERE model_name = %s AND is_active = 1", (model_name,))
    model = cursor.fetchone()
    if not model:
        return False
    cursor.execute("SELECT * FROM agent_status WHERE agent_name = %s", (agent_name,))
    agent = cursor.fetchone()
    if not agent:
        return False
    if model.get("requires_gpu") and (not agent.get("gpu_mem_total_mb") or agent["gpu_mem_total_mb"] < 1024):
        return False
    if model.get("min_ram_mb") and agent.get("mem_used_percent", 100) > 90:
        return False
    if model.get("min_vram_mb") and (not agent.get("gpu_mem_total_mb") or agent["gpu_mem_total_mb"] < model["min_vram_mb"]):
        return False
    return True

def handle_request(cfg, row):
    try:
        conn = mysql.connector.connect(**cfg)
        cursor = conn.cursor(dictionary=True)
        conv_id = row["id"]
        prompt = row["user_message"]
        user_id = row["user_id"]
        if not row.get("pre_prompt_id"):
            row["pre_prompt_id"] = find_best_prompt_id_by_tags(cursor, prompt)
        model = row.get("model_used")
        if not model and row.get("pre_prompt_id"):
            cursor.execute("SELECT model FROM prompts WHERE id = %s", (row["pre_prompt_id"],))
            result = cursor.fetchone()
            if result:
                model = result.get("model") or model
        if not model:
            model = "stablelm2:1.6b"
        if not is_model_supported_by_agent(cursor, AGENT_NAME, model):
            cursor.execute("""
                UPDATE conversations SET message_status = 'error', notes = 'Modell nicht kompatibel mit Agent'
                WHERE id = %s
            """, (conv_id,))
            conn.commit()
            return
        dialog_id = get_or_create_dialog_id(cursor, user_id)
        cursor.execute("""
            UPDATE conversations SET locked_by_agent = %s, locked_at = NOW(),
            processing_started_at = NOW(), message_status = 'progress',
            dialog_id = %s, pre_prompt_id = %s WHERE id = %s
        """, (AGENT_NAME, dialog_id, row.get("pre_prompt_id"), conv_id))
        conn.commit()
        history = build_chat_history(cursor, dialog_id, prompt)
        cursor.execute("SELECT content FROM prompts WHERE id = %s", (row.get("pre_prompt_id"),))
        result = cursor.fetchone()
        if result:
            history.insert(0, {"role": "system", "content": result.get("content")})
        reply = query_ollama(history, model)
        cursor.execute("""
            UPDATE conversations SET model_response = %s, model_used = %s,
            message_status = 'solved', processing_finished_at = NOW(), agent = %s
            WHERE id = %s
        """, (reply, model, AGENT_NAME, conv_id))
        conn.commit()
    except Exception as e:
        logging.error(f"Fehler bei der Verarbeitung von Anfrage {row['id']}: {e}")
    finally:
        cursor.close()
        conn.close()

def process_pending_requests(cfg):
    conn = mysql.connector.connect(**cfg)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM conversations
        WHERE message_status = 'queued'
        AND agent = %s
        AND (locked_by_agent IS NULL OR locked_by_agent = %s)
        ORDER BY timestamp ASC LIMIT 1
    """, (AGENT_NAME, AGENT_NAME))
    row = cursor.fetchone()
    if row:
        thread = threading.Thread(target=handle_request, args=(cfg, row), daemon=True)
        thread.start()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    logging.info(f"Starte Agent Light: {AGENT_NAME}")
    cfg = load_db_config()
    while True:
        try:
            process_pending_requests(cfg)
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logging.warning("Agent wurde manuell beendet.")
            break
        except Exception as e:
            logging.error("Fehler in Hauptschleife: %s", e)
            time.sleep(5)