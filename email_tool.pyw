"""Vertrieb Email Tool – verschickt Standard-Emails zu Projekten.

Start ohne Konsolenfenster:  pythonw email_tool.pyw   (oder Doppelklick)
"""

from __future__ import annotations

import imaplib
import json
import re
import time
from html import escape as esc
import smtplib
import subprocess
import ssl
import sys
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from PyQt6.QtCore import QByteArray, QObject, QPoint, QRect, QRectF, QSize, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QGuiApplication, QIcon, QIntValidator, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QFrame,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:  # Passwort sicher im Windows-Anmeldeinformationsspeicher ablegen
    import keyring
except ImportError:  # pragma: no cover
    keyring = None

APP_ID = "gcd.vertrieb.emailtool"
APP_NAME = "Vertrieb Email Tool"
KEYRING_SERVICE = "VertriebEmailTool"
KEYRING_SERVICE_ALT = "UliEmailTool"  # frühere Version – Passwort wird übernommen


def app_dir() -> Path:
    """Ordner des Skripts bzw. der .exe (PyInstaller)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_path(name: str) -> Path:
    """Pfad zu mitgelieferten Dateien (auch in der PyInstaller-onefile-exe)."""
    base = Path(getattr(sys, "_MEIPASS", app_dir()))
    return base / name


CONFIG_FILE = app_dir() / "config.json"

INFO_TEXTE = {  # erscheint als "Bestellung <b>gemäß …</b>"
    "PO": "gemäß PO",
    "Ang": "gemäß Angebot",
}

ZUSAETZE = [  # (Button, Text in der Mail) – erscheinen nach "Bauteile"
    ("US", "US Reinigung"),
    ("Lasertrennung", "Lasertrennung"),
    ("Beist", "Beistellung"),
]

ACCENT = "#2563eb"

STYLESHEET = """
* { font-family: "Segoe UI", "Segoe UI Variable", "Inter", sans-serif; font-size: 10pt; }
QMainWindow, QDialog { background: #f3f5f9; }
QWidget { color: #1f2937; }

/* Karten */
QGroupBox {
    background: #ffffff;
    border: 1px solid #e3e7ee;
    border-radius: 12px;
    margin-top: 22px;
    padding: 8px 14px 8px 14px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 6px;
    top: 2px;
    padding: 0 4px;
    color: #64748b;
    font-size: 9pt;
    font-weight: 600;
    letter-spacing: 1px;
}

QLabel { background: transparent; }
QLabel[role="section"] { color: #0f172a; font-weight: 600; }
QLabel[role="field"] { color: #64748b; }

/* Eingabefelder */
QLineEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background: #f8fafc;
    border: 1px solid #d7dde6;
    border-radius: 8px;
    padding: 5px 8px;
    selection-background-color: #bfdbfe;
    selection-color: #0f172a;
}
QLineEdit:hover, QPlainTextEdit:hover, QSpinBox:hover, QComboBox:hover { border-color: #b6c0ce; }
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid ACCENT;
    background: #ffffff;
}
QLineEdit[role="termin"] { color: #dc2626; font-weight: 700; }
QTabWidget::pane { background: #ffffff; border: 1px solid #e3e7ee; border-radius: 12px; top: -1px; }
QTabBar::tab {
    background: transparent; color: #64748b; padding: 8px 16px; margin-right: 4px;
    border: none; border-bottom: 2px solid transparent;
}
QTabBar::tab:selected { color: ACCENT; border-bottom: 2px solid ACCENT; font-weight: 600; }
QTabBar::tab:hover { color: #1f2937; }

/* Buttons */
QPushButton {
    background: #ffffff;
    border: 1px solid #d7dde6;
    border-radius: 8px;
    padding: 6px 14px;
    color: #1f2937;
}
QPushButton:hover { background: #f1f5f9; border-color: #b6c0ce; }
QPushButton:pressed { background: #e2e8f0; }
QPushButton:disabled { color: #94a3b8; background: #f1f5f9; }

QPushButton[role="primary"] {
    background: ACCENT; border: 1px solid ACCENT; color: #ffffff; font-weight: 600;
    padding: 8px 26px;
}
QPushButton[role="primary"]:hover { background: #1d4ed8; }
QPushButton[role="primary"]:pressed { background: #1e40af; }
QPushButton[role="primary"]:disabled { background: #93c5fd; border-color: #93c5fd; }

QPushButton[role="ghost"] { background: transparent; border: 1px solid transparent; color: #475569; }
QPushButton[role="ghost"]:hover { background: #e8edf4; }

/* Schalter (Pills) */
QPushButton[role="toggle"] {
    border-radius: 11px;
    padding: 4px 16px;
    background: #f1f5f9;
    border: 1px solid #e2e8f0;
    color: #334155;
}
QPushButton[role="toggle"]:hover { background: #e2e8f0; }
QPushButton[role="toggle"]:checked {
    background: ACCENT; border-color: ACCENT; color: #ffffff; font-weight: 600;
}

/* Shortcut-Chips */
QPushButton[role="chip"] {
    border-radius: 10px;
    padding: 3px 12px;
    background: #ffffff;
    border: 1px dashed #b6c0ce;
    color: #475569;
    font-size: 9pt;
}
QPushButton[role="chip"]:hover { border: 1px solid ACCENT; color: ACCENT; background: #f8fafc; }
QPushButton[role="chip"]:pressed { background: #e2e8f0; }

/* Vorschau */
QScrollArea#leftScroll, QWidget#leftInner { background: transparent; border: none; }
QWidget#editbar { background: #eff6ff; border: 1px solid #dbeafe; border-radius: 8px; }
QWidget#editbar QLabel { color: #1e40af; font-size: 9pt; }
QWidget#editbar QPushButton { color: ACCENT; font-weight: 600; }
QWidget#editbar QPushButton:hover { background: #dbeafe; }
QTextEdit#preview {
    background: #ffffff;
    border: none;
    padding: 18px 20px;
}

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #94a3b8; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QToolTip { background: #0f172a; color: #ffffff; border: none; padding: 4px 8px; border-radius: 4px; }
""".replace("ACCENT", ACCENT)


LABEL_W = 92


def fixed_label(text: str) -> QLabel:
    lbl = field_label(text)
    lbl.setFixedWidth(LABEL_W)
    return lbl


# Linien-Icons (Stil angelehnt an Lucide, 24x24, nur Kontur)
ICON_PATHS = {
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "copy": '<rect x="8" y="8" width="13" height="13" rx="2"/>'
            '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    "send": '<path d="M22 2 11 13"/><path d="m22 2-7 20-4-9-9-4Z"/>',
    "reset": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    "settings": '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0'
                'l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51'
                'a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08'
                'a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18'
                'a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39'
                'a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09'
                'a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25'
                'a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
    "pencil": '<path d="M21.17 6.81a1 1 0 0 0-3.98-3.98L3.84 16.17a2 2 0 0 0-.5.83l-1.32 4.35'
              'a.5.5 0 0 0 .62.62l4.35-1.32a2 2 0 0 0 .83-.5z"/><path d="m15 5 4 4"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/>'
                '<path d="M12 15V3"/>',
    "monitor": '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>',
    "plus": '<path d="M12 5v14"/><path d="M5 12h14"/>',
    "plug": '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/>'
            '<path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
    "folder": '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9'
              'A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
}


def icon(name: str, color: str = "#475569", size: int = 16, stroke: float = 2.0) -> QIcon:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">'
        f"{ICON_PATHS[name]}</svg>"
    )
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    scale = 3  # scharf auf hochauflösenden Bildschirmen
    pix = QPixmap(size * scale, size * scale)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    renderer.render(painter, QRectF(0, 0, size * scale, size * scale))
    painter.end()
    pix.setDevicePixelRatio(scale)
    return QIcon(pix)


def with_icon(btn: QPushButton, name: str, color: str = "#475569", size: int = 16) -> QPushButton:
    btn.setIcon(icon(name, color, size))
    btn.setIconSize(QSize(size, size))
    return btn


def set_role(widget, role: str):
    widget.setProperty("role", role)
    return widget


def field_label(text: str) -> QLabel:
    return set_role(QLabel(text), "field")

DEFAULT_CONFIG = {
    "projekt_basis": r"M:\Projekte_ab_20000",
    "smtp_server": "mail.gcd.de",
    "smtp_port": 587,
    "smtp_user": "",  # wird beim ersten Start abgefragt
    "smtp_security": "STARTTLS",  # STARTTLS | SSL/TLS | Keine
    # Kopie in den Gesendet-Ordner (IMAP, gleiche Zugangsdaten wie SMTP)
    "imap_aktiv": True,
    "imap_server": "mail.gcd.de",
    "imap_port": 993,
    "imap_ordner": "",  # leer = automatisch erkennen
    "absender": "",  # z.B. vorname.nachname@gcd.de
    "empfaenger": "vertrieb@gcd.de",  # mehrere mit ; trennen
    "cc": "",
    # Platzhalter: {nr} Projektnummer, {firma} Kundenordner, {board} Teil nach ___
    "betreff": "PN{nr} / Baugruppendaten {firma} {board} / {nr} sind auf M",
    "anrede": "Hallo Vertrieb,",
    "gruss": "",  # z.B. "VG\n<Vorname>" – wird beim ersten Start abgefragt
    # Textbausteine (Buttons unter den Textfeldern)
    "bausteine_info": [],
    "bausteine_achtung": [],
    # Buttons neben den Feldern im Bereich LP
    "shortcuts_lieferant": ["Fima", "KC", "Piu", "Zeroone"],
    "shortcuts_sonstiges": ["Daten sind bei Hersteller"],
    "shortcuts_bauteile": ["BOM"],
}


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass
    # alte / leere Werte auf neue Standards heben
    if not cfg.get("empfaenger"):
        cfg["empfaenger"] = DEFAULT_CONFIG["empfaenger"]
    # "Bestellung gemäß PO" ist jetzt ein eigener Schalter
    cfg["bausteine_info"] = [b for b in cfg.get("bausteine_info", []) if b != "Bestellung gemäß PO"]
    # Paste hat jetzt einen eigenen Bereich
    cfg["bausteine_achtung"] = [
        b for b in cfg.get("bausteine_achtung", []) if not b.upper().startswith("PASTE")
    ]
    if cfg.get("shortcuts_lieferant") in (["Lieferant 1", "Lieferant 2"], ["Fima", "KC", "Piu"]):
        cfg["shortcuts_lieferant"] = DEFAULT_CONFIG["shortcuts_lieferant"]
    if cfg.get("betreff") in ("", "Baugruppendaten Projekt {nr}"):
        cfg["betreff"] = DEFAULT_CONFIG["betreff"]
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def get_password(user: str) -> str | None:
    if keyring is None or not user:
        return None
    try:
        pw = keyring.get_password(KEYRING_SERVICE, user)
        if pw is None:
            # Passwort aus der früheren Version übernehmen
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


# --------------------------------------------------------------------------- #
# Projektsuche
# --------------------------------------------------------------------------- #
def find_project_dirs(base: Path, nr: str) -> list[Path]:
    """Sucht im 2. Unterordner nach einem Ordner, der mit der Projektnummer beginnt.

    Beispiel: M:\\Projekte_ab_20000\\FEINMETALL\\21156___G0056D-...
    """
    treffer: list[Path] = []
    for kunde in base.iterdir():
        try:
            if not kunde.is_dir():
                continue
            for projekt in kunde.iterdir():
                name = projekt.name
                if (name == nr or name.startswith(nr + "_")) and projekt.is_dir():
                    treffer.append(projekt)
        except (PermissionError, OSError):
            continue
    return sorted(treffer)


def parse_project_path(pfad: str, nr: str) -> tuple[str, str]:
    r"""Liefert (Firma, Boardname) aus dem Pfad.

    ...\FEINMETALL\21156___G0056D-V01-J7-00126-PV_1191274\...
      -> ("FEINMETALL", "G0056D-V01-J7-00126-PV_1191274")
    """
    teile = [t for t in pfad.replace("/", "\\").split("\\") if t]
    for i, teil in enumerate(teile):
        if nr and (teil == nr or teil.startswith(nr + "_")):
            firma = teile[i - 1] if i > 0 else ""
            board = teil.split("___", 1)[1] if "___" in teil else teil[len(nr):].lstrip("_")
            return firma, board
    return "", ""


def aktuell_path(projekt_dir: Path, nr: str) -> Path:
    return projekt_dir / f"{nr}.01" / "Aktuell"


class SearchWorker(QObject):
    finished = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, base: str, nr: str):
        super().__init__()
        self.base, self.nr = base, nr

    def run(self):
        try:
            base = Path(self.base)
            if not base.is_dir():
                raise FileNotFoundError(f"Basisordner nicht gefunden:\n{base}")
            self.finished.emit(find_project_dirs(base, self.nr))
        except Exception as exc:
            self.failed.emit(str(exc))


# --------------------------------------------------------------------------- #
# Email versenden
# --------------------------------------------------------------------------- #
def split_addresses(text: str) -> list[str]:
    return [a.strip() for a in text.replace(",", ";").split(";") if a.strip()]


def imap_connect(cfg: dict, password: str) -> imaplib.IMAP4_SSL:
    imap = imaplib.IMAP4_SSL(
        cfg["imap_server"], int(cfg["imap_port"]), ssl_context=ssl.create_default_context(), timeout=30
    )
    imap.login(cfg["smtp_user"], password)
    return imap


_LIST_RE = re.compile(rb'\((?P<flags>[^)]*)\) (?:"[^"]*"|NIL) (?P<name>.+)')


def find_sent_folder(imap: imaplib.IMAP4, wunsch: str = "") -> str:
    """Gesendet-Ordner finden: eingestellter Name, sonst \\Sent-Flag, sonst übliche Namen."""
    if wunsch:
        return wunsch
    typ, daten = imap.list()
    ordner: list[tuple[str, str]] = []
    for zeile in daten or []:
        if not isinstance(zeile, bytes):
            continue
        m = _LIST_RE.match(zeile)
        if not m:
            continue
        name = m.group("name").decode("utf-8", "replace").strip()
        if name.startswith('"') and name.endswith('"'):
            name = name[1:-1]
        ordner.append((m.group("flags").decode().lower(), name))
    for flags, name in ordner:
        if "\\sent" in flags:
            return name
    namen = {n.lower(): n for _, n in ordner}
    for kandidat in ("sent", "gesendet", "sent items", "gesendete objekte", "inbox.sent", "inbox/sent"):
        if kandidat in namen:
            return namen[kandidat]
    return "Sent"


def imap_quote(name: str) -> str:
    return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'


def save_to_sent(cfg: dict, password: str, msg: EmailMessage) -> str:
    """Legt die Mail im Gesendet-Ordner ab. Gibt den Ordnernamen zurück."""
    imap = imap_connect(cfg, password)
    try:
        ordner = find_sent_folder(imap, cfg.get("imap_ordner", "").strip())
        typ, daten = imap.append(
            imap_quote(ordner), "\\Seen", imaplib.Time2Internaldate(time.time()), msg.as_bytes()
        )
        if typ != "OK":
            raise RuntimeError(f"Server meldet: {daten}")
        return ordner
    finally:
        try:
            imap.logout()
        except Exception:
            pass


_SPAN_RE = re.compile(r'<span style="([^"]*)">(.*?)</span>', re.S | re.I)


def harden_html(html: str) -> str:
    """Farbe/Fett zusätzlich als <font color>/<b> schreiben.

    Viele Mailprogramme (z.B. Thunderbird "Vereinfachtes HTML", manche Webmailer)
    entfernen style-Attribute – die alten HTML-Tags bleiben dagegen erhalten.
    """

    def ersetze(m: re.Match) -> str:
        style, inhalt = m.group(1), m.group(2)
        farbe = re.search(r"(?<![-\w])color\s*:\s*(#[0-9a-fA-F]{3,6})", style)
        fett = re.search(r"font-weight\s*:\s*(bold|[6-9]00)", style)
        if fett:
            inhalt = f"<b>{inhalt}</b>"
        if farbe:
            inhalt = f'<font color="{farbe.group(1)}">{inhalt}</font>'
        return f'<span style="{style}">{inhalt}</span>'

    return _SPAN_RE.sub(ersetze, html)


def send_mail(cfg: dict, password: str, to: list[str], cc: list[str], subject: str,
              body: str, html: str | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = cfg["absender"]
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg.set_content(body)
    if html:
        html = harden_html(html)
        if not html.lstrip().lower().startswith(("<!doctype", "<html")):
            html = f"<html><body>{html}</body></html>"
        msg.add_alternative(html, subtype="html")

    ctx = ssl.create_default_context()
    host, port, sec = cfg["smtp_server"], int(cfg["smtp_port"]), cfg["smtp_security"]
    if sec == "SSL/TLS":
        server = smtplib.SMTP_SSL(host, port, context=ctx, timeout=30)
    else:
        server = smtplib.SMTP(host, port, timeout=30)
    with server:
        server.ehlo()
        if sec == "STARTTLS":
            server.starttls(context=ctx)
            server.ehlo()
        if cfg["smtp_user"]:
            server.login(cfg["smtp_user"], password)
        server.send_message(msg)
    return msg


class SendWorker(QObject):
    finished = pyqtSignal(str)  # Hinweis (leer = alles ok)
    failed = pyqtSignal(str)

    def __init__(self, *args):
        super().__init__()
        self.args = args

    def run(self):
        try:
            msg = send_mail(*self.args)
        except smtplib.SMTPAuthenticationError:
            self.failed.emit("Anmeldung fehlgeschlagen – Benutzername oder Passwort falsch.")
            return
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        cfg, password = self.args[0], self.args[1]
        if not cfg.get("imap_aktiv"):
            self.finished.emit("")
            return
        try:
            save_to_sent(cfg, password, msg)
            self.finished.emit("")
        except Exception as exc:
            self.finished.emit(
                f"Die Email wurde versendet, konnte aber nicht im Gesendet-Ordner "
                f"abgelegt werden:\n{type(exc).__name__}: {exc}"
            )


def smtp_test(v: dict, password: str):
    """Verbindung + Anmeldung testen; wirft eine Exception bei Fehler."""
    ctx = ssl.create_default_context()
    if v["smtp_security"] == "SSL/TLS":
        s = smtplib.SMTP_SSL(v["smtp_server"], int(v["smtp_port"]), context=ctx, timeout=15)
    else:
        s = smtplib.SMTP(v["smtp_server"], int(v["smtp_port"]), timeout=15)
    with s:
        s.ehlo()
        if v["smtp_security"] == "STARTTLS":
            s.starttls(context=ctx)
            s.ehlo()
        if v["smtp_user"]:
            s.login(v["smtp_user"], password)


def missing_setup(cfg: dict) -> list[str]:
    """Welche Pflichtangaben fehlen noch? (leer = alles eingerichtet)"""
    fehlt = []
    if not cfg.get("gruss", "").strip():
        fehlt.append("Name")
    if not cfg.get("absender", "").strip():
        fehlt.append("Absender")
    if not cfg.get("smtp_user", "").strip():
        fehlt.append("Benutzername")
    elif keyring is not None and not get_password(cfg["smtp_user"]):
        fehlt.append("Passwort")
    return fehlt


# --------------------------------------------------------------------------- #
# Einstellungen
# --------------------------------------------------------------------------- #
def as_bullets(text: str) -> str:
    """Jede nicht-leere Zeile bekommt ein '- ' davor (doppelte Striche vermeiden)."""
    zeilen = []
    for z in text.splitlines():
        z = z.strip()
        if not z:
            continue
        if z.startswith(("- ", "* ", "• ")):
            z = z[2:].strip()
        elif z == "-":
            continue
        zeilen.append(f"- {z}")
    return "\n".join(zeilen)


class FlowLayout(QLayout):
    """Layout, das Buttons automatisch in die nächste Zeile umbricht."""

    def __init__(self, parent=None, spacing: int = 4):
        super().__init__(parent)
        self._items = []
        self.setSpacing(spacing)
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _do_layout(self, rect, test):
        x, y, line_h, sp = rect.x(), rect.y(), 0, self.spacing()
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > rect.right() + 1 and line_h > 0:
                x, y, line_h = rect.x(), y + line_h + sp, 0
            if not test:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + sp
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y()


def append_line(edit: QPlainTextEdit, text: str):
    """Hängt einen Textbaustein als neue Zeile an das Textfeld an."""
    vorhanden = edit.toPlainText()
    if vorhanden and not vorhanden.endswith("\n"):
        vorhanden += "\n"
    edit.setPlainText(vorhanden + text)
    cursor = edit.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    edit.setTextCursor(cursor)
    edit.setFocus()


def append_inline(edit: QLineEdit, text: str):
    """Hängt Text mit ', ' an ein einzeiliges Feld an."""
    vorhanden = edit.text().strip()
    edit.setText(f"{vorhanden}, {text}" if vorhanden else text)
    edit.setFocus()


def bold_label(text: str) -> QLabel:
    return set_role(QLabel(text), "section")


# --------------------------------------------------------------------------- #
# Update (git)
# --------------------------------------------------------------------------- #
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


class UpdateWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, func):
        super().__init__()
        self.func = func

    def run(self):
        try:
            self.finished.emit(self.func())
        except Exception as exc:
            self.failed.emit(str(exc))


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
        target, args = _pythonw(), f'"{Path(__file__).resolve()}"'
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


def restart_app():
    """Tool neu starten (nach einem Update)."""
    from PyQt6.QtCore import QProcess
    QProcess.startDetached(sys.executable, [str(Path(__file__).resolve())], str(app_dir()))
    QApplication.quit()


class SettingsDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.cfg = cfg

        self.basis = QLineEdit(cfg["projekt_basis"])
        self.server = QLineEdit(cfg["smtp_server"])
        self.port = QLineEdit(str(cfg["smtp_port"]))
        self.port.setValidator(QIntValidator(1, 65535, self))
        self.port.setFixedWidth(90)
        self.security = QComboBox()
        self.security.addItems(["STARTTLS", "SSL/TLS", "Keine"])
        self.security.setCurrentText(cfg["smtp_security"])
        self.user = QLineEdit(cfg["smtp_user"])
        self.password = QLineEdit(get_password(cfg["smtp_user"]) or "")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.absender = QLineEdit(cfg["absender"])
        self.absender.setPlaceholderText("name@gcd.de")
        self.empfaenger = QLineEdit(cfg["empfaenger"])
        self.empfaenger.setPlaceholderText("vertrieb@firma.de; ...")
        self.cc = QLineEdit(cfg["cc"])
        self.betreff = QLineEdit(cfg["betreff"])
        self.betreff.setToolTip("Platzhalter: {nr} Projektnummer, {firma} Firma, {board} Boardname")
        self.anrede = QLineEdit(cfg["anrede"])
        self.gruss = QPlainTextEdit(cfg["gruss"])
        self.gruss.setFixedHeight(60)

        self.bs_info = QPlainTextEdit("\n".join(cfg["bausteine_info"]))
        self.bs_achtung = QPlainTextEdit("\n".join(cfg["bausteine_achtung"]))
        self.sc_lieferant = QPlainTextEdit("\n".join(cfg["shortcuts_lieferant"]))
        self.sc_sonst = QPlainTextEdit("\n".join(cfg["shortcuts_sonstiges"]))
        self.sc_bauteile = QPlainTextEdit("\n".join(cfg["shortcuts_bauteile"]))
        for w in (self.bs_info, self.bs_achtung, self.sc_lieferant, self.sc_sonst, self.sc_bauteile):
            w.setFixedHeight(64)

        def page(rows):
            w = QWidget()
            outer = QVBoxLayout(w)
            outer.setContentsMargins(16, 16, 16, 16)
            f = QFormLayout()
            outer.addLayout(f)
            outer.addStretch(1)
            f.setHorizontalSpacing(14)
            f.setVerticalSpacing(10)
            for label, widget in rows:
                if label is None:
                    f.addRow(widget)
                else:
                    f.addRow(field_label(label), widget)
            return w

        test_btn = with_icon(QPushButton("  Verbindung zum Server testen"), "plug")
        test_btn.clicked.connect(self.test_connection)
        server_rows = [
            ("Server", self.server),
            ("Port", self.port),
            ("Verbindungssicherheit", self.security),
            ("Benutzername", self.user),
            ("Passwort", self.password),
        ]
        if keyring is None:
            server_rows.append(("", QLabel("<i>'keyring' nicht installiert – Passwort wird nicht gespeichert.</i>")))
        server_rows.append(("", test_btn))

        self.imap_aktiv = QCheckBox("Kopie jeder gesendeten Mail im Gesendet-Ordner ablegen")
        self.imap_aktiv.setChecked(bool(cfg["imap_aktiv"]))
        self.imap_server = QLineEdit(cfg["imap_server"])
        self.imap_port = QLineEdit(str(cfg["imap_port"]))
        self.imap_port.setValidator(QIntValidator(1, 65535, self))
        self.imap_port.setFixedWidth(90)
        self.imap_ordner = QLineEdit(cfg["imap_ordner"])
        self.imap_ordner.setPlaceholderText("leer lassen = automatisch erkennen")
        imap_test = with_icon(QPushButton("  Gesendet-Ordner suchen"), "folder")
        imap_test.clicked.connect(self.test_imap)
        imap_rows = [
            (None, self.imap_aktiv),
            ("IMAP-Server", self.imap_server),
            ("Port (SSL/TLS)", self.imap_port),
            ("Ordner", self.imap_ordner),
            ("", set_role(QLabel("Benutzername und Passwort wie beim Postausgangs-Server."), "field")),
            ("", imap_test),
        ]

        tabs = QTabWidget()
        tabs.addTab(page([
            ("Absender", self.absender),
            ("Standard-Empfänger", self.empfaenger),
            ("Standard-CC", self.cc),
            ("Betreff", self.betreff),
            ("", set_role(QLabel("Platzhalter: {nr}  {firma}  {board}"), "field")),
            ("Anrede", self.anrede),
            ("Gruß", self.gruss),
            ("Projekt-Basisordner", self.basis),
        ]), "Email")
        tabs.addTab(page(server_rows), "Server (SMTP)")
        tabs.addTab(page(imap_rows), "Gesendet-Ordner")
        tabs.addTab(page([
            (None, set_role(QLabel("Ein Eintrag pro Zeile – jeder wird ein Button."), "field")),
            ("LP → Lieferant", self.sc_lieferant),
            ("LP → Sonstiges", self.sc_sonst),
            ("Bauteile", self.sc_bauteile),
            ("Achtung → Freitext", self.bs_achtung),
            ("Info (Text)", self.bs_info),
        ]), "Textbausteine")
        tabs.addTab(self._system_page(), "System")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Speichern")
        set_role(buttons.button(QDialogButtonBox.StandardButton.Save), "primary")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        set_role(buttons.button(QDialogButtonBox.StandardButton.Cancel), "ghost")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        layout.addWidget(tabs)
        layout.addWidget(buttons)
        self.resize(620, self.sizeHint().height())

    def values(self) -> dict:
        return {
            "projekt_basis": self.basis.text().strip(),
            "smtp_server": self.server.text().strip(),
            "smtp_port": int(self.port.text() or 587),
            "smtp_security": self.security.currentText(),
            "imap_aktiv": self.imap_aktiv.isChecked(),
            "imap_server": self.imap_server.text().strip(),
            "imap_port": int(self.imap_port.text() or 993),
            "imap_ordner": self.imap_ordner.text().strip(),
            "smtp_user": self.user.text().strip(),
            "absender": self.absender.text().strip(),
            "empfaenger": self.empfaenger.text().strip(),
            "cc": self.cc.text().strip(),
            "betreff": self.betreff.text(),
            "anrede": self.anrede.text(),
            "gruss": self.gruss.toPlainText(),
            "bausteine_info": [z.strip() for z in self.bs_info.toPlainText().splitlines() if z.strip()],
            "bausteine_achtung": [z.strip() for z in self.bs_achtung.toPlainText().splitlines() if z.strip()],
            "shortcuts_lieferant": [z.strip() for z in self.sc_lieferant.toPlainText().splitlines() if z.strip()],
            "shortcuts_sonstiges": [z.strip() for z in self.sc_sonst.toPlainText().splitlines() if z.strip()],
            "shortcuts_bauteile": [z.strip() for z in self.sc_bauteile.toPlainText().splitlines() if z.strip()],
        }

    # ----- Update-Tab -----
    def _system_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)
        self._bg_jobs: list = []

        lay.addWidget(bold_label("Version & Update"))

        grund = update_possible()
        version = set_role(QLabel(f"Installierte Version:  {current_version() if not grund else '–'}"), "field")
        lay.addWidget(version)

        self.upd_status = QLabel(grund or "Prüft, ob es auf GitHub eine neuere Version gibt.")
        self.upd_status.setWordWrap(True)
        set_role(self.upd_status, "field")
        lay.addWidget(self.upd_status)

        self.upd_list = QLabel()
        self.upd_list.setWordWrap(True)
        self.upd_list.hide()
        lay.addWidget(self.upd_list)

        row = QHBoxLayout()
        self.upd_check = with_icon(QPushButton("  Nach Updates suchen"), "search")
        self.upd_check.clicked.connect(self._check_updates)
        self.upd_apply = with_icon(set_role(QPushButton("  Jetzt aktualisieren"), "primary"),
                                   "download", "#ffffff")
        self.upd_apply.clicked.connect(self._apply_update)
        self.upd_apply.hide()
        row.addWidget(self.upd_check)
        row.addWidget(self.upd_apply)
        row.addStretch(1)
        lay.addLayout(row)
        self.upd_check.setEnabled(not grund)

        # --- Desktop-Verknüpfung ---
        trenner = QWidget()
        trenner.setFixedHeight(1)
        trenner.setStyleSheet("background: #e3e7ee;")
        lay.addSpacing(8)
        lay.addWidget(trenner)
        lay.addSpacing(4)
        lay.addWidget(bold_label("Desktop-Verknüpfung"))
        sc_grund = shortcut_possible()
        self.sc_status = set_role(QLabel(sc_grund or "Prüfe …"), "field")
        self.sc_status.setWordWrap(True)
        lay.addWidget(self.sc_status)
        sc_row = QHBoxLayout()
        self.sc_btn = with_icon(QPushButton("  Verknüpfung erstellen"), "monitor")
        self.sc_btn.clicked.connect(self._create_shortcut)
        self.sc_btn.setEnabled(False)
        sc_row.addWidget(self.sc_btn)
        sc_row.addStretch(1)
        lay.addLayout(sc_row)
        lay.addStretch(1)
        if not sc_grund:
            self._bg(shortcut_status, self._sc_status_done, lambda e: self._sc_set(f"Fehler: {e}", "#dc2626"))
        return w

    # ----- Verknüpfung -----
    def _sc_set(self, text: str, color: str = "#64748b"):
        self.sc_status.setStyleSheet(f"color: {color};")
        self.sc_status.setText(text)

    def _sc_status_done(self, status: str):
        self.sc_btn.setEnabled(True)
        if status == "alle":
            self._sc_set("Auf dem Desktop und im Startmenü vorhanden (für alle Benutzer).", "#16a34a")
            self.sc_btn.setText("  Verknüpfung reparieren")
        elif status == "benutzer":
            self._sc_set("Auf dem Desktop und im Startmenü vorhanden.", "#16a34a")
            self.sc_btn.setText("  Verknüpfung reparieren")
        else:
            self._sc_set("Noch keine Verknüpfung auf dem Desktop.")
            self.sc_btn.setText("  Verknüpfung erstellen")

    def _create_shortcut(self):
        self.sc_btn.setEnabled(False)
        self._sc_set("Erstelle Verknüpfung …")
        self._bg(create_shortcuts, self._sc_created, lambda e: (
            self.sc_btn.setEnabled(True), self._sc_set(f"Fehler: {e}", "#dc2626")))

    def _sc_created(self, ergebnis: str):
        self.sc_btn.setEnabled(True)
        self.sc_btn.setText("  Verknüpfung reparieren")
        if ergebnis == "alle-unveraendert":
            self._sc_set("Es gibt bereits eine Verknüpfung für alle Benutzer. Zum Ändern sind "
                         "Admin-Rechte nötig – dafür Email_tool_setup.bat erneut ausführen.", "#64748b")
        else:
            self._sc_set("Verknüpfung „" + APP_NAME + "“ auf dem Desktop und im Startmenü angelegt.", "#16a34a")

    def _bg(self, func, ok, fail):
        """Funktion im Hintergrund ausführen (Fenster bleibt bedienbar)."""
        thread = QThread(self)
        worker = UpdateWorker(func)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(ok)
        worker.failed.connect(fail)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        self._bg_jobs.append((thread, worker))
        thread.start()

    def _upd_run(self, func, ok, fail):
        self._bg(func, ok, fail)

    def _upd_set(self, text: str, color: str = "#64748b"):
        self.upd_status.setStyleSheet(f"color: {color};")
        self.upd_status.setText(text)

    def _check_updates(self):
        self.upd_check.setEnabled(False)
        self.upd_apply.hide()
        self.upd_list.hide()
        self._upd_set("Suche nach Updates …")
        self._upd_run(check_updates, self._check_done, self._upd_failed)

    def _check_done(self, neu: list):
        self.upd_check.setEnabled(True)
        if not neu:
            self._upd_set("Du hast die neueste Version.", "#16a34a")
            return
        self._upd_set(f"{len(neu)} Änderung(en) verfügbar:", ACCENT)
        self.upd_list.setText("<br>".join(f"•&nbsp; {esc(z)}" for z in neu[:12])
                              + ("<br>…" if len(neu) > 12 else ""))
        self.upd_list.show()
        self.upd_apply.show()

    def _apply_update(self):
        self.upd_check.setEnabled(False)
        self.upd_apply.setEnabled(False)
        self._upd_set("Lade Update … (kann bei neuen Paketen etwas dauern)")
        self._upd_run(apply_update, self._apply_done, self._upd_failed)

    def _apply_done(self, _pakete):
        self.upd_list.hide()
        self.upd_apply.hide()
        self._upd_set("Update installiert.", "#16a34a")
        if QMessageBox.question(
            self, "Update installiert", "Das Update ist installiert. Jetzt neu starten?"
        ) == QMessageBox.StandardButton.Yes:
            restart_app()

    def _upd_failed(self, err: str):
        self.upd_check.setEnabled(True)
        self.upd_apply.setEnabled(True)
        self._upd_set(f"Fehler: {err}", "#dc2626")

    def test_imap(self):
        v = dict(self.cfg, **self.values())
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            imap = imap_connect(v, self.password.text())
            try:
                ordner = find_sent_folder(imap, v["imap_ordner"])
                typ, _ = imap.select(imap_quote(ordner), readonly=True)
            finally:
                imap.logout()
            QApplication.restoreOverrideCursor()
            if typ == "OK":
                QMessageBox.information(self, "Gesendet-Ordner", f"Gefunden: „{ordner}“")
            else:
                QMessageBox.warning(self, "Gesendet-Ordner", f"Ordner „{ordner}“ existiert nicht.")
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Test fehlgeschlagen", f"{type(exc).__name__}: {exc}")

    def test_connection(self):
        v = self.values()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            smtp_test(v, self.password.text())
            QApplication.restoreOverrideCursor()
            QMessageBox.information(self, "Test", "Verbindung und Anmeldung erfolgreich.")
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Test fehlgeschlagen", f"{type(exc).__name__}: {exc}")

    def accept(self):
        self.cfg.update(self.values())
        save_config(self.cfg)
        if self.password.text():
            set_password(self.cfg["smtp_user"], self.password.text())
        super().accept()


class ToggleRow(QWidget):
    """Reihe von Umschalt-Buttons, von denen höchstens einer aktiv ist.

    allow_none=True: erneuter Klick auf den aktiven Button hebt die Auswahl auf.
    """

    changed = pyqtSignal()

    def __init__(self, labels: list[str], allow_none: bool = True, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.allow_none = allow_none
        self.buttons: list[QPushButton] = []
        for text in labels:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setMinimumWidth(70)
            set_role(btn, "toggle")
            btn.clicked.connect(lambda checked, b=btn: self._clicked(b, checked))
            lay.addWidget(btn)
            self.buttons.append(btn)
        lay.addStretch(1)

    def _clicked(self, btn: QPushButton, checked: bool):
        if checked:
            for other in self.buttons:
                if other is not btn:
                    other.setChecked(False)
        elif not self.allow_none:
            btn.setChecked(True)
        self.changed.emit()

    def value(self) -> str:
        for b in self.buttons:
            if b.isChecked():
                return b.text()
        return ""

    def set_value(self, text: str):
        for b in self.buttons:
            b.setChecked(b.text() == text)
        self.changed.emit()


def shortcut_button(text: str, slot) -> QPushButton:
    btn = with_icon(QPushButton(text), "plus", "#64748b", 12)
    btn.setToolTip(f"„{text}“ einfügen")
    set_role(btn, "chip")
    btn.clicked.connect(lambda: slot(text))
    return btn


# --------------------------------------------------------------------------- #
# Hauptfenster
# --------------------------------------------------------------------------- #
class OnboardingDialog(QDialog):
    """Kurze Ersteinrichtung: nur die Angaben, ohne die nichts geht."""

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle(f"Willkommen – {APP_NAME}")
        self.setMinimumWidth(500)

        titel = QLabel("Willkommen!")
        titel.setStyleSheet("font-size: 15pt; font-weight: 600;")
        intro = set_role(QLabel(
            "Bevor es losgeht, brauche ich ein paar Angaben zu dir. "
            "Alles lässt sich später unter „Einstellungen“ ändern."
        ), "field")
        intro.setWordWrap(True)

        # Name aus vorhandenem Gruß übernehmen ("VG\n<Name>" -> "<Name>")
        alt_gruss = [z for z in cfg.get("gruss", "").splitlines() if z.strip()]
        self.name = QLineEdit(alt_gruss[-1] if len(alt_gruss) > 1 else "")
        self.name.setPlaceholderText("Vorname")
        self.absender = QLineEdit(cfg.get("absender", ""))
        self.absender.setPlaceholderText("vorname.nachname@gcd.de")
        self.user = QLineEdit(cfg.get("smtp_user", ""))
        self.user.setPlaceholderText("Anmeldename am Mailserver")
        self.password = QLineEdit(get_password(cfg.get("smtp_user", "")) or "")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)

        self.gruss_preview = set_role(QLabel(), "field")
        self.name.textChanged.connect(self._update_gruss)
        self._update_gruss()

        karte = QGroupBox("DEINE DATEN")
        f = QFormLayout(karte)
        f.setHorizontalSpacing(14)
        f.setVerticalSpacing(8)
        f.addRow(fixed_label("Name"), self.name)
        f.addRow("", self.gruss_preview)
        f.addRow(fixed_label("Email-Adresse"), self.absender)
        f.addRow(fixed_label("Benutzername"), self.user)
        f.addRow(fixed_label("Passwort"), self.password)
        hinweis = set_role(QLabel(
            "Benutzername und Passwort sind dieselben wie in Thunderbird "
            f"(Postausgangs-Server {cfg['smtp_server']}). Das Passwort wird sicher im "
            "Windows-Anmeldespeicher abgelegt."
        ), "field")
        hinweis.setWordWrap(True)
        f.addRow("", hinweis)

        test_btn = with_icon(QPushButton("  Verbindung testen"), "plug")
        test_btn.clicked.connect(self.test_connection)
        self.status = QLabel("")
        self.status.setWordWrap(True)

        later = set_role(QPushButton("Später"), "ghost")
        later.clicked.connect(self.reject)
        save = set_role(QPushButton("Speichern und loslegen"), "primary")
        save.clicked.connect(self.accept)
        save.setDefault(True)

        test_row = QHBoxLayout()
        test_row.addWidget(test_btn)
        test_row.addWidget(self.status, 1)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(later)
        btn_row.addWidget(save)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(10)
        lay.addWidget(titel)
        lay.addWidget(intro)
        lay.addWidget(karte)
        lay.addLayout(test_row)
        lay.addSpacing(6)
        lay.addLayout(btn_row)

        for feld in (self.name, self.absender, self.user, self.password):
            feld.textChanged.connect(lambda _=None: self.status.clear())

        # Fokus auf das erste leere Feld
        for feld in (self.name, self.absender, self.user, self.password):
            if not feld.text():
                feld.setFocus()
                break

    def _update_gruss(self):
        name = self.name.text().strip() or "…"
        self.gruss_preview.setText(f"Gruß in der Mail:  VG / {name}")

    def _werte(self) -> dict:
        return dict(self.cfg, absender=self.absender.text().strip(), smtp_user=self.user.text().strip())

    def _set_status(self, text: str, ok: bool):
        self.status.setStyleSheet(f"color: {'#16a34a' if ok else '#dc2626'};")
        self.status.setText(text)

    def test_connection(self):
        if not self.user.text().strip() or not self.password.text():
            self._set_status("Bitte Benutzername und Passwort eintragen.", False)
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            smtp_test(self._werte(), self.password.text())
            self._set_status("Anmeldung erfolgreich.", True)
        except smtplib.SMTPAuthenticationError:
            self._set_status("Benutzername oder Passwort falsch.", False)
        except Exception as exc:
            self._set_status(f"{type(exc).__name__}: {exc}", False)
        finally:
            QApplication.restoreOverrideCursor()

    def accept(self):
        fehlt = [n for n, w in (("Name", self.name), ("Email-Adresse", self.absender),
                                ("Benutzername", self.user), ("Passwort", self.password))
                 if not w.text().strip()]
        if fehlt:
            self._set_status("Bitte noch ausfüllen: " + ", ".join(fehlt), False)
            return
        if "@" not in self.absender.text():
            self._set_status("Die Email-Adresse sieht nicht vollständig aus.", False)
            return
        self.cfg.update(self._werte())
        self.cfg["gruss"] = f"VG\n{self.name.text().strip()}"
        save_config(self.cfg)
        set_password(self.cfg["smtp_user"], self.password.text())
        super().accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.session_password: str | None = None
        self._thread: QThread | None = None
        self.setWindowTitle(APP_NAME)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(18, 8, 18, 16)
        outer.setSpacing(12)
        columns = QHBoxLayout()
        columns.setSpacing(16)
        outer.addLayout(columns, 1)
        # Linke Spalte scrollbar: auf kleinen Bildschirmen wird gescrollt statt gestaucht
        left_w = QWidget()
        left_w.setObjectName("leftInner")
        root = QVBoxLayout(left_w)
        root.setContentsMargins(0, 0, 10, 0)  # Platz für die Scrollleiste
        root.setSpacing(4)
        self.left_scroll = QScrollArea()
        self.left_scroll.setObjectName("leftScroll")
        self.left_scroll.setWidget(left_w)
        self.left_scroll.setWidgetResizable(True)
        self.left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.left_scroll.viewport().setAutoFillBackground(False)
        self._left_inner = left_w
        columns.addWidget(self.left_scroll, 5)

        # --- Projekt ---
        proj_box = QGroupBox("PROJEKT")
        pl = QGridLayout(proj_box)
        pl.setColumnMinimumWidth(0, LABEL_W)
        pl.setHorizontalSpacing(12)
        pl.setVerticalSpacing(6)
        self.nr_edit = QLineEdit()
        self.nr_edit.setMaxLength(10)
        self.nr_edit.returnPressed.connect(self.search)
        self.search_btn = with_icon(QPushButton("  Suchen"), "search")
        self.search_btn.clicked.connect(self.search)
        pl.addWidget(field_label("Projektnummer"), 0, 0)
        pl.addWidget(self.nr_edit, 0, 1)
        pl.addWidget(self.search_btn, 0, 2)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("wird nach der Suche gefüllt (kann auch angepasst werden)")
        self.path_edit.textChanged.connect(self.update_preview)
        self.path_edit.textChanged.connect(self.update_subject)
        copy_btn = with_icon(QPushButton("  Kopieren"), "copy")
        copy_btn.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.path_edit.text()))
        pl.addWidget(field_label("Pfad"), 1, 0)
        pl.addWidget(self.path_edit, 1, 1)
        pl.addWidget(copy_btn, 1, 2)

        self.dev_edit = QLineEdit()
        self.dev_edit.setPlaceholderText("optional – erscheint im Betreff in Klammern hinter der Firma")
        self.dev_edit.textChanged.connect(self.update_subject)
        pl.addWidget(field_label("Entwickler"), 2, 0)
        pl.addWidget(self.dev_edit, 2, 1, 1, 2)
        self.status_lbl = QLabel("")
        pl.addWidget(self.status_lbl, 3, 0, 1, 3)
        root.addWidget(proj_box)

        # --- Empfänger ---
        mail_box = QGroupBox("EMAIL")
        ml = QFormLayout(mail_box)
        ml.setHorizontalSpacing(12)
        ml.setVerticalSpacing(6)
        self.to_edit = QLineEdit(self.cfg["empfaenger"])
        self.cc_edit = QLineEdit(self.cfg["cc"])
        self.subject_edit = QLineEdit()
        ml.addRow(fixed_label("An"), self.to_edit)
        ml.addRow(fixed_label("CC"), self.cc_edit)
        ml.addRow(fixed_label("Betreff"), self.subject_edit)
        root.addWidget(mail_box)

        # --- Info ---
        info_box = QGroupBox("INFO")
        ig = QGridLayout(info_box)
        ig.setColumnMinimumWidth(0, LABEL_W)
        ig.setHorizontalSpacing(12)
        ig.setVerticalSpacing(6)
        self.info_mode = ToggleRow(["PO", "Ang"])
        self.info_mode.changed.connect(self.update_preview)
        ig.addWidget(field_label("Bestellung"), 0, 0)
        ig.addWidget(self.info_mode, 0, 1)

        self.info_panel = QWidget()
        il = QVBoxLayout(self.info_panel)
        il.setContentsMargins(0, 0, 0, 0)
        self.info_edit = QPlainTextEdit()
        self.info_edit.setFixedHeight(2 * self.info_edit.fontMetrics().lineSpacing() + 18)
        self.info_edit.textChanged.connect(self.update_preview)
        il.addWidget(self.info_edit)
        self.info_layout = il
        self.info_buttons: QWidget | None = None
        ig.addWidget(self.info_panel, 1, 1)

        self.termin_edit = QLineEdit()
        set_role(self.termin_edit, "termin")
        self.termin_edit.textChanged.connect(self.update_preview)
        ig.addWidget(field_label("Liefertermin"), 2, 0)
        ig.addWidget(self.termin_edit, 2, 1)
        root.addWidget(info_box)

        # --- Achtung ---
        warn_box = QGroupBox("ACHTUNG")
        ag = QGridLayout(warn_box)
        ag.setColumnMinimumWidth(0, LABEL_W)
        ag.setHorizontalSpacing(12)
        ag.setVerticalSpacing(6)
        ag.setColumnStretch(1, 1)
        r = 0

        # LP
        ag.addWidget(bold_label("LP"), r, 0, 1, 2)
        r += 1
        lp_row = QHBoxLayout()
        lp_row.setSpacing(8)
        self.lp_typ = ToggleRow(["Einzel-LP", "Nutzen"])
        self.lp_typ.changed.connect(self.update_preview)
        lp_row.addWidget(self.lp_typ)
        lp_row.addSpacing(12)
        lp_row.addWidget(field_label("Anzahl"))
        self.lp_anzahl = QLineEdit()
        self.lp_anzahl.setFixedWidth(60)
        self.lp_anzahl.textChanged.connect(self.update_preview)
        lp_row.addWidget(self.lp_anzahl)
        self.lp_anzahl2 = QLineEdit()
        self.lp_anzahl2.setFixedWidth(160)
        self.lp_anzahl2.textChanged.connect(self.update_preview)
        lp_row.addWidget(self.lp_anzahl2)
        lp_row.addStretch(1)
        ag.addWidget(field_label("Art"), r, 0)
        ag.addLayout(lp_row, r, 1)
        r += 1

        self.lieferant_edit = QLineEdit()
        self.lieferant_edit.textChanged.connect(self.update_preview)
        self.lieferant_row = QHBoxLayout()
        self.lieferant_row.setSpacing(8)
        self.lieferant_row.addWidget(self.lieferant_edit, 1)
        ag.addWidget(field_label("Lieferant"), r, 0)
        ag.addLayout(self.lieferant_row, r, 1)
        r += 1

        self.sonst_edit = QLineEdit()
        self.sonst_edit.textChanged.connect(self.update_preview)
        self.sonst_row = QHBoxLayout()
        self.sonst_row.setSpacing(8)
        self.sonst_row.addWidget(self.sonst_edit, 1)
        ag.addWidget(field_label("Sonstiges"), r, 0)
        ag.addLayout(self.sonst_row, r, 1)
        r += 1

        # Paste
        ag.addWidget(bold_label("Paste"), r, 0)
        self.paste = ToggleRow(["von M", "Hersteller", "Keine"])
        self.paste.changed.connect(self.update_preview)
        ag.addWidget(self.paste, r, 1)
        r += 1

        # Bauteile
        ag.addWidget(bold_label("Bauteile"), r, 0)
        self.bauteile_edit = QLineEdit()
        self.bauteile_edit.textChanged.connect(self.update_preview)
        self.bauteile_row = QHBoxLayout()
        self.bauteile_row.setSpacing(8)
        self.bauteile_row.addWidget(self.bauteile_edit, 1)
        ag.addLayout(self.bauteile_row, r, 1)
        r += 1

        # Zusätze – jeder aktive wird ein eigener Aufzählungspunkt
        zusatz_row = QHBoxLayout()
        zusatz_row.setSpacing(8)
        self.zusatz_buttons: list[tuple[QPushButton, str]] = []
        for label, ausgabe in ZUSAETZE:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setMinimumWidth(70)
            btn.setToolTip(ausgabe)
            set_role(btn, "toggle")
            btn.toggled.connect(self.update_preview)
            zusatz_row.addWidget(btn)
            self.zusatz_buttons.append((btn, ausgabe))
        # Textfeld zu "Beist" – Tippen aktiviert den Schalter automatisch
        self.beist_btn = self.zusatz_buttons[-1][0]
        self.beist_edit = QLineEdit()
        self.beist_edit.textChanged.connect(self.beist_text_changed)
        zusatz_row.addWidget(self.beist_edit, 1)
        ag.addLayout(zusatz_row, r, 1)
        r += 1

        # Freitext
        ag.addWidget(bold_label("Freitext"), r, 0, Qt.AlignmentFlag.AlignTop)
        frei = QVBoxLayout()
        self.warn_edit = QPlainTextEdit()
        self.warn_edit.setPlaceholderText("jede Zeile wird ein eigener Aufzählungspunkt")
        self.warn_edit.setFixedHeight(4 * self.warn_edit.fontMetrics().lineSpacing() + 14)
        self.warn_edit.textChanged.connect(self.update_preview)
        frei.addWidget(self.warn_edit)
        self.warn_layout = frei
        self.warn_buttons: QWidget | None = None
        ag.addLayout(frei, r, 1)
        root.addWidget(warn_box)
        root.addStretch(1)

        self.lieferant_shortcuts: QWidget | None = None
        self.sonst_shortcuts: QWidget | None = None
        self.bauteile_shortcuts: QWidget | None = None
        self.build_baustein_buttons()

        # --- Vorschau (rechts) ---
        prev_box = QGroupBox("VORSCHAU")
        prl = QVBoxLayout(prev_box)
        prl.setContentsMargins(4, 4, 4, 4)
        # Hinweisleiste, sobald die Vorschau von Hand geändert wurde
        self.edit_bar = QWidget()
        self.edit_bar.setObjectName("editbar")
        eb = QHBoxLayout(self.edit_bar)
        eb.setContentsMargins(10, 6, 6, 6)
        eb.setSpacing(8)
        eb_icon = QLabel()
        eb_icon.setPixmap(icon("pencil", ACCENT, 16).pixmap(16, 16))
        eb.addWidget(eb_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        eb_lbl = QLabel("Von Hand bearbeitet – Änderungen an den Feldern werden nicht mehr übernommen.")
        eb_lbl.setWordWrap(True)
        eb.addWidget(eb_lbl, 1)
        reset_btn = with_icon(set_role(QPushButton("  Neu aus Feldern"), "ghost"), "reset", ACCENT)
        reset_btn.clicked.connect(self.reset_preview)
        eb.addWidget(reset_btn)
        self.edit_bar.hide()
        prl.addWidget(self.edit_bar)

        self.preview = QTextEdit()
        self.preview.setObjectName("preview")
        self.preview.setToolTip("Die Vorschau kann direkt bearbeitet werden – gesendet wird, was hier steht.")
        self.preview.textChanged.connect(self.preview_edited)
        self.preview_manuell = False
        self._preview_update = False
        prl.addWidget(self.preview)
        columns.addWidget(prev_box, 4)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        settings_btn = with_icon(set_role(QPushButton("  Einstellungen"), "ghost"), "settings")
        settings_btn.clicked.connect(self.open_settings)
        btn_row.addWidget(settings_btn)
        btn_row.addStretch(1)
        clear_btn = with_icon(set_role(QPushButton("  Leeren"), "ghost"), "reset")
        clear_btn.clicked.connect(self.clear)
        btn_row.addWidget(clear_btn)
        self.send_btn = with_icon(set_role(QPushButton("  Senden"), "primary"), "send", "#ffffff")
        self.send_btn.setMinimumWidth(140)
        self.send_btn.clicked.connect(self.send)
        btn_row.addWidget(self.send_btn)
        outer.addLayout(btn_row)

        self.nr_edit.textChanged.connect(self.update_subject)
        self.info_mode.set_value("PO")
        self.update_subject()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        # Breite so, dass links nie horizontal gescrollt werden muss
        self.left_scroll.setMinimumWidth(
            self._left_inner.minimumSizeHint().width() + self.left_scroll.verticalScrollBar().sizeHint().width()
        )
        self.resize(min(1400, screen.width() - 40), min(1000, screen.height() - 60))

    # ----- Hilfen -----
    def nr(self) -> str:
        return self.nr_edit.text().strip()

    def update_subject(self):
        firma, board = parse_project_path(self.path_edit.text(), self.nr())
        entwickler = self.dev_edit.text().strip()
        if entwickler:
            firma = f"{firma} ({entwickler})" if firma else f"({entwickler})"
        betreff = (
            self.cfg["betreff"]
            .replace("{nr}", self.nr())
            .replace("{firma}", firma)
            .replace("{board}", board)
        )
        self.subject_edit.setText(" ".join(betreff.split()))

    def beist_text_changed(self, text: str):
        if text.strip() and not self.beist_btn.isChecked():
            self.beist_btn.setChecked(True)  # löst update_preview aus
        else:
            self.update_preview()

    def lp_text(self) -> str:
        teile = []
        typ = self.lp_typ.value()
        if typ:
            teile.append(typ)
        anzahl = ", ".join(t for t in (self.lp_anzahl.text().strip(), self.lp_anzahl2.text().strip()) if t)
        if anzahl:
            teile.append(f"Anzahl: {anzahl}")
        if self.lieferant_edit.text().strip():
            teile.append(f"Lieferant: {self.lieferant_edit.text().strip()}")
        if self.sonst_edit.text().strip():
            teile.append(self.sonst_edit.text().strip())
        return ", ".join(teile)

    def build_mail(self) -> tuple[str, str]:
        """Liefert (Text, HTML) der Mail."""
        absaetze: list[list[tuple[str, str]]] = []  # Absätze aus Zeilen (text, html)

        def zeile(text: str, html: str | None = None) -> tuple[str, str]:
            return text, html if html is not None else esc(text)

        absaetze.append([zeile(self.cfg["anrede"])])
        absaetze.append([zeile(f"die Baugruppendaten für das Board sind auf {self.path_edit.text().strip()}")])

        info: list[tuple[str, str]] = []
        modus = self.info_mode.value()
        zeilen = [z.rstrip() for z in self.info_edit.toPlainText().strip().splitlines()]
        if modus in INFO_TEXTE:
            # "Bestellung: gemäß PO, <Text>"  (gemäß … fett)
            rest = f", {zeilen[0]}" if zeilen else ""
            info.append(zeile(
                f"Bestellung: {INFO_TEXTE[modus]}{rest}",
                f"Bestellung: <b>{esc(INFO_TEXTE[modus])}</b>{esc(rest)}",
            ))
            info += [zeile(z) for z in zeilen[1:]]
        elif zeilen:
            info.append(zeile(f"Bestellung: {zeilen[0]}"))
            info += [zeile(z) for z in zeilen[1:]]
        termin = self.termin_edit.text().strip()
        if termin:
            info.append(zeile(
                f"Liefertermin: {termin}",
                f'<span style="color:#c00000;font-weight:bold">Liefertermin: {esc(termin)}</span>',
            ))
        if info:
            absaetze.append(info)

        punkte: list[str] = []
        if self.lp_text():
            punkte.append(f"LP -> {self.lp_text()}")
        if self.paste.value():
            punkte.append(f"Paste -> {self.paste.value()}")
        if self.bauteile_edit.text().strip():
            punkte.append(f"Bauteile -> {self.bauteile_edit.text().strip()}")
        for btn, ausgabe in self.zusatz_buttons:
            if not btn.isChecked():
                continue
            if btn is self.beist_btn and self.beist_edit.text().strip():
                ausgabe = f"{ausgabe} -> {self.beist_edit.text().strip()}"
            punkte.append(ausgabe)
        frei = as_bullets(self.warn_edit.toPlainText())
        punkte += [z[2:] for z in frei.splitlines()]
        if punkte:
            absaetze.append([zeile("Achtung:")])
            absaetze.append([zeile(f"- {p}") for p in punkte])

        gruss = [zeile(z) for z in self.cfg["gruss"].splitlines()]
        if gruss:
            absaetze.append(gruss)

        text = "\n\n".join("\n".join(t for t, _ in a) for a in absaetze)
        html = (
            '<div style="font-family:Calibri,Arial,sans-serif;font-size:11pt">'
            + "<br><br>".join("<br>".join(h for _, h in a) for a in absaetze)
            + "</div>"
        )
        return text, html

    def update_preview(self):
        if not hasattr(self, "preview") or self.preview_manuell:
            return
        self._preview_update = True
        self.preview.setHtml(self.build_mail()[1])
        self._preview_update = False

    def preview_edited(self):
        if self._preview_update or self.preview_manuell:
            return
        self.preview_manuell = True
        self.edit_bar.show()

    def reset_preview(self):
        self.preview_manuell = False
        self.edit_bar.hide()
        self.update_preview()

    def mail_content(self) -> tuple[str, str]:
        """Inhalt zum Versenden: von Hand bearbeitete Vorschau oder frisch erzeugt."""
        if self.preview_manuell:
            return self.preview.toPlainText(), self.preview.toHtml()
        return self.build_mail()

    def set_status(self, text: str, ok: bool | None = None):
        color = {True: "#16a34a", False: "#dc2626", None: "#64748b"}[ok]
        self.status_lbl.setStyleSheet(f"color: {color};")
        self.status_lbl.setText(text)

    def run_worker(self, worker: QObject):
        self._thread = QThread(self)
        self._worker = worker
        worker.moveToThread(self._thread)
        self._thread.started.connect(worker.run)
        worker.finished.connect(self._thread.quit)
        worker.failed.connect(self._thread.quit)
        self._thread.start()

    # ----- Suche -----
    def search(self):
        nr = self.nr()
        if not nr.isdigit():
            self.set_status("Bitte eine gültige Projektnummer eingeben.", False)
            return
        self.search_btn.setEnabled(False)
        self.set_status(f"Suche nach {nr} in {self.cfg['projekt_basis']} …")
        worker = SearchWorker(self.cfg["projekt_basis"], nr)
        worker.finished.connect(lambda res: self.search_done(nr, res))
        worker.failed.connect(self.search_failed)
        self.run_worker(worker)

    def search_failed(self, err: str):
        self.search_btn.setEnabled(True)
        self.set_status(err, False)

    def search_done(self, nr: str, results: list):
        self.search_btn.setEnabled(True)
        if not results:
            self.set_status(f"Kein Projektordner für {nr} gefunden.", False)
            return
        projekt = results[0]
        if len(results) > 1:
            namen = [str(p) for p in results]
            wahl, ok = QInputDialog.getItem(
                self, "Mehrere Treffer", "Bitte Projektordner wählen:", namen, 0, False
            )
            if not ok:
                self.set_status("Suche abgebrochen.")
                return
            projekt = Path(wahl)
        pfad = aktuell_path(projekt, nr)
        self.path_edit.setText(str(pfad))
        if pfad.is_dir():
            self.set_status("Ordner gefunden.", True)
        else:
            self.set_status("Projekt gefunden, aber der Ordner 'Aktuell' existiert (noch) nicht!", False)
        self.dev_edit.setFocus()

    # ----- Senden -----
    def send(self):
        cfg = self.cfg
        to = split_addresses(self.to_edit.text())
        cc = split_addresses(self.cc_edit.text())
        if not self.path_edit.text().strip():
            QMessageBox.warning(self, APP_NAME, "Es ist noch kein Pfad eingetragen.")
            return
        if not to:
            QMessageBox.warning(self, APP_NAME, "Bitte mindestens einen Empfänger angeben.")
            return
        if not cfg["absender"] or not cfg["smtp_user"] or not cfg["gruss"].strip():
            if not self.run_onboarding():
                return
            cfg = self.cfg

        password = self.session_password or get_password(cfg["smtp_user"])
        if cfg["smtp_user"] and not password:
            pw, ok = QInputDialog.getText(
                self, "Passwort", f"Passwort für {cfg['smtp_user']}@{cfg['smtp_server']}:",
                QLineEdit.EchoMode.Password,
            )
            if not ok or not pw:
                return
            password = pw
            self.session_password = pw
            if keyring is not None and QMessageBox.question(
                self, "Passwort speichern", "Passwort sicher im Windows-Anmeldespeicher merken?"
            ) == QMessageBox.StandardButton.Yes:
                set_password(cfg["smtp_user"], pw)

        if QMessageBox.question(
            self, "Senden?", f"Email an {', '.join(to)} senden?"
        ) != QMessageBox.StandardButton.Yes:
            return

        self.send_btn.setEnabled(False)
        self.set_status("Sende Email …")
        text, html = self.mail_content()
        worker = SendWorker(cfg, password or "", to, cc, self.subject_edit.text(), text, html)
        worker.finished.connect(self.send_done)
        worker.failed.connect(self.send_failed)
        self.run_worker(worker)

    def send_done(self, hinweis: str = ""):
        self.send_btn.setEnabled(True)
        if hinweis:
            self.set_status("Email versendet – aber nicht im Gesendet-Ordner abgelegt.", False)
            QMessageBox.warning(self, APP_NAME, hinweis)
            return
        self.set_status("Email erfolgreich versendet.", True)
        QMessageBox.information(self, APP_NAME, "Email wurde versendet.")

    def send_failed(self, err: str):
        self.send_btn.setEnabled(True)
        self.session_password = None
        self.set_status("Senden fehlgeschlagen.", False)
        QMessageBox.critical(self, "Fehler beim Senden", err)

    # ----- Textbausteine / Shortcuts -----
    def _replace_container(self, attr: str, layout, widget: QWidget):
        alt = getattr(self, attr)
        if alt is not None:
            layout.removeWidget(alt)
            alt.hide()
            alt.deleteLater()
        layout.addWidget(widget)
        setattr(self, attr, widget)

    def build_baustein_buttons(self):
        # Flow-Buttons unter den Textfeldern (Info-Text, Freitext)
        for attr, box, edit, key in (
            ("info_buttons", self.info_layout, self.info_edit, "bausteine_info"),
            ("warn_buttons", self.warn_layout, self.warn_edit, "bausteine_achtung"),
        ):
            container = QWidget()
            flow = FlowLayout(container)
            for text in self.cfg.get(key, []):
                flow.addWidget(shortcut_button(text, lambda t, e=edit: append_line(e, t)))
            self._replace_container(attr, box, container)

        # Buttons rechts neben Lieferant / Sonstiges
        for attr, row, key, slot in (
            ("lieferant_shortcuts", self.lieferant_row, "shortcuts_lieferant",
             lambda t: self.lieferant_edit.setText(t)),
            ("sonst_shortcuts", self.sonst_row, "shortcuts_sonstiges",
             lambda t: append_inline(self.sonst_edit, t)),
            ("bauteile_shortcuts", self.bauteile_row, "shortcuts_bauteile",
             lambda t: append_inline(self.bauteile_edit, t)),
        ):
            container = QWidget()
            hl = QHBoxLayout(container)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(6)
            for text in self.cfg.get(key, []):
                hl.addWidget(shortcut_button(text, slot))
            self._replace_container(attr, row, container)

    # ----- Ersteinrichtung -----
    def run_onboarding(self) -> bool:
        dlg = OnboardingDialog(self.cfg, self)
        if not dlg.exec():
            return False
        self.session_password = None
        self.update_preview()
        return True

    def check_setup(self):
        """Beim Start: fehlen Pflichtangaben, kurz das Onboarding zeigen."""
        if missing_setup(self.cfg):
            self.run_onboarding()

    # ----- Sonstiges -----
    def open_settings(self):
        dlg = SettingsDialog(self.cfg, self)
        if dlg.exec():
            self.session_password = None
            self.to_edit.setText(self.cfg["empfaenger"])
            self.cc_edit.setText(self.cfg["cc"])
            self.build_baustein_buttons()
            self.update_subject()
            self.update_preview()

    def clear(self):
        for w in (self.nr_edit, self.path_edit, self.dev_edit, self.termin_edit, self.lp_anzahl, self.lp_anzahl2,
                  self.lieferant_edit, self.sonst_edit, self.bauteile_edit, self.beist_edit):
            w.clear()
        self.info_edit.clear()
        self.warn_edit.clear()
        self.lp_typ.set_value("")
        self.paste.set_value("")
        for btn, _ in self.zusatz_buttons:
            btn.setChecked(False)
        self.info_mode.set_value("PO")
        self.reset_preview()
        self.set_status("")
        self.nr_edit.setFocus()


def main():
    # Eigene AppUserModelID -> Windows zeigt unser Icon in der Taskleiste
    # statt des Python-Icons.
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    icon_file = resource_path("icon.ico")
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))

    win = MainWindow()
    win.show()
    QTimer.singleShot(150, win.check_setup)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
