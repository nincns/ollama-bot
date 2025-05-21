#!/usr/bin/env python3
# Filename: agent_status_monitor.py

import mysql.connector
import time
from datetime import datetime
from rich.console import Console
from rich.table import Table

ACCESS_FILE = "../private/.mariadb_access"
INTERVAL = 10  # Sekunden

def read_access():
    cfg = {}
    with open(ACCESS_FILE) as f:
        for line in f:
            if "=" in line:
                key, value = line.strip().split("=", 1)
                cfg[key.strip()] = value.strip()
    return cfg

def extract_active_model(runtime_status):
    if runtime_status:
        lines = runtime_status.strip().splitlines()
        if len(lines) > 1:
            return lines[1].split()[0]
    return "-"

def monitor_agents():
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
    console.print("[bold green]▶ Starte Agent-Status-Überwachung... (STRG+C zum Beenden)[/bold green]")

    try:
        while True:
            cursor.execute("""
                SELECT agent_name, hostname, last_seen, performance_class,
                       recommended_models, model_list, model_active, runtime_status, is_available,
                       cpu_load_percent, mem_used_percent,
                       gpu_util_percent, gpu_mem_used_mb, gpu_mem_total_mb
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

            for (
                agent, host, seen, klass,
                recommended, model_list, model_active, runtime,
                available, cpu, mem, gpu, gpu_used, gpu_total
            ) in statuses:

                gpu_ram = "-"
                if gpu_used is not None and gpu_total:
                    gpu_ram = f"{gpu_used:.0f}/{gpu_total} MB"

                table.add_row(
                    agent or "-",
                    host or "-",
                    seen.strftime("%Y-%m-%d %H:%M:%S") if seen else "-",
                    klass or "-",
                    model_active or "-",
                    f"{cpu:.1f}%" if cpu is not None else "-",
                    f"{mem:.1f}%" if mem is not None else "-",
                    f"{gpu:.1f}%" if gpu is not None else "-",
                    gpu_ram,
                    "✅" if available else "❌"
                )

            console.clear()
            console.print(table)
            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        console.print("[bold red]Beendet durch Nutzer.[/bold red]")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    monitor_agents()