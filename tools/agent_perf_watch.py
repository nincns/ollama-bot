#!/usr/bin/env python3
# Filename: agent_perf_watch.py

import mysql.connector
import time
from datetime import datetime
from rich.console import Console
from rich.table import Table

ACCESS_FILE = ".mariadb_access"
REFRESH_SEC = 2

def read_access():
    cfg = {}
    with open(ACCESS_FILE) as f:
        for line in f:
            if "=" in line:
                key, value = line.strip().split("=", 1)
                cfg[key.strip()] = value.strip()
    return cfg

def fetch_perf(cursor):
    cursor.execute("""
        SELECT agent_name, hostname, last_seen, performance_class, runtime_status
        FROM agent_status
        ORDER BY agent_name
    """)
    return cursor.fetchall()

def extract_model_load(runtime_status):
    if not runtime_status:
        return "-"
    lines = runtime_status.strip().splitlines()
    if len(lines) > 1:
        parts = lines[1].split()
        return parts[0] if parts else "-"
    return "-"

def monitor_perf():
    cfg = read_access()
    conn = mysql.connector.connect(
        host=cfg["host"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        port=int(cfg.get("port", 3306))
    )
    cursor = conn.cursor()

    console = Console()

    try:
        while True:
            data = fetch_perf(cursor)  # direkt aufrufen, ohne Dummy-SQL davor

            table = Table(title=f"Agent Performance – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            table.add_column("Agent", style="cyan")
            table.add_column("Letztes Update", style="magenta")
            table.add_column("Klasse", style="yellow")
            table.add_column("Aktiv genutzt", style="green")
            table.add_column("Raw Status", style="dim", no_wrap=False)

            for agent, _, last_seen, cls, status in data:
                table.add_row(
                    agent,
                    last_seen.strftime("%H:%M:%S"),
                    cls or "-",
                    extract_model_load(status),
                    status.replace("\n", " | ")[:80] + ("…" if status and len(status) > 80 else "")
                )

            console.clear()
            console.print(table)
            time.sleep(REFRESH_SEC)

    except KeyboardInterrupt:
        console.print("[bold red]Beendet durch Nutzer.[/bold red]")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    monitor_perf()