# MCP Task Manager

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?style=for-the-badge&logo=python&logoColor=white)
![FastMCP](https://img.shields.io/badge/FastMCP-MCP%201.27+-orange.svg?style=for-the-badge)
![SQLite](https://img.shields.io/badge/SQLite-persistenza-lightgrey.svg?style=for-the-badge&logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)

Un server **MCP (Model Context Protocol)** personalizzato per la gestione di task, scritto in Python con [FastMCP](https://github.com/jlowin/fastmcp). Espone tool, resource e prompt che permettono a qualsiasi client MCP compatibile (Claude Desktop, VS Code Copilot Agent Mode) di creare, consultare, completare ed eliminare task con persistenza su SQLite.

---

## Contesto: vibecoding con Antigravity

Questo progetto è un esercizio di **vibecoding** — un approccio alla creazione di software in cui l'idea guida il flusso di lavoro e l'AI affianca lo sviluppo in ogni fase, dalla definizione delle specifiche alla scrittura del codice.

È stato realizzato nell'ambito delle attività di [**Antigravity**](https://www.antigravity.it) per esplorare concretamente il Model Context Protocol: come costruire un server MCP da zero, come esporre tool, resource e prompt, e come integrarli in un client AI reale.

---

## Architettura

Il server è sviluppato con un approccio modulare attorno a tre primitive MCP:

- **Tool** — azioni che il modello può invocare per modificare o consultare lo stato del sistema.
- **Resource** — dati strutturati che il modello può leggere come contesto.
- **Prompt** — template parametrici che iniettano dati reali nel testo prima di passarlo al modello.

### Tool esposti

| Nome | Tipo | Descrizione |
|---|---|---|
| `crea_task` | write | Crea un nuovo task con titolo, descrizione e priorità |
| `elenca_tasks` | read | Elenca i task filtrati per stato (`aperto` / `chiuso` / `tutti`) |
| `chiudi_task` | write | Segna un task come completato dato il suo `task_id` |
| `elimina_task` | destructive | Rimuove definitivamente un task dal database |

### Resource

| URI | Descrizione |
|---|---|
| `tasks://riepilogo` | JSON aggregato con totale, aperti, chiusi e lista completa |

### Prompt

| Nome | Parametri | Descrizione |
|---|---|---|
| `pianifica_sprint` | `team`, `durata_giorni` | Genera un prompt per agile coach con i task aperti iniettati in tempo reale |

### Stack tecnico

- **[FastMCP](https://github.com/jlowin/fastmcp)** — framework Python per server MCP (SDK `mcp[cli] >= 1.6.0`)
- **SQLite** — persistenza locale con thread-safety tramite `threading.Lock`
- **Pydantic v2** — validazione degli input con `Field` constraints
- **[uv](https://github.com/astral-sh/uv)** — package manager Python moderno

---

## Installazione

### Prerequisiti

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) installato globalmente
- Node.js (solo per MCP Inspector, opzionale)

### Clona il repository

```bash
git clone https://github.com/tuo-utente/mcp-task-manager.git
cd mcp-task-manager
```

### Crea l'ambiente virtuale e installa le dipendenze

```bash
uv venv
uv sync
```

In alternativa con pip:

```bash
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install "mcp[cli]>=1.6.0" "pydantic>=2.0"
```

---

## Avvio del server

### Metodo 1 — tramite uv (consigliato)

```bash
uv run python server.py
```

### Metodo 2 — con l'ambiente virtuale attivo

```bash
# Attiva il venv (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Avvia il server
python server.py
```

### Metodo 3 — tramite run_server.bat (Windows)

Il file `run_server.bat` usa percorsi relativi alla propria posizione (`%~dp0`), quindi funziona in qualsiasi cartella in cui sia clonato il repo — nessuna modifica necessaria.

```powershell
.\run_server.bat
```

Contenuto del file:

```bat
@echo off
REM Usa percorsi relativi alla posizione di questo file (%~dp0),
REM quindi funziona in qualsiasi cartella in cui sia clonato il repo.

"%~dp0.venv\Scripts\python.exe" "%~dp0server.py"
```

La variabile `%~dp0` si espande automaticamente al percorso assoluto della cartella che contiene il bat, con la barra finale inclusa. Il server si avvia usando il Python del venv locale (`mcp-task-manager\.venv\Scripts\python.exe`) e il `server.py` nella stessa cartella.

> **Nota:** il server usa il trasporto `stdio`, quindi non produce output visibile nel terminale quando avviato direttamente. È progettato per essere gestito da un client MCP (Claude Desktop, VS Code). Per testarlo interattivamente usa MCP Inspector (sezione successiva).

Il database `tasks.db` viene creato automaticamente nella stessa cartella del server al primo avvio.

---

## Test con MCP Inspector

[MCP Inspector](https://github.com/modelcontextprotocol/inspector) è lo strumento ufficiale per testare un server MCP in modo interattivo, senza bisogno di un client AI.

### Avvio dell'Inspector

**Metodo rapido con `mcp dev` (richiede il venv attivo):**

```bash
# Attiva il venv
.venv\Scripts\Activate.ps1

# Lancia l'inspector
mcp dev server.py
```

**Metodo alternativo con npx:**

```powershell
npx @modelcontextprotocol/inspector .\run_server.bat
```

In entrambi i casi il browser si apre automaticamente su `http://127.0.0.1:6274`. Se non si apre, copia e incolla l'URL dal terminale (con `npx` l'URL include un token di autenticazione).

> **Warning Node:** se vedi `Unsupported engine: node >=22.7.5`, non blocca il funzionamento. Per eliminarlo aggiorna Node con `nvm install 22 && nvm use 22`.

### Pannelli disponibili

Dopo aver cliccato **Connect** (lo stato deve diventare verde):

- **Tools** — invoca i tool con parametri liberi e visualizza il JSON di risposta grezzo.
- **Resources** — legge le resource esposte dal server e ne mostra il contenuto aggiornato.
- **Prompts** — compila i parametri e clicca **Get Prompt** per vedere il testo generato con i dati reali iniettati.
- **Stderr** — output del processo Python. Primo punto di controllo in caso di errore.

Se la connessione fallisce, controlla il pannello **Stderr**: un `ModuleNotFoundError: mcp` indica che le dipendenze non sono installate nel venv corretto. Esegui `.venv\Scripts\pip install "mcp[cli]"`.

---

## Esempi di prompt per il test

La sequenza seguente copre tutti i tool, la resource e il prompt. Eseguila nell'ordine indicato dall'Inspector (tab **Tools**) per verificare che il server si comporti correttamente.

### Tool: `crea_task`

**Test 1 — task ad alta priorità**
```json
{
  "titolo": "Scrivere i test unitari",
  "descrizione": "Coprire almeno l'80% del codice con pytest",
  "priorita": "alta"
}
```
Risposta attesa: oggetto task con `"id": 1` e `"stato": "aperto"`.

**Test 2 — task a bassa priorità (descrizione opzionale)**
```json
{
  "titolo": "Aggiornare il README",
  "priorita": "bassa"
}
```
Risposta attesa: `"id": 2`.

---

### Tool: `elenca_tasks`

**Test 3 — elenca tutti i task aperti**
```json
{ "stato": "aperto" }
```
Risposta attesa: `"totale": 2` con entrambi i task nella lista.

---

### Tool: `chiudi_task`

**Test 4 — chiudi il primo task**
```json
{ "task_id": 1 }
```
Risposta attesa: `"stato": "chiuso"` e campo `"completato"` con timestamp ISO 8601.

**Test 5 — verifica che i chiusi siano separati dagli aperti**
```json
{ "stato": "chiuso" }
```
Deve comparire solo il task 1.

---

### Tool: `elimina_task`

**Test 6 — elimina il secondo task**
```json
{ "task_id": 2 }
```
Risposta attesa:
```json
{ "eliminato": 2, "rimanenti": 1 }
```

**Test 7 — errore su id inesistente**
```json
{ "task_id": 999 }
```
Il server deve rispondere con un errore: `"Nessun task con id 999"`.

---

### Resource: `tasks://riepilogo`

Vai nel tab **Resources** → **List Resources** → seleziona `tasks://riepilogo`.

Risposta attesa (dopo i test precedenti):
```json
{
  "totale": 1,
  "aperti": 0,
  "chiusi": 1,
  "tasks": [
    {
      "id": 1,
      "titolo": "Scrivere i test unitari",
      "descrizione": "Coprire almeno l'80% del codice con pytest",
      "priorita": "alta",
      "stato": "chiuso",
      "creato": "2026-05-16T10:00:00+00:00",
      "completato": "2026-05-16T10:05:00+00:00"
    }
  ]
}
```

---

### Prompt: `pianifica_sprint`

Vai nel tab **Prompts** → **List Prompts** → seleziona `pianifica_sprint` → compila:

```json
{
  "team": "Backend",
  "durata_giorni": 10
}
```

Clicca **Get Prompt**. Il testo generato deve contenere il nome del team, la durata, il JSON dei task aperti recuperato in tempo reale dal database e le istruzioni per l'agile coach su prioritizzazione e rischi.

---

### Prompt di test in linguaggio naturale (Agent Mode)

Se usi il server con Claude Desktop o VS Code Copilot in Agent Mode, puoi testarlo con prompt in italiano:

```
Ho trovato un bug critico nel modulo di autenticazione.
Crea un task ad alta priorità con titolo "Fix: token refresh non funziona dopo 24h"
e descrizione dettagliata del problema.
```

```
Mostrami tutti i task aperti e dimmi quali hanno priorità alta.
```

```
I task 3 e 7 sono stati completati stamattina. Chiudili entrambi.
```

```
Usa il riepilogo del task manager e pianifica lo sprint del team Backend
della durata di 14 giorni.
```

---

## Integrazione con Claude Desktop

Aggiungi questa configurazione al file `claude_desktop_config.json`
(percorso tipico: `%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "task-manager": {
      "command": "C:\\percorso\\mcp-task-manager\\.venv\\Scripts\\python.exe",
      "args": ["C:\\percorso\\mcp-task-manager\\server.py"]
    }
  }
}
```

Sostituisci `C:\\percorso\\mcp-task-manager` con il percorso assoluto della tua installazione locale.

## Integrazione con VS Code (Copilot Agent Mode)

Crea o modifica il file `.vscode/mcp.json` nella cartella del workspace:

```json
{
  "servers": {
    "task-manager": {
      "command": "C:\\percorso\\mcp-task-manager\\.venv\\Scripts\\python.exe",
      "args": ["C:\\percorso\\mcp-task-manager\\server.py"],
      "env": {}
    }
  }
}
```

---

## Struttura del progetto

```
mcp-task-manager/
├── server.py          # Server MCP principale (tool, resource, prompt)
├── run_server.bat     # Wrapper di avvio per Windows (aggiorna i percorsi)
├── pyproject.toml     # Dipendenze e metadati del progetto (uv)
├── uv.lock            # Lock file delle dipendenze
└── tasks.db           # Database SQLite — creato automaticamente, non versionato
```
