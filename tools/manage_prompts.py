#!/usr/bin/env python3
# Filename: manage_prompts.py
import mysql.connector
from configparser import ConfigParser
from getpass import getpass
from pathlib import Path

ACCESS_FILE = "../private/.mariadb_access"
TABLE = "prompts"

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

def create_prompt(cfg):
    import tempfile
    import os
    import subprocess

    print("\n🆕 Neuen Prompt erstellen:")
    name = input("Name: ").strip()
    role = input("Rolle (system|pre|post|analysis|other): ").strip()
    version = input("Version (optional): ").strip()
    description = input("Beschreibung: ").strip()
    tags = input("Tags (komma-separiert, optional): ").strip()

    print("Inhalt: Der Standard-Editor wird geöffnet. Speichern und schließen zum Übernehmen.")
    with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False, mode="w+", encoding="utf-8") as tf:
        editor = os.environ.get("EDITOR", "nano")
        tf_path = tf.name
        tf.write("# Hier Prompt-Inhalt eingeben. Zeilen mit # werden ignoriert.\n")
        tf.flush()
        subprocess.call([editor, tf_path])
        tf.seek(0)
        content_lines = [line for line in tf if not line.strip().startswith("#")]
        content = "".join(content_lines)
        os.unlink(tf_path)

    language = input("Sprache (z. B. de/en) [de]: ").strip() or "de"
    model = input("Bevorzugtes Modell (optional): ").strip()

    conn = get_connection(cfg)
    cursor = conn.cursor()
    cursor.execute(f"""
        INSERT INTO {TABLE} (name, role, version, description, tags, content, language, model)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
          version = VALUES(version),
          description = VALUES(description),
          tags = VALUES(tags),
          content = VALUES(content),
          language = VALUES(language),
          model = VALUES(model),
          updated_at = CURRENT_TIMESTAMP
    """, (name, role, version, description, tags, content, language, model))
    conn.commit()
    cursor.close()
    conn.close()
    print(colored("✅ Prompt erstellt oder aktualisiert.", "GREEN"))

def list_prompts(cfg):
    conn = get_connection(cfg)
    cursor = conn.cursor()
    cursor.execute(f"SELECT id, name, role, version, LEFT(description, 60) AS description FROM {TABLE} ORDER BY id;")
    print("\n📋 Verfügbare Prompts:")
    for row in cursor.fetchall():
        print(row)
    cursor.close()
    conn.close()

def view_prompt(cfg):
    pid = input("🔍 Prompt-ID zum Anzeigen: ")
    if not pid.isdigit():
        return
    conn = get_connection(cfg)
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {TABLE} WHERE id = %s", (pid,))
    result = cursor.fetchone()
    if not result:
        print(colored("❌ Prompt nicht gefunden.", "RED"))
    else:
        for desc, val in zip(cursor.column_names, result):
            print(f"{desc}: {val}")
    cursor.close()
    conn.close()

def edit_field(cfg):
    import tempfile
    import os
    import subprocess

    pid = input("🛠 Prompt-ID: ")
    if not pid.isdigit():
        return

    fields = ["name", "role", "version", "description", "tags", "content", "is_active", "language", "model"]
    print("Feld auswählen:")
    for i, f in enumerate(fields, 1):
        print(f"{i}) {f}")
    print(f"{len(fields) + 1}) Abbrechen")
    
    try:
        choice = int(input("Auswahl: "))
        if choice < 1 or choice > len(fields):
            return
        field = fields[choice - 1]
    except (ValueError, IndexError):
        return

    conn = get_connection(cfg)
    cursor = conn.cursor()

    if field == "content":
        # Lade bisherigen Inhalt
        cursor.execute(f"SELECT content FROM {TABLE} WHERE id = %s", (pid,))
        result = cursor.fetchone()
        if not result:
            print(colored("❌ Prompt nicht gefunden.", "RED"))
            return
        old_content = result[0] or ""

        print("🔧 Editor wird geöffnet...")
        with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False, mode="w+", encoding="utf-8") as tf:
            editor = os.environ.get("EDITOR", "nano")
            tf_path = tf.name
            tf.write(old_content)
            tf.flush()
            subprocess.call([editor, tf_path])
            tf.seek(0)
            new_content = tf.read()
            os.unlink(tf_path)

        value = new_content
    else:
        value = input(f"📝 Neuer Wert für {field}: ")

    cursor.execute(
        f"UPDATE {TABLE} SET {field} = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (value, pid)
    )
    conn.commit()
    cursor.close()
    conn.close()
    print(colored("✅ Aktualisiert.", "GREEN"))

def delete_prompt(cfg):
    pid = input("🗑 Prompt-ID zum Löschen: ")
    if not pid.isdigit():
        return
    confirm = input("⚠️ Sicher? (y/N): ")
    if confirm.lower() != "y":
        return
    conn = get_connection(cfg)
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {TABLE} WHERE id = %s", (pid,))
    conn.commit()
    cursor.close()
    conn.close()
    print(colored(f"❌ Prompt {pid} gelöscht.", "RED"))

def main_menu(cfg):
    while True:
        print("\n====== 📘 Prompt-Verwaltung ======")
        print("1) Prompts anzeigen")
        print("2) Prompt anzeigen (Details)")
        print("3) Einzelnes Feld bearbeiten")
        print("4) Prompt löschen")
        print("5) Neuen Prompt erstellen")
        print("6) Beenden")
        choice = input("Auswahl: ")
        if choice == "1":
            list_prompts(cfg)
        elif choice == "2":
            view_prompt(cfg)
        elif choice == "3":
            edit_field(cfg)
        elif choice == "4":
            delete_prompt(cfg)
        elif choice == "5":
            create_prompt(cfg)
        elif choice == "6":
            print("👋 Ende.")
            break
        else:
            print(colored("Ungültige Eingabe.", "YELLOW"))

if __name__ == "__main__":
    cfg = load_db_config()
    main_menu(cfg)