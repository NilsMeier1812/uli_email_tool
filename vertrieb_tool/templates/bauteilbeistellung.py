"""Vorlage „Bauteilbeistellung“: Beistellung in die Warenannahme gebracht – Info an Lager und Vertrieb.

Ablauf: Mail senden, danach das Scan-PDF (Wareneingang-Beistellung-Zettel) nach
Aktuell\\BGR kopieren und – je nach Variante – einen Eintrag oben in die README schreiben.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape as esc

from PyQt6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from .. import projekt as pj
from ..core import save_config
from ..mail import fetch_scans
from ..ui.style import LABEL_W, field_label, hint_label
from ..ui.widgets import ScanPicker, ToggleRow, multiline, run_in_background
from .base import Aktion, Projekt, Vorlage, fett, info_label, rot, settings_form, zeile, zeilen


@dataclass(frozen=True)
class Variante:
    betreff_zusatz: str = ""  # Teil 1/2: Zusatz im Betreff, sonst Schema "Fa. … (PNV:…)"
    satz: str = ""  # Teil 1/2: zweiter Satz der Mail
    art: str = ""  # QUAL / EVM (fett im Text) – leer bei "Ohne"
    datei: str = "Bestellung_{datum}.pdf"  # Name des Scans in Aktuell\BGR ({datum} = TTMMJJ)
    details: bool = False  # Felder "Beistellung von" usw. + README-Eintrag


VARIANTEN: dict[str, Variante] = {
    "Teil 1": Variante(
        betreff_zusatz="Teil1 Zu Zeroone",
        satz="Das ist die Beistellung zum Bestücken bei Zeroone => Shipping nach Hongkong.",
        datei="Bestellung_Teil1_{datum}.pdf",
    ),
    "Teil 2": Variante(
        betreff_zusatz="Teil2 Vernieten GCD",
        satz="Das ist die Beistellung zum Vernieten bei GCD.",
        datei="Bestellung_Teil2_{datum}.pdf",
    ),
    # TODO Dateinamen für QUAL/EVM/Ohne sind vorläufig – Schema wird noch geklärt
    "QUAL": Variante(art="QUAL", datei="Bestellung_QUAL_{datum}.pdf", details=True),
    "EVM": Variante(art="EVM", datei="Bestellung_EVM_{datum}.pdf", details=True),
    "Ohne": Variante(datei="Bestellung_{datum}.pdf", details=True),
}

SPARE_TEXT = "Rest sind Spare und müssen mit der Lieferung wieder zurück."
TRENNER = "=" * 42


class Bauteilbeistellung(Vorlage):
    id = "bauteilbeistellung"
    name = "Bauteilbeistellung"
    DEFAULTS = {
        "bb_empfaenger": "lager@gcd.de; vertrieb@gcd.de",
        "bb_cc": "",
        "bb_anrede": "Hallo Lager, hallo Vertrieb,",
        "kunden_kurz": {},  # Kundenordner -> Kurzname, z.B. TEXAS_INSTRUMENTS -> TI (wird gelernt)
    }

    def __init__(self, cfg, fenster):
        super().__init__(cfg, fenster)
        self._scans_geladen = False
        self._kunde_manuell = False

    # ----- Formular -----
    def build(self) -> QWidget:
        w = QWidget()
        root = QVBoxLayout(w)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)
        upd = self.changed.emit

        # --- Beistellung ---
        box = QGroupBox("BEISTELLUNG")
        g = QGridLayout(box)
        g.setColumnMinimumWidth(0, LABEL_W)
        g.setHorizontalSpacing(12)
        g.setVerticalSpacing(6)
        g.setColumnStretch(1, 1)
        self.variante = ToggleRow(list(VARIANTEN), allow_none=False)
        self.variante.changed.connect(self._variante_geaendert)
        g.addWidget(field_label("Variante"), 0, 0)
        g.addWidget(self.variante, 0, 1)
        self.kunde_edit = QLineEdit()
        self.kunde_edit.textChanged.connect(upd)
        self.kunde_edit.textEdited.connect(self._kunde_bearbeitet)
        self.kunde_hint = hint_label("")
        kunde_row = QHBoxLayout()
        kunde_row.setSpacing(10)
        kunde_row.addWidget(self.kunde_edit, 1)
        kunde_row.addWidget(self.kunde_hint, 1)
        g.addWidget(field_label("Kunde"), 1, 0)
        g.addLayout(kunde_row, 1, 1)
        root.addWidget(box)

        # --- Details (QUAL / EVM / Ohne) ---
        self.details_box = QGroupBox("INHALT")
        d = QGridLayout(self.details_box)
        d.setColumnMinimumWidth(0, LABEL_W)
        d.setHorizontalSpacing(12)
        d.setVerticalSpacing(6)
        d.setColumnStretch(1, 1)
        self.von_edit = multiline(3)
        self.von_edit.setPlaceholderText("z.B. 300 x TPSM8286N Lot1 – eine Position pro Zeile")
        self.von_edit.textChanged.connect(upd)
        self.bestuecken_edit = multiline(2)
        self.bestuecken_edit.setPlaceholderText("optional, z.B. 2 x 90 units => 2 x 30 coupons")
        self.bestuecken_edit.textChanged.connect(upd)
        self.spare = QCheckBox(SPARE_TEXT.rstrip("."))
        self.spare.toggled.connect(upd)
        self.frei_edit = multiline(2)
        self.frei_edit.setPlaceholderText("optional – erscheint rot und fett")
        self.frei_edit.textChanged.connect(upd)
        d.addWidget(field_label("Beistellung von"), 0, 0)
        d.addWidget(self.von_edit, 0, 1)
        d.addWidget(field_label("Bestücken von"), 1, 0)
        d.addWidget(self.bestuecken_edit, 1, 1)
        d.addWidget(self.spare, 2, 1)
        d.addWidget(field_label("Freitext"), 3, 0)
        d.addWidget(self.frei_edit, 3, 1)
        root.addWidget(self.details_box)

        # --- Scan ---
        scan_box = QGroupBox("SCAN  (Wareneingang-Beistellung-Zettel)")
        sl = QVBoxLayout(scan_box)
        sl.setSpacing(8)
        self.picker = ScanPicker()
        self.picker.refresh_requested.connect(self.lade_scans)
        self.picker.changed.connect(upd)
        sl.addWidget(self.picker)
        self.ablage = info_label("")
        sl.addWidget(self.ablage)
        root.addWidget(scan_box)

        self.changed.connect(self._ablage_anzeigen)
        self._variante_geaendert()
        return w

    def _variante_geaendert(self):
        v = self._variante()
        self.details_box.setVisible(v is None or v.details)
        self.changed.emit()

    def _variante(self) -> Variante | None:
        return VARIANTEN.get(self.variante.value())

    def _kunde_bearbeitet(self, _text: str):
        self._kunde_manuell = True

    def _kunde_vorschlag(self, firma: str) -> str:
        return self.cfg.get("kunden_kurz", {}).get(firma, firma)

    def projekt_geaendert(self, p: Projekt) -> None:
        alt = self.projekt.firma
        super().projekt_geaendert(p)
        if self._widget is None:
            return
        if p.firma != alt:
            self._kunde_manuell = False
        if not self._kunde_manuell:
            self.kunde_edit.setText(self._kunde_vorschlag(p.firma))
        self.kunde_hint.setText(f"Ordner: {p.firma}" if p.firma and p.firma != self.kunde() else "")

    def kunde(self) -> str:
        return self.kunde_edit.text().strip()

    def _dateiname(self) -> str:
        v = self._variante()
        return v.datei.format(datum=pj.datum_kurz()) if v else ""

    def _ablage_anzeigen(self):
        if not self.projekt.pfad:
            self.ablage.setText("Ablage: Projekt suchen, dann wird der Scan nach Aktuell\\BGR kopiert.")
            return
        v = self._variante()
        ziel = pj.bgr_dir(self.projekt.aktuell)
        text = f"Ablage: {ziel}\\{self._dateiname() if v else '…'}"
        if v and v.details:
            text += "  ·  README dort wird ergänzt"
        self.ablage.setText(text)

    # --- Scans ---
    def aktiviert(self) -> None:
        if not self._scans_geladen:
            self.lade_scans()

    def zugangsdaten_geaendert(self) -> None:
        if self._scans_geladen:
            self.lade_scans()

    def lade_scans(self):
        self._scans_geladen = True
        pw = self.fenster.passwort(nachfragen=False)
        if not pw:
            self.picker.set_error("Für die Scans aus dem Posteingang fehlt das Passwort "
                                  "(Einstellungen). PDF kann auch hineingezogen werden.")
            return
        self.picker.set_loading()
        cfg = dict(self.cfg)
        run_in_background(self, lambda: fetch_scans(cfg, pw), self.picker.set_scans,
                          lambda e: self.picker.set_error(f"Scans konnten nicht geladen werden: {e}"))

    def leeren(self) -> None:
        self.variante.set_value("")
        self.von_edit.clear()
        self.bestuecken_edit.clear()
        self.frei_edit.clear()
        self.spare.setChecked(False)
        self._kunde_manuell = False
        self.kunde_edit.setText(self._kunde_vorschlag(self.projekt.firma))
        self.picker.clear_selection()

    # ----- Mail -----
    def empfaenger(self) -> tuple[str, str]:
        return self.cfg.get("bb_empfaenger", ""), self.cfg.get("bb_cc", "")

    def betreff(self, p: Projekt) -> str:
        v = self._variante()
        kunde = self.kunde() or p.firma
        if v is None or not v.betreff_zusatz:
            entw = f"{p.entwickler} " if p.entwickler else ""
            text = f"PN{p.nr} / Beistellung Fa. {kunde} / {entw}(PNV:{p.nr}) {p.board}"
        else:
            text = f"PN{p.nr} / Beistellung {kunde} / {p.board} => {v.betreff_zusatz}"
        return " ".join(text.split())

    def absaetze(self, p: Projekt):
        v = self._variante() or Variante(details=True)
        kunde = self.kunde() or p.firma or "…"
        k_html = f"<b>{esc(kunde)}</b>"
        zettel = "habe ich mit dem Wareneingang-Beistellung-Zettel in die Warenannahme gebracht."
        out = [[zeile(self.cfg.get("bb_anrede", ""))]]

        if not v.details:  # Teil 1 / Teil 2
            out.append([zeile(f"die {kunde}-Beistellung für das oben genannte Projekt {zettel}",
                              f"die {k_html}-Beistellung für das oben genannte Projekt {esc(zettel)}")])
            out.append([zeile(v.satz)])
            out.append(self.gruss())
            return out

        board = f" ({p.board})" if p.board else ""
        if v.art:
            satz_t = f"die {kunde}-Beistellung für die {v.art}-Boards{board} {zettel}"
            satz_h = (f"die {k_html}-Beistellung für die <b>{esc(v.art)}</b>-Boards{esc(board)} "
                      f"{esc(zettel)}")
        else:
            satz_t = f"die {kunde}-Beistellung für die Boards{board} {zettel}"
            satz_h = f"die {k_html}-Beistellung für die Boards{esc(board)} {esc(zettel)}"
        out.append([zeile(satz_t, satz_h)])

        von = zeilen(self.von_edit.toPlainText())
        if von:
            out.append([zeile("Beistellung von:")])
            out.append([fett(f"- {x}") for x in von])
        bestuecken = zeilen(self.bestuecken_edit.toPlainText())
        if bestuecken:
            out.append([zeile("Zum Bestücken von:")])
            out.append([fett(x) for x in bestuecken])
        if self.spare.isChecked():
            out.append([fett(SPARE_TEXT)])
        frei = zeilen(self.frei_edit.toPlainText())
        if frei:
            out.append([rot(x) for x in frei])
        out.append(self.gruss())
        return out

    def pruefen(self, p: Projekt) -> str | None:
        fehler = super().pruefen(p)
        if fehler:
            return fehler
        v = self._variante()
        if v is None:
            return "Bitte die Variante wählen (Teil 1, Teil 2, QUAL, EVM oder Ohne)."
        if not self.kunde():
            return "Bitte den Kunden eintragen."
        if v.details and not zeilen(self.von_edit.toPlainText()):
            return "Bitte eintragen, was beigestellt wurde („Beistellung von“)."
        if self.picker.selected() is None:
            return "Bitte den Scan des Beistellung-Zettels auswählen (oder als PDF hineinziehen)."
        return None

    # ----- Dateien ablegen -----
    def _readme_block(self) -> str:
        teile = [TRENNER, f"  {pj.datum_us()} / {self.cfg.get('kuerzel', '').strip()}", ""]
        von = zeilen(self.von_edit.toPlainText())
        if von:
            teile += ["Beistellung von"] + [f"- {x}" for x in von] + [""]
        bestuecken = zeilen(self.bestuecken_edit.toPlainText())
        if bestuecken:
            teile += ["Zum Bestücken von"] + bestuecken + [""]
        if self.spare.isChecked():
            teile += [SPARE_TEXT, ""]
        frei = zeilen(self.frei_edit.toPlainText())
        if frei:
            teile += frei + [""]
        teile.append(TRENNER)
        return "\n".join(teile) + "\n"

    def aktionen(self, p: Projekt) -> list[Aktion]:
        v = self._variante()
        scan = self.picker.selected()
        if v is None or scan is None or p.aktuell is None:
            return []
        bgr = pj.bgr_dir(p.aktuell)
        ziel = bgr / self._dateiname()
        daten = scan.lesen()  # jetzt lesen – die Auswahl kann sich danach ändern

        def scan_ablegen() -> str:
            return f"Scan abgelegt: {pj.ablegen(daten, ziel)}"

        aktionen = [Aktion("Scan ablegen", f"{scan.name}  →  {ziel}", scan_ablegen)]
        if v.details:
            block = self._readme_block()
            vorhanden = pj.find_readme(bgr)
            detail = (f"Eintrag oben in {vorhanden}" if vorhanden
                      else f"Neue README.txt in {bgr}")

            def readme() -> str:
                datei, neu = pj.readme_voranstellen(bgr, block)
                return f"README {'angelegt' if neu else 'ergänzt'}: {datei}"

            aktionen.append(Aktion("README ergänzen", detail, readme))
        return aktionen

    def nach_senden(self, p: Projekt) -> None:
        # Kurznamen merken (z.B. TEXAS_INSTRUMENTS -> TI), beim nächsten Mal vorbelegt
        kunde = self.kunde()
        if p.firma and kunde and kunde != self.cfg.get("kunden_kurz", {}).get(p.firma, p.firma):
            self.cfg.setdefault("kunden_kurz", {})[p.firma] = kunde
            save_config(self.cfg)

    # ----- Einstellungen -----
    def settings_page(self, cfg: dict):
        an = QLineEdit(cfg.get("bb_empfaenger", ""))
        cc = QLineEdit(cfg.get("bb_cc", ""))
        anrede = QLineEdit(cfg.get("bb_anrede", ""))
        kurz = multiline(4)
        kurz.setPlainText("\n".join(f"{k} = {v}" for k, v in sorted(cfg.get("kunden_kurz", {}).items())))
        page = settings_form([
            ("An", an),
            ("CC", cc),
            ("Anrede", anrede),
            ("Kunden-Kurznamen", kurz),
            ("", info_label("Ordnername = Name in der Mail, z.B. TEXAS_INSTRUMENTS = TI. "
                            "Wird automatisch gemerkt, wenn der Kunde in der Mail geändert wird.")),
        ])

        def werte() -> dict:
            mapping = {}
            for z in kurz.toPlainText().splitlines():
                if "=" in z:
                    k, v = (t.strip() for t in z.split("=", 1))
                    if k and v:
                        mapping[k] = v
            return {"bb_empfaenger": an.text().strip(), "bb_cc": cc.text().strip(),
                    "bb_anrede": anrede.text(), "kunden_kurz": mapping}

        return page, werte
