"""Uli Email Tool – verschickt Standard-Emails zu Projekten.

Start ohne Konsolenfenster:  pythonw email_tool.pyw   (oder Doppelklick)
"""

from __future__ import annotations

import json
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from PyQt6.QtCore import QObject, QPoint, QRect, QSize, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QGuiApplication, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

try:  # Passwort sicher im Windows-Anmeldeinformationsspeicher ablegen
    import keyring
except ImportError:  # pragma: no cover
    keyring = None

APP_ID = "gcd.uli.emailtool"
APP_NAME = "Uli Email Tool"
KEYRING_SERVICE = "UliEmailTool"


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

INFO_TEXTE = {
    "PO": "Bestellung gemäß PO",
    "Ang": "Bestellung gemäß Angebot",
}

DEFAULT_CONFIG = {
    "projekt_basis": r"M:\Projekte_ab_20000",
    "smtp_server": "mail.gcd.de",
    "smtp_port": 587,
    "smtp_user": "nimeier",
    "smtp_security": "STARTTLS",  # STARTTLS | SSL/TLS | Keine
    "absender": "",  # z.B. vorname.nachname@gcd.de
    "empfaenger": "vertrieb@gcd.de",  # mehrere mit ; trennen
    "cc": "",
    # Platzhalter: {nr} Projektnummer, {firma} Kundenordner, {board} Teil nach ___
    "betreff": "PN{nr} / Baugruppendaten {firma} {board} / {nr} sind auf M",
    "anrede": "Hallo Vertrieb,",
    "gruss": "VG\nUli",
    # Textbausteine (Buttons unter den Textfeldern)
    "bausteine_info": [],
    "bausteine_achtung": ["PASTE -> aktuell (TOP/BOTTOM)"],
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
    if cfg.get("betreff") in ("", "Baugruppendaten Projekt {nr}"):
        cfg["betreff"] = DEFAULT_CONFIG["betreff"]
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def get_password(user: str) -> str | None:
    if keyring is None or not user:
        return None
    try:
        return keyring.get_password(KEYRING_SERVICE, user)
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


def send_mail(cfg: dict, password: str, to: list[str], cc: list[str], subject: str, body: str):
    msg = EmailMessage()
    msg["From"] = cfg["absender"]
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg.set_content(body)

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


class SendWorker(QObject):
    finished = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, *args):
        super().__init__()
        self.args = args

    def run(self):
        try:
            send_mail(*self.args)
            self.finished.emit()
        except smtplib.SMTPAuthenticationError:
            self.failed.emit("Anmeldung fehlgeschlagen – Benutzername oder Passwort falsch.")
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


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


class SettingsDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.cfg = cfg
        form = QFormLayout()

        self.basis = QLineEdit(cfg["projekt_basis"])
        self.server = QLineEdit(cfg["smtp_server"])
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(int(cfg["smtp_port"]))
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

        form.addRow("Projekt-Basisordner:", self.basis)
        form.addRow(QLabel("<b>Postausgangs-Server (SMTP)</b>"))
        form.addRow("Server:", self.server)
        form.addRow("Port:", self.port)
        form.addRow("Verbindungssicherheit:", self.security)
        form.addRow("Benutzername:", self.user)
        form.addRow("Passwort:", self.password)
        if keyring is None:
            form.addRow("", QLabel("<i>'keyring' nicht installiert – Passwort wird nicht gespeichert.</i>"))
        form.addRow(QLabel("<b>Email</b>"))
        form.addRow("Absender:", self.absender)
        form.addRow("Standard-Empfänger:", self.empfaenger)
        form.addRow("Standard-CC:", self.cc)
        form.addRow("Betreff:", self.betreff)
        form.addRow("Anrede:", self.anrede)
        form.addRow("Gruß:", self.gruss)
        form.addRow(QLabel("<b>Textbausteine</b> (ein Baustein pro Zeile)"))
        self.bs_info = QPlainTextEdit("\n".join(cfg["bausteine_info"]))
        self.bs_info.setFixedHeight(80)
        self.bs_achtung = QPlainTextEdit("\n".join(cfg["bausteine_achtung"]))
        self.bs_achtung.setFixedHeight(80)
        form.addRow("Info (Modus Text):", self.bs_info)
        form.addRow("Achtung:", self.bs_achtung)

        test_btn = QPushButton("Verbindung zum Server testen")
        test_btn.clicked.connect(self.test_connection)
        form.addRow("", test_btn)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.resize(520, self.sizeHint().height())

    def values(self) -> dict:
        return {
            "projekt_basis": self.basis.text().strip(),
            "smtp_server": self.server.text().strip(),
            "smtp_port": self.port.value(),
            "smtp_security": self.security.currentText(),
            "smtp_user": self.user.text().strip(),
            "absender": self.absender.text().strip(),
            "empfaenger": self.empfaenger.text().strip(),
            "cc": self.cc.text().strip(),
            "betreff": self.betreff.text(),
            "anrede": self.anrede.text(),
            "gruss": self.gruss.toPlainText(),
            "bausteine_info": [z.strip() for z in self.bs_info.toPlainText().splitlines() if z.strip()],
            "bausteine_achtung": [z.strip() for z in self.bs_achtung.toPlainText().splitlines() if z.strip()],
        }

    def test_connection(self):
        v = self.values()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ctx = ssl.create_default_context()
            if v["smtp_security"] == "SSL/TLS":
                s = smtplib.SMTP_SSL(v["smtp_server"], v["smtp_port"], context=ctx, timeout=15)
            else:
                s = smtplib.SMTP(v["smtp_server"], v["smtp_port"], timeout=15)
            with s:
                s.ehlo()
                if v["smtp_security"] == "STARTTLS":
                    s.starttls(context=ctx)
                    s.ehlo()
                if v["smtp_user"]:
                    s.login(v["smtp_user"], self.password.text())
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


# --------------------------------------------------------------------------- #
# Hauptfenster
# --------------------------------------------------------------------------- #
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.session_password: str | None = None
        self._thread: QThread | None = None
        self.setWindowTitle(APP_NAME)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # --- Projekt ---
        proj_box = QGroupBox("Projekt")
        pl = QVBoxLayout(proj_box)
        row = QHBoxLayout()
        row.addWidget(QLabel("Projektnummer:"))
        self.nr_edit = QLineEdit()
        self.nr_edit.setPlaceholderText("z.B. 21156")
        self.nr_edit.setMaxLength(10)
        self.nr_edit.returnPressed.connect(self.search)
        row.addWidget(self.nr_edit, 1)
        self.search_btn = QPushButton("Suchen")
        self.search_btn.clicked.connect(self.search)
        row.addWidget(self.search_btn)
        pl.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Pfad:"))
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("wird nach der Suche gefüllt (kann auch angepasst werden)")
        self.path_edit.textChanged.connect(self.update_preview)
        self.path_edit.textChanged.connect(self.update_subject)
        row2.addWidget(self.path_edit, 1)
        copy_btn = QPushButton("Kopieren")
        copy_btn.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.path_edit.text()))
        row2.addWidget(copy_btn)
        pl.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Entwickler:"))
        self.dev_edit = QLineEdit()
        self.dev_edit.setPlaceholderText("optional – erscheint im Betreff in Klammern hinter der Firma")
        self.dev_edit.textChanged.connect(self.update_subject)
        row3.addWidget(self.dev_edit, 1)
        pl.addLayout(row3)
        self.status_lbl = QLabel("")
        pl.addWidget(self.status_lbl)
        root.addWidget(proj_box)

        for lay in (row, row2, row3):
            lay.itemAt(0).widget().setMinimumWidth(95)

        # --- Empfänger ---
        mail_box = QGroupBox("Email")
        ml = QFormLayout(mail_box)
        self.to_edit = QLineEdit(self.cfg["empfaenger"])
        self.cc_edit = QLineEdit(self.cfg["cc"])
        self.subject_edit = QLineEdit()
        ml.addRow("An:", self.to_edit)
        ml.addRow("CC:", self.cc_edit)
        ml.addRow("Betreff:", self.subject_edit)
        root.addWidget(mail_box)

        # --- Texte ---
        txt_row = QHBoxLayout()
        info_box = QGroupBox("Info")
        ib = QVBoxLayout(info_box)
        mode_row = QHBoxLayout()
        self.info_mode = QButtonGroup(self)
        self.info_mode.setExclusive(True)
        for text, tip in (
            ("PO", INFO_TEXTE["PO"]),
            ("Ang", INFO_TEXTE["Ang"]),
            ("Text", "Eigenen Text schreiben"),
        ):
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setToolTip(tip)
            btn.setMinimumWidth(60)
            btn.setStyleSheet(
                "QPushButton:checked { background: #206ec8; color: white; font-weight: bold; }"
            )
            self.info_mode.addButton(btn)
            mode_row.addWidget(btn)
        mode_row.addStretch(1)
        ib.addLayout(mode_row)
        self.info_mode_label = QLabel()
        self.info_mode_label.setStyleSheet("color: gray;")
        ib.addWidget(self.info_mode_label)

        # Textfeld nur im Modus "Text"
        self.info_panel = QWidget()
        il = QVBoxLayout(self.info_panel)
        il.setContentsMargins(0, 0, 0, 0)
        self.info_edit = QPlainTextEdit()
        self.info_edit.setFixedHeight(4 * self.info_edit.fontMetrics().lineSpacing() + 14)
        self.info_edit.textChanged.connect(self.update_preview)
        il.addWidget(self.info_edit)
        self.info_layout = il
        self.info_buttons: QWidget | None = None
        ib.addWidget(self.info_panel)
        ib.addStretch(1)
        txt_row.addWidget(info_box, 2)
        self.info_mode.buttonToggled.connect(self.info_mode_changed)

        warn_box = QGroupBox("Achtung (jede Zeile wird ein Aufzählungspunkt)")
        wl = QVBoxLayout(warn_box)
        self.warn_edit = QPlainTextEdit()
        self.warn_edit.textChanged.connect(self.update_preview)
        wl.addWidget(self.warn_edit, 1)
        self.warn_layout = wl
        self.warn_buttons: QWidget | None = None
        txt_row.addWidget(warn_box, 3)
        root.addLayout(txt_row, 2)
        self.build_baustein_buttons()

        # --- Vorschau ---
        prev_box = QGroupBox("Vorschau")
        prl = QVBoxLayout(prev_box)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QFont("Consolas", 10))
        prl.addWidget(self.preview)
        # Platz für ca. 20 Zeilen, damit eine normale Mail komplett sichtbar ist
        zeile = self.preview.fontMetrics().lineSpacing()
        self.preview.setMinimumHeight(20 * zeile + 12)
        root.addWidget(prev_box, 3)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        settings_btn = QPushButton("Einstellungen…")
        settings_btn.clicked.connect(self.open_settings)
        btn_row.addWidget(settings_btn)
        btn_row.addStretch(1)
        clear_btn = QPushButton("Leeren")
        clear_btn.clicked.connect(self.clear)
        btn_row.addWidget(clear_btn)
        self.send_btn = QPushButton("Senden")
        self.send_btn.setDefault(False)
        self.send_btn.setMinimumWidth(120)
        self.send_btn.setStyleSheet("font-weight: bold;")
        self.send_btn.clicked.connect(self.send)
        btn_row.addWidget(self.send_btn)
        root.addLayout(btn_row)

        self.nr_edit.textChanged.connect(self.update_subject)
        self.update_subject()
        self.update_preview()
        self.info_mode.buttons()[0].setChecked(True)  # Standard: PO
        self.warn_edit.setMinimumHeight(70)
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(min(960, screen.width() - 40), min(1000, screen.height() - 60))

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

    def info_mode_name(self) -> str:
        btn = self.info_mode.checkedButton()
        return btn.text() if btn else "PO"

    def info_mode_changed(self, *_):
        modus = self.info_mode_name()
        self.info_panel.setVisible(modus == "Text")
        self.info_mode_label.setVisible(modus != "Text")
        self.info_mode_label.setText(INFO_TEXTE.get(modus, ""))
        if modus == "Text":
            self.info_edit.setFocus()
        self.update_preview()

    def info_text(self) -> str:
        modus = self.info_mode_name()
        if modus == "Text":
            return self.info_edit.toPlainText().strip()
        return INFO_TEXTE[modus]

    def build_body(self) -> str:
        teile = [
            self.cfg["anrede"],
            "",
            f"Die Baugruppendaten für das Board sind auf {self.path_edit.text().strip()}",
        ]
        info = self.info_text()
        if info:
            teile += ["", info]
        achtung = as_bullets(self.warn_edit.toPlainText())
        if achtung:
            teile += ["", "Achtung:", "", achtung]
        teile += ["", self.cfg["gruss"]]
        return "\n".join(teile)

    def update_preview(self):
        self.preview.setPlainText(self.build_body())

    def set_status(self, text: str, ok: bool | None = None):
        color = {True: "green", False: "#c00000", None: "gray"}[ok]
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
        self.info_edit.setFocus()

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
        if not cfg["absender"]:
            QMessageBox.information(self, APP_NAME, "Bitte zuerst die Absender-Adresse in den Einstellungen eintragen.")
            self.open_settings()
            return

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
        worker = SendWorker(cfg, password or "", to, cc, self.subject_edit.text(), self.build_body())
        worker.finished.connect(self.send_done)
        worker.failed.connect(self.send_failed)
        self.run_worker(worker)

    def send_done(self):
        self.send_btn.setEnabled(True)
        self.set_status("Email erfolgreich versendet.", True)
        QMessageBox.information(self, APP_NAME, "Email wurde versendet.")

    def send_failed(self, err: str):
        self.send_btn.setEnabled(True)
        self.session_password = None
        self.set_status("Senden fehlgeschlagen.", False)
        QMessageBox.critical(self, "Fehler beim Senden", err)

    # ----- Textbausteine -----
    def build_baustein_buttons(self):
        for attr, box, edit, key in (
            ("info_buttons", self.info_layout, self.info_edit, "bausteine_info"),
            ("warn_buttons", self.warn_layout, self.warn_edit, "bausteine_achtung"),
        ):
            alt = getattr(self, attr)
            if alt is not None:
                box.removeWidget(alt)
                alt.hide()
                alt.deleteLater()
            container = QWidget()
            layout = FlowLayout(container)
            box.addWidget(container)
            setattr(self, attr, container)
            for text in self.cfg.get(key, []):
                btn = QPushButton(text)
                btn.setToolTip(f"„{text}“ einfügen")
                btn.setStyleSheet("padding: 2px 8px;")
                btn.clicked.connect(lambda _=False, e=edit, t=text: append_line(e, t))
                layout.addWidget(btn)

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
        self.nr_edit.clear()
        self.path_edit.clear()
        self.dev_edit.clear()
        self.info_edit.clear()
        self.info_mode.buttons()[0].setChecked(True)
        self.warn_edit.clear()
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
    icon_file = resource_path("icon.ico")
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
