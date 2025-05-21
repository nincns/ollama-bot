#!/usr/bin/env python3
# Filename: live_log.py
import mysql.connector
from datetime import datetime
import time
from rich import print
from rich.console import Console

ACCESS_FILE = ".mariadb_access"
INTERVAL = 3  # Sekunden

def read_access():
    cfg = {}
    with open(ACCESS_FILE) as f:
        for line in f:
            if "=" in line:
                key, value = line.strip().split("=", 1)
                cfg[key.strip()] = value.strip()
    return cfg

def live_log():
    cfg = read_access()
    conn = mysql.connector.connect(
        host=cfg["host"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        port=int(cfg.get("port", 3306))
    )
    cursor = conn.cursor()

    last_ts = {
        "conversations": datetime.min,
        "conversation_log": datetime.min,
        "user_profile": datetime.min,
    }

    console = Console()
    console.print("[bold green]▶ Starte Live-Log... (STRG+C zum Beenden)[/bold green]")

    while True:
        try:
            # conversations
            cursor.execute("""
                SELECT id, timestamp, user_id, message_status,
                       LEFT(user_message, 50), LEFT(model_response, 50),
                       model_used, agent, dialog_id
                FROM conversations
                WHERE timestamp > %s ORDER BY timestamp ASC
            """, (last_ts["conversations"],))
            for row in cursor.fetchall():
                last_ts["conversations"] = max(last_ts["conversations"], row[1])
                ts, uid, status = row[1], row[2], row[3]
                user_msg, model_reply = row[4], row[5]
                model, agent, dialog_id = row[6], row[7], row[8]
                console.print(
                    f"[bold cyan]{ts}[/bold cyan] | [green]conversations[/green] | "
                    f"ID={row[0]} | UID={uid} | {status.upper()} | '{user_msg}' → '{model_reply}' | "
                    f"Modell={model or '-'} | Agent={agent or '-'} | Dialog={dialog_id or '-'}"
                )

            # conversation_log
            cursor.execute("""
                SELECT id, timestamp, role, LEFT(message, 40)
                FROM conversation_log
                WHERE timestamp > %s ORDER BY timestamp ASC
            """, (last_ts["conversation_log"],))
            for row in cursor.fetchall():
                last_ts["conversation_log"] = max(last_ts["conversation_log"], row[1])
                console.print(f"[bold cyan]{row[1]}[/bold cyan] | [yellow]conversation_log[/yellow] | {row[2]}: {row[3]}")

            # user_profile
            cursor.execute("""
                SELECT user_id, first_name, last_name, role, last_active
                FROM user_profile
                WHERE last_active > %s ORDER BY last_active ASC
            """, (last_ts["user_profile"],))
            for row in cursor.fetchall():
                last_ts["user_profile"] = max(last_ts["user_profile"], row[4])
                name = f"{row[1]} {row[2]}".strip()
                console.print(
                    f"[bold cyan]{row[4]}[/bold cyan] | [white]user_profile[/white] | 👤 Neue Registrierung: {name} (ID {row[0]}, Rolle={row[3]})"
                )

            time.sleep(INTERVAL)

        except KeyboardInterrupt:
            print("[bold red]Beendet durch Nutzer.[/bold red]")
            break
        except Exception as e:
            print(f"[red]Fehler:[/red] {e}")
            time.sleep(5)

    cursor.close()
    conn.close()


    cursor.close()
    conn.close()

if __name__ == "__main__":
    live_log()