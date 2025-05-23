#!/usr/bin/env python3
# Filename: ollama_agent.py
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
import psutil

#logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")

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

# === Perfomance Informationen ermitteln ===

def get_cpu_load():
    return psutil.cpu_percent(interval=None)

def get_memory_usage():
    return psutil.virtual_memory().percent

def get_gpu_info():
    try:
        out = subprocess.check_output(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
                                       "--format=csv,noheader,nounits"],
                                      text=True)
        util_str, used_str, total_str = out.strip().split(", ")
        return float(util_str), int(used_str), int(total_str)
    except Exception:
        return None, None, None

# === Agent-Infos eintragen und agent_status aktualisieren ===
def log_agent_info(cursor):
    def run_cmd(command):
        try:
            return subprocess.check_output(command, text=True).strip().splitlines()[1:]
        except Exception as e:
            return [f"Fehler: {e}"]

    models = run_cmd(["ollama", "list"])
    status = run_cmd(["ollama", "ps"])

    model_info_str = "\n".join(models)
    runtime_status_str = "\n".join(status)

    # Aktives Modell extrahieren
    active_model = "-"
    for line in status:
        if line.strip():
            parts = line.split()
            if parts:
                active_model = parts[0]
                break

      # Performance-Daten sammeln
    cpu = get_cpu_load()
    mem = get_memory_usage()
    gpu_util, gpu_used, gpu_total = get_gpu_info()

    # agent_log aktualisieren wenn sich Status ändert
    if status:
        cursor.execute("""
            SELECT model_info FROM agent_log
            WHERE agent_name = %s AND log_type = 'status'
            ORDER BY timestamp DESC LIMIT 1
        """, (AGENT_NAME,))
        last_status = cursor.fetchone()
        if not last_status or last_status["model_info"] != model_info_str:
            cursor.execute("""
                INSERT INTO agent_log (conversation_id, agent_name, log_type, model_info, timestamp)
                VALUES (%s, %s, %s, %s, %s)
            """, (None, AGENT_NAME, "status", model_info_str, datetime.now()))

    # Aktualisiere agent_status
    cursor.execute("""
        REPLACE INTO agent_status (
            agent_name, hostname, last_seen, performance_class,
            recommended_models, model_list, model_active, runtime_status, is_available, notes,
            cpu_load_percent, mem_used_percent, gpu_util_percent,
            gpu_mem_used_mb, gpu_mem_total_mb
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        AGENT_NAME,
        socket.gethostname(),
        datetime.now(),
        None,           # performance_class
        None,           # recommended_models
        model_info_str,
        active_model,
        runtime_status_str,
        True,
        None,
        cpu,
        mem,
        gpu_util,
        gpu_used,
        gpu_total
    ))

    #print(f"[{datetime.now().strftime('%H:%M:%S')}] Status-Update ✅ Modell: {active_model}") #nur zum Troubleshooting

# === Prompt Logik ===

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

# === Konversation aus DB laden ===
def build_chat_history(cursor, dialog_id, new_prompt):
    cursor.execute("""
        SELECT user_message, model_response
        FROM conversations
        WHERE dialog_id = %s
        AND message_status = 'solved'
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

# === Verarbeitung einzelner Anfrage in separatem Thread ===
def handle_request(cfg, row):
    try:
        conn = mysql.connector.connect(**cfg)
        cursor = conn.cursor(dictionary=True)

        conv_id = row["id"]
        prompt = row["user_message"]
        user_id = row["user_id"]

        logging.debug(f"🛠 Anfrage erhalten: ID={conv_id} | Text='{prompt}'")
        logging.debug("🔍 Starte Tag-Matching auf pre-Prompts...")

        # 🧠 Pre-Prompt-Erkennung durch präzises Wort-Matching gegen Tags
        if not row.get("pre_prompt_id"):
            best_id = find_best_prompt_id_by_tags(cursor, prompt)
            if best_id:
                logging.debug(f"➤ Gewählt: Prompt ID {best_id}")
                row["pre_prompt_id"] = best_id
            else:
                logging.debug("⚠️ Kein passender Pre-Prompt gefunden.")

        # 🧠 Modellwahl: conversation → prompt → Fallback
        model = row.get("model_used")
        pre_prompt_text = None
        prompt_name = None
        if not model and row.get("pre_prompt_id"):
            cursor.execute("SELECT model, content, name FROM prompts WHERE id = %s", (row["pre_prompt_id"],))
            result = cursor.fetchone()
            if result:
                model = result.get("model") or model
                pre_prompt_text = result.get("content")
                prompt_name = result.get("name")
                logging.debug(f"📦 Modellzuordnung: {model} durch Prompt {prompt_name}")
                if pre_prompt_text:
                    logging.debug(f"🧠 Pre-Prompt-Inhalt (Auszug): {pre_prompt_text[:80]}...")
        if not model:
            model = "stablelm2:1.6b"
            logging.debug(f"📦 Kein Modell im Prompt definiert. Fallback: {model}")

        prompt_info = f"Prompt-ID={row.get('pre_prompt_id') or '-'}"
        if prompt_name:
            prompt_info += f" ({prompt_name})"
        logging.info(f"⛰ Bearbeite Anfrage {conv_id} mit Modell '{model}' | {prompt_info}")

        dialog_id = get_or_create_dialog_id(cursor, user_id)

        # 🧩 pre_prompt_id in DB sichern
        cursor.execute("""
            UPDATE conversations
            SET locked_by_agent = %s,
                locked_at = NOW(),
                processing_started_at = NOW(),
                message_status = 'progress',
                dialog_id = %s,
                pre_prompt_id = %s
            WHERE id = %s
        """, (AGENT_NAME, dialog_id, row.get("pre_prompt_id"), conv_id))
        conn.commit()

        # Prompt-Verlauf aufbauen, Pre-Prompt ggf. voranstellen
        start_time = datetime.now()
        history = build_chat_history(cursor, dialog_id, prompt)
        if pre_prompt_text:
            history.insert(0, {"role": "system", "content": pre_prompt_text})

        logging.debug("💬 Zusammengesetzter Chatverlauf:")
        for msg in history:
            role = msg["role"]
            snippet = msg["content"][:80].replace("\n", " ")
            logging.debug(f"[{role}] {snippet}")

        reply = query_ollama(history, model)
        duration = (datetime.now() - start_time).total_seconds()

        # Ergebnisse speichern
        cursor.execute("""
            UPDATE conversations
            SET model_response = %s,
                model_used = %s,
                message_status = 'solved',
                processing_finished_at = NOW(),
                agent = %s
            WHERE id = %s
        """, (reply, model, AGENT_NAME, conv_id))
        conn.commit()

        log_text = f"Model={model} | Prompt={row.get('pre_prompt_id')} | Dauer={duration:.1f}s"
        cursor.execute("""
            INSERT INTO agent_log (conversation_id, agent_name, log_type, message, timestamp)
            VALUES (%s, %s, 'assignment', %s, %s)
        """, (conv_id, AGENT_NAME, log_text, datetime.now()))
        conn.commit()

        logging.info(f"✅ Anfrage {conv_id} abgeschlossen.")

    except Exception as e:
        logging.error(f"Fehler bei der Verarbeitung von Anfrage {row['id']}: {e}")
    finally:
        cursor.close()
        conn.close()

# === Verarbeitung neuer Einträge in Hauptloop ===
def process_pending_requests(cfg):
    conn = mysql.connector.connect(**cfg)
    cursor = conn.cursor(dictionary=True)

    log_agent_info(cursor)
    conn.commit()

    cursor.execute("""
        SELECT * FROM conversations
        WHERE message_status = 'queued'
        AND agent = %s
        AND (locked_by_agent IS NULL OR locked_by_agent = %s)
        ORDER BY timestamp ASC
        LIMIT 1
    """, (AGENT_NAME, AGENT_NAME))

    row = cursor.fetchone()

    if row:
        thread = threading.Thread(target=handle_request, args=(cfg, row), daemon=True)
        thread.start()
    else:
        logging.debug("Keine offenen Anfragen für diesen Agent.")

    cursor.close()
    conn.close()

# === Anfrage an Ollama senden ===
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

# === Dialog-ID bestimmen oder neu erzeugen ===
def get_or_create_dialog_id(cursor, user_id):
    cursor.execute("""
        SELECT dialog_id, MAX(timestamp) AS ts FROM conversations
        WHERE user_id = %s AND dialog_id IS NOT NULL
        GROUP BY dialog_id ORDER BY ts DESC LIMIT 1
    """, (user_id,))
    last = cursor.fetchone()

    if last and last["ts"]:
        last_time = last["ts"]
        if datetime.now() - last_time < timedelta(minutes=15):
            return last["dialog_id"]

    return str(uuid.uuid4())

# === Hauptfunktion ===
def status_updater(cfg):
    while True:
        try:
            conn = mysql.connector.connect(**cfg)
            cursor = conn.cursor(dictionary=True)
            log_agent_info(cursor)
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            logging.error(f"Fehler beim Status-Update: {e}")
        time.sleep(3)

# In main():
if __name__ == "__main__":
    logging.info(f"Starte Agent: {AGENT_NAME}")
    cfg = load_db_config()
    
    # Hintergrundthread für Statusupdates
    threading.Thread(target=status_updater, args=(cfg,), daemon=True).start()
    
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