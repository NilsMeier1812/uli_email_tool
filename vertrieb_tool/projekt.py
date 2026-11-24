"""Projektordner auf M: suchen, Pfade bestimmen, Dateien ablegen."""

from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path


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
    r"""Ordner "Aktuell" im Projekt.

    Unter dem Projekt gibt es "<nr>.01", "<nr>" ohne Index oder mehrere (.01, .02 …).
    Regel: immer in "<nr>.01", sonst in den Ordner ohne Index.
    """
    for kandidat in (f"{nr}.01", nr):
        if (projekt_dir / kandidat).is_dir():
            return projekt_dir / kandidat / "Aktuell"
    return projekt_dir / f"{nr}.01" / "Aktuell"


def find_child(ordner: Path, name: str) -> Path | None:
    """Unterordner unabhängig von Groß-/Kleinschreibung finden."""
    try:
        for p in ordner.iterdir():
            if p.is_dir() and p.name.lower() == name.lower():
                return p
    except OSError:
        pass
    return None


def bgr_dir(aktuell: Path) -> Path:
    """Ordner Aktuell\\BGR (vorhandene Schreibweise wird übernommen)."""
    return find_child(aktuell, "BGR") or (aktuell / "BGR")


def datum_kurz(d: date | None = None) -> str:
    """TTMMJJ, z.B. 241126 (für Dateinamen)."""
    return (d or date.today()).strftime("%d%m%y")


def datum_us(d: date | None = None) -> str:
    """MM-TT-JJ (amerikanisch), z.B. 11-24-26 (für README)."""
    return (d or date.today()).strftime("%m-%d-%y")


def freier_name(ziel: Path) -> Path:
    """Vorhandene Datei nicht überschreiben: name_2.pdf, name_3.pdf …"""
    if not ziel.exists():
        return ziel
    i = 2
    while True:
        p = ziel.with_name(f"{ziel.stem}_{i}{ziel.suffix}")
        if not p.exists():
            return p
        i += 1


def ablegen(quelle_bytes: bytes, ziel: Path) -> Path:
    """Datei speichern (Ordner wird angelegt, nichts wird überschrieben)."""
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel = freier_name(ziel)
    ziel.write_bytes(quelle_bytes)
    return ziel


def kopieren(quelle: Path, ziel: Path) -> Path:
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel = freier_name(ziel)
    shutil.copy2(quelle, ziel)
    return ziel


# ----- README -----------------------------------------------------------------
_README_RE = re.compile(r"^read[\s_\-.]*me$", re.I)


def find_readme(ordner: Path) -> Path | None:
    """README in beliebiger Schreibweise finden (README, Read_Me, ReadMe.txt …)."""
    try:
        kandidaten = [p for p in ordner.iterdir() if p.is_file() and _README_RE.match(p.stem)]
    except OSError:
        return None
    kandidaten.sort(key=lambda p: (p.suffix.lower() != ".txt", p.name.lower()))
    return kandidaten[0] if kandidaten else None


def readme_voranstellen(ordner: Path, block: str) -> tuple[Path, bool]:
    """Block oben in die README schreiben. Gibt (Datei, neu_angelegt) zurück.

    Kodierung und Zeilenenden der vorhandenen Datei bleiben erhalten.
    """
    datei = find_readme(ordner)
    neu = datei is None
    if neu:
        ordner.mkdir(parents=True, exist_ok=True)
        datei = ordner / "README.txt"
        alt, kodierung, nl = "", "utf-8", "\r\n"
    else:
        roh = datei.read_bytes()
        if roh.startswith(b"\xef\xbb\xbf"):
            kodierung = "utf-8-sig"  # BOM bleibt am Dateianfang
        else:
            try:
                roh.decode("utf-8")
                kodierung = "utf-8"
            except UnicodeDecodeError:
                kodierung = "cp1252"  # klassisches Windows-Notepad (ANSI)
        alt = roh.decode(kodierung, errors="replace")
        nl = "\r\n" if "\r\n" in alt or not alt else "\n"
        alt = alt.replace("\r\n", "\n")
    text = block.rstrip("\n") + "\n\n" + alt
    datei.write_bytes(text.replace("\n", nl).encode(kodierung, errors="replace"))
    return datei, neu
