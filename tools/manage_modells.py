#!/usr/bin/env python3
# Filename: manage_modells.py
import mysql.connector
from tabulate import tabulate

ACCESS_FILE = "../private/.mariadb_access"
TABLE = "modell_catalog"

def connect_db():
    with open(ACCESS_FILE, 'r') as f:
        creds = dict(line.strip().split('=', 1) for line in f if '=' in line)
    return mysql.connector.connect(
        host=creds['host'],
        user=creds['user'],
        password=creds['password'],
        database=creds['database']
    )

def list_models():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {TABLE}")
    rows = cursor.fetchall()
    headers = [i[0] for i in cursor.description]
    print(tabulate(rows, headers=headers, tablefmt="fancy_grid"))
    cursor.close()
    conn.close()

def prompt_input(prompt, example, default=None):
    print(f"{prompt}\nBeispiel: {example}")
    if default:
        return input(f"Eingabe [{default}]: ").strip() or default
    return input("Eingabe: ").strip()

def add_model():
    print("\n--- Neues Modell hinzufügen ---")
    name = prompt_input("Name des Modells:", "tinyllama-1.1b-gguf")
    description = prompt_input("Kurzbeschreibung des Modells:", "Kleines Modell für einfache deutsche Anfragen, sehr schnell.")
    context_size = prompt_input("Maximale Kontextgröße (Tokens):", "2048")
    quantization = prompt_input("Quantisierungsstufe:", "Q4_K_M")
    hardware_hint = prompt_input("Empfohlene Hardware (optional):", "mind. 8 GB RAM, CPU ausreichend")
    tags = prompt_input("Tags/Stichworte kommasepariert:", "deutsch, schnell, low-resource")

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(f"""
        INSERT INTO {TABLE} (name, description, context_size, quantization, hardware_hint, tags)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (name, description, context_size, quantization, hardware_hint, tags))
    conn.commit()
    cursor.close()
    conn.close()
    print("\n✅ Modell wurde erfolgreich hinzugefügt.")

def edit_model():
    print("\n--- Modell bearbeiten ---")
    list_models()
    model_id = input("\nID des zu bearbeitenden Modells: ").strip()

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {TABLE} WHERE id = %s", (model_id,))
    model = cursor.fetchone()
    if not model:
        print("❌ Modell-ID nicht gefunden.")
        return

    columns = [i[0] for i in cursor.description]
    updated = []
    for i, col in enumerate(columns):
        if col == "id":
            continue
        new_val = prompt_input(f"{col.replace('_', ' ').capitalize()}:", f"{model[i]}", default=model[i])
        updated.append(new_val)

    cursor.execute(f"""
        UPDATE {TABLE} SET
            name = %s,
            description = %s,
            context_size = %s,
            quantization = %s,
            hardware_hint = %s,
            tags = %s
        WHERE id = %s
    """, (*updated, model_id))
    conn.commit()
    cursor.close()
    conn.close()
    print("\n✅ Modell wurde erfolgreich aktualisiert.")

def main():
    while True:
        print("\n=== Sprachmodell-Katalog Management ===")
        print("1. Modelle auflisten")
        print("2. Neues Modell hinzufügen")
        print("3. Bestehendes Modell bearbeiten")
        print("0. Beenden")
        choice = input("Auswahl: ").strip()

        if choice == '1':
            list_models()
        elif choice == '2':
            add_model()
        elif choice == '3':
            edit_model()
        elif choice == '0':
            break
        else:
            print("Ungültige Auswahl.")

if __name__ == '__main__':
    main()
