#!/usr/bin/env python3
# Filename: setup_ollama_db.py
# Version : 1.5
import os
import subprocess
import mysql.connector
from configparser import ConfigParser
from getpass import getpass
from pathlib import Path
import re

VERSION = "1.5"
ACCESS_FILE = ".mariadb_access"
SCHEMA_FILE = "SQL_Tables.sql"
COLOR = {
    "GREEN": "\033[0;32m",
    "RED": "\033[0;31m",
    "YELLOW": "\033[1;33m",
    "NC": "\033[0m"
}

def colored(msg, color):
    return f"{COLOR[color]}{msg}{COLOR['NC']}"

def check_service():
    if subprocess.call(["systemctl", "is-active", "--quiet", "mariadb"]) == 0 or \
       subprocess.call(["systemctl", "is-active", "--quiet", "mysql"]) == 0:
        print(colored("✅ MariaDB-Dienst läuft.", "GREEN"))
    elif subprocess.call(["pgrep", "-x", "mariadbd"], stdout=subprocess.DEVNULL) == 0 or \
         subprocess.call(["pgrep", "-x", "mysqld"], stdout=subprocess.DEVNULL) == 0:
        print(colored("✅ MariaDB/MySQL-Prozess läuft.", "GREEN"))
    else:
        print(colored("❌ MariaDB/MySQL Dienst nicht erkannt.", "RED"))
        exit(1)

def parse_access():
    config = ConfigParser()
    config.read(ACCESS_FILE)
    client = config["client"]
    if not client.get("user") or not client.get("database"):
        print(colored(f"❌ DB‑Zugangsdaten unvollständig. Bitte {ACCESS_FILE} prüfen.", "RED"))
        exit(1)
    return {
        "host": client.get("host", "127.0.0.1"),
        "port": int(client.get("port", 3306)),
        "user": client.get("user"),
        "password": client.get("password"),
        "database": client.get("database")
    }

def exec_sql(cfg, sql):
    try:
        conn = mysql.connector.connect(**cfg)
        cursor = conn.cursor()
        for stmt in sql.split(";"):
            if stmt.strip():
                cursor.execute(stmt)
        conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        print(colored("❌ Fehler bei SQL-Ausführung:", "RED"), err)
        exit(1)

def read_schema_sql():
    with open(SCHEMA_FILE, "r") as f:
        return f.read()

def add_column_if_not_exists(cfg, table, column, coltype):
    conn = mysql.connector.connect(**cfg)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
    """, (cfg['database'], table, column))
    if cursor.fetchone()[0] == 0:
        print(colored(f"→ Spalte '{column}' wird zu '{table}' hinzugefügt...", "YELLOW"))
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
            conn.commit()
        except mysql.connector.Error as err:
            print(colored(f"❌ Fehler beim Hinzufügen von {column} zu {table}: {err}", "RED"))
    else:
        print(colored(f"✔ Spalte '{column}' in '{table}' existiert bereits.", "GREEN"))
    cursor.close()
    conn.close()

def create_or_update_tables(cfg):
    print(colored(f"→ Tabellen werden erstellt oder aktualisiert (Version {VERSION})...", "GREEN"))
    exec_sql(cfg, read_schema_sql())
    exec_sql(cfg, f"INSERT IGNORE INTO db_meta (version) VALUES ('{VERSION}')")

    # Dynamisches Parsing aller Spalten aus dem SQL-File
    with open(SCHEMA_FILE, "r") as f:
        sql = f.read()

    schema = {}
    table_blocks = re.findall(
        r'CREATE TABLE IF NOT EXISTS\s+`?(\w+)`?\s*\((.*?)\);',
        sql,
        re.DOTALL | re.IGNORECASE
    )

    for table_name, body in table_blocks:
        parts = re.split(r',\s*(?![^()]*\))', body.strip())
        for part in parts:
            line = part.strip()
            if line.upper().startswith(('PRIMARY ', 'FOREIGN ', 'UNIQUE ', 'KEY ', 'CONSTRAINT ')):
                continue
            match = re.match(r'`?(\w+)`?\s+(.*)', line)
            if match:
                col_name, definition = match.groups()
                add_column_if_not_exists(cfg, table_name, col_name, definition)

def wipe_tables(cfg):
    print(colored("[WARNUNG] Alle Tabellen werden geleert (DELETE)...", "RED"))
    exclude_tables = set()  # Optional

    try:
        conn = mysql.connector.connect(**cfg)
        cursor = conn.cursor()

        cursor.execute("SET FOREIGN_KEY_CHECKS=0")

        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            if table not in exclude_tables:
                try:
                    cursor.execute(f"DELETE FROM `{table}`")
                    print(colored(f"🧹 Tabelle geleert: {table}", "YELLOW"))
                except mysql.connector.Error as err:
                    print(colored(f"❌ Fehler bei {table}: {err}", "RED"))

        cursor.execute("SET FOREIGN_KEY_CHECKS=1")
        conn.commit()
        cursor.close()
        conn.close()
        print(colored("✅ Alle Tabellen wurden erfolgreich geleert.", "GREEN"))

    except mysql.connector.Error as err:
        print(colored("❌ Fehler beim Leeren der Tabellen:", "RED"), err)

def setup_db_user():
    print("Root-Zugang zur MariaDB wird benötigt")
    root_user = input("Root-Benutzer [root]: ") or "root"
    root_pass = getpass("Root-Passwort: ")

    new_db = input("Datenbankname: ")
    new_user = input("Neuer DB-User: ")
    new_pass = getpass("Neues Passwort für DB-User: ")
    new_host = input("Host (z.B. 127.0.0.1): ") or "127.0.0.1"

    print(colored("→ Verbindungstest mit Root...", "GREEN"))
    try:
        conn = mysql.connector.connect(user=root_user, password=root_pass)
    except mysql.connector.Error as err:
        print(colored("❌ Verbindung fehlgeschlagen.", "RED"), err)
        return

    cursor = conn.cursor()
    try:
        for _ in cursor.execute(f"""
            CREATE DATABASE IF NOT EXISTS `{new_db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            CREATE USER IF NOT EXISTS '{new_user}'@'{new_host}' IDENTIFIED BY '{new_pass}';
            ALTER USER '{new_user}'@'{new_host}' IDENTIFIED BY '{new_pass}';
            GRANT ALL PRIVILEGES ON `{new_db}`.* TO '{new_user}'@'{new_host}';
            FLUSH PRIVILEGES;
        """, multi=True):
            pass  # Ergebnisse bewusst ignorieren
    except mysql.connector.Error as err:
        print(colored("❌ Fehler beim Ausführen der SQL-Befehle.", "RED"), err)
        cursor.close()
        conn.close()
        return

    conn.commit()
    cursor.close()
    conn.close()
    print(colored("🎉 Datenbank + Benutzer erfolgreich eingerichtet.", "GREEN"))

    if Path(ACCESS_FILE).exists():
        overwrite = input(f"⚠️ Die Datei {ACCESS_FILE} existiert bereits. Überschreiben? (y/N): ").lower()
        if overwrite != "y":
            print(colored("❌ Schreiben abgebrochen.", "YELLOW"))
            return

    if input(f"Soll die Datei {ACCESS_FILE} automatisch geschrieben werden? (y/n) ").lower() == "y":
        Path(ACCESS_FILE).write_text(f"""[client]
host = {new_host}
port = 3306
user = {new_user}
password = {new_pass}
database = {new_db}
""")
        os.chmod(ACCESS_FILE, 0o600)
        print(colored(f"✅ {ACCESS_FILE} gespeichert.", "GREEN"))


def check_status(cfg):
    print(colored("→ Verbindungsprüfung zur Datenbank...", "GREEN"))
    try:
        conn = mysql.connector.connect(**cfg)
    except mysql.connector.Error:
        print(colored("❌ Verbindung zur Datenbank fehlgeschlagen.", "RED"))
        return

    cursor = conn.cursor()

    print("\n📊 Verfügbare Datenbanken:")
    cursor.execute("SHOW DATABASES")
    for (db,) in cursor.fetchall():
        print(f"- {db}")

    print(f"\n📦 Tabellenübersicht für Datenbank `{cfg['database']}`:\n")
    cursor.execute("""
        SELECT 
            table_name, table_rows,
            ROUND(data_length/1024/1024, 2) AS data_mb,
            ROUND(index_length/1024/1024, 2) AS index_mb,
            ROUND((data_length + index_length)/1024/1024, 2) AS total_mb
        FROM information_schema.tables
        WHERE table_schema = %s
        ORDER BY total_mb DESC;
    """, (cfg["database"],))
    tables = cursor.fetchall()

    for table_name, rows, data_mb, index_mb, total_mb in tables:
        print(f"{table_name:<30} {rows:>8} Zeilen  {data_mb:>6} MB Daten")
        
        # Spalteninformationen
        cursor.execute("""
            SELECT column_name, column_type 
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """, (cfg["database"], table_name))
        columns = cursor.fetchall()
        if columns:
            print("  Spalten:")
            for name, col_type in columns:
                print(f"    - {name}: {col_type}")
        print()

    cursor.close()
    conn.close()

def sync_schema(cfg):
    print(colored("→ SQL-Schema wird mit Datenbank abgeglichen...", "YELLOW"))
    with open(SCHEMA_FILE, 'r') as f:
        sql = f.read()

    schema = {}
    table_blocks = re.findall(
        r'CREATE TABLE IF NOT EXISTS\s+`?(\w+)`?\s*\((.*?)\);',
        sql,
        re.DOTALL | re.IGNORECASE
    )

    # Parse Tabellen aus SQL
    for table_name, body in table_blocks:
        columns = []
        parts = re.split(r',\s*(?![^()]*\))', body.strip())
        for part in parts:
            line = part.strip()
            if line.upper().startswith(('PRIMARY ', 'FOREIGN ', 'UNIQUE ', 'KEY ', 'CONSTRAINT ')):
                continue
            match = re.match(r'`?(\w+)`?\s+(.*)', line)
            if match:
                col, definition = match.groups()
                columns.append((col.strip(), definition.strip()))
        schema[table_name] = (columns, f'CREATE TABLE IF NOT EXISTS `{table_name}` ({body});')

    conn = mysql.connector.connect(**cfg)
    cursor = conn.cursor()

    # Vorab alle existierenden Tabellen abfragen
    cursor.execute("SHOW TABLES")
    existing_tables = set(row[0] for row in cursor.fetchall())

    for table, (columns, create_stmt) in schema.items():
        if table not in existing_tables:
            print(colored(f"➕ Erstelle fehlende Tabelle: {table}", "YELLOW"))
            try:
                cursor.execute(create_stmt)
                conn.commit()
            except Exception as e:
                print(colored(f"❌ Fehler beim Erstellen von {table}: {e}", "RED"))
            continue  # Spaltenprüfung überspringen – frisch erstellt

        for col, definition in columns:
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
            """, (cfg['database'], table, col))
            exists = cursor.fetchone()[0]
            if not exists:
                print(colored(f"➕ Hinzufügen: {table}.{col}", "YELLOW"))
                try:
                    cursor.execute(f'ALTER TABLE `{table}` ADD COLUMN `{col}` {definition}')
                    conn.commit()
                except Exception as e:
                    print(colored(f"❌ Fehler bei {table}.{col}: {e}", "RED"))
            else:
                print(colored(f"✅ {table}.{col} existiert bereits", "GREEN"))

    cursor.close()
    conn.close()

def compare_schema(cfg):
    print(colored("→ Starte SCHEMA-VERGLEICH (read-only)…", "YELLOW"))
    with open(SCHEMA_FILE, 'r') as f:
        sql = f.read()

    expected_schema = re.findall(
        r'CREATE TABLE IF NOT EXISTS\s+`?(\w+)`?\s*\((.*?)\);',
        sql,
        re.DOTALL | re.IGNORECASE
    )

    conn = mysql.connector.connect(**cfg)
    cursor = conn.cursor()

    for table, _ in expected_schema:
        print(f"\n📄 Tabelle: {table}")
        cursor.execute("""
            SELECT column_name, column_type
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """, (cfg['database'], table))
        actual_columns = {name: ctype for name, ctype in cursor.fetchall()}

        # Finde die erwarteten Spalten aus dem SQL-Block
        match = re.search(
            rf'CREATE TABLE IF NOT EXISTS\s+`?{table}`?\s*\((.*?)\);',
            sql,
            re.DOTALL | re.IGNORECASE
        )
        if match:
            col_block = match.group(1)
            lines = re.split(r',\s*(?![^()]*\))', col_block)
            for line in lines:
                line = line.strip()
                if line.upper().startswith(('PRIMARY', 'FOREIGN', 'KEY', 'UNIQUE', 'CONSTRAINT')):
                    continue
                col_match = re.match(r'`?(\w+)`?\s+(.*)', line)
                if col_match:
                    col_name, expected_type = col_match.groups()
                    actual_type = actual_columns.get(col_name)
                    if actual_type:
                        print(colored(f"  ✔ {col_name} vorhanden – Typ: {actual_type}", "GREEN"))
                    else:
                        print(colored(f"  ✖ {col_name} fehlt in DB", "RED"))

    cursor.close()
    conn.close()

def main_menu():
    while True:
        os.system("clear")
        print("""
==============================
  OLLAMA BOT DB SETUP TOOL
==============================

📦 SETUP & KONFIGURATION
0) Neue Datenbank + Benutzer anlegen
1) Tabellenstruktur erstellen (Initial-Setup)
2) SQL-Schema abgleichen & aktualisieren

🧹 WARTUNG & REINIGUNG
3) Tabellen leeren (Wipe – Struktur bleibt erhalten)

📊 STATUS & ANALYSE
4) Verbindung & Tabellenstatus prüfen
5) Schema vergleichen (Read-Only)

🚪 BEENDEN
6) Beenden
""")
        choice = input("Auswahl: ")
        if choice == "0":
            check_service()
            setup_db_user()
        elif choice == "1":
            if Path(ACCESS_FILE).exists():
                cfg = parse_access()
                create_or_update_tables(cfg)
            else:
                print(colored(f"{ACCESS_FILE} nicht gefunden.", "RED"))
        elif choice == "2":
            if Path(ACCESS_FILE).exists():
                cfg = parse_access()
                sync_schema(cfg)
            else:
                print(colored(f"{ACCESS_FILE} nicht gefunden.", "RED"))
        elif choice == "3":
            if Path(ACCESS_FILE).exists():
                cfg = parse_access()
                wipe_tables(cfg)
            else:
                print(colored(f"{ACCESS_FILE} nicht gefunden.", "RED"))
        elif choice == "4":
            if Path(ACCESS_FILE).exists():
                cfg = parse_access()
                check_status(cfg)
            else:
                print(colored(f"{ACCESS_FILE} nicht gefunden.", "RED"))
        elif choice == "5":
            if Path(ACCESS_FILE).exists():
                cfg = parse_access()
                compare_schema(cfg)
            else:
                print(colored(f"{ACCESS_FILE} nicht gefunden.", "RED"))
        elif choice == "6":
            print("Beendet.")
            break
        else:
            print(colored("Ungültige Eingabe.", "YELLOW"))
        input("\nWeiter mit ENTER...")

if __name__ == "__main__":
    check_service()
    main_menu()