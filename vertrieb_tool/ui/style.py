"""Design: Farben, Stylesheet, Icons und kleine Label-Helfer."""

from __future__ import annotations

from PyQt6.QtCore import QByteArray, QRectF, QSize, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QLabel, QPushButton


ACCENT = "#2563eb"

STYLESHEET = """
* { font-family: "Segoe UI", "Segoe UI Variable", "Inter", sans-serif; font-size: 10pt; }
QMainWindow, QDialog { background: #f3f5f9; }
QWidget { color: #1f2937; }

/* Karten */
QGroupBox {
    background: #ffffff;
    border: 1px solid #e3e7ee;
    border-radius: 12px;
    margin-top: 22px;
    padding: 8px 14px 8px 14px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 6px;
    top: 2px;
    padding: 0 4px;
    color: #64748b;
    font-size: 9pt;
    font-weight: 600;
    letter-spacing: 1px;
}

QLabel { background: transparent; }
QLabel[role="section"] { color: #0f172a; font-weight: 600; }
QLabel[role="field"] { color: #64748b; }

/* Eingabefelder */
QLineEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background: #f8fafc;
    border: 1px solid #d7dde6;
    border-radius: 8px;
    padding: 5px 8px;
    selection-background-color: #bfdbfe;
    selection-color: #0f172a;
}
QLineEdit:hover, QPlainTextEdit:hover, QSpinBox:hover, QComboBox:hover { border-color: #b6c0ce; }
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid ACCENT;
    background: #ffffff;
}
QLineEdit[role="termin"] { color: #dc2626; font-weight: 700; }
QTabWidget::pane { background: #ffffff; border: 1px solid #e3e7ee; border-radius: 12px; top: -1px; }
QTabBar::tab {
    background: transparent; color: #64748b; padding: 8px 16px; margin-right: 4px;
    border: none; border-bottom: 2px solid transparent;
}
QTabBar::tab:selected { color: ACCENT; border-bottom: 2px solid ACCENT; font-weight: 600; }
QTabBar::tab:hover { color: #1f2937; }

/* Buttons */
QPushButton {
    background: #ffffff;
    border: 1px solid #d7dde6;
    border-radius: 8px;
    padding: 6px 14px;
    color: #1f2937;
}
QPushButton:hover { background: #f1f5f9; border-color: #b6c0ce; }
QPushButton:pressed { background: #e2e8f0; }
QPushButton:disabled { color: #94a3b8; background: #f1f5f9; }

QPushButton[role="primary"] {
    background: ACCENT; border: 1px solid ACCENT; color: #ffffff; font-weight: 600;
    padding: 8px 26px;
}
QPushButton[role="primary"]:hover { background: #1d4ed8; }
QPushButton[role="primary"]:pressed { background: #1e40af; }
QPushButton[role="primary"]:disabled { background: #93c5fd; border-color: #93c5fd; }

QPushButton[role="ghost"] { background: transparent; border: 1px solid transparent; color: #475569; }
QPushButton[role="ghost"]:hover { background: #e8edf4; }

/* Schalter (Pills) */
QPushButton[role="toggle"] {
    border-radius: 11px;
    padding: 4px 16px;
    background: #f1f5f9;
    border: 1px solid #e2e8f0;
    color: #334155;
}
QPushButton[role="toggle"]:hover { background: #e2e8f0; }
QPushButton[role="toggle"]:checked {
    background: ACCENT; border-color: ACCENT; color: #ffffff; font-weight: 600;
}

/* Shortcut-Chips */
QPushButton[role="chip"] {
    border-radius: 10px;
    padding: 3px 12px;
    background: #ffffff;
    border: 1px dashed #b6c0ce;
    color: #475569;
    font-size: 9pt;
}
QPushButton[role="chip"]:hover { border: 1px solid ACCENT; color: ACCENT; background: #f8fafc; }
QPushButton[role="chip"]:pressed { background: #e2e8f0; }

/* Vorschau */
QScrollArea#leftScroll, QWidget#leftInner { background: transparent; border: none; }
QWidget#editbar { background: #eff6ff; border: 1px solid #dbeafe; border-radius: 8px; }
QWidget#editbar QLabel { color: #1e40af; font-size: 9pt; }
QWidget#editbar QPushButton { color: ACCENT; font-weight: 600; }
QWidget#editbar QPushButton:hover { background: #dbeafe; }
QTextEdit#preview {
    background: #ffffff;
    border: none;
    padding: 18px 20px;
}

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #94a3b8; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QToolTip { background: #0f172a; color: #ffffff; border: none; padding: 4px 8px; border-radius: 4px; }

/* Vorlagen-Umschalter oben */
QPushButton[role="tab"] {
    border: none; border-radius: 9px; padding: 8px 18px;
    background: transparent; color: #475569; font-weight: 600;
}
QPushButton[role="tab"]:hover { background: #e8edf4; }
QPushButton[role="tab"]:checked { background: #ffffff; color: ACCENT; border: 1px solid #dbe3ee; }
QWidget#tabbar { background: #e9eef5; border-radius: 12px; }

/* Scan-Auswahl */
QFrame#scanrow { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; }
QFrame#scanrow[selected="true"] { background: #eff6ff; border: 1px solid ACCENT; }
QFrame#dropzone { background: #f8fafc; border: 1px dashed #b6c0ce; border-radius: 8px; }
QFrame#dropzone[hover="true"] { background: #eff6ff; border: 1px dashed ACCENT; }
QLabel[role="hint"] { color: #94a3b8; font-size: 9pt; }
QCheckBox { spacing: 8px; }
""".replace("ACCENT", ACCENT)


LABEL_W = 92


def fixed_label(text: str) -> QLabel:
    lbl = field_label(text)
    lbl.setFixedWidth(LABEL_W)
    return lbl


# Linien-Icons (Stil angelehnt an Lucide, 24x24, nur Kontur)
ICON_PATHS = {
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "copy": '<rect x="8" y="8" width="13" height="13" rx="2"/>'
            '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    "send": '<path d="M22 2 11 13"/><path d="m22 2-7 20-4-9-9-4Z"/>',
    "reset": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    "settings": '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0'
                'l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51'
                'a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08'
                'a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18'
                'a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39'
                'a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09'
                'a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25'
                'a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
    "pencil": '<path d="M21.17 6.81a1 1 0 0 0-3.98-3.98L3.84 16.17a2 2 0 0 0-.5.83l-1.32 4.35'
              'a.5.5 0 0 0 .62.62l4.35-1.32a2 2 0 0 0 .83-.5z"/><path d="m15 5 4 4"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/>'
                '<path d="M12 15V3"/>',
    "monitor": '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>',
    "file": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/>'
            '<path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
    "eye": '<path d="M2.06 12.35a1 1 0 0 1 0-.7 10.75 10.75 0 0 1 19.88 0 1 1 0 0 1 0 .7'
           ' 10.75 10.75 0 0 1-19.88 0"/><circle cx="12" cy="12" r="3"/>',
    "refresh": '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>'
               '<path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/>'
              '<path d="M12 3v12"/>',
    "plus": '<path d="M12 5v14"/><path d="M5 12h14"/>',
    "plug": '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/>'
            '<path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
    "folder": '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9'
              'A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
}


def icon(name: str, color: str = "#475569", size: int = 16, stroke: float = 2.0) -> QIcon:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">'
        f"{ICON_PATHS[name]}</svg>"
    )
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    scale = 3  # scharf auf hochauflösenden Bildschirmen
    pix = QPixmap(size * scale, size * scale)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    renderer.render(painter, QRectF(0, 0, size * scale, size * scale))
    painter.end()
    pix.setDevicePixelRatio(scale)
    return QIcon(pix)


def with_icon(btn: QPushButton, name: str, color: str = "#475569", size: int = 16) -> QPushButton:
    btn.setIcon(icon(name, color, size))
    btn.setIconSize(QSize(size, size))
    return btn


def set_role(widget, role: str):
    widget.setProperty("role", role)
    return widget


def field_label(text: str) -> QLabel:
    return set_role(QLabel(text), "field")


def bold_label(text: str) -> QLabel:
    return set_role(QLabel(text), "section")


def hint_label(text: str) -> QLabel:
    lbl = set_role(QLabel(text), "hint")
    lbl.setWordWrap(True)
    return lbl
