"""Vorlage „Daten auf M“: Baugruppendaten liegen auf M – Info an den Vertrieb."""

from __future__ import annotations

from html import escape as esc

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGridLayout, QGroupBox, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ..ui.style import LABEL_W, bold_label, field_label, set_role
from ..ui.widgets import Slot, ToggleRow, append_inline, append_line, chip_flow, chip_row, multiline
from .base import Projekt, Vorlage, info_label, rot, settings_form, zeile, zeilen

INFO_TEXTE = {  # erscheint als "Bestellung: <b>gemäß …</b>"
    "PO": "gemäß PO",
    "Ang": "gemäß Angebot",
}

ZUSAETZE = [  # (Button, Text in der Mail) – erscheinen nach "Bauteile"
    ("US", "US Reinigung"),
    ("Lasertrennung", "Lasertrennung"),
    ("Beist", "Beistellung"),
]


def _liste(edit) -> list[str]:
    return [z.strip() for z in edit.toPlainText().splitlines() if z.strip()]


class DatenAufM(Vorlage):
    id = "daten_auf_m"
    name = "Daten auf M"
    DEFAULTS = {
        "empfaenger": "vertrieb@gcd.de",
        "cc": "",
        # Platzhalter: {nr} Projektnummer, {firma} Kundenordner, {board} Teil nach ___
        "betreff": "PN{nr} / Baugruppendaten {firma} {board} / {nr} sind auf M",
        "anrede": "Hallo Vertrieb,",
        "bausteine_info": [],
        "bausteine_achtung": [],
        "shortcuts_lieferant": ["Fima", "KC", "Piu", "Zeroone"],
        "shortcuts_sonstiges": ["Daten sind bei Hersteller"],
        "shortcuts_bauteile": ["BOM"],
    }

    # ----- Formular -----
    def build(self) -> QWidget:
        w = QWidget()
        root = QVBoxLayout(w)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)
        upd = self.changed.emit

        # --- Info ---
        info_box = QGroupBox("INFO")
        ig = QGridLayout(info_box)
        ig.setColumnMinimumWidth(0, LABEL_W)
        ig.setHorizontalSpacing(12)
        ig.setVerticalSpacing(6)
        self.info_mode = ToggleRow(["PO", "Ang"])
        self.info_mode.changed.connect(upd)
        ig.addWidget(field_label("Bestellung"), 0, 0)
        ig.addWidget(self.info_mode, 0, 1)
        info_panel = QWidget()
        il = QVBoxLayout(info_panel)
        il.setContentsMargins(0, 0, 0, 0)
        self.info_edit = multiline(2)
        self.info_edit.textChanged.connect(upd)
        il.addWidget(self.info_edit)
        self.info_chips = Slot()
        il.addWidget(self.info_chips)
        ig.addWidget(info_panel, 1, 1)
        self.termin_edit = QLineEdit()
        set_role(self.termin_edit, "termin")
        self.termin_edit.textChanged.connect(upd)
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
        ag.addWidget(bold_label("LP"), r, 0, 1, 2)
        r += 1
        lp_row = QHBoxLayout()
        lp_row.setSpacing(8)
        self.lp_typ = ToggleRow(["Einzel-LP", "Nutzen"])
        self.lp_typ.changed.connect(upd)
        lp_row.addWidget(self.lp_typ)
        lp_row.addSpacing(12)
        lp_row.addWidget(field_label("Anzahl"))
        self.lp_anzahl = QLineEdit()
        self.lp_anzahl.setFixedWidth(60)
        self.lp_anzahl.textChanged.connect(upd)
        lp_row.addWidget(self.lp_anzahl)
        self.lp_anzahl2 = QLineEdit()
        self.lp_anzahl2.setFixedWidth(160)
        self.lp_anzahl2.textChanged.connect(upd)
        lp_row.addWidget(self.lp_anzahl2)
        lp_row.addStretch(1)
        ag.addWidget(field_label("Art"), r, 0)
        ag.addLayout(lp_row, r, 1)
        r += 1

        def feld_mit_chips(label: str):
            nonlocal r
            edit = QLineEdit()
            edit.textChanged.connect(upd)
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(edit, 1)
            slot = Slot()
            row.addWidget(slot)
            if label in ("Bauteile",):
                ag.addWidget(bold_label(label), r, 0)
            else:
                ag.addWidget(field_label(label), r, 0)
            ag.addLayout(row, r, 1)
            r += 1
            return edit, slot

        self.lieferant_edit, self.lieferant_chips = feld_mit_chips("Lieferant")
        self.sonst_edit, self.sonst_chips = feld_mit_chips("Sonstiges")

        ag.addWidget(bold_label("Paste"), r, 0)
        self.paste = ToggleRow(["von M", "Hersteller", "Keine"])
        self.paste.changed.connect(upd)
        ag.addWidget(self.paste, r, 1)
        r += 1

        self.bauteile_edit, self.bauteile_chips = feld_mit_chips("Bauteile")

        zusatz_row = QHBoxLayout()
        zusatz_row.setSpacing(8)
        self.zusatz_buttons: list[tuple[QPushButton, str]] = []
        for label, ausgabe in ZUSAETZE:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setMinimumWidth(70)
            btn.setToolTip(ausgabe)
            set_role(btn, "toggle")
            btn.toggled.connect(upd)
            zusatz_row.addWidget(btn)
            self.zusatz_buttons.append((btn, ausgabe))
        # Textfeld zu "Beist" – Tippen aktiviert den Schalter automatisch
        self.beist_btn = self.zusatz_buttons[-1][0]
        self.beist_edit = QLineEdit()
        self.beist_edit.textChanged.connect(self._beist_text)
        zusatz_row.addWidget(self.beist_edit, 1)
        ag.addLayout(zusatz_row, r, 1)
        r += 1

        ag.addWidget(bold_label("Freitext"), r, 0, Qt.AlignmentFlag.AlignTop)
        frei = QVBoxLayout()
        self.warn_edit = multiline(4)
        self.warn_edit.setPlaceholderText("jede Zeile wird ein eigener Aufzählungspunkt")
        self.warn_edit.textChanged.connect(upd)
        frei.addWidget(self.warn_edit)
        self.warn_chips = Slot()
        frei.addWidget(self.warn_chips)
        ag.addLayout(frei, r, 1)
        root.addWidget(warn_box)

        self.info_mode.set_value("PO")
        self.einstellungen_neu()
        return w

    def _beist_text(self, text: str):
        if text.strip() and not self.beist_btn.isChecked():
            self.beist_btn.setChecked(True)  # löst changed aus
        else:
            self.changed.emit()

    def einstellungen_neu(self) -> None:
        if self._widget is None and not hasattr(self, "info_chips"):
            return
        c = self.cfg
        self.info_chips.set(chip_flow(c.get("bausteine_info", []), lambda t: append_line(self.info_edit, t)))
        self.warn_chips.set(chip_flow(c.get("bausteine_achtung", []), lambda t: append_line(self.warn_edit, t)))
        self.lieferant_chips.set(chip_row(c.get("shortcuts_lieferant", []), self.lieferant_edit.setText))
        self.sonst_chips.set(chip_row(c.get("shortcuts_sonstiges", []),
                                      lambda t: append_inline(self.sonst_edit, t)))
        self.bauteile_chips.set(chip_row(c.get("shortcuts_bauteile", []),
                                         lambda t: append_inline(self.bauteile_edit, t)))

    def leeren(self) -> None:
        for e in (self.termin_edit, self.lp_anzahl, self.lp_anzahl2, self.lieferant_edit,
                  self.sonst_edit, self.bauteile_edit, self.beist_edit):
            e.clear()
        self.info_edit.clear()
        self.warn_edit.clear()
        self.lp_typ.set_value("")
        self.paste.set_value("")
        for btn, _ in self.zusatz_buttons:
            btn.setChecked(False)
        self.info_mode.set_value("PO")

    # ----- Mail -----
    def empfaenger(self) -> tuple[str, str]:
        return self.cfg.get("empfaenger", ""), self.cfg.get("cc", "")

    def betreff(self, p: Projekt) -> str:
        firma = p.firma
        if p.entwickler:
            firma = f"{firma} ({p.entwickler})" if firma else f"({p.entwickler})"
        betreff = (self.cfg.get("betreff", "")
                   .replace("{nr}", p.nr).replace("{firma}", firma).replace("{board}", p.board))
        return " ".join(betreff.split())

    def _lp_text(self) -> str:
        teile = []
        if self.lp_typ.value():
            teile.append(self.lp_typ.value())
        anzahl = ", ".join(t for t in (self.lp_anzahl.text().strip(), self.lp_anzahl2.text().strip()) if t)
        if anzahl:
            teile.append(f"Anzahl: {anzahl}")
        if self.lieferant_edit.text().strip():
            teile.append(f"Lieferant: {self.lieferant_edit.text().strip()}")
        if self.sonst_edit.text().strip():
            teile.append(self.sonst_edit.text().strip())
        return ", ".join(teile)

    def absaetze(self, p: Projekt):
        out = [[zeile(self.cfg.get("anrede", ""))],
               [zeile(f"die Baugruppendaten für das Board sind auf {p.pfad}")]]

        info = []
        modus = self.info_mode.value()
        text = [z.rstrip() for z in self.info_edit.toPlainText().strip().splitlines()]
        if modus in INFO_TEXTE:
            rest = f", {text[0]}" if text else ""
            info.append(zeile(f"Bestellung: {INFO_TEXTE[modus]}{rest}",
                              f"Bestellung: <b>{esc(INFO_TEXTE[modus])}</b>{esc(rest)}"))
            info += [zeile(z) for z in text[1:]]
        elif text:
            info.append(zeile(f"Bestellung: {text[0]}"))
            info += [zeile(z) for z in text[1:]]
        termin = self.termin_edit.text().strip()
        if termin:
            info.append(rot(f"Liefertermin: {termin}"))
        out.append(info)

        punkte: list[str] = []
        if self._lp_text():
            punkte.append(f"LP -> {self._lp_text()}")
        if self.paste.value():
            punkte.append(f"Paste -> {self.paste.value()}")
        if self.bauteile_edit.text().strip():
            punkte.append(f"Bauteile -> {self.bauteile_edit.text().strip()}")
        for btn, ausgabe in self.zusatz_buttons:
            if btn.isChecked():
                if btn is self.beist_btn and self.beist_edit.text().strip():
                    ausgabe = f"{ausgabe} -> {self.beist_edit.text().strip()}"
                punkte.append(ausgabe)
        punkte += zeilen(self.warn_edit.toPlainText())
        if punkte:
            out.append([zeile("Achtung:")])
            out.append([zeile(f"- {x}") for x in punkte])
        out.append(self.gruss())
        return out

    # ----- Einstellungen -----
    def settings_page(self, cfg: dict):
        def edit(key):
            return QLineEdit(cfg.get(key, ""))

        def liste(key):
            e = multiline(3)
            e.setPlainText("\n".join(cfg.get(key, [])))
            return e

        f = {k: edit(k) for k in ("empfaenger", "cc", "betreff", "anrede")}
        l = {k: liste(k) for k in ("shortcuts_lieferant", "shortcuts_sonstiges", "shortcuts_bauteile",
                                   "bausteine_achtung", "bausteine_info")}
        page = settings_form([
            ("An", f["empfaenger"]),
            ("CC", f["cc"]),
            ("Betreff", f["betreff"]),
            ("", info_label("Platzhalter: {nr}  {firma}  {board}")),
            ("Anrede", f["anrede"]),
            (None, info_label("Shortcut-Buttons – ein Eintrag pro Zeile:")),
            ("LP → Lieferant", l["shortcuts_lieferant"]),
            ("LP → Sonstiges", l["shortcuts_sonstiges"]),
            ("Bauteile", l["shortcuts_bauteile"]),
            ("Freitext", l["bausteine_achtung"]),
            ("Info (Text)", l["bausteine_info"]),
        ])

        def werte() -> dict:
            v = {k: e.text().strip() for k, e in f.items()}
            v["betreff"] = f["betreff"].text()
            v.update({k: _liste(e) for k, e in l.items()})
            return v

        return page, werte
