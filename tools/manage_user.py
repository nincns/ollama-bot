#!/usr/bin/env python3
# Filename: user_admin.py

import mysql.connector
from configparser import ConfigParser
from pathlib import Path

ACCESS_FILE = ".mariadb_access"
TABLE = "user_profile"

COLOR = {
    "GREEN": "\033[0;32m",
    "RED": "\033[0;31m",
    "YELLOW": "\033[1;33m",
    "NC": "\033[0m"
}

def colored(msg, color):
    return f"{COLOR[color]}{msg}{COLOR['NC']}"

def load_db_config():
    if not Path(ACCESS_FILE).exists():
        print(colored(f"❌ Zugriffskonfig {ACCESS_FILE} fehlt.", "RED"))
        exit(1)
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

def get_connection(cfg):
    return mysql.connector.connect(**cfg)

def list_users(cfg):
    conn = get_connection(cfg)
    cursor = conn.cursor()

    print("\n🟢 Aktive Benutzer:")
    cursor.execute(f"""
        SELECT user_id, first_name, last_name, role, preferred_language
        FROM {TABLE}
        WHERE role IN ('user', 'admin')
        ORDER BY user_id
    """)
    for row in cursor.fetchall():
        uid, first, last, role, lang = row
        print(f"{uid:<10} {first} {last:<20} ({role}, Sprache: {lang})")

    print("\n🔴 Deaktivierte Benutzer:")
    cursor.execute(f"""
        SELECT user_id, first_name, last_name, role, preferred_language
        FROM {TABLE}
        WHERE role = 'disabled'
        ORDER BY user_id
    """)
    for row in cursor.fetchall():
        uid, first, last, role, lang = row
        print(f"{uid:<10} {first} {last:<20} ({role}, Sprache: {lang})")

    cursor.close()
    conn.close()

def view_user(cfg):
    uid = input("🔍 user_id anzeigen: ")
    if not uid.isdigit():
        return
    conn = get_connection(cfg)
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {TABLE} WHERE user_id = %s", (uid,))
    for desc, val in zip(cursor.column_names, cursor.fetchone() or []):
        print(f"{desc}: {val}")
    cursor.close()
    conn.close()

def edit_user(cfg):
    uid = input("🛠 user_id: ")
    if not uid.isdigit():
        return
    fields = [
        "first_name", "last_name", "messenger_id", "role",
        "preferred_language", "frequent_script_ids", "usage_pattern", "meta_notes"
    ]
    print("Feld auswählen:")
    for i, f in enumerate(fields, 1):
        print(f"{i}) {f}")
    print(f"{len(fields) + 1}) Abbrechen")
    try:
        choice = int(input("Auswahl: "))
        if choice < 1 or choice > len(fields):
            return
        field = fields[choice - 1]
        value = input(f"📝 Neuer Wert für {field}: ")
    except (ValueError, IndexError):
        return
    conn = get_connection(cfg)
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE {TABLE} SET {field} = %s WHERE user_id = %s",
        (value, uid)
    )
    conn.commit()
    cursor.close()
    conn.close()
    print(colored("✅ Benutzer aktualisiert.", "GREEN"))

def delete_user(cfg):
    uid = input("🗑 user_id löschen: ")
    if not uid.isdigit():
        return
    confirm = input("⚠️ Sicher? (y/N): ")
    if confirm.lower() != "y":
        return
    conn = get_connection(cfg)
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {TABLE} WHERE user_id = %s", (uid,))
    conn.commit()
    cursor.close()
    conn.close()
    print(colored(f"❌ Benutzer {uid} gelöscht.", "RED"))

def main_menu(cfg):
    while True:
        print("\n====== 👥 Benutzer-Verwaltung ======")
        print("1) Benutzer anzeigen")
        print("2) Benutzer anzeigen (Details)")
        print("3) Benutzerfeld bearbeiten")
        print("4) Benutzer löschen")
        print("5) Beenden")
        choice = input("Auswahl: ")
        if choice == "1":
            list_users(cfg)
        elif choice == "2":
            view_user(cfg)
        elif choice == "3":
            edit_user(cfg)
        elif choice == "4":
            delete_user(cfg)
        elif choice == "5":
            print("👋 Ende.")
            break
        else:
            print(colored("Ungültige Eingabe.", "YELLOW"))

if __name__ == "__main__":
    cfg = load_db_config()
    main_menu(cfg)