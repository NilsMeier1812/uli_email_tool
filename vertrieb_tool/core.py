"""Grundlagen: Programmordner, Konfiguration, Passwort-Speicher."""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:  # Passwort sicher im Windows-Anmeldeinformationsspeicher ablegen
    import keyring
except ImportError:  # pragma: no cover
    keyring = None

APP_ID = "gcd.vertrieb.emailtool"
APP_NAME = "Vertrieb Email Tool"
KEYRING_SERVICE = "VertriebEmailTool"
KEYRING_SERVICE_ALT = "UliEmailTool"  # frühere Version – Passwort wird übernommen


def app_dir() -> Path:
    """Programmordner (Repo-Wurzel bzw. Ordner der .exe)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_path(name: str) -> Path:
    """Pfad zu mitgelieferten Dateien (auch in der PyInstaller-onefile-exe)."""
    base = Path(getattr(sys, "_MEIPASS", app_dir()))
    return base / name


ENTRY_SCRIPT = app_dir() / "email_tool.pyw"  # Ziel der Desktop-Verknüpfung
CONFIG_FILE = app_dir() / "config.json"

# Allgemeine Einstellungen. Vorlagen ergänzen ihre eigenen über register_defaults().
DEFAULT_CONFIG: dict = {
    "projekt_basis": r"M:\Projekte_ab_20000",
    # Postausgang
    "smtp_server": "mail.gcd.de",
    "smtp_port": 587,
    "smtp_user": "",  # wird beim ersten Start abgefragt
    "smtp_security": "STARTTLS",  # STARTTLS | SSL/TLS | Keine
    # Postfach (IMAP, gleiche Zugangsdaten wie SMTP)
    "imap_aktiv": True,  # Kopie in den Gesendet-Ordner
    "imap_server": "mail.gcd.de",
    "imap_port": 993,
    "imap_ordner": "",  # Gesendet-Ordner, leer = automatisch erkennen
    "scan_absender": "mail.sender@gcd.de",  # Scanner verschickt Scans per Mail
    "scan_ordner": "INBOX",
    "scan_anzahl": 5,
    # Person – wird beim ersten Start abgefragt
    "absender": "",
    "gruss": "",  # z.B. "VG\n<Vorname>"
    "kuerzel": "",  # Initialen, z.B. für README-Einträge
    # zuletzt benutzte Vorlage
    "vorlage": "",
}


def register_defaults(werte: dict) -> None:
    """Vorlagen melden hier ihre Standardwerte an."""
    for k, v in werte.items():
        DEFAULT_CONFIG.setdefault(k, v)


def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # tiefe Kopie
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass
    # Migrationen älterer Versionen
    cfg["bausteine_info"] = [b for b in cfg.get("bausteine_info", []) if b != "Bestellung gemäß PO"]
    cfg["bausteine_achtung"] = [
        b for b in cfg.get("bausteine_achtung", []) if not b.upper().startswith("PASTE")
    ]
    if cfg.get("shortcuts_lieferant") in (["Lieferant 1", "Lieferant 2"], ["Fima", "KC", "Piu"]):
        cfg["shortcuts_lieferant"] = DEFAULT_CONFIG.get("shortcuts_lieferant", [])
    for key in ("empfaenger", "betreff"):
        if key in DEFAULT_CONFIG and cfg.get(key) in ("", "Baugruppendaten Projekt {nr}"):
            cfg[key] = DEFAULT_CONFIG[key]
    # Gruß einheitlich mit "VG"
    gruss = cfg.get("gruss", "")
    if gruss and not gruss.startswith("VG"):
        zeilen = [z for z in gruss.splitlines() if z.strip()]
        if len(zeilen) > 1:
            cfg["gruss"] = "VG\n" + zeilen[-1]
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def gruss_name(cfg: dict) -> str:
    zeilen = [z for z in cfg.get("gruss", "").splitlines() if z.strip()]
    return zeilen[-1] if len(zeilen) > 1 else ""


def get_password(user: str) -> str | None:
    if keyring is None or not user:
        return None
    try:
        pw = keyring.get_password(KEYRING_SERVICE, user)
        if pw is None:
            pw = keyring.get_password(KEYRING_SERVICE_ALT, user)
            if pw is not None:
                keyring.set_password(KEYRING_SERVICE, user, pw)
        return pw
    except Exception:
        return None


def set_password(user: str, password: str) -> None:
    if keyring is None or not user:
        return
    try:
        keyring.set_password(KEYRING_SERVICE, user, password)
    except Exception:
        pass


def missing_setup(cfg: dict) -> list[str]:
    """Welche Pflichtangaben fehlen noch? (leer = alles eingerichtet)"""
    fehlt = []
    if not cfg.get("gruss", "").strip():
        fehlt.append("Name")
    if not cfg.get("kuerzel", "").strip():
        fehlt.append("Kürzel")
    if not cfg.get("absender", "").strip():
        fehlt.append("Absender")
    if not cfg.get("smtp_user", "").strip():
        fehlt.append("Benutzername")
    elif keyring is not None and not get_password(cfg["smtp_user"]):
        fehlt.append("Passwort")
    return fehlt
