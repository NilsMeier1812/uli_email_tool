"""System: Updates per git und Desktop-Verknüpfung (Windows)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .core import APP_NAME, ENTRY_SCRIPT, app_dir, resource_path


def run_git(*args: str, timeout: int = 60) -> str:
    """git im Programmordner ausführen (ohne Konsolenfenster). Wirft bei Fehler."""
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    res = subprocess.run(
        ["git", *args], cwd=app_dir(), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout, creationflags=flags,
    )
    if res.returncode != 0:
        raise RuntimeError((res.stderr or res.stdout).strip() or f"git {args[0]} fehlgeschlagen")
    return res.stdout.strip()


def update_possible() -> str:
    """Leerer String, wenn Updates per git gehen – sonst der Grund, warum nicht."""
    if getattr(sys, "frozen", False):
        return "Die .exe-Version kann sich nicht selbst aktualisieren."
    if not (app_dir() / ".git").exists():
        return "Kein Git-Ordner – bitte Email_tool_setup.bat erneut ausführen, um zu aktualisieren."
    try:
        run_git("--version", timeout=10)
    except Exception:
        return "Git ist nicht installiert – bitte Email_tool_setup.bat erneut ausführen."
    return ""


def current_version() -> str:
    try:
        return run_git("log", "-1", "--format=%h vom %cd", "--date=format:%d.%m.%Y", timeout=10)
    except Exception:
        return "unbekannt"


def upstream_ref() -> str:
    try:
        return run_git("rev-parse", "--abbrev-ref", "@{u}", timeout=10)
    except Exception:
        return "origin/main"


def check_updates() -> list[str]:
    """Holt den Stand vom Server und liefert die neuen Änderungen (leer = aktuell)."""
    run_git("fetch", "--quiet")
    log = run_git("log", "--format=%s", f"HEAD..{upstream_ref()}")
    return [z for z in log.splitlines() if z.strip()]


def apply_update() -> bool:
    """git pull; aktualisiert Pakete, falls requirements.txt sich ändert.

    Gibt zurück, ob Pakete aktualisiert wurden.
    """
    alt = run_git("rev-parse", "HEAD")
    run_git("pull", "--ff-only", timeout=120)
    geaendert = run_git("diff", "--name-only", alt, "HEAD").splitlines()
    if "requirements.txt" not in geaendert:
        return False
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    res = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "-r", str(app_dir() / "requirements.txt")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600, creationflags=flags,
    )
    if res.returncode != 0:
        raise RuntimeError("Update geladen, aber Pakete konnten nicht installiert werden:\n"
                           + (res.stderr or res.stdout).strip()[-800:])
    return True


# --------------------------------------------------------------------------- #
# Desktop-Verknüpfung (Windows)
# --------------------------------------------------------------------------- #
OLD_APP_NAMES = ["Uli Email Tool"]  # frühere Bezeichnungen – alte Verknüpfungen werden entfernt


def _ps_str(value) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def run_powershell(script: str, timeout: int = 30) -> str:
    res = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "PowerShell-Fehler")
    return res.stdout.strip()


def shortcut_possible() -> str:
    """Leerer String, wenn Verknüpfungen angelegt werden können – sonst der Grund."""
    if sys.platform != "win32":
        return "Nur unter Windows verfügbar."
    return ""


def _pythonw() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    return str(pyw if pyw.exists() else exe)


def shortcut_status() -> str:
    """'alle' (öffentlicher Desktop), 'benutzer' (eigener Desktop) oder 'keine'."""
    name = _ps_str(APP_NAME + ".lnk")
    out = run_powershell(
        f"if (Test-Path (Join-Path ([Environment]::GetFolderPath('CommonDesktopDirectory')) {name})) {{ 'alle' }} "
        f"elseif (Test-Path (Join-Path ([Environment]::GetFolderPath('Desktop')) {name})) {{ 'benutzer' }} "
        f"else {{ 'keine' }}"
    )
    return out.splitlines()[-1] if out else "keine"


def create_shortcuts() -> str:
    """Desktop- und Startmenü-Verknüpfung anlegen bzw. reparieren.

    Gibt es schon eine für alle Benutzer (vom Setup), wird diese aktualisiert –
    dafür fehlen ohne Admin-Rechte meist die Rechte, dann bleibt sie, wie sie ist.
    Sonst wird sie für den aktuellen Benutzer angelegt.
    """
    if getattr(sys, "frozen", False):
        target, args = sys.executable, ""
    else:
        target, args = _pythonw(), f'"{ENTRY_SCRIPT}"'
    icon = resource_path("icon.ico")
    alt = ", ".join(_ps_str(n + ".lnk") for n in OLD_APP_NAMES)
    script = f"""
$ErrorActionPreference = 'Stop'
$ws = New-Object -ComObject WScript.Shell
function Make($ordner) {{
    $lnk = $ws.CreateShortcut((Join-Path $ordner {_ps_str(APP_NAME + '.lnk')}))
    $lnk.TargetPath = {_ps_str(target)}
    $lnk.Arguments = {_ps_str(args)}
    $lnk.WorkingDirectory = {_ps_str(app_dir())}
    $lnk.IconLocation = {_ps_str(icon)} + ',0'
    $lnk.Description = {_ps_str(APP_NAME)}
    $lnk.Save()
}}
$userDirs = @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))
foreach ($o in $userDirs) {{ foreach ($n in @({alt})) {{
    $p = Join-Path $o $n; if (Test-Path $p) {{ Remove-Item $p -Force -ErrorAction SilentlyContinue }} }} }}
$pub = [Environment]::GetFolderPath('CommonDesktopDirectory')
if (Test-Path (Join-Path $pub {_ps_str(APP_NAME + '.lnk')})) {{
    try {{
        Make $pub
        Make ([Environment]::GetFolderPath('CommonPrograms'))
        'alle'
    }} catch {{ 'alle-unveraendert' }}
}} else {{
    foreach ($o in $userDirs) {{ Make $o }}
    'benutzer'
}}
"""
    out = run_powershell(script)
    return out.splitlines()[-1] if out else ""
