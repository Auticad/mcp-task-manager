@echo off
REM ── MCP Task Manager — avvio server ──────────────────────────
REM Usa percorsi relativi alla posizione di questo file (%~dp0),
REM quindi funziona in qualsiasi cartella in cui sia clonato il repo.

"%~dp0.venv\Scripts\python.exe" "%~dp0server.py"
