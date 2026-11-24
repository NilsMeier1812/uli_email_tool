# Vertrieb Email Tool

Kleines PyQt6-Tool, um die immer gleiche Email „Baugruppendaten liegen auf …“ an den Vertrieb zu verschicken.

## Vorlagen
Oben im Fenster wählt man die Vorlage. Der Kopf (Projektnummer → Suche → Pfad, Entwickler) ist bei allen gleich.

### Daten auf M
Baugruppendaten liegen auf M – Info an den Vertrieb.
- **Info**: `PO` / `Ang` (abwählbar) und Textfeld – „Bestellung: **gemäß PO**, Text“; optional **Liefertermin** (rot, fett)
- **Achtung** (wird zur Aufzählung): LP (Einzel-LP/Nutzen, Anzahl, Lieferant, Sonstiges), Paste, Bauteile, US / Lasertrennung / Beist, Freitext

### Bauteilbeistellung
Beistellung in die Warenannahme gebracht – Info an Lager und Vertrieb.
- **Variante**: `Teil 1` (Zeroone) · `Teil 2` (Vernieten GCD) · `QUAL` · `EVM` · `Ohne`
- **Kunde**: aus dem Pfad vorbelegt, änderbar (z.B. TEXAS_INSTRUMENTS → TI, wird gemerkt)
- bei QUAL/EVM/Ohne: Beistellung von, Bestücken von, Spare-Hinweis, Freitext (rot)
- **Scan**: die letzten Scans vom Scanner (`mail.sender@gcd.de`) aus dem Posteingang – ansehen, richtigen wählen; oder PDF hineinziehen
- **nach dem Senden**: Scan nach `Aktuell\BGR\Bestellung_…_TTMMJJ.pdf`; bei QUAL/EVM/Ohne Eintrag oben in die README im BGR-Ordner (`MM-TT-JJ / Kürzel`)

Projektordner: es wird immer `<nr>.01` verwendet, sonst der Ordner ohne Index.

Vor dem Senden zeigt das Tool, was danach automatisch passiert (abwählbar). Die Vorschau rechts kann direkt bearbeitet werden.

## Neue Vorlage hinzufügen (für Entwickler)
1. `vertrieb_tool/templates/meine_vorlage.py` anlegen, Klasse von `Vorlage` ableiten (siehe `templates/base.py`)
2. `build()` (Formular), `betreff()`, `absaetze()` (Mailtext), optional `pruefen()`, `aktionen()`, `settings_page()`
3. in `vertrieb_tool/templates/__init__.py` in `VORLAGEN` eintragen

Aufbau: `core.py` (Konfiguration) · `projekt.py` (Ordner, BGR, README) · `mail.py` (SMTP/IMAP, Scans) · `system.py` (Updates, Verknüpfung) · `ui/` (Fenster, Dialoge, Widgets, Design) · `templates/` (Vorlagen)

## Installation (Windows) – neue PCs
**`Email_tool_setup.bat`** herunterladen und doppelklicken (Admin-Rechte werden abgefragt). Mehr braucht es nicht –
die .bat holt sich den Rest selbst von GitHub. Das Setup:

1. installiert bei Bedarf **Python** und **Git** (per winget, sonst Direkt-Download)
2. holt das Tool nach **`C:\vertrieb_email_tool`**
3. gibt normalen Benutzern Schreibrechte dort (für Einstellungen und Updates)
4. installiert die Pakete (PyQt6, keyring)
5. legt **„Vertrieb Email Tool“** mit Icon auf den Desktop und ins Startmenü – für alle Benutzer des PCs
6. startet das Tool einmal

Danach im Tool unter **Einstellungen** Absender-Adresse, Benutzername und Passwort eintragen.

Erneut ausführen ist unbedenklich: es aktualisiert die vorhandene Installation, `config.json` bleibt erhalten.

**Danach läuft alles über das Tool** – unter **Einstellungen → System**:
- **Nach Updates suchen** → zeigt die Änderungen, **Jetzt aktualisieren** installiert sie und startet neu
- **Desktop-Verknüpfung** erstellen bzw. reparieren

Keine Admin-Rechte nötig, keine Dateien anfassen.

Als eigenständige `.exe` (Rechner ohne Python): `build_exe.bat` → `dist\VertriebEmailTool.exe`.

## Einstellungen
Beim **ersten Start** (bzw. solange etwas fehlt) öffnet sich ein kurzes **Willkommen-Fenster**: Name (für den Gruß), Kürzel (für README-Einträge), Email-Adresse, Benutzername und Passwort – mit Verbindungstest. Es ist keine Person voreingestellt.

Beim ersten Mal unter **Einstellungen…** eintragen:
- Empfänger, Anrede und Shortcut-Buttons je Vorlage im jeweiligen Tab (mehrere Adressen mit `;` trennen)
- Postfach: Gesendet-Ordner und Scanner-Absender für die Scans
- SMTP ist vorbelegt: `mail.gcd.de`, Port `587`, STARTTLS
- Passwort wird über `keyring` im Windows-Anmeldeinformationsspeicher abgelegt – nicht im Klartext

**Gesendet-Ordner:** Nach dem Versand legt das Tool per IMAP (`mail.gcd.de:993`, gleiche Zugangsdaten) eine Kopie in deinen Gesendet-Ordner. Der Ordner wird automatisch erkannt; unter **Einstellungen → Gesendet-Ordner** kann man ihn testen, fest eintragen oder die Funktion abschalten.

Die Einstellungen landen in `config.json` neben dem Programm (nicht im Git).
Shortcut-Buttons (Lieferant, Sonstiges, Freitext, Info-Text) legst du unter **Einstellungen → Textbausteine** an (ein Eintrag pro Zeile).

Die Mail wird als HTML (fett/rot) mit Nur-Text-Alternative verschickt.

Betreff (Platzhalter `{nr}`, `{firma}`, `{board}`; Standard: `PN{nr} / Baugruppendaten {firma} {board} / {nr} sind auf M`), Anrede und Gruß sind dort ebenfalls änderbar.
