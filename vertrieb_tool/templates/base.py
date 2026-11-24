"""Grundgerüst für Email-Vorlagen.

Eine neue Vorlage:
  1. Datei in diesem Ordner anlegen, Klasse von `Vorlage` ableiten
  2. id, name, DEFAULTS setzen und die Methoden unten überschreiben
  3. in templates/__init__.py in VORLAGEN eintragen
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape as esc
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget

from ..ui.style import field_label, set_role

ROT = "#c00000"


# ----- Projektdaten aus dem Kopf ----------------------------------------------------
@dataclass
class Projekt:
    nr: str = ""
    pfad: str = ""  # Ordner "Aktuell" (wie im Feld Pfad)
    firma: str = ""  # Kundenordner, z.B. FEINMETALL
    board: str = ""  # Teil nach "___"
    entwickler: str = ""

    @property
    def aktuell(self) -> Path | None:
        return Path(self.pfad) if self.pfad else None


# ----- Mailtext: Absätze aus Zeilen (Text, HTML) ------------------------------------
Zeile = tuple[str, str]
Absatz = list[Zeile]


def zeile(text: str, html: str | None = None) -> Zeile:
    return text, html if html is not None else esc(text)


def fett(text: str) -> Zeile:
    return text, f"<b>{esc(text)}</b>"


def rot(text: str) -> Zeile:
    return text, f'<span style="color:{ROT};font-weight:bold">{esc(text)}</span>'


def absatz(*zeilen: Zeile) -> Absatz:
    return list(zeilen)


def text_absatz(text: str) -> Absatz:
    return [zeile(z) for z in text.splitlines()]


def render(absaetze: list[Absatz]) -> tuple[str, str]:
    """(Text, HTML) aus Absätzen; leere Absätze fallen weg."""
    absaetze = [a for a in absaetze if a]
    text = "\n\n".join("\n".join(t for t, _ in a) for a in absaetze)
    html = (
        '<div style="font-family:Calibri,Arial,sans-serif;font-size:11pt">'
        + "<br><br>".join("<br>".join(h for _, h in a) for a in absaetze)
        + "</div>"
    )
    return text, html


def zeilen(text: str) -> list[str]:
    """Nicht-leere Zeilen, führende Aufzählungszeichen entfernt."""
    out = []
    for z in text.splitlines():
        z = z.strip()
        if z.startswith(("- ", "* ", "• ")):
            z = z[2:].strip()
        if z and z != "-":
            out.append(z)
    return out


def as_bullets(text: str) -> str:
    """Jede nicht-leere Zeile bekommt ein '- ' davor."""
    return "\n".join(f"- {z}" for z in zeilen(text))


# ----- Aktionen nach dem Senden (Dateien ablegen usw.) ------------------------------
@dataclass
class Aktion:
    titel: str  # z.B. "Scan ablegen"
    detail: str  # z.B. "doc123.pdf → …\BGR\Bestellung_Teil1_241126.pdf"
    ausfuehren: Callable[[], str]  # gibt eine Erfolgsmeldung zurück, wirft bei Fehler
    vorgewaehlt: bool = True


# ----- Basisklasse ------------------------------------------------------------------
class Vorlage(QObject):
    """Eine Email-Vorlage. `changed` auslösen, sobald sich etwas am Inhalt ändert."""

    id = ""
    name = ""
    DEFAULTS: dict = {}  # eigene Einstellungen (Präfix empfohlen, z.B. "bb_")

    changed = pyqtSignal()

    def __init__(self, cfg: dict, fenster):
        super().__init__()
        self.cfg = cfg
        self.fenster = fenster  # Hauptfenster (Passwort, Status …)
        self.projekt = Projekt()
        self._widget: QWidget | None = None

    # --- Formular ---
    def widget(self) -> QWidget:
        if self._widget is None:
            self._widget = self.build()
        return self._widget

    def build(self) -> QWidget:
        """Formular der Vorlage (linke Spalte unter dem Kopf)."""
        raise NotImplementedError

    def aktiviert(self) -> None:
        """Wird aufgerufen, wenn die Vorlage ausgewählt wird."""

    def projekt_geaendert(self, p: Projekt) -> None:
        """Kopf (Projektnummer, Pfad, Entwickler) hat sich geändert."""
        self.projekt = p

    def leeren(self) -> None:
        """Alle Eingaben zurücksetzen."""

    def einstellungen_neu(self) -> None:
        """Einstellungen wurden gespeichert (z.B. Shortcut-Buttons neu bauen)."""

    def zugangsdaten_geaendert(self) -> None:
        """Passwort/Benutzer wurden (neu) eingetragen – z.B. Postfach erneut abfragen."""

    # --- Mail ---
    def empfaenger(self) -> tuple[str, str]:
        """(An, CC) als Text, mehrere Adressen mit ; getrennt."""
        return "", ""

    def betreff(self, p: Projekt) -> str:
        raise NotImplementedError

    def absaetze(self, p: Projekt) -> list[Absatz]:
        """Kompletter Mailtext inkl. Anrede und Gruß."""
        raise NotImplementedError

    def gruss(self) -> Absatz:
        return text_absatz(self.cfg.get("gruss", ""))

    def pruefen(self, p: Projekt) -> str | None:
        """Fehlermeldung, wenn noch etwas fehlt – sonst None."""
        if not p.pfad:
            return "Es ist noch kein Pfad eingetragen."
        return None

    def aktionen(self, p: Projekt) -> list[Aktion]:
        """Was nach dem Senden zusätzlich passieren soll (Dateien ablegen …)."""
        return []

    def nach_senden(self, p: Projekt) -> None:
        """Nach erfolgreichem Senden (z.B. Eingaben merken)."""

    # --- Einstellungen (eigener Tab im Einstellungsfenster) ---
    def settings_page(self, cfg: dict):
        """(Widget, Funktion die die geänderten Werte als dict liefert) oder None."""
        return None


# ----- kleine Helfer für Formulare --------------------------------------------------
def settings_form(rows) -> QWidget:
    """Formular-Seite für den Einstellungs-Dialog. rows: (Label|None, Widget)."""
    w = QWidget()
    outer = QVBoxLayout(w)
    outer.setContentsMargins(16, 16, 16, 16)
    f = QFormLayout()
    f.setHorizontalSpacing(14)
    f.setVerticalSpacing(10)
    outer.addLayout(f)
    outer.addStretch(1)
    for label, widget in rows:
        if label is None:
            f.addRow(widget)
        else:
            f.addRow(field_label(label), widget)
    return w


def info_label(text: str) -> QLabel:
    lbl = set_role(QLabel(text), "field")
    lbl.setWordWrap(True)
    return lbl
