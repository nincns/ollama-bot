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
CHANGE_THRESHOLD = 5.0  # Prozent

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

def get_ram_total_mb():
    return int(psutil.virtual_memory().total / 1024 / 1024)

def get_gpu_info():
    try:
        out = subprocess.check_output([
            "nvidia-smi",
            "--query-gpu=utilization.gpu,memory.used,memory.total",
            "--format=csv,noheader,nounits"
        ], text=True)
        util_str, used_str, total_str = out.strip().split(", ")
        return float(util_str), int(used_str), int(total_str)
    except Exception:
        return None, None, None

def get_current_model():
    try:
        result = subprocess.check_output(["ollama", "ps"], text=True)
        for line in result.splitlines():
            if line.strip().startswith("NAME"):
                continue
            if line.strip():
                return line.split()[0]  # erster Wert: Modellname
        return "none"
    except Exception:
        return "error"

# === Vergleichsfunktion ===
def has_significant_change(prev, curr):
    def diff(a, b):
        return abs((a or 0) - (b or 0)) >= CHANGE_THRESHOLD

    return (
        diff(prev.get("cpu"), curr["cpu"])
        or diff(prev.get("ram"), curr["ram"])
        or diff(prev.get("gpu_util"), curr["gpu_util"])
        or diff(prev.get("gpu_mem_used"), curr["gpu_mem_used"])
        or prev.get("model") != curr["model"]
    )

# === DB-Update ===
prev_status = {}

def update_agent_status():
    global prev_status

    config = load_db_config()
    conn = mysql.connector.connect(**config)
    cursor = conn.cursor()

    cpu = get_cpu_load()
    ram = get_memory_usage()
    ram_total = get_ram_total_mb()
    gpu_util, gpu_mem_used, gpu_mem_total = get_gpu_info()
    model = get_current_model()
    timestamp = datetime.now()

    curr_status = {
        "cpu": cpu,
        "ram": ram,
        "gpu_util": gpu_util,
        "gpu_mem_used": gpu_mem_used,
        "model": model
    }

    if not prev_status or has_significant_change(prev_status, curr_status):
        query = """
            INSERT INTO agent_status (
                agent_name, hostname, last_seen, model_active,
                cpu_load_percent, mem_used_percent,
                gpu_util_percent, gpu_mem_used_mb, gpu_mem_total_mb,
                ram_mem_total_mb
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                hostname = VALUES(hostname),
                last_seen = VALUES(last_seen),
                model_active = VALUES(model_active),
                cpu_load_percent = VALUES(cpu_load_percent),
                mem_used_percent = VALUES(mem_used_percent),
                gpu_util_percent = VALUES(gpu_util_percent),
                gpu_mem_used_mb = VALUES(gpu_mem_used_mb),
                gpu_mem_total_mb = VALUES(gpu_mem_total_mb),
                ram_mem_total_mb = VALUES(ram_mem_total_mb)
        """

        values = (
            AGENT_NAME,
            socket.gethostname(),
            timestamp,
            model,
            cpu,
            ram,
            gpu_util,
            gpu_mem_used,
            gpu_mem_total,
            ram_total
        )

        cursor.execute(query, values)
        conn.commit()
        logging.info(f"Status aktualisiert: CPU={cpu}%, RAM={ram}%, Modell={model}, GPU={gpu_util}%")
        prev_status = curr_status

    cursor.close()
    conn.close()

# === Hauptloop ===
if __name__ == "__main__":
    while True:
        update_agent_status()
        time.sleep(CHECK_INTERVAL)