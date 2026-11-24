"""Dialoge: Einstellungen, Willkommen (Ersteinrichtung), Aktionen vor dem Senden."""

from __future__ import annotations

import smtplib

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core import APP_NAME, get_password, gruss_name, keyring, save_config, set_password
from ..mail import find_sent_folder, imap_connect, imap_quote, smtp_test
from ..system import (
    apply_update,
    check_updates,
    create_shortcuts,
    current_version,
    shortcut_possible,
    shortcut_status,
    update_possible,
)
from .style import ACCENT, bold_label, fixed_label, set_role, with_icon
from .widgets import restart_app, run_in_background
from ..templates.base import Aktion, info_label, settings_form

from html import escape as esc


class SettingsDialog(QDialog):
    def __init__(self, cfg: dict, vorlagen: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.cfg = cfg

        # --- Allgemein ---
        self.name = QLineEdit(gruss_name(cfg))
        self.kuerzel = QLineEdit(cfg.get("kuerzel", ""))
        self.kuerzel.setMaxLength(6)
        self.kuerzel.setFixedWidth(90)
        self.absender = QLineEdit(cfg["absender"])
        self.absender.setPlaceholderText("vorname.nachname@gcd.de")
        self.basis = QLineEdit(cfg["projekt_basis"])

        # --- Server ---
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
            server_rows.append(("", info_label("'keyring' nicht installiert – Passwort wird nicht gespeichert.")))
        server_rows.append(("", test_btn))

        # --- Postfach (IMAP) ---
        self.imap_server = QLineEdit(cfg["imap_server"])
        self.imap_port = QLineEdit(str(cfg["imap_port"]))
        self.imap_port.setValidator(QIntValidator(1, 65535, self))
        self.imap_port.setFixedWidth(90)
        self.imap_aktiv = QCheckBox("Kopie jeder gesendeten Mail im Gesendet-Ordner ablegen")
        self.imap_aktiv.setChecked(bool(cfg["imap_aktiv"]))
        self.imap_ordner = QLineEdit(cfg["imap_ordner"])
        self.imap_ordner.setPlaceholderText("leer lassen = automatisch erkennen")
        imap_test = with_icon(QPushButton("  Gesendet-Ordner suchen"), "folder")
        imap_test.clicked.connect(self.test_imap)
        self.scan_absender = QLineEdit(cfg["scan_absender"])
        self.scan_ordner = QLineEdit(cfg["scan_ordner"])
        self.scan_anzahl = QLineEdit(str(cfg["scan_anzahl"]))
        self.scan_anzahl.setValidator(QIntValidator(1, 20, self))
        self.scan_anzahl.setFixedWidth(90)

        tabs = QTabWidget()
        tabs.addTab(settings_form([
            ("Name", self.name),
            ("", info_label("Gruß in der Mail: „VG“ und darunter der Name.")),
            ("Kürzel", self.kuerzel),
            ("Email-Adresse", self.absender),
            ("Projekt-Basisordner", self.basis),
        ]), "Allgemein")
        tabs.addTab(settings_form(server_rows), "Server")
        tabs.addTab(settings_form([
            ("IMAP-Server", self.imap_server),
            ("Port (SSL/TLS)", self.imap_port),
            ("", info_label("Benutzername und Passwort wie beim Postausgangs-Server.")),
            (None, bold_label("Gesendet-Ordner")),
            (None, self.imap_aktiv),
            ("Ordner", self.imap_ordner),
            ("", imap_test),
            (None, bold_label("Scans")),
            ("Scanner-Absender", self.scan_absender),
            ("Ordner", self.scan_ordner),
            ("Anzahl anzeigen", self.scan_anzahl),
        ]), "Postfach")

        # eine Seite je Vorlage
        self._vorlagen_werte = []
        for v in vorlagen:
            seite = v.settings_page(cfg)
            if seite is not None:
                widget, werte = seite
                tabs.addTab(widget, v.name)
                self._vorlagen_werte.append(werte)
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
        self.resize(680, self.sizeHint().height())

    def values(self) -> dict:
        v = {
            "projekt_basis": self.basis.text().strip(),
            "absender": self.absender.text().strip(),
            "kuerzel": self.kuerzel.text().strip().upper(),
            "smtp_server": self.server.text().strip(),
            "smtp_port": int(self.port.text() or 587),
            "smtp_security": self.security.currentText(),
            "smtp_user": self.user.text().strip(),
            "imap_aktiv": self.imap_aktiv.isChecked(),
            "imap_server": self.imap_server.text().strip(),
            "imap_port": int(self.imap_port.text() or 993),
            "imap_ordner": self.imap_ordner.text().strip(),
            "scan_absender": self.scan_absender.text().strip(),
            "scan_ordner": self.scan_ordner.text().strip() or "INBOX",
            "scan_anzahl": int(self.scan_anzahl.text() or 5),
        }
        if self.name.text().strip():
            v["gruss"] = f"VG\n{self.name.text().strip()}"
        for werte in self._vorlagen_werte:
            v.update(werte())
        return v

    # ----- Update-Tab -----
    def _system_page(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

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
        run_in_background(self, func, ok, fail)

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

        self.name = QLineEdit(gruss_name(cfg))
        self.name.setPlaceholderText("Vorname")
        self.kuerzel = QLineEdit(cfg.get("kuerzel", ""))
        self.kuerzel.setPlaceholderText("Initialen")
        self.kuerzel.setMaxLength(6)
        self.kuerzel.setFixedWidth(90)
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
        f.addRow(fixed_label("Kürzel"), self.kuerzel)
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

        for feld in (self.name, self.kuerzel, self.absender, self.user, self.password):
            feld.textChanged.connect(lambda _=None: self.status.clear())

        # Fokus auf das erste leere Feld
        for feld in (self.name, self.kuerzel, self.absender, self.user, self.password):
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
        fehlt = [n for n, w in (("Name", self.name), ("Kürzel", self.kuerzel), ("Email-Adresse", self.absender),
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
        self.cfg["kuerzel"] = self.kuerzel.text().strip().upper()
        save_config(self.cfg)
        set_password(self.cfg["smtp_user"], self.password.text())
        super().accept()


class AktionenDialog(QDialog):
    """Vor dem Senden: Empfänger bestätigen und Aktionen (Dateien ablegen …) abhaken."""

    def __init__(self, an: list[str], aktionen: list[Aktion], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Senden?")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(10)
        titel = QLabel("Email senden?")
        titel.setStyleSheet("font-size: 13pt; font-weight: 600;")
        lay.addWidget(titel)
        lay.addWidget(info_label("An: " + ", ".join(an)))
        self._boxen: list[tuple[QCheckBox, Aktion]] = []
        if aktionen:
            karte = QGroupBox("DANACH AUTOMATISCH")
            kl = QVBoxLayout(karte)
            kl.setSpacing(8)
            for a in aktionen:
                box = QCheckBox(a.titel)
                box.setChecked(a.vorgewaehlt)
                box.setStyleSheet("font-weight: 600;")
                kl.addWidget(box)
                # lange Pfade nach jedem \ umbrechbar machen (unsichtbares Leerzeichen)
                detail = info_label(a.detail.replace("\\", "\\\u200b"))
                detail.setContentsMargins(26, 0, 0, 4)
                kl.addWidget(detail)
                self._boxen.append((box, a))
            lay.addWidget(karte)
        row = QHBoxLayout()
        row.addStretch(1)
        nein = set_role(QPushButton("Abbrechen"), "ghost")
        nein.clicked.connect(self.reject)
        ja = with_icon(set_role(QPushButton("  Senden"), "primary"), "send", "#ffffff")
        ja.clicked.connect(self.accept)
        ja.setDefault(True)
        row.addWidget(nein)
        row.addWidget(ja)
        lay.addSpacing(6)
        lay.addLayout(row)

    def gewaehlt(self) -> list[Aktion]:
        return [a for box, a in self._boxen if box.isChecked()]
