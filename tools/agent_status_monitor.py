#!/usr/bin/env python3
# Filename: agent_status_monitor.py

import mysql.connector
import time
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.live import Live

ACCESS_FILE = "../private/.mariadb_access"
INTERVAL = 1  # Sekunden

def read_access():
    cfg = {}
    with open(ACCESS_FILE) as f:
        for line in f:
            if "=" in line:
                key, value = line.strip().split("=", 1)
                cfg[key.strip()] = value.strip()
    return cfg

def create_agent_table(cursor):
    cursor.execute("""
        SELECT agent_name, hostname, last_seen, performance_class,
               recommended_models, model_list, runtime_status, is_available,
               cpu_load_percent, mem_used_percent,
               gpu_util_percent, gpu_mem_used_mb, gpu_mem_total_mb,
               model_active, ram_mem_total_mb
        FROM agent_status
        ORDER BY last_seen DESC
    """)
    statuses = cursor.fetchall()

    table = Table(title=f"Agent Status – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    table.add_column("Agent", style="cyan")
    table.add_column("Host")
    table.add_column("Letztes Update", style="magenta")
    table.add_column("Klasse", style="yellow")
    table.add_column("Modell aktiv", style="green")
    table.add_column("CPU %", justify="right")
    table.add_column("RAM %", justify="right")
    table.add_column("GPU %", justify="right")
    table.add_column("GPU RAM", justify="right")
    table.add_column("Verfügbar")

    for row in statuses:
        gpu_ram = "-"
        if row["gpu_mem_used_mb"] is not None and row["gpu_mem_total_mb"]:
            gpu_ram = f"{row['gpu_mem_used_mb']}/{row['gpu_mem_total_mb']} MB"

        table.add_row(
            row.get("agent_name", "-"),
            row.get("hostname", "-"),
            row["last_seen"].strftime("%Y-%m-%d %H:%M:%S") if row["last_seen"] else "-",
            row.get("performance_class", "-") or "-",
            row.get("model_active", "-"),
            f"{row['cpu_load_percent']:.1f}%" if row.get("cpu_load_percent") is not None else "-",
            f"{row['mem_used_percent']:.1f}%" if row.get("mem_used_percent") is not None else "-",
            f"{row['gpu_util_percent']:.1f}%" if row.get("gpu_util_percent") is not None else "-",
            gpu_ram,
            "✅" if row.get("is_available") else "❌"
        )
    return table

def monitor_agents():
    cfg = read_access()
    conn = mysql.connector.connect(
        host=cfg["host"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        port=int(cfg.get("port", 3306))
    )

    console = Console()
    console.print("[bold green]▶ Live Agent-Status-Monitor wird gestartet... (STRG+C zum Beenden)[/bold green]")

    try:
        with Live(console=console, screen=True, refresh_per_second=1) as live:
            while True:
                # Cursor frisch pro Durchlauf
                cursor = conn.cursor(dictionary=True)
                table = create_agent_table(cursor)
                cursor.close()
                live.update(table, refresh=True)
                time.sleep(INTERVAL)

    except KeyboardInterrupt:
        console.print("[bold red]Beendet durch Nutzer.[/bold red]")
    finally:
        conn.close()

if __name__ == "__main__":
    monitor_agents()