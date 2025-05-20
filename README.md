# Roadmap: Ollama Bot Plattform (Telegram Connector + Agent + Datenbank)

## ✅ Aktueller Funktionsstand

### Telegram-Connector

* Empfang von Nachrichten über Telegram-Bot
* Nutzer-Authentifizierung (Neuanlage in `user_profile`)
* Speicherung neuer Nachrichten in `conversations`
* Gruppierung von Konversationen anhand Zeit/Trigger

### Ollama-Agent

* Prüft Datenbank auf neue `conversations`-Einträge
* Nutzt lokales Ollama-Modell zur Sprachverarbeitung
* Verarbeitet Kontext mit Pre-/Postprompt (derzeit statisch)
* Misst eigene Last (CPU, Speicher, Threads)
* Speichert Ergebnis + Metriken in Datenbank

### Datenbanksystem (MariaDB)

* Struktur für Nutzer, Prompts, Agenten, Konversationen
* Überwiegend genutzt:

  * `user_profile`, `conversations`, `prompts`, `agent_log`
* Schema versioniert mit `db_meta`

---

## 🔄 Ungenutzte Tabellen & Spalten (aus `SQL_Tables.sql`)

| Tabelle / Spalte              | Zweck laut Konzeption                  | Status                |
| ----------------------------- | -------------------------------------- | --------------------- |
| `scripts`                     | Verwaltung von Shell/Python-Skripten   | ungenutzt             |
| `prompt_analysis`             | Qualitätsbewertung von Modellantworten | ungenutzt             |
| `conversation_tags`           | Tagging zur thematischen Einordnung    | ungenutzt             |
| `user_profile.language`       | Nutzer-Sprachprofil zur Modellwahl     | ungenutzt             |
| `agent_log.performance_class` | Leistungsbewertung für Agent-Matching  | vorgesehen, aber leer |

Diese Felder können für dynamische Modellwahl, Qualitätskontrolle und Kontextverarbeitung genutzt werden.

---

## 🔧 Statisch definierte Variablen (Verbesserungspotenzial)

| Variable / Parameter           | Aktuell                      | Potenzial                      |
| ------------------------------ | ---------------------------- | ------------------------------ |
| `OLLAMA_URL`                   | Fester Wert                  | Dynamische Zielwahl pro Agent  |
| `AGENT_NAME`                   | Hostname                     | Gruppierung in Klassen/Rollen  |
| Modellwahl in Request          | Statisch (z. B. `tinyllama`) | DB-basiert per Sprache/Kontext |
| Prompt-Auswahl                 | Hart kodiert                 | Laden aus `prompts`-Tabelle    |
| Zeit-Timeout Telegram (15 Min) | Konstant                     | Pro Benutzer konfigurierbar    |

---

## 🚀 Nächste Entwicklungsschritte

### 1. Watchdog-Prozess

* Zentraler Dienst, der neue Konversationseinträge bewertet
* Analyse von:

  * Sprache (aus `user_profile.language` oder NLP)
  * Komplexität (Tokenanzahl, Prompttyp)
  * Prompt-Metadaten (`prompts`, `prompt_analysis`)
  * Agent-Auslastung (`agent_log`, Live-Daten via API oder DB)
* Entscheidung für geeigneten Agent:

  * Performance Class (CPU/RAM)
  * Spezialisierung (Modellgröße, Rolle)
  * Verfügbarkeit (online, frei)
* Automatischer Lock: `locked_by_agent`

### 2. Dynamische Modellwahl

* Sprachabhängige Auswahl via `user_profile.language`
* Modellgröße nach Komplexitätsabschätzung
* Direktwahl durch Nutzer möglich (z. B. via Befehl)
* Nutzung verschiedener lokaler oder Remote-Modelle

### 3. Kontextoptimierung

* Pre-/Postprompts dynamisch aus `prompts` laden
* Nutzung von Tags zur besseren Steuerung
* Verknüpfung mit `prompt_analysis` zur Qualitätsbewertung

### 4. Nutzung der Tabelle `scripts`

* Steuerung interner Aufgaben als Script-Objekte
* Metadaten (Typ, Parameter, Version)
* Automatisierter Aufruf durch Agenten

### 5. Tagging & Analyse

* Automatisches Tagging durch NLP oder vordefinierte Liste
* Speicherung in `conversation_tags`
* Auswertung nach Themen, Trends, Nutzerverhalten

---

## ✍️ Weiterführende Ideen

* Sprachmodell-Wechsel basierend auf Kontext-Stil (z. B. sachlich, kreativ, technisch)
* Long-Term Memory per kontextueller DB-Referenzierung
* Nutzer-Dashboards für Prompt- und Scriptverwaltung
* Versionierung von Antworten zur Qualitätsentwicklung
