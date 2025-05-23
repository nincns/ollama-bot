
#!/usr/bin/env python3
# Filename: manage_models.py
import mysql.connector
import configparser
from tabulate import tabulate
import textwrap

ACCESS_FILE = "../private/.mariadb_access"
TABLE = "model_catalog"

def connect_db():
    config = configparser.ConfigParser()
    config.read(ACCESS_FILE)
    creds = config['client']
    return mysql.connector.connect(
        host=creds['host'],
        port=int(creds.get('port', 3306)),
        user=creds['user'],
        password=creds['password'],
        database=creds['database']
    )

def wrap_text(text, width=60):
    if isinstance(text, str) and len(text) > width:
        return '\n'.join(textwrap.wrap(text, width))
    return text

def list_models():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT id, display_name, model_name, version, provider, model_size, language_support,
               supports_chat, supports_reasoning, supports_knowledge,
               requires_gpu, min_ram_mb, min_vram_mb,
               tags, is_active
        FROM {TABLE}
    """)
    rows = cursor.fetchall()
    headers = [i[0] for i in cursor.description]
    wrapped_rows = [tuple(wrap_text(col) for col in row) for row in rows]
    print(tabulate(wrapped_rows, headers=headers, tablefmt="fancy_grid"))
    cursor.close()
    conn.close()

def prompt_input(prompt, example, default=None):
    print(f"{prompt}\nBeispiel: {example}")
    if default:
        return input(f"Eingabe [{default}]: ").strip() or default
    return input("Eingabe: ").strip()

def add_model():
    print("\n--- Neues Modell hinzufügen ---")
    model_name = prompt_input("Interner Modellname:", "tinyllama-1.1b-gguf")
    display_name = prompt_input("Anzeigename:", "TinyLLaMA Deutsch")
    provider = prompt_input("Anbieter (ollama, openai, local, huggingface):", "local")
    version = prompt_input("Versionsbezeichnung:", "v1")
    model_size = prompt_input("Modellgröße (small, medium, large, xl):", "small")
    language_support = prompt_input("Unterstützte Sprachen (kommasepariert):", "de,en")
    supports_chat = prompt_input("Unterstützt Chat (0/1):", "1")
    supports_reasoning = prompt_input("Unterstützt Reasoning (0/1):", "0")
    supports_knowledge = prompt_input("Unterstützt Wissensabfragen (0/1):", "0")
    requires_gpu = prompt_input("Benötigt GPU (0/1):", "0")
    min_ram_mb = prompt_input("Min. RAM in MB:", "0")
    min_vram_mb = prompt_input("Min. VRAM in MB:", "0")
    tags = prompt_input("Tags/Stichworte kommasepariert:", "deutsch, schnell, low-resource")
    notes = prompt_input("Zusatzinformationen:", "nur für Testzwecke")

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(f"""
        INSERT INTO {TABLE} (
            model_name, display_name, provider, version, model_size, language_support,
            supports_chat, supports_reasoning, supports_knowledge,
            requires_gpu, min_ram_mb, min_vram_mb,
            tags, notes
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (model_name, display_name, provider, version, model_size, language_support,
          int(supports_chat), int(supports_reasoning), int(supports_knowledge),
          int(requires_gpu), int(min_ram_mb), int(min_vram_mb), tags, notes))
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
        if col.startswith('supports_') or col in ('is_active', 'requires_gpu', 'min_ram_mb', 'min_vram_mb'):
            updated.append(int(new_val))
        else:
            updated.append(str(new_val))

    update_clause = ", ".join([f"{col} = %s" for col in columns if col != "id"])
    cursor.execute(f"UPDATE {TABLE} SET {update_clause} WHERE id = %s", (*updated, model_id))
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
