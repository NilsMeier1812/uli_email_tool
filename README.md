# Uli Email Tool

Kleines PyQt6-Tool, um die immer gleiche Email „Baugruppendaten liegen auf …“ an den Vertrieb zu verschicken.

## Ablauf
1. Projektnummer eingeben (z.B. `21156`) → Enter / **Suchen**
2. Das Tool sucht im zweiten Unterordner von `M:\Projekte_ab_20000` nach `21156___…`
   und hängt `\21156.01\Aktuell` an, z.B.
   `M:\Projekte_ab_20000\FEINMETALL\21156___G0056D-V01-J7-00126-PV_1191274\21156.01\Aktuell`
   (bei mehreren Treffern erscheint eine Auswahl, der Pfad kann auch von Hand angepasst werden)
3. Optional **Entwickler** eintragen → steht im Betreff in Klammern hinter der Firma, z.B. `FEINMETALL (Müller)`
4. **Info** wählen: `PO` (Bestellung gemäß PO), `Ang` (Bestellung gemäß Angebot) oder `Text` (eigenes Textfeld)
5. **Achtung** ausfüllen – oder per Klick auf einen **Textbaustein-Button** einfügen.
   Jede Zeile bei Achtung wird in der Mail automatisch ein Aufzählungspunkt (`- `). Leeres Achtung-Feld → Abschnitt entfällt.
6. **Senden** – die Mail geht direkt über SMTP raus

## Installation (Windows)
```bat
pip install -r requirements.txt
```
Starten per Doppelklick auf `email_tool.pyw` oder `start.bat` – ohne Konsolenfenster, mit eigenem Icon in der Taskleiste.

Als eigenständige `.exe` (kein Python auf dem Zielrechner nötig): `build_exe.bat` ausführen → `dist\UliEmailTool.exe`.

## Einstellungen
Beim ersten Mal unter **Einstellungen…** eintragen:
- **Absender-Adresse** (Empfänger ist `vertrieb@gcd.de` vorbelegt, mehrere mit `;` trennen)
- SMTP ist vorbelegt: `mail.gcd.de`, Port `587`, STARTTLS, Benutzer `nimeier`
- Passwort wird über `keyring` im Windows-Anmeldeinformationsspeicher abgelegt – nicht im Klartext

Die Einstellungen landen in `config.json` neben dem Programm (nicht im Git).
Textbausteine für Info und Achtung legst du unter **Einstellungen → Textbausteine** an (ein Baustein pro Zeile).

Betreff (Platzhalter `{nr}`, `{firma}`, `{board}`; Standard: `PN{nr} / Baugruppendaten {firma} {board} / {nr} sind auf M`), Anrede und Gruß sind dort ebenfalls änderbar.
