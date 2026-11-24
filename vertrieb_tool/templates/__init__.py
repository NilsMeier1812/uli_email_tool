"""Alle Email-Vorlagen. Neue Vorlage: Datei anlegen und hier in VORLAGEN eintragen."""

from ..core import register_defaults
from .base import Vorlage
from .bauteilbeistellung import Bauteilbeistellung
from .daten_auf_m import DatenAufM

VORLAGEN: list[type[Vorlage]] = [
    DatenAufM,
    Bauteilbeistellung,
]

for _v in VORLAGEN:
    register_defaults(_v.DEFAULTS)
