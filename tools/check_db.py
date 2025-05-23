#!/usr/bin/env python3
import mysql.connector
from configparser import ConfigParser

def load_db_config():
    config = ConfigParser()
    config.read("private/.mariadb_access")
    client = config["client"]
    return {
        "host": client.get("host", "127.0.0.1"),
        "port": int(client.get("port", 3306)),
        "user": client.get("user"),
        "password": client.get("password"),
        "database": client.get("database")
    }

def main():
    cfg = load_db_config()
    conn = mysql.connector.connect(**cfg)
    cursor = conn.cursor()

    table = input("🔍 Welche Tabelle möchtest du anzeigen? ").strip()
    try:
        cursor.execute(f"SELECT * FROM `{table}`")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        print(f"\n📄 Inhalte von Tabelle `{table}`:")
        print("━" * 80)
        print("\t".join(columns))
        print("━" * 80)
        for row in rows:
            print("\t".join(str(col) if col is not None else "NULL" for col in row))
        print("━" * 80)
        print(f"✅ {len(rows)} Zeile(n) angezeigt.")
    except Exception as e:
        print(f"❌ Fehler: {e}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()