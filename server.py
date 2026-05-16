# server.py — MCP Task Manager con FastMCP
# Compatibile con mcp SDK 1.27+ (aprile 2026)
#
#   1. Persistenza SQLite (non più lista in memoria)
#   2. Thread safety tramite threading.Lock su tutte le scritture
#   3. Id derivato da ROWID SQLite (no collisioni al riavvio)
#   4. Validazione input con Pydantic v2 + Field constraints
#   5. Tutti i tool sono async
#   6. Annotations MCP corrette (readOnlyHint, destructiveHint, …)
#   7. Prompt pianifica_sprint inietta i dati reali da riepilogo_tasks()
#   8. Nessun uso di `global` come anti-pattern

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from typing import Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Costanti ─────────────────────────────────────────────────
DB_PATH = "tasks.db"

# ── DB helpers ───────────────────────────────────────────────
_lock = threading.Lock()


@contextmanager
def _get_conn():
    """Context manager per connessione SQLite thread-safe."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _init_db() -> None:
    """Crea la tabella tasks se non esiste già."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                titolo      TEXT    NOT NULL,
                descrizione TEXT    NOT NULL DEFAULT '',
                priorita    TEXT    NOT NULL DEFAULT 'media',
                stato       TEXT    NOT NULL DEFAULT 'aperto',
                creato      TEXT    NOT NULL,
                completato  TEXT
            )
        """)


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


# ── Pydantic input models ─────────────────────────────────────


class CreaTaskInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    titolo: str = Field(
        ..., description="Titolo breve del task.", min_length=1, max_length=200
    )
    descrizione: str = Field(
        "", description="Dettaglio opzionale del task.", max_length=2000
    )
    priorita: Literal["bassa", "media", "alta"] = Field(
        "media", description="Priorità del task: 'bassa', 'media' o 'alta'."
    )


class ElencaTasksInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stato: Literal["aperto", "chiuso", "tutti"] = Field(
        "aperto", description="Filtra per stato: 'aperto', 'chiuso' o 'tutti'."
    )


class TaskIdInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: int = Field(..., description="Id numerico del task.", ge=1)


class PianificaSprintInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    team: str = Field(..., description="Nome del team.", min_length=1, max_length=100)
    durata_giorni: int = Field(
        14, description="Durata dello sprint in giorni.", ge=1, le=90
    )

    @field_validator("durata_giorni")
    @classmethod
    def durata_positiva(cls, v: int) -> int:
        if v < 1:
            raise ValueError("durata_giorni deve essere almeno 1.")
        return v


# ── Lifespan ─────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Inizializza il DB alla partenza del server."""
    _init_db()
    yield


# ── Inizializzazione ──────────────────────────────────────────
mcp = FastMCP("task_manager_mcp", lifespan=lifespan)


# ── Tools ─────────────────────────────────────────────────────


@mcp.tool(
    name="crea_task",
    annotations={
        "title": "Crea Task",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def crea_task(params: CreaTaskInput) -> str:
    """Crea un nuovo task e lo persiste nel DB.

    Args:
        params (CreaTaskInput): Parametri validati:
            - titolo (str): Titolo breve, non vuoto, max 200 caratteri.
            - descrizione (str): Dettaglio opzionale, max 2000 caratteri.
            - priorita (str): 'bassa', 'media' o 'alta'.

    Returns:
        str: JSON del task creato con id, titolo, descrizione, priorita,
             stato, creato, completato.
    """
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        with _get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO tasks (titolo, descrizione, priorita, stato, creato, completato)
                VALUES (?, ?, ?, 'aperto', ?, NULL)
                """,
                (params.titolo, params.descrizione, params.priorita, now),
            )
            task_id = cur.lastrowid
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
    return json.dumps(_row_to_dict(row), ensure_ascii=False, indent=2)


@mcp.tool(
    name="elenca_tasks",
    annotations={
        "title": "Elenca Tasks",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def elenca_tasks(params: ElencaTasksInput) -> str:
    """Elenca i task filtrati per stato.

    Args:
        params (ElencaTasksInput):
            - stato (str): 'aperto', 'chiuso' o 'tutti'.

    Returns:
        str: JSON con 'totale' (int) e 'tasks' (lista di oggetti task).
    """
    with _get_conn() as conn:
        if params.stato == "tutti":
            rows = conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE stato = ? ORDER BY id", (params.stato,)
            ).fetchall()
    tasks = [_row_to_dict(r) for r in rows]
    return json.dumps(
        {"totale": len(tasks), "tasks": tasks}, ensure_ascii=False, indent=2
    )


@mcp.tool(
    name="chiudi_task",
    annotations={
        "title": "Chiudi Task",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def chiudi_task(params: TaskIdInput) -> str:
    """Segna un task come completato dato il suo id.

    Args:
        params (TaskIdInput):
            - task_id (int): Id numerico del task, >= 1.

    Returns:
        str: JSON del task aggiornato.

    Raises:
        ValueError: Se il task_id non esiste.
    """
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        with _get_conn() as conn:
            cur = conn.execute(
                "UPDATE tasks SET stato = 'chiuso', completato = ? WHERE id = ?",
                (now, params.task_id),
            )
            if cur.rowcount == 0:
                raise ValueError(f"Nessun task con id {params.task_id}.")
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (params.task_id,)
            ).fetchone()
    return json.dumps(_row_to_dict(row), ensure_ascii=False, indent=2)


@mcp.tool(
    name="elimina_task",
    annotations={
        "title": "Elimina Task",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def elimina_task(params: TaskIdInput) -> str:
    """Rimuove definitivamente un task dalla lista.

    Args:
        params (TaskIdInput):
            - task_id (int): Id numerico del task, >= 1.

    Returns:
        str: JSON con 'eliminato' (id rimosso) e 'rimanenti' (conteggio).

    Raises:
        ValueError: Se il task_id non esiste.
    """
    with _lock:
        with _get_conn() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (params.task_id,))
            if cur.rowcount == 0:
                raise ValueError(f"Task id {params.task_id} non trovato.")
            rimanenti = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    return json.dumps(
        {"eliminato": params.task_id, "rimanenti": rimanenti},
        ensure_ascii=False,
        indent=2,
    )


# ── Resource ──────────────────────────────────────────────────


@mcp.resource("tasks://riepilogo")
async def riepilogo_tasks() -> str:
    """Riepilogo JSON di tutti i task con statistiche aggregate.

    Restituisce totale, aperti, chiusi e lista completa dei task.
    """
    with _get_conn() as conn:
        rows = conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()
    tasks = [_row_to_dict(r) for r in rows]
    aperti = sum(1 for t in tasks if t["stato"] == "aperto")
    return json.dumps(
        {
            "totale": len(tasks),
            "aperti": aperti,
            "chiusi": len(tasks) - aperti,
            "tasks": tasks,
        },
        indent=2,
        ensure_ascii=False,
    )


# ── Prompt ────────────────────────────────────────────────────


@mcp.prompt()
async def pianifica_sprint(params: PianificaSprintInput) -> str:
    """Genera un prompt per pianificare il prossimo sprint.

    Inietta direttamente il riepilogo aggiornato dei task aperti
    nel testo del prompt, così il modello dispone di dati reali.

    Args:
        params (PianificaSprintInput):
            - team (str): Nome del team.
            - durata_giorni (int): Durata dello sprint in giorni (1-90).
    """
    # Recupera i dati reali dalla resource
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE stato = 'aperto' ORDER BY id"
        ).fetchall()
    tasks_aperti = [_row_to_dict(r) for r in rows]
    riepilogo_json = json.dumps(tasks_aperti, indent=2, ensure_ascii=False)

    return (
        f"Sei un agile coach esperto. Il team '{params.team}' ha {params.durata_giorni} giorni "
        f"per il prossimo sprint.\n\n"
        f"Di seguito i task attualmente aperti:\n\n"
        f"```json\n{riepilogo_json}\n```\n\n"
        f"Sulla base di questi dati:\n"
        f"1. Proponi un piano di sprint prioritizzato, ordinando i task per priorità e valore.\n"
        f"2. Identifica eventuali rischi (task bloccanti, dipendenze implicite, carico eccessivo).\n"
        f"3. Suggerisci quali task rimandare allo sprint successivo se il carico è troppo alto.\n"
        f"Rispondi in italiano con un formato strutturato."
    )


# ── Avvio server ──────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run()  # trasporto stdio per VS Code / Claude Desktop
