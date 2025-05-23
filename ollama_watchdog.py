#!/usr/bin/env python3
# Filename: ollama_watchdog.py
import mysql.connector
import logging
from configparser import ConfigParser
from datetime import datetime
import time

# === Konfiguration ===
ACCESS_FILE = "private/.mariadb_access"
LOGLEVEL = logging.INFO
INTERVAL_SECONDS = 10  # Zeit zwischen den Zyklen

logging.basicConfig(level=LOGLEVEL, format="%(asctime)s [%(levelname)s] %(message)s")

# === DB-Zugriff ===

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

def load_open_requests(cursor):
    cursor.execute("""
        SELECT * FROM conversations
        WHERE message_status = 'new' AND agent IS NULL
        ORDER BY timestamp ASC
    """)
    return cursor.fetchall()

def get_available_agents(cursor):
    cursor.execute("""
        SELECT * FROM agent_status
        WHERE is_available = TRUE
        ORDER BY cpu_load_percent ASC, mem_used_percent ASC
    """)
    return cursor.fetchall()

def get_all_pre_prompts(cursor):
    cursor.execute("SELECT * FROM prompts WHERE role = 'pre'")
    return cursor.fetchall()

def get_model_catalog(cursor):
    cursor.execute("SELECT * FROM model_catalog WHERE is_active = 1")
    return cursor.fetchall()

# === Logikfunktionen ===

def score_prompt(prompt, message):
    score = 0
    keywords = prompt.get("tags", "")
    prompt_text = prompt.get("content", "")
    if keywords:
        for word in keywords.split(","):
            if word.strip().lower() in message.lower():
                score += 3
    for word in prompt_text.split():
        if word.strip().lower() in message.lower():
            score += 1
    return score

def assign_request(cursor, request_id, agent_name, pre_prompt_id):
    cursor.execute("""
        UPDATE conversations
        SET agent = %s, pre_prompt_id = %s, message_status = 'queued'
        WHERE id = %s
    """, (agent_name, pre_prompt_id, request_id))

def is_agent_suitable(agent, model):
    try:
        ram_mem_total_mb = agent.get("ram_mem_total_mb", 0)
        used_ram_percent = agent.get("mem_used_percent", 100)
        available_ram_mb = (1 - used_ram_percent / 100) * ram_mem_total_mb
        available_vram_mb = agent.get("gpu_mem_total_mb", 0) - agent.get("gpu_mem_used_mb", 0)

        print(f"\n🔍 Prüfe Agent: {agent['agent_name']}")
        print(f"   → RAM gesamt: {ram_mem_total_mb} MB | RAM verfügbar: {available_ram_mb:.0f} MB")
        print(f"   → GPU gesamt: {agent.get('gpu_mem_total_mb', 0)} MB | GPU verfügbar: {available_vram_mb:.0f} MB")
        print(f"   → Modellanforderung: min_ram={model.get('min_ram_mb')} MB | min_vram={model.get('min_vram_mb')} MB | GPU erforderlich: {bool(model.get('requires_gpu'))}")

        if model.get("requires_gpu") and agent.get("gpu_mem_total_mb", 0) <= 0:
            print("   ⛔ Kein GPU verfügbar – nicht geeignet.")
            return False
        if model.get("min_ram_mb") and available_ram_mb < model["min_ram_mb"]:
            print("   ⛔ RAM zu gering – nicht geeignet.")
            return False
        if model.get("min_vram_mb") and available_vram_mb < model["min_vram_mb"]:
            print("   ⛔ VRAM zu gering – nicht geeignet.")
            return False

        print("   ✅ Agent ist geeignet.")
        return True
    except Exception as e:
        print(f"   ⚠️ Fehler bei der Agentprüfung: {e}")
        return False

# === Haupt-Dispatcher ===

def run_dispatcher_cycle():
    cfg = load_db_config()
    conn = mysql.connector.connect(**cfg)
    cursor = conn.cursor(dictionary=True)

    open_requests = load_open_requests(cursor)
    agents = get_available_agents(cursor)
    prompts = get_all_pre_prompts(cursor)
    model_catalog = get_model_catalog(cursor)

    print(f"\n🔍 {len(open_requests)} offene Anfragen gefunden.")
    print(f"⚙️ {len(agents)} verfügbare Agents gefunden:\n")

    for a in agents:
        print(f"  - {a['agent_name']} | CPU: {a['cpu_load_percent']}% | RAM: {a['mem_used_percent']}%")

    for req in open_requests:
        print(f"\n📨 Anfrage {req['id']} von User {req['user_id']}: '{req['user_message'][:60]}'")

        best_score = -1
        best_prompt_id = None
        best_prompt = None

        for prompt in prompts:
            score = score_prompt(prompt, req["user_message"])
            print(f"   → Prompt {prompt['id']} („{prompt['name']}“): Score {score}")
            if score > best_score:
                best_score = score
                best_prompt_id = prompt["id"]
                best_prompt = prompt

        if not best_prompt:
            print("⚠️ Kein passender PrePrompt gefunden.")
            continue

        model_name = best_prompt.get("model")
        model = next((m for m in model_catalog if m["model_name"] == model_name), None)

        if not model:
            print(f"⚠️ Modell '{model_name}' nicht im Katalog gefunden.")
            continue

        suitable_agents = [a for a in agents if is_agent_suitable(a, model)]
        if not suitable_agents:
            print(f"⚠️ Kein geeigneter Agent für Modell '{model_name}' mit RAM/VRAM verfügbar.")
            continue

        selected_agent = suitable_agents[0]
        print(f"✅ Zuweisung: Agent '{selected_agent['agent_name']}' übernimmt mit PrePrompt {best_prompt_id}")
        assign_request(cursor, req["id"], selected_agent["agent_name"], best_prompt_id)

    conn.commit()
    cursor.close()
    conn.close()
    print("⏳ Zyklus abgeschlossen. Warte auf nächste Runde ...\n")

# === Main Loop ===

def main():
    while True:
        try:
            run_dispatcher_cycle()
        except Exception as e:
            logging.error(f"❌ Fehler im Zyklus: {e}")
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    main()