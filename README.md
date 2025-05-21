# Roadmap: Ollama Bot Plattform (Telegram Connector + Agent + Datenbank)

## ✅ Aktueller Funktionsstand

### Telegram-Connector

* Nachrichtenempfang via Telegram-Bot
* Nutzer-Authentifizierung und -Neuanlage (`user_profile`)
* Speicherung neuer Nachrichten in `conversations`
* Gruppierung von Konversationen nach Zeit/Trigger

### Ollama-Agent

* Verarbeitung neuer `conversations`-Einträge
* Nutzung lokaler Ollama-Modelle
* Kontextaufbau mit Pre-/Postprompts (statisch aus DB)
* Speicherung von Ergebnissen & Metriken in Datenbank
* Eigene Lastmessung (CPU, RAM, Threads)

### Datenbanksystem (MariaDB)

* Genutzte Tabellen: `user_profile`, `conversations`, `prompts`, `agent_log`, `db_meta`
* Teilweise genutzt / vorbereitet: `scripts`, `conversation_log`, `agent_status`, `script_usage`, `reasoning_log`
* Nicht oder nur konzeptionell vorhanden: `prompt_analysis`, `conversation_tags`, `performance_class`

---

## 🔄 Analyse: Tabellen ohne aktuelle Funktion

| Tabelle / Spalte              | Zweck laut Konzeption                | Status                  |
| ----------------------------- | ------------------------------------ | ----------------------- |
| `scripts`                     | Verwaltung von Shell/Python-Skripten | vorgesehen              |
| `prompt_analysis`             | Bewertet Modellantworten qualitativ  | fehlt im Schema         |
| `conversation_tags`           | thematische Klassifikation           | fehlt im Schema         |
| `user_profile.language`       | Sprachwahl für Modellauswahl         | existiert, ungenutzt    |
| `agent_log.performance_class` | Leistungsklasse für Matching         | nicht vorhanden         |
| `reasoning_log`               | Modellgründe + Confidence Score      | vorhanden, ungenutzt    |
| `agent_status`                | Live-Zustand und Metriken pro Agent  | vorhanden, aber inaktiv |

---

## 🔧 Statisch definierte Parameter mit Potenzial zur Dynamisierung

| Parameter                 | Aktuell                | Potenzial                        |
| ------------------------- | ---------------------- | -------------------------------- |
| `OLLAMA_URL`              | fix                    | dynamisch pro Agent auswählbar   |
| `AGENT_NAME`              | Hostname               | Klassifizierbar für Matching     |
| Modellwahl im Prompt      | statisch (`tinyllama`) | dynamisch aus `user_profile`     |
| Prompt-Auswahl            | manuell                | über `prompts`-Tabelle steuerbar |
| Timeout Telegram (15 Min) | fix                    | konfigurierbar pro Nutzer        |

---

## 🚀 Erweiterte Roadmap (Stand: Mai 2025)

### Entwicklungsstand (nach Implementierung)

* [x] Telegram Connector (inkl. Nutzeranlage, Nachrichtenempfang)
* [x] DB-Modell für Konversationen, Prompts, Nutzer
* [x] Ollama Agent: Verarbeitung neuer Einträge mit Statuswechsel
* [x] Kontextbildung mit Pre-/Postprompts
* \[\~] Watchdog: Grundstruktur zur Verteilung vorhanden

### Offene Erweiterungen / geplante Features

* [ ] Priorisierung nach Keywords, Tokenanzahl, Triggern
* [ ] Agent-Auswertung über `agent_status` + `performance_class`
* [ ] Promptanalyse über `prompt_analysis` für Qualitätsmetriken
* [ ] Nutzung von `scripts` & `script_usage` bei bestimmten Anfragen
* [ ] Einsatz von `reasoning_log` für Modell-Erklärungen
* [ ] Aufbau eines Tagging-Systems über `conversation_tags`
* [ ] Konfigurierbare Timeout- und Modellwahl pro Nutzer
* [ ] Admin-Weboberfläche zur Prompt-, Script- und Userpflege

---

## ✍️ Weiterführende Ideen

* Modellwechsel anhand Kontextstimmung (technisch, kreativ etc.)
* Long-Term Memory per SQL-Referenzen auf frühere Threads
* Transparente Agent-Matching-Logik für Load-Balancing
* Tokenbudgetierung für Kontextlänge + Qualität
