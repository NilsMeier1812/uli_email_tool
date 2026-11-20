# Vertrieb Email Tool

Kleines PyQt6-Tool, um die immer gleiche Email „Baugruppendaten liegen auf …“ an den Vertrieb zu verschicken.

## Ablauf
1. Projektnummer eingeben (z.B. `21156`) → Enter / **Suchen**
2. Das Tool sucht im zweiten Unterordner von `M:\Projekte_ab_20000` nach `21156___…`
   und hängt `\21156.01\Aktuell` an, z.B.
   `M:\Projekte_ab_20000\FEINMETALL\21156___G0056D-V01-J7-00126-PV_1191274\21156.01\Aktuell`
   (bei mehreren Treffern erscheint eine Auswahl, der Pfad kann auch von Hand angepasst werden)
3. Optional **Entwickler** eintragen → steht im Betreff in Klammern hinter der Firma, z.B. `FEINMETALL (Müller)`
4. **Info**: `PO` / `Ang` (abwählbar) und ein Textfeld:
   - PO + Text → „Bestellung: **gemäß PO**, Text“ · nur PO → „Bestellung: **gemäß PO**“ · nur Text → „Bestellung: Text“
   - optional **Liefertermin** (in der Mail rot und fett)
5. **Achtung** – wird in der Mail zur Aufzählung:
   - **LP**: Einzel-LP / Nutzen, Anzahl (zwei Felder, z.B. `10` + `5er mit Rand`), Lieferant (mit Shortcut-Buttons Fima, KC, Piu, Zeroone), Sonstiges (z.B. „Daten sind bei Hersteller“)
   - **Paste**: von M / Hersteller / Keine
   - **Bauteile**: Freitext (Shortcut „BOM“)
   - Schalter **US** (US Reinigung), **Lasertrennung**, **Beist** (Beistellung, mit Textfeld → `Beistellung -> ...`) – je ein eigener Punkt
   - **Freitext**: jede Zeile ein eigener Punkt

   Ergebnis z.B.:
   ```
   - LP -> Nutzen, Anzahl: 10, 5er mit Rand, Lieferant: KC, Daten sind bei Hersteller
   - Paste -> von M
   - Bauteile -> ...
   - ...
   ```
6. Bei Bedarf direkt in der **Vorschau** nachbessern (dann werden Feldänderungen nicht mehr übernommen, „Neu aus Feldern“ setzt zurück)
7. **Senden** – die Mail geht direkt über SMTP raus

## Installation (Windows) – neue PCs
**`setup.bat`** herunterladen und doppelklicken (Admin-Rechte werden abgefragt). Mehr braucht es nicht –
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
Beim **ersten Start** (bzw. solange etwas fehlt) öffnet sich ein kurzes **Willkommen-Fenster**: Name (für den Gruß), Email-Adresse, Benutzername und Passwort – mit Verbindungstest. Es ist keine Person voreingestellt.

Beim ersten Mal unter **Einstellungen…** eintragen:
- **Absender-Adresse** (Empfänger ist `vertrieb@gcd.de` vorbelegt, mehrere mit `;` trennen)
- SMTP ist vorbelegt: `mail.gcd.de`, Port `587`, STARTTLS
- Passwort wird über `keyring` im Windows-Anmeldeinformationsspeicher abgelegt – nicht im Klartext

**Gesendet-Ordner:** Nach dem Versand legt das Tool per IMAP (`mail.gcd.de:993`, gleiche Zugangsdaten) eine Kopie in deinen Gesendet-Ordner. Der Ordner wird automatisch erkannt; unter **Einstellungen → Gesendet-Ordner** kann man ihn testen, fest eintragen oder die Funktion abschalten.

Die Einstellungen landen in `config.json` neben dem Programm (nicht im Git).
Shortcut-Buttons (Lieferant, Sonstiges, Freitext, Info-Text) legst du unter **Einstellungen → Textbausteine** an (ein Eintrag pro Zeile).

Die Mail wird als HTML (fett/rot) mit Nur-Text-Alternative verschickt.

Betreff (Platzhalter `{nr}`, `{firma}`, `{board}`; Standard: `PN{nr} / Baugruppendaten {firma} {board} / {nr} sind auf M`), Anrede und Gruß sind dort ebenfalls änderbar.
