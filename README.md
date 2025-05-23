# Ollama Bot Plattform

Ein modulares System zur Verarbeitung von Telegram-Nachrichten über lokale Sprachmodelle (Ollama) mit intelligenter Agentensteuerung und persistenter Datenbanklogik.

---

## ✅ Aktueller Projektstatus (Mai 2025)

### Komponenten

**Telegram Connector** (`telegram_connector_db.py`)

* Telegram-Bot-Empfang
* Nutzererkennung und -neuanlage in `user_profile`
* Speichern von Nachrichten in `conversations`
* Timeout-basierte Konversationsbestätigung

**Ollama Agent** (`ollama_agent.py`)

* Periodisches Pollen nach zugewiesenen Aufgaben
* Kontextaufbau per `pre`- und `post`-Prompts aus der Datenbank
* Kommunikation mit lokalem Ollama-Modell
* Persistenz der Antworten und Metriken
* Eintrag von Systemmetriken in `agent_status`

**Watchdog Dispatcher** (`ollama_watchdog.py`)

* Zuweisung offener Konversationen an passende Agents
* Bewertet `pre`-Prompts anhand Schlagwörter und Keywords
* Auswahl verfügbarer Agents nach Last (CPU/RAM)

**Tools** (`tools/*.py`)

* Verwaltungsskripte für Prompts, Nutzer, Modelle, Agenten, Datenbankzustand
* Setup- und Monitoring-Tools (siehe `tools/README_tools.md` in Planung)

**Datenbanktabellen (aktiv genutzt)**

* `user_profile`, `conversations`, `prompts`, `scripts`
* `agent_log`, `agent_status`, `db_meta`

---

## 📈 Geplante Weiterentwicklungen (Ausblick)

Basierend auf vorhandenen, aber noch nicht genutzten Tabellen und Feldern:

| Tabelle / Spalte              | Ziel / Nutzen                                              |
| ----------------------------- | ---------------------------------------------------------- |
| `prompt_analysis`             | Bewertung der Modellantworten zur Qualitätsmessung         |
| `conversation_tags`           | Thematische Verschlagwortung von Dialogen                  |
| `reasoning_log`               | Speicherung von Modellbegründungen inkl. Confidence-Werten |
| `agent_log.performance_class` | Klassifizierung zur intelligenten Agentenauswahl           |
| `script_usage`                | Nachverfolgung von ausgeführten Scripts pro Nutzer/Kontext |
| `user_profile.language`       | Modellwahl abhängig von Sprachpräferenzen                  |

Diese Strukturen bilden die Grundlage für:

* Automatisiertes Prompt-Routing
* Qualitätssicherung der Antworten
* Performance-Matching von Agents
* Adaptive Modellwahl & Personalisierung

---

## 🚀 Ziele & Vision

* Multi-Agent-System mit dynamischem Load-Balancing
* Kontextabhängiger Prompt-Einsatz und Modellsteuerung
* Transparente Historie, Analyse und Performancebewertung
* Admin-UI zur Verwaltung von Prompts, Nutzern und Scripts
* Modularer Ausbau für Discord, Web-Frontend oder CLI

---

## ⚡ Installation & Start (in Vorbereitung)

> ⚙️ Einrichtungsskripte für Datenbank & Komponenten folgen.

```bash
# Platzhalter
python telegram_connector_db.py &
python ollama_watchdog.py &
python ollama_agent.py &
```

---

## 📊 Lizenz / Mitwirkung

Prototypisches Projekt unter Entwicklung. Feedback willkommen!
