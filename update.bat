@echo off
REM ============================================================
REM  Vertrieb Email Tool - Update (ohne Admin-Rechte)
REM  Holt die neueste Version und aktualisiert die Pakete.
REM  Einstellungen (config.json) bleiben erhalten.
REM ============================================================
cd /d "%~dp0"

where git >nul 2>nul
if errorlevel 1 (
  echo Git ist nicht installiert - bitte setup.bat erneut ausfuehren.
  pause
  exit /b 1
)

echo Hole neueste Version ...
git pull --ff-only
if errorlevel 1 (
  echo.
  echo Update fehlgeschlagen. Bitte Meldung oben pruefen.
  pause
  exit /b 1
)

echo.
echo Aktualisiere Python-Pakete ...
where py >nul 2>nul
if errorlevel 1 (
  python -m pip install --upgrade -r requirements.txt
) else (
  py -3 -m pip install --upgrade -r requirements.txt
)

echo.
echo Fertig - das Tool einfach neu starten.
pause
