"""Mail: senden (SMTP), Gesendet-Ordner und Scans aus dem Posteingang (IMAP)."""

from __future__ import annotations

import email
import email.policy
import imaplib
import re
import smtplib
import ssl
import time
from dataclasses import dataclass, field
from datetime import datetime
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parsedate_to_datetime
from pathlib import Path


def split_addresses(text: str) -> list[str]:
    return [a.strip() for a in text.replace(",", ";").split(";") if a.strip()]


def imap_connect(cfg: dict, password: str) -> imaplib.IMAP4_SSL:
    imap = imaplib.IMAP4_SSL(
        cfg["imap_server"], int(cfg["imap_port"]), ssl_context=ssl.create_default_context(), timeout=30
    )
    imap.login(cfg["smtp_user"], password)
    return imap


_LIST_RE = re.compile(rb'\((?P<flags>[^)]*)\) (?:"[^"]*"|NIL) (?P<name>.+)')


def find_sent_folder(imap: imaplib.IMAP4, wunsch: str = "") -> str:
    """Gesendet-Ordner finden: eingestellter Name, sonst \\Sent-Flag, sonst übliche Namen."""
    if wunsch:
        return wunsch
    typ, daten = imap.list()
    ordner: list[tuple[str, str]] = []
    for zeile in daten or []:
        if not isinstance(zeile, bytes):
            continue
        m = _LIST_RE.match(zeile)
        if not m:
            continue
        name = m.group("name").decode("utf-8", "replace").strip()
        if name.startswith('"') and name.endswith('"'):
            name = name[1:-1]
        ordner.append((m.group("flags").decode().lower(), name))
    for flags, name in ordner:
        if "\\sent" in flags:
            return name
    namen = {n.lower(): n for _, n in ordner}
    for kandidat in ("sent", "gesendet", "sent items", "gesendete objekte", "inbox.sent", "inbox/sent"):
        if kandidat in namen:
            return namen[kandidat]
    return "Sent"


def imap_quote(name: str) -> str:
    return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'


def save_to_sent(cfg: dict, password: str, msg: EmailMessage) -> str:
    """Legt die Mail im Gesendet-Ordner ab. Gibt den Ordnernamen zurück."""
    imap = imap_connect(cfg, password)
    try:
        ordner = find_sent_folder(imap, cfg.get("imap_ordner", "").strip())
        typ, daten = imap.append(
            imap_quote(ordner), "\\Seen", imaplib.Time2Internaldate(time.time()), msg.as_bytes()
        )
        if typ != "OK":
            raise RuntimeError(f"Server meldet: {daten}")
        return ordner
    finally:
        try:
            imap.logout()
        except Exception:
            pass


_SPAN_RE = re.compile(r'<span style="([^"]*)">(.*?)</span>', re.S | re.I)


def harden_html(html: str) -> str:
    """Farbe/Fett zusätzlich als <font color>/<b> schreiben.

    Viele Mailprogramme (z.B. Thunderbird "Vereinfachtes HTML", manche Webmailer)
    entfernen style-Attribute – die alten HTML-Tags bleiben dagegen erhalten.
    """

    def ersetze(m: re.Match) -> str:
        style, inhalt = m.group(1), m.group(2)
        farbe = re.search(r"(?<![-\w])color\s*:\s*(#[0-9a-fA-F]{3,6})", style)
        fett = re.search(r"font-weight\s*:\s*(bold|[6-9]00)", style)
        if fett:
            inhalt = f"<b>{inhalt}</b>"
        if farbe:
            inhalt = f'<font color="{farbe.group(1)}">{inhalt}</font>'
        return f'<span style="{style}">{inhalt}</span>'

    return _SPAN_RE.sub(ersetze, html)


def send_mail(cfg: dict, password: str, to: list[str], cc: list[str], subject: str,
              body: str, html: str | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = cfg["absender"]
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg.set_content(body)
    if html:
        html = harden_html(html)
        if not html.lstrip().lower().startswith(("<!doctype", "<html")):
            html = f"<html><body>{html}</body></html>"
        msg.add_alternative(html, subtype="html")

    ctx = ssl.create_default_context()
    host, port, sec = cfg["smtp_server"], int(cfg["smtp_port"]), cfg["smtp_security"]
    if sec == "SSL/TLS":
        server = smtplib.SMTP_SSL(host, port, context=ctx, timeout=30)
    else:
        server = smtplib.SMTP(host, port, timeout=30)
    with server:
        server.ehlo()
        if sec == "STARTTLS":
            server.starttls(context=ctx)
            server.ehlo()
        if cfg["smtp_user"]:
            server.login(cfg["smtp_user"], password)
        server.send_message(msg)
    return msg




def smtp_test(v: dict, password: str):
    """Verbindung + Anmeldung testen; wirft eine Exception bei Fehler."""
    ctx = ssl.create_default_context()
    if v["smtp_security"] == "SSL/TLS":
        s = smtplib.SMTP_SSL(v["smtp_server"], int(v["smtp_port"]), context=ctx, timeout=15)
    else:
        s = smtplib.SMTP(v["smtp_server"], int(v["smtp_port"]), timeout=15)
    with s:
        s.ehlo()
        if v["smtp_security"] == "STARTTLS":
            s.starttls(context=ctx)
            s.ehlo()
        if v["smtp_user"]:
            s.login(v["smtp_user"], password)


class SendError(Exception):
    """Senden fehlgeschlagen (verständliche Meldung)."""


def send_and_file(cfg: dict, password: str, to: list[str], cc: list[str], subject: str,
                  body: str, html: str | None) -> str:
    """Senden und Kopie in den Gesendet-Ordner legen.

    Gibt einen Hinweis zurück (leer = alles ok). Wirft SendError, wenn das Senden scheitert.
    """
    try:
        msg = send_mail(cfg, password, to, cc, subject, body, html)
    except smtplib.SMTPAuthenticationError:
        raise SendError("Anmeldung fehlgeschlagen – Benutzername oder Passwort falsch.")
    except Exception as exc:
        raise SendError(f"{type(exc).__name__}: {exc}")
    if not cfg.get("imap_aktiv"):
        return ""
    try:
        save_to_sent(cfg, password, msg)
        return ""
    except Exception as exc:
        return ("Die Email wurde versendet, konnte aber nicht im Gesendet-Ordner "
                f"abgelegt werden:\n{type(exc).__name__}: {exc}")


# ----- Scans aus dem Posteingang ----------------------------------------------
@dataclass
class Scan:
    """Ein Scan-PDF – aus einer Mail des Scanners oder als Datei hineingezogen."""

    name: str
    datum: datetime
    daten: bytes = field(repr=False, default=b"")
    pfad: Path | None = None  # bei Dateien von der Festplatte

    @property
    def groesse(self) -> int:
        if self.pfad is not None:
            try:
                return self.pfad.stat().st_size
            except OSError:
                return 0
        return len(self.daten)

    def lesen(self) -> bytes:
        return self.pfad.read_bytes() if self.pfad is not None else self.daten

    @classmethod
    def aus_datei(cls, pfad: Path) -> "Scan":
        return cls(pfad.name, datetime.fromtimestamp(pfad.stat().st_mtime), pfad=pfad)


def fetch_scans(cfg: dict, password: str) -> list[Scan]:
    """Die neuesten Scan-PDFs (Mails vom Scanner-Absender) holen, neueste zuerst.

    Die Mails werden nur gelesen, nicht als gelesen markiert oder verändert.
    """
    anzahl = max(1, int(cfg.get("scan_anzahl", 5)))
    absender = cfg.get("scan_absender", "").strip()
    if not absender:
        raise RuntimeError("Kein Scanner-Absender eingestellt (Einstellungen → Postfach).")
    imap = imap_connect(cfg, password)
    try:
        ordner = cfg.get("scan_ordner", "").strip() or "INBOX"
        typ, _ = imap.select(imap_quote(ordner), readonly=True)
        if typ != "OK":
            raise RuntimeError(f"Postfach-Ordner „{ordner}“ nicht gefunden.")
        typ, daten = imap.uid("SEARCH", None, "FROM", imap_quote(absender))
        if typ != "OK":
            raise RuntimeError("Suche im Postfach fehlgeschlagen.")
        uids = (daten[0] or b"").split()
        scans: list[Scan] = []
        for uid in reversed(uids[-anzahl * 2:]):  # neueste Mails zuerst
            typ, teile = imap.uid("FETCH", uid, "(BODY.PEEK[])")
            roh = next((t[1] for t in teile or [] if isinstance(t, tuple)), None)
            if typ != "OK" or not roh:
                continue
            msg = email.message_from_bytes(roh, policy=email.policy.default)
            try:
                datum = parsedate_to_datetime(msg["Date"]).astimezone().replace(tzinfo=None)
            except Exception:
                datum = datetime.now()
            for anhang in msg.iter_attachments():
                name = anhang.get_filename() or ""
                if name.lower().endswith(".pdf") or anhang.get_content_type() == "application/pdf":
                    inhalt = anhang.get_payload(decode=True) or b""
                    scans.append(Scan(name or "scan.pdf", datum, inhalt))
            if len(scans) >= anzahl:
                break
        scans.sort(key=lambda s: s.datum, reverse=True)
        return scans[:anzahl]
    finally:
        try:
            imap.logout()
        except Exception:
            pass
