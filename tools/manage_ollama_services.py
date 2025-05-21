#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path

AGENT_FILES = {
    "ollama_agent": "ollama_agent.py",
    "telegram_connector_db": "telegram_connector_db.py",
    "ollama_watchdog": "ollama_watchdog.py"
}
SERVICE_DIR = "/etc/systemd/system"

def service_installed(name):
    return Path(SERVICE_DIR, f"{name}.service").exists()

def install_service(name, path):
    service_path = Path(SERVICE_DIR) / f"{name}.service"
    service_content = f'''[Unit]
Description={name}
After=network.target

[Service]
Type=simple
WorkingDirectory={path.parent}
ExecStart={path.parent}/tools/venv/bin/python3 {path}
Restart=always
User=root

[Install]
WantedBy=multi-user.target
'''
    with open(service_path, "w") as f:
        f.write(service_content)
    subprocess.run(["systemctl", "daemon-reexec"])
    subprocess.run(["systemctl", "daemon-reload"])
    subprocess.run(["systemctl", "enable", "--now", f"{name}.service"])
    print(f"Service '{name}.service' wurde eingerichtet und gestartet.")

def manage_service(name):
    while True:
        print(f"Dienst: {name}")
        print("1) Status anzeigen")
        print("2) Starten")
        print("3) Stoppen")
        print("4) Neustarten")
        print("5) Dienst einrichten")
        print("6) Zurück")
        choice = input("Auswahl: ")
        service_name = f"{name}.service"

        if choice == "1":
            subprocess.run(["systemctl", "status", service_name])
        elif choice == "2":
            subprocess.run(["systemctl", "start", service_name])
        elif choice == "3":
            subprocess.run(["systemctl", "stop", service_name])
        elif choice == "4":
            subprocess.run(["systemctl", "restart", service_name])
        elif choice == "5":
            install_service(name, Path(__file__).resolve().parent.parent / AGENT_FILES[name])
        elif choice == "6":
            break
        else:
            print("Ungültige Eingabe.")

def main_menu():
    if os.geteuid() != 0:
        print("Dieses Skript muss als root ausgeführt werden.")
        exit(1)

    while True:
        print("==========================")
        print(" OLLAMA AGENT SERVICE TOOL")
        print("==========================")
        for i, key in enumerate(AGENT_FILES.keys(), start=1):
            print(f"{i}) {key}")
        print("q) Beenden")

        choice = input("Auswahl: ").lower()
        if choice == "q":
            break
        elif choice in map(str, range(1, len(AGENT_FILES)+1)):
            key = list(AGENT_FILES.keys())[int(choice)-1]
            manage_service(key)
        else:
            print("Ungültige Eingabe.")

if __name__ == "__main__":
    main_menu()