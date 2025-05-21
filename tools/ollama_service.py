#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path

AGENT_FILES = ["ollama_agent.py", "telegram_connector_db.py", "ollama_watchdog.py"]
SERVICE_DIR = "/etc/systemd/system"

def check_service(script_path):
    name = script_path.stem
    service_name = f"{name}.service"
    service_path = Path(SERVICE_DIR) / service_name

    if service_path.exists():
        print(f"✅ Dienst '{service_name}' ist bereits eingerichtet.")
        return

    print(f"⚙️ Dienst '{service_name}' ist noch nicht vorhanden.")
    answer = input(f"→ Möchtest du '{name}' als systemd-Dienst einrichten? (y/N): ").lower()
    if answer != "y":
        return

    service_content = f"""[Unit]
Description={name}
After=network.target

[Service]
Type=simple
WorkingDirectory={script_path.parent}
ExecStart={script_path.parent}/venv/bin/python3 {script_path}
Restart=always
User=root

[Install]
WantedBy=multi-user.target
"""
    # Dienst schreiben
    with open(service_path, "w") as f:
        f.write(service_content)

    subprocess.run(["systemctl", "daemon-reexec"])
    subprocess.run(["systemctl", "daemon-reload"])
    subprocess.run(["systemctl", "enable", "--now", service_name])

    print(f"✅ Dienst '{service_name}' wurde eingerichtet und gestartet.")

def main():
    base_dir = Path(__file__).resolve().parent.parent
    print(f"🔍 Suche nach Agenten im Verzeichnis: {base_dir}")
    for name in AGENT_FILES:
        script = base_dir / name
        if script.exists():
            check_service(script)

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("❌ Dieses Skript muss als root ausgeführt werden.")
        exit(1)
    main()