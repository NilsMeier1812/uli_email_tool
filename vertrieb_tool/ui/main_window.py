"""Hauptfenster: Vorlagen-Umschalter, gemeinsamer Kopf, Formular der Vorlage, Vorschau."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core import APP_NAME, get_password, keyring, load_config, missing_setup, save_config, set_password
from ..mail import send_and_file, split_addresses
from ..projekt import aktuell_path, find_project_dirs, parse_project_path
from ..templates import VORLAGEN
from ..templates.base import Projekt, render
from .dialogs import AktionenDialog, OnboardingDialog, SettingsDialog
from .style import ACCENT, LABEL_W, field_label, fixed_label, icon, set_role, with_icon
from .widgets import run_in_background


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.session_password: str | None = None
        self.setWindowTitle(APP_NAME)
        self.vorlagen = [cls(self.cfg, self) for cls in VORLAGEN]
        self.vorlage = self.vorlagen[0]

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(18, 12, 18, 16)
        outer.setSpacing(10)

        # --- Vorlagen-Umschalter ---
        top = QHBoxLayout()
        tabbar = QWidget()
        tabbar.setObjectName("tabbar")
        tl = QHBoxLayout(tabbar)
        tl.setContentsMargins(4, 4, 4, 4)
        tl.setSpacing(4)
        self._tab_gruppe = QButtonGroup(self)
        self._tab_gruppe.setExclusive(True)
        self._tabs: dict[str, QPushButton] = {}
        for v in self.vorlagen:
            btn = set_role(QPushButton(v.name), "tab")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, vid=v.id: self.vorlage_waehlen(vid))
            self._tab_gruppe.addButton(btn)
            tl.addWidget(btn)
            self._tabs[v.id] = btn
        top.addWidget(tabbar)
        top.addStretch(1)
        outer.addLayout(top)

        columns = QHBoxLayout()
        columns.setSpacing(16)
        outer.addLayout(columns, 1)

        # Linke Spalte scrollbar: auf kleinen Bildschirmen wird gescrollt statt gestaucht
        left_w = QWidget()
        left_w.setObjectName("leftInner")
        root = QVBoxLayout(left_w)
        root.setContentsMargins(0, 0, 10, 0)
        root.setSpacing(4)
        self.left_scroll = QScrollArea()
        self.left_scroll.setObjectName("leftScroll")
        self.left_scroll.setWidget(left_w)
        self.left_scroll.setWidgetResizable(True)
        self.left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.left_scroll.viewport().setAutoFillBackground(False)
        columns.addWidget(self.left_scroll, 5)

        # --- Projekt (für alle Vorlagen gleich) ---
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
        copy_btn = with_icon(QPushButton("  Kopieren"), "copy")
        copy_btn.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.path_edit.text()))
        pl.addWidget(field_label("Pfad"), 1, 0)
        pl.addWidget(self.path_edit, 1, 1)
        pl.addWidget(copy_btn, 1, 2)
        self.dev_edit = QLineEdit()
        self.dev_edit.setPlaceholderText("optional – erscheint im Betreff")
        pl.addWidget(field_label("Entwickler"), 2, 0)
        pl.addWidget(self.dev_edit, 2, 1, 1, 2)
        self.status_lbl = QLabel("")
        pl.addWidget(self.status_lbl, 3, 0, 1, 3)
        root.addWidget(proj_box)
        for e in (self.nr_edit, self.path_edit, self.dev_edit):
            e.textChanged.connect(self.projekt_geaendert)

        # --- Email ---
        mail_box = QGroupBox("EMAIL")
        ml = QFormLayout(mail_box)
        ml.setHorizontalSpacing(12)
        ml.setVerticalSpacing(6)
        self.to_edit = QLineEdit()
        self.cc_edit = QLineEdit()
        self.subject_edit = QLineEdit()
        ml.addRow(fixed_label("An"), self.to_edit)
        ml.addRow(fixed_label("CC"), self.cc_edit)
        ml.addRow(fixed_label("Betreff"), self.subject_edit)
        root.addWidget(mail_box)

        # --- Formulare der Vorlagen (nur das aktive ist sichtbar) ---
        for v in self.vorlagen:
            w = v.widget()
            w.hide()
            root.addWidget(w)
            v.changed.connect(lambda v=v: self._vorlage_geaendert(v))
        root.addStretch(1)

        # --- Vorschau (rechts) ---
        prev_box = QGroupBox("VORSCHAU")
        prl = QVBoxLayout(prev_box)
        prl.setContentsMargins(4, 4, 4, 4)
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

        # Breite so, dass links nie horizontal gescrollt werden muss (breitestes Formular zählt)
        breite = max([proj_box.minimumSizeHint().width()]
                     + [v.widget().minimumSizeHint().width() for v in self.vorlagen])
        self.left_scroll.setMinimumWidth(breite + 10 + self.left_scroll.verticalScrollBar().sizeHint().width())
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(min(1400, screen.width() - 40), min(1000, screen.height() - 60))

        start = self.cfg.get("vorlage") or self.vorlagen[0].id
        if start not in self._tabs:
            start = self.vorlagen[0].id
        self.vorlage_waehlen(start, speichern=False)

    # ----- Vorlagen -----
    def vorlage_waehlen(self, vid: str, speichern: bool = True):
        neu = next(v for v in self.vorlagen if v.id == vid)
        if self.preview_manuell and neu is not self.vorlage:
            if QMessageBox.question(
                self, APP_NAME, "Die Vorschau wurde von Hand bearbeitet. Vorlage trotzdem wechseln?"
            ) != QMessageBox.StandardButton.Yes:
                self._tabs[self.vorlage.id].setChecked(True)
                return
        for v in self.vorlagen:
            v.widget().setVisible(v is neu)
        self.vorlage = neu
        self._tabs[vid].setChecked(True)
        an, cc = neu.empfaenger()
        self.to_edit.setText(an)
        self.cc_edit.setText(cc)
        neu.projekt_geaendert(self.projekt())
        self.preview_manuell = False
        self.edit_bar.hide()
        self.aktualisieren()
        self.left_scroll.verticalScrollBar().setValue(0)
        neu.aktiviert()
        if speichern and self.cfg.get("vorlage") != vid:
            self.cfg["vorlage"] = vid
            save_config(self.cfg)

    def _vorlage_geaendert(self, v):
        if v is self.vorlage:
            self.aktualisieren()

    # ----- Kopf -----
    def nr(self) -> str:
        return self.nr_edit.text().strip()

    def projekt(self) -> Projekt:
        pfad = self.path_edit.text().strip()
        firma, board = parse_project_path(pfad, self.nr())
        return Projekt(self.nr(), pfad, firma, board, self.dev_edit.text().strip())

    def projekt_geaendert(self):
        p = self.projekt()
        for v in self.vorlagen:
            v.projekt_geaendert(p)
        self.aktualisieren()

    # ----- Betreff & Vorschau -----
    def aktualisieren(self):
        p = self.projekt()
        self.subject_edit.setText(self.vorlage.betreff(p))
        self.update_preview()

    def build_mail(self) -> tuple[str, str]:
        return render(self.vorlage.absaetze(self.projekt()))

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

    # ----- Suche -----
    def search(self):
        nr = self.nr()
        if not nr.isdigit():
            self.set_status("Bitte eine gültige Projektnummer eingeben.", False)
            return
        self.search_btn.setEnabled(False)
        basis = self.cfg["projekt_basis"]
        self.set_status(f"Suche nach {nr} in {basis} …")

        def suchen():
            base = Path(basis)
            if not base.is_dir():
                raise FileNotFoundError(f"Basisordner nicht gefunden: {base}")
            return find_project_dirs(base, nr)

        run_in_background(self, suchen, lambda res: self.search_done(nr, res), self.search_failed)

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
            wahl, ok = QInputDialog.getItem(self, "Mehrere Treffer", "Bitte Projektordner wählen:",
                                            namen, 0, False)
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

    # ----- Passwort -----
    def passwort(self, nachfragen: bool = True) -> str | None:
        cfg = self.cfg
        pw = self.session_password or get_password(cfg.get("smtp_user", ""))
        if pw or not nachfragen or not cfg.get("smtp_user"):
            return pw
        pw, ok = QInputDialog.getText(
            self, "Passwort", f"Passwort für {cfg['smtp_user']}@{cfg['smtp_server']}:",
            QLineEdit.EchoMode.Password,
        )
        if not ok or not pw:
            return None
        self.session_password = pw
        if keyring is not None and QMessageBox.question(
            self, "Passwort speichern", "Passwort sicher im Windows-Anmeldespeicher merken?"
        ) == QMessageBox.StandardButton.Yes:
            set_password(cfg["smtp_user"], pw)
        return pw

    # ----- Senden -----
    def send(self):
        p = self.projekt()
        to = split_addresses(self.to_edit.text())
        cc = split_addresses(self.cc_edit.text())
        fehler = self.vorlage.pruefen(p)
        if fehler:
            QMessageBox.warning(self, APP_NAME, fehler)
            return
        if not to:
            QMessageBox.warning(self, APP_NAME, "Bitte mindestens einen Empfänger angeben.")
            return
        if [x for x in missing_setup(self.cfg) if x != "Passwort"]:
            if not self.run_onboarding():
                return
        password = self.passwort()
        if self.cfg["smtp_user"] and not password:
            return

        aktionen = self.vorlage.aktionen(p)
        dlg = AktionenDialog(to + cc, aktionen, self)
        if not dlg.exec():
            return
        gewaehlt = dlg.gewaehlt()

        self.send_btn.setEnabled(False)
        self.set_status("Sende Email …")
        text, html = self.mail_content()
        cfg, subject, vorlage = dict(self.cfg), self.subject_edit.text(), self.vorlage

        def senden():
            return send_and_file(cfg, password or "", to, cc, subject, text, html)

        run_in_background(self, senden, lambda hinweis: self.send_done(hinweis, vorlage, p, gewaehlt),
                          self.send_failed)

    def send_done(self, hinweis: str, vorlage, p: Projekt, aktionen: list):
        self.send_btn.setEnabled(True)
        ergebnisse, fehler = [], []
        for a in aktionen:
            try:
                ergebnisse.append(a.ausfuehren())
            except Exception as exc:
                fehler.append(f"{a.titel}: {type(exc).__name__}: {exc}")
        try:
            vorlage.nach_senden(p)
        except Exception:
            pass

        text = "Email wurde versendet."
        if ergebnisse:
            text += "\n\n" + "\n".join(ergebnisse)
        if hinweis:
            text += "\n\n" + hinweis
        if fehler:
            text += "\n\nFehler:\n" + "\n".join(fehler)
            self.set_status("Email versendet – aber nicht alles hat geklappt.", False)
            QMessageBox.warning(self, APP_NAME, text)
        elif hinweis:
            self.set_status("Email versendet – aber nicht im Gesendet-Ordner abgelegt.", False)
            QMessageBox.warning(self, APP_NAME, text)
        else:
            self.set_status("Email erfolgreich versendet.", True)
            QMessageBox.information(self, APP_NAME, text)

    def send_failed(self, err: str):
        self.send_btn.setEnabled(True)
        self.session_password = None
        self.set_status("Senden fehlgeschlagen.", False)
        QMessageBox.critical(self, "Fehler beim Senden", err)

    # ----- Ersteinrichtung & Einstellungen -----
    def run_onboarding(self) -> bool:
        if not OnboardingDialog(self.cfg, self).exec():
            return False
        self._nach_einstellungen()
        return True

    def check_setup(self):
        """Beim Start: fehlen Pflichtangaben, kurz das Onboarding zeigen."""
        if missing_setup(self.cfg):
            self.run_onboarding()

    def open_settings(self):
        if SettingsDialog(self.cfg, self.vorlagen, self).exec():
            self._nach_einstellungen()

    def _nach_einstellungen(self):
        self.session_password = None
        for v in self.vorlagen:
            v.einstellungen_neu()
        an, cc = self.vorlage.empfaenger()
        self.to_edit.setText(an)
        self.cc_edit.setText(cc)
        self.aktualisieren()
        for v in self.vorlagen:
            v.zugangsdaten_geaendert()

    def clear(self):
        for w in (self.nr_edit, self.path_edit, self.dev_edit):
            w.clear()
        for v in self.vorlagen:
            v.leeren()
        an, cc = self.vorlage.empfaenger()
        self.to_edit.setText(an)
        self.cc_edit.setText(cc)
        self.reset_preview()
        self.set_status("")
        self.nr_edit.setFocus()
