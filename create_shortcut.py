"""Legt eine Desktop-Verknüpfung (und einen Startmenü-Eintrag) für das Email-Tool an.

Einfach einmal ausführen:  Doppelklick auf "Verknuepfung_erstellen.bat"
Die Verknüpfung startet das Tool ohne Konsolenfenster und zeigt das eigene Icon.
"""

import subprocess
import sys
from pathlib import Path

NAME = "Vertrieb Email Tool"
ALT_NAME = "Uli Email Tool"  # frühere Bezeichnung – alte Verknüpfung wird entfernt
here = Path(__file__).resolve().parent
script = here / "email_tool.pyw"
icon = here / "icon.ico"

# pythonw.exe = Python ohne Konsolenfenster
pythonw = Path(sys.executable).with_name("pythonw.exe")
if not pythonw.exists():
    pythonw = Path(sys.executable)


def ps_str(value) -> str:
    return "'" + str(value).replace("'", "''") + "'"


ps = f"""
$ws = New-Object -ComObject WScript.Shell
$ziele = @(
    [Environment]::GetFolderPath('Desktop'),
    [Environment]::GetFolderPath('Programs')
)
foreach ($ordner in $ziele) {{
    $alt = Join-Path $ordner {ps_str(ALT_NAME + '.lnk')}
    if (Test-Path $alt) {{ Remove-Item $alt -Force }}
    $lnk = $ws.CreateShortcut((Join-Path $ordner {ps_str(NAME + '.lnk')}))
    $lnk.TargetPath = {ps_str(pythonw)}
    $lnk.Arguments = '"' + {ps_str(script)} + '"'
    $lnk.WorkingDirectory = {ps_str(here)}
    $lnk.IconLocation = {ps_str(icon)} + ',0'
    $lnk.Description = {ps_str(NAME)}
    $lnk.Save()
    Write-Output ('Erstellt: ' + $lnk.FullName)
}}
"""

result = subprocess.run(
    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
    capture_output=True, text=True,
)
print(result.stdout.strip())
if result.returncode != 0:
    print("Fehler:", result.stderr.strip())
    sys.exit(1)
print("\nFertig - das Tool kann jetzt per Doppelklick auf dem Desktop gestartet werden.")
