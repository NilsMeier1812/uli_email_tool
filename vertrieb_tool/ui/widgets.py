"""Wiederverwendbare Widgets: Hintergrund-Worker, Schalter, Chips, Scan-Auswahl."""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QObject, QPoint, QProcess, QRect, QSize, QThread, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ..core import ENTRY_SCRIPT, app_dir
from ..mail import Scan
from .style import hint_label, set_role, with_icon


# ----- Hintergrund-Arbeit ---------------------------------------------------------
class Worker(QObject):
    """Führt eine Funktion in einem eigenen Thread aus (Fenster bleibt bedienbar)."""

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


def run_in_background(owner: QObject, func, ok, fail) -> None:
    """func() im Hintergrund ausführen, danach ok(ergebnis) bzw. fail(text)."""
    thread = QThread(owner)
    worker = Worker(func)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(ok)
    worker.failed.connect(fail)
    worker.finished.connect(thread.quit)
    worker.failed.connect(thread.quit)
    jobs = owner.__dict__.setdefault("_bg_jobs", [])
    jobs.append((thread, worker))
    thread.finished.connect(lambda: jobs.remove((thread, worker)) if (thread, worker) in jobs else None)
    thread.start()


def restart_app():
    """Tool neu starten (nach einem Update)."""
    if getattr(sys, "frozen", False):
        QProcess.startDetached(sys.executable, [], str(app_dir()))
    else:
        QProcess.startDetached(sys.executable, [str(ENTRY_SCRIPT)], str(app_dir()))
    QApplication.quit()


# ----- Layout & Schalter --------------------------------------------------------
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


def chip_row(texte: list[str], slot) -> QWidget:
    """Reihe von Shortcut-Chips (Klick ruft slot(text) auf)."""
    container = QWidget()
    hl = QHBoxLayout(container)
    hl.setContentsMargins(0, 0, 0, 0)
    hl.setSpacing(6)
    for text in texte:
        hl.addWidget(shortcut_button(text, slot))
    return container


def chip_flow(texte: list[str], slot) -> QWidget:
    """Wie chip_row, bricht aber in mehrere Zeilen um."""
    container = QWidget()
    flow = FlowLayout(container)
    for text in texte:
        flow.addWidget(shortcut_button(text, slot))
    return container


class Slot(QWidget):
    """Platzhalter, dessen Inhalt sich austauschen lässt (z.B. Chips nach Einstellungen)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._inhalt: QWidget | None = None

    def set(self, widget: QWidget):
        if self._inhalt is not None:
            self._lay.removeWidget(self._inhalt)
            self._inhalt.hide()
            self._inhalt.deleteLater()
        self._inhalt = widget
        self._lay.addWidget(widget)


def multiline(zeilen: int) -> QPlainTextEdit:
    edit = QPlainTextEdit()
    edit.setTabChangesFocus(True)
    edit.setFixedHeight(zeilen * edit.fontMetrics().lineSpacing() + 18)
    return edit


# ----- Scan-Auswahl -------------------------------------------------------------
def _groesse(n: int) -> str:
    return f"{n / 1024:.0f} kB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f} MB"


def _wann(d: datetime) -> str:
    heute = datetime.now().date()
    if d.date() == heute:
        tag = "Heute"
    elif (heute - d.date()).days == 1:
        tag = "Gestern"
    else:
        tag = d.strftime("%d.%m.%Y")
    return f"{tag}, {d:%H:%M}"


def open_scan(scan: Scan) -> None:
    """Scan im Standard-PDF-Programm öffnen."""
    if scan.pfad is not None:
        pfad = scan.pfad
    else:
        ordner = Path(tempfile.gettempdir()) / "vertrieb_email_tool"
        ordner.mkdir(exist_ok=True)
        pfad = ordner / f"{scan.datum:%Y%m%d_%H%M%S}_{scan.name}"
        pfad.write_bytes(scan.daten)
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(pfad)))


class _ScanRow(QFrame):
    def __init__(self, scan: Scan, radio: QRadioButton, parent=None):
        super().__init__(parent)
        self.setObjectName("scanrow")
        self.scan = scan
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 6, 6)
        lay.setSpacing(10)
        lay.addWidget(radio)
        text = QVBoxLayout()
        text.setSpacing(0)
        quelle = "Datei" if scan.pfad is not None else "Scanner"
        titel = QLabel(f"<b>{_wann(scan.datum)}</b>")
        unter = set_role(QLabel(f"{scan.name}  ·  {_groesse(scan.groesse)}  ·  {quelle}"), "field")
        text.addWidget(titel)
        text.addWidget(unter)
        lay.addLayout(text, 1)
        ansehen = with_icon(set_role(QPushButton("  Ansehen"), "ghost"), "eye")
        ansehen.clicked.connect(lambda: open_scan(scan))
        lay.addWidget(ansehen)
        self.radio = radio
        radio.toggled.connect(self._mark)

    def _mark(self, an: bool):
        self.setProperty("selected", "true" if an else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, ev):
        self.radio.setChecked(True)
        super().mousePressEvent(ev)


class ScanPicker(QWidget):
    """Liste der letzten Scans + Datei hineinziehen/auswählen. Genau einer ist gewählt."""

    changed = pyqtSignal()
    refresh_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._scans: list[Scan] = []
        self._eigene: list[Scan] = []
        self._gruppe = QButtonGroup(self)
        self._gruppe.buttonToggled.connect(lambda *_: self.changed.emit())

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        kopf = QHBoxLayout()
        self.status = hint_label("")
        kopf.addWidget(self.status, 1)
        self.refresh_btn = with_icon(set_role(QPushButton("  Aktualisieren"), "ghost"), "refresh")
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        kopf.addWidget(self.refresh_btn)
        lay.addLayout(kopf)

        self._liste = QVBoxLayout()
        self._liste.setSpacing(4)
        lay.addLayout(self._liste)

        self.drop = QFrame()
        self.drop.setObjectName("dropzone")
        dl = QHBoxLayout(self.drop)
        dl.setContentsMargins(12, 8, 8, 8)
        dl.addWidget(hint_label("PDF hierher ziehen – oder"), 1)
        waehlen = with_icon(set_role(QPushButton("  Datei wählen…"), "ghost"), "upload")
        waehlen.clicked.connect(self._waehlen)
        dl.addWidget(waehlen)
        lay.addWidget(self.drop)

    # --- Daten ---
    def set_loading(self, text: str = "Suche Scans im Posteingang …"):
        self.status.setText(text)
        self.refresh_btn.setEnabled(False)

    def set_error(self, text: str):
        self.status.setText(text)
        self.refresh_btn.setEnabled(True)

    def set_scans(self, scans: list[Scan]):
        self._scans = list(scans)
        self.refresh_btn.setEnabled(True)
        n = len(self._scans)
        self.status.setText(
            f"Die letzten {n} Scans aus dem Posteingang – bitte den richtigen wählen." if n
            else "Keine Scans im Posteingang gefunden."
        )
        self._render(auswahl=None)

    def add_file(self, pfad: Path):
        scan = Scan.aus_datei(pfad)
        self._eigene.insert(0, scan)
        self._render(auswahl=scan)

    def selected(self) -> Scan | None:
        btn = self._gruppe.checkedButton()
        return btn.property("scan") if btn is not None else None

    def clear_selection(self):
        self._eigene.clear()
        self._render(auswahl=None)

    def _render(self, auswahl: Scan | None):
        alt = self.selected()
        while self._liste.count():
            w = self._liste.takeAt(0).widget()
            if w is not None:
                self._gruppe.removeButton(w.radio)
                w.hide()
                w.deleteLater()
        for scan in self._eigene + self._scans:
            radio = QRadioButton()
            radio.setProperty("scan", scan)
            self._gruppe.addButton(radio)
            self._liste.addWidget(_ScanRow(scan, radio))
            if scan is (auswahl or alt):
                radio.setChecked(True)
        self.changed.emit()

    # --- Datei wählen / Drag & Drop ---
    def _waehlen(self):
        pfad, _ = QFileDialog.getOpenFileName(self, "Scan auswählen", "", "PDF (*.pdf)")
        if pfad:
            self.add_file(Path(pfad))

    @staticmethod
    def _pdfs(ev) -> list[Path]:
        if not ev.mimeData().hasUrls():
            return []
        return [Path(u.toLocalFile()) for u in ev.mimeData().urls()
                if u.isLocalFile() and u.toLocalFile().lower().endswith(".pdf")]

    def _hover(self, an: bool):
        self.drop.setProperty("hover", "true" if an else "false")
        self.drop.style().unpolish(self.drop)
        self.drop.style().polish(self.drop)

    def dragEnterEvent(self, ev):
        if self._pdfs(ev):
            ev.acceptProposedAction()
            self._hover(True)

    def dragLeaveEvent(self, ev):
        self._hover(False)

    def dropEvent(self, ev):
        self._hover(False)
        for pfad in self._pdfs(ev):
            self.add_file(pfad)
        ev.acceptProposedAction()
