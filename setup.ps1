<#
================================================================
 Vertrieb Email Tool - Automatische Einrichtung (Windows)
================================================================

 Richtet ALLES ein, was fuer das Email-Tool noetig ist:

   1. Python pruefen  -> sonst installieren (winget, sonst Direkt-Download)
   2. Git pruefen     -> sonst installieren (winget) [optional, fuer Updates]
   3. Repo nach C:\vertrieb_email_tool holen (git clone / ZIP-Download)
   4. Schreibrechte fuer normale Benutzer (config.json, git pull)
   5. pip install -r requirements.txt (PyQt6, keyring - PFLICHT)
   6. Verknuepfung "Vertrieb Email Tool" mit Icon auf den Desktop + ins Startmenue
      (fuer ALLE Benutzer des PCs)
   7. Das Tool einmal starten (als normaler Benutzer, nicht als Admin)

 Danach einmal im Tool unter "Einstellungen" eintragen:
   - Absender-Adresse und SMTP-Passwort (Benutzername ggf. anpassen)

 Aufruf:
   - Bequem: Email_tool_setup.bat doppelklicken (holt Admin-Rechte + dieses Skript).
   - Direkt: Rechtsklick auf setup.ps1 -> "Mit PowerShell ausfuehren".
   Das Skript fordert bei Bedarf selbst Administrator-Rechte an.

 Erneut ausfuehren ist ungefaehrlich: vorhandene Installation wird
 aktualisiert (git pull), Einstellungen (config.json) bleiben erhalten.
================================================================
#>

param(
    [string]$InstallDir = "C:\vertrieb_email_tool",
    [string]$RepoUrl    = "https://github.com/NilsMeier1812/uli_email_tool.git",
    [string]$Branch     = "main"
)

$ErrorActionPreference = "Stop"
$ZipUrl   = "https://codeload.github.com/NilsMeier1812/uli_email_tool/zip/refs/heads/$Branch"
$AppName  = "Vertrieb Email Tool"
$OldNames = @("Uli Email Tool")          # fruehere Bezeichnungen (Verknuepfungen)
$OldDirs  = @("C:\uli_email_tool")       # fruehere Installationsordner

# ---------- kleine Ausgabe-Helfer -------------------------------------------
function Info($m) { Write-Host ""; Write-Host "==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "    [ok]  $m" -ForegroundColor Green }
function Warn($m) { Write-Host "    [!]   $m" -ForegroundColor Yellow }
function Step($m) { Write-Host "    ...   $m" -ForegroundColor Gray }

function Have($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

# PATH neu aus der Registry laden (nach einer Installation weiss die aktuelle
# Sitzung sonst nichts von neu hinzugekommenen Programmen wie python/git).
function Update-EnvPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user    = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (@($machine, $user) | Where-Object { $_ }) -join ";"
}

# ---------- Administrator-Rechte sicherstellen ------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal] `
            [Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)

if (-not $isAdmin) {
    if ($PSCommandPath) {
        Info "Fordere Administrator-Rechte an (fuer Installationen + C:\-Ordner) ..."
        $argList = @(
            "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", "`"$PSCommandPath`"",
            "-InstallDir", "`"$InstallDir`"",
            "-RepoUrl", "`"$RepoUrl`"",
            "-Branch", "`"$Branch`""
        )
        Start-Process -FilePath "powershell.exe" -ArgumentList $argList -Verb RunAs
        exit
    } else {
        Warn "Ohne Administrator-Rechte gestartet. Bitte PowerShell 'als Administrator'"
        Warn "oeffnen und das Skript erneut ausfuehren (oder Email_tool_setup.bat doppelklicken)."
        Read-Host "Zum Beenden Enter druecken"
        exit 1
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor White
Write-Host " $AppName - Automatische Einrichtung" -ForegroundColor White
Write-Host " Zielordner: $InstallDir" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor White

$hasWinget = Have "winget"
if (-not $hasWinget) {
    Warn "winget ist nicht vorhanden. Installationen laufen ueber Direkt-Download."
    Warn "(winget kommt mit dem 'App Installer' aus dem Microsoft Store, empfohlen auf Win10/11.)"
}

# ============================================================================
# 1. Python
# ============================================================================
function Install-PythonViaWinget {
    Step "Installiere Python 3.12 ueber winget ..."
    winget install --id Python.Python.3.12 --scope machine --silent `
        --accept-source-agreements --accept-package-agreements | Out-Host
}

function Install-PythonViaDownload {
    $url = "https://www.python.org/ftp/python/3.12.6/python-3.12.6-amd64.exe"
    $exe = Join-Path $env:TEMP "python-3.12.6-amd64.exe"
    Step "Lade Python-Installer herunter ..."
    Invoke-WebRequest -Uri $url -OutFile $exe -UseBasicParsing
    Step "Installiere Python (still, fuer alle Benutzer, PATH wird gesetzt) ..."
    # PrependPath=1 -> python/pythonw landen im PATH; Include_launcher=1 -> "py"
    Start-Process -FilePath $exe -ArgumentList `
        "/quiet InstallAllUsers=1 PrependPath=1 Include_launcher=1" -Wait
    Remove-Item $exe -ErrorAction SilentlyContinue
}

# Merkt sich, wie Python aufzurufen ist (z.B. @("py","-3") oder @("python")).
$script:PyCmd = $null

# Prueft, ob ein Aufruf ein ECHTES Python ist (liefert "Python X.Y.Z" zurueck).
# Der Microsoft-Store-Platzhalter gibt stattdessen einen Hinweistext aus und
# faellt hier durch.
function Test-PythonCall($file, [string[]]$verArgs) {
    try { $out = (& $file @verArgs) 2>&1 | Out-String } catch { return $null }
    if ($out -match 'Python\s+(\d+\.\d+\.\d+)') { return "Python $($Matches[1])" }
    return $null
}

# Findet ein echtes Python und setzt $script:PyCmd. $null, wenn keins da ist.
# WICHTIG: Windows legt in ...\WindowsApps einen Schein-"python.exe" an, der nur
# den Microsoft Store oeffnet. Der wird hier bewusst ausgeschlossen; stattdessen
# wird zuerst der py-Launcher (nicht vom Alias betroffen) genutzt.
function Find-Python {
    Update-EnvPath
    # 1) py-Launcher bevorzugen (immun gegen den Store-Alias)
    if (Have "py") {
        $v = Test-PythonCall "py" @("-3", "--version")
        if ($v) { $script:PyCmd = @("py", "-3"); return $v }
    }
    # 2) echtes python.exe im PATH - den WindowsApps-Platzhalter ueberspringen
    foreach ($c in @(Get-Command python -All -ErrorAction SilentlyContinue)) {
        if ($c.Source -and ($c.Source -like "*\WindowsApps\*")) { continue }
        $v = Test-PythonCall $c.Source @("--version")
        if ($v) { $script:PyCmd = @($c.Source); return $v }
    }
    return $null
}

# Fuehrt Python mit den gemerkten Aufruf-Argumenten aus.
function Invoke-Py([string[]]$pyArgs) {
    $py   = $script:PyCmd[0]
    $rest = @($script:PyCmd | Select-Object -Skip 1)
    & $py @rest @pyArgs
}

function Ensure-Python {
    Info "Pruefe Python ..."
    $v = Find-Python
    if ($v) { Ok "Python gefunden: $v"; return }

    Warn "Kein echtes Python gefunden (evtl. nur der Microsoft-Store-Platzhalter)."
    Warn "Python wird jetzt installiert ..."
    if ($hasWinget) { Install-PythonViaWinget } else { Install-PythonViaDownload }

    $v = Find-Python
    if ($v) {
        Ok "Python installiert: $v"
    } else {
        throw "Python-Installation fehlgeschlagen oder noch nicht im PATH. " +
              "Bitte einmal ab-/anmelden und das Setup erneut starten."
    }
}

# ============================================================================
# 2. Git (optional - fuer Updates aus dem Tool heraus)
# ============================================================================
function Ensure-Git {
    Info "Pruefe Git ..."
    Update-EnvPath
    if (Have "git") {
        Ok "Git gefunden: $((& git --version) 2>&1)"
        return
    }
    if ($hasWinget) {
        Warn "Git nicht gefunden - wird installiert (fuer spaetere Updates)."
        Step "Installiere Git ueber winget ..."
        try {
            winget install --id Git.Git --scope machine --silent `
                --accept-source-agreements --accept-package-agreements | Out-Host
            Update-EnvPath
        } catch {
            Warn "Git-Installation fehlgeschlagen - nicht schlimm, es geht auch per ZIP."
        }
    } else {
        Warn "Kein winget vorhanden - Git wird uebersprungen (Repo kommt per ZIP)."
    }
    if (Have "git") { Ok "Git installiert: $((& git --version) 2>&1)" }
}

# ============================================================================
# 3. Repo nach $InstallDir holen
# ============================================================================
function Get-RepoViaZip {
    $zip = Join-Path $env:TEMP "vertrieb_email_tool.zip"
    $tmp = Join-Path $env:TEMP "vertrieb_email_tool-extract"
    Step "Lade Repo als ZIP herunter ..."
    Invoke-WebRequest -Uri $ZipUrl -OutFile $zip -UseBasicParsing
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Step "Entpacke ..."
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    # Das ZIP enthaelt einen Unterordner "uli_email_tool-<branch>".
    $inner = Get-ChildItem -Path $tmp -Directory | Select-Object -First 1
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    Copy-Item -Path (Join-Path $inner.FullName "*") -Destination $InstallDir -Recurse -Force
    Remove-Item $zip -ErrorAction SilentlyContinue
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

function Ensure-Repo {
    Info "Hole das Repo nach $InstallDir ..."

    if (Test-Path (Join-Path $InstallDir ".git")) {
        Step "Repo existiert bereits - aktualisiere (git pull) ..."
        try {
            & git -C $InstallDir pull --ff-only | Out-Host
            Ok "Repo aktualisiert."
        } catch {
            Warn "git pull fehlgeschlagen (lokale Aenderungen?). Bestand bleibt unveraendert."
        }
        return
    }

    # Ordner existiert, ist aber kein Git-Repo -> Einstellungen retten, Rest sichern.
    $savedConfig = $null
    if ((Test-Path $InstallDir) -and (Get-ChildItem $InstallDir -Force -ErrorAction SilentlyContinue)) {
        $cfg = Join-Path $InstallDir "config.json"
        if (Test-Path $cfg) {
            $savedConfig = Join-Path $env:TEMP "vertrieb_email_tool_config.json"
            Copy-Item $cfg $savedConfig -Force
        }
        $backup = "$InstallDir" + "_backup_" + (Get-Date -Format "yyyyMMdd_HHmmss")
        Warn "Ordner existiert und ist kein Git-Repo. Sichere ihn nach:"
        Warn "  $backup"
        Rename-Item -Path $InstallDir -NewName $backup
    }

    if (Have "git") {
        Step "Klone Repo (git clone) ..."
        & git clone --branch $Branch $RepoUrl $InstallDir | Out-Host
        if (-not (Test-Path (Join-Path $InstallDir "email_tool.pyw"))) {
            throw "git clone fehlgeschlagen. Ist das Repo erreichbar ($RepoUrl)?"
        }
        Ok "Repo geklont."
    } else {
        Get-RepoViaZip
        Ok "Repo per ZIP abgelegt (ohne Git - Updates dann erneut per Email_tool_setup.bat)."
    }

    if ($savedConfig) {
        Copy-Item $savedConfig (Join-Path $InstallDir "config.json") -Force
        Remove-Item $savedConfig -ErrorAction SilentlyContinue
        Ok "Vorhandene Einstellungen (config.json) uebernommen."
    }
    Import-OldConfig
}

# Einstellungen aus einem frueheren Installationsordner uebernehmen.
function Import-OldConfig {
    $ziel = Join-Path $InstallDir "config.json"
    if (Test-Path $ziel) { return }
    foreach ($alt in $OldDirs) {
        $quelle = Join-Path $alt "config.json"
        if (($alt -ne $InstallDir) -and (Test-Path $quelle)) {
            Copy-Item $quelle $ziel -Force
            Ok "Einstellungen aus $alt uebernommen."
            Warn "Der alte Ordner $alt wird nicht mehr gebraucht und kann geloescht werden."
            return
        }
    }
}

# ============================================================================
# 4. Rechte fuer normale Benutzer
# ============================================================================
function Ensure-Permissions {
    Info "Setze Schreibrechte fuer normale Benutzer ..."
    # Das Tool speichert seine Einstellungen (config.json) im Programmordner,
    # und Updates aus dem Tool (git pull) sollen ohne Admin-Rechte funktionieren.
    # *S-1-5-32-545 = Gruppe "Benutzer" (sprachunabhaengig).
    & icacls $InstallDir /grant "*S-1-5-32-545:(OI)(CI)M" /T /Q | Out-Null
    Ok "Benutzer duerfen in $InstallDir schreiben."

    if (Have "git") {
        # Repo gehoert dem Admin -> Git verweigert sonst anderen Benutzern das
        # Arbeiten darin ("dubious ownership").
        $safe = ($InstallDir -replace '\\', '/')
        $vorhanden = @(& git config --system --get-all safe.directory 2>$null)
        if ($vorhanden -notcontains $safe) {
            & git config --system --add safe.directory $safe
        }
        Ok "Git: $safe als sicheres Verzeichnis eingetragen."
    }
}

# ============================================================================
# 5. Python-Pakete (PFLICHT: PyQt6 + keyring)
# ============================================================================
function Ensure-Requirements {
    Info "Installiere Python-Pakete (PyQt6, keyring) ..."
    $req = Join-Path $InstallDir "requirements.txt"
    if (-not (Test-Path $req)) { throw "requirements.txt nicht gefunden in $InstallDir." }
    Invoke-Py @("-m", "pip", "install", "--upgrade", "pip") | Out-Host
    Invoke-Py @("-m", "pip", "install", "--upgrade", "-r", $req) | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "pip install fehlgeschlagen (Internet/Proxy pruefen)." }

    # Gegenprobe: laesst sich PyQt6 wirklich importieren?
    # (Warnungen auf stderr sollen hier nicht zum Abbruch fuehren.)
    $ErrorActionPreference = "Continue"
    $check = (Invoke-Py @("-c", "import PyQt6.QtWidgets, keyring; print('ok')")) 2>&1 | Out-String
    $ErrorActionPreference = "Stop"
    if ($check -notmatch "ok") { throw "PyQt6/keyring nicht importierbar:`n$check" }
    Ok "Pakete installiert und getestet."
}

# ============================================================================
# 6. Verknuepfungen (Desktop + Startmenue, fuer alle Benutzer)
# ============================================================================
function Get-Pythonw {
    $exe = ((Invoke-Py @("-c", "import sys; print(sys.executable)")) | Out-String).Trim()
    $pyw = Join-Path (Split-Path $exe) "pythonw.exe"
    if (Test-Path $pyw) { return $pyw }
    Warn "pythonw.exe nicht gefunden - nutze python.exe (dann mit Konsolenfenster)."
    return $exe
}

function Ensure-Shortcuts {
    Info "Lege Verknuepfungen mit Icon an ..."
    $toolFile = Join-Path $InstallDir "email_tool.pyw"
    $icon    = Join-Path $InstallDir "icon.ico"
    $pythonw = Get-Pythonw

    # Alte Verknuepfungen entfernen: nur fuer einen Benutzer angelegte und
    # solche unter frueheren Programmnamen - sonst doppelte Icons.
    $common = @([Environment]::GetFolderPath("CommonDesktopDirectory"),
                [Environment]::GetFolderPath("CommonPrograms"))
    $user   = @([Environment]::GetFolderPath("Desktop"),
                [Environment]::GetFolderPath("Programs"))
    foreach ($ordner in $user) {
        foreach ($n in @($AppName) + $OldNames) {
            $alt = Join-Path $ordner "$n.lnk"
            if (Test-Path $alt) { Remove-Item $alt -Force -ErrorAction SilentlyContinue }
        }
    }
    foreach ($ordner in $common) {
        foreach ($n in $OldNames) {
            $alt = Join-Path $ordner "$n.lnk"
            if (Test-Path $alt) { Remove-Item $alt -Force -ErrorAction SilentlyContinue }
        }
    }

    $wsh = New-Object -ComObject WScript.Shell
    $script:DesktopLink = $null
    foreach ($ordner in @([Environment]::GetFolderPath("CommonDesktopDirectory"),
                          [Environment]::GetFolderPath("CommonPrograms"))) {
        $link = Join-Path $ordner "$AppName.lnk"
        $sc = $wsh.CreateShortcut($link)
        $sc.TargetPath       = $pythonw
        $sc.Arguments        = "`"$toolFile`""
        $sc.WorkingDirectory = $InstallDir
        $sc.IconLocation     = "$icon,0"
        $sc.Description      = $AppName
        $sc.Save()
        Step $link
        if (-not $script:DesktopLink) { $script:DesktopLink = $link }
    }
    Ok "Verknuepfung '$AppName' auf dem Desktop und im Startmenue (alle Benutzer)."
    Step "Nach einem Update bleibt die Verknuepfung gueltig."
}

# ============================================================================
# 7. Tool einmal starten - als normaler Benutzer, nicht als Admin
# ============================================================================
function Start-ToolNow {
    Info "Starte das Tool ..."
    if (-not $script:DesktopLink) { return }
    # Ueber explorer.exe gestartet laeuft das Tool OHNE Admin-Rechte im
    # angemeldeten Benutzer (wichtig: Passwort-Speicher ist pro Benutzer).
    Start-Process -FilePath "explorer.exe" -ArgumentList "`"$script:DesktopLink`""
    Ok "Tool gestartet."
}

# ============================================================================
# Ablauf
# ============================================================================
try {
    Ensure-Python
    Ensure-Git
    Ensure-Repo
    Ensure-Permissions
    Ensure-Requirements
    Ensure-Shortcuts
    Start-ToolNow

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " FERTIG - $AppName ist eingerichtet." -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host " Starten: Doppelklick auf '$AppName' auf dem Desktop." -ForegroundColor White
    Write-Host ""
    Write-Host " Beim ersten Mal im Tool unter 'Einstellungen' eintragen:" -ForegroundColor Yellow
    Write-Host "   - Email:  Absender-Adresse" -ForegroundColor White
    Write-Host "   - Server: Benutzername + Passwort (dann 'Verbindung testen')" -ForegroundColor White
    Write-Host ""
    Write-Host " Updates und Verknuepfung: im Tool unter Einstellungen -> System." -ForegroundColor White
    Write-Host ""
}
catch {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host " FEHLER bei der Einrichtung:" -ForegroundColor Red
    Write-Host "   $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host ""
}
finally {
    Read-Host "Zum Schliessen dieses Fensters Enter druecken"
}
