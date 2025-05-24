#!/usr/bin/env python3
# Filename: ollama_agent_performance.py

import time
import logging
import socket
import subprocess
import mysql.connector
import psutil
from configparser import ConfigParser
from datetime import datetime

# === Konfiguration ===
ACCESS_FILE = "private/.mariadb_access"
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

# === Performance Informationen ===
def get_cpu_load():
    return psutil.cpu_percent(interval=None)

def get_memory_usage():
    return psutil.virtual_memory().percent

def get_current_model():
    try:
        result = subprocess.check_output(["ollama", "ps"], text=True)
        for line in result.splitlines():
            if line.strip().startswith("NAME"):
                continue
            if line.strip():
                return line.split()[0]  # erster Wert: Modellname
        return "none"
    except Exception as e:
        logging.warning(f"Fehler bei 'ollama ps': {e}")
        return "error"

# === DB-Update ===
def update_agent_status():
    config = load_db_config()
    conn = mysql.connector.connect(**config)
    cursor = conn.cursor()

    cpu = get_cpu_load()
    ram = get_memory_usage()
    model = get_current_model()
    timestamp = datetime.now()

    query = """
        INSERT INTO agent_status (agent_name, cpu_usage, ram_usage, current_model, last_updated)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            cpu_usage = VALUES(cpu_usage),
            ram_usage = VALUES(ram_usage),
            current_model = VALUES(current_model),
            last_updated = VALUES(last_updated)
    """
    values = (AGENT_NAME, cpu, ram, model, timestamp)
    cursor.execute(query, values)
    conn.commit()
    cursor.close()
    conn.close()

    logging.info(f"Status aktualisiert: CPU={cpu}%, RAM={ram}%, Modell={model}")

# === Hauptloop ===
if __name__ == "__main__":
    while True:
        update_agent_status()
        time.sleep(CHECK_INTERVAL)