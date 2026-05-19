"""
laserTask/dialog.py
-------------------
Pre-experiment session dialog built with PyQt6.

Replaces psychopy.gui.DlgFromDict to remove the wx / wxWidgets
dependency that caused ABI mismatches on Linux.

Returns a populated dict identical in shape to the one psychopy.gui
would have produced, so the rest of experiment.py is unaffected.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

# ── palette ────────────────────────────────────────────────────────────────
_BG       = "#11111b"   # window background
_CARD     = "#1e1e2e"   # form card background
_SURFACE  = "#313244"   # input background
_BORDER   = "#45475a"   # subtle border
_BORDER_FOCUS = "#89b4fa"
_ACCENT   = "#89b4fa"   # blue accent
_ACCENT_H = "#b4befe"   # hover
_TEXT     = "#cdd6f4"   # primary text
_SUBTEXT  = "#a6adc8"   # labels / hints
_PLACEHOLDER = "#7f849c"  # dropdown placeholder colour
_SUCCESS  = "#a6e3a1"
_ERROR    = "#f38ba8"

_STYLESHEET = f"""
/* ── window ── */
QDialog {{
    background-color: {_BG};
    color: {_TEXT};
}}

/* ── card frame ── */
QFrame#card {{
    background-color: {_CARD};
    border-radius: 10px;
    border: 1px solid {_BORDER};
}}

/* ── labels ── */
QLabel {{
    color: {_TEXT};
    font-size: 13px;
    background: transparent;
}}
QLabel#title {{
    font-size: 20px;
    font-weight: 700;
    color: {_TEXT};
    letter-spacing: 0.3px;
}}
QLabel#subtitle {{
    font-size: 12px;
    color: {_SUBTEXT};
}}
QLabel#field_label {{
    font-size: 12px;
    font-weight: 600;
    color: {_SUBTEXT};
    min-width: 90px;
}}
QLabel#hint {{
    font-size: 11px;
    color: {_PLACEHOLDER};
    font-style: italic;
}}

/* ── text input ── */
QLineEdit {{
    background-color: {_SURFACE};
    color: {_TEXT};
    border: 1.5px solid {_BORDER};
    border-radius: 7px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: {_ACCENT};
}}
QLineEdit:focus {{
    border-color: {_BORDER_FOCUS};
    background-color: #2a2d45;
}}

/* ── dropdown ── */
QComboBox {{
    background-color: {_SURFACE};
    color: {_TEXT};
    border: 1.5px solid {_BORDER};
    border-radius: 7px;
    padding: 8px 12px;
    font-size: 13px;
    min-width: 220px;
}}
QComboBox:focus {{
    border-color: {_BORDER_FOCUS};
    background-color: #3b3c50;
}}
/* popup list */
QComboBox QAbstractItemView {{
    background-color: {_SURFACE};
    color: {_TEXT};
    border: 1.5px solid {_BORDER_FOCUS};
    border-radius: 7px;
    padding: 4px;
    outline: 0;
    selection-background-color: {_ACCENT};
    selection-color: white;
    show-decoration-selected: 1;
}}
QComboBox QAbstractItemView::item {{
    padding: 7px 12px;
    border-radius: 4px;
    min-height: 26px;
}}
QComboBox QAbstractItemView::item:selected {{
    background-color: {_ACCENT};
    color: white;
}}

/* ── separator ── */
QFrame#sep {{
    background-color: {_BORDER};
    max-height: 1px;
}}

/* ── buttons ── */
QDialogButtonBox QPushButton {{
    background-color: {_ACCENT};
    color: white;
    border: none;
    border-radius: 7px;
    padding: 9px 28px;
    font-size: 13px;
    font-weight: 600;
    min-width: 100px;
}}
QDialogButtonBox QPushButton:hover  {{ background-color: {_ACCENT_H}; }}
QDialogButtonBox QPushButton:pressed {{ background-color: #6c5ce7; }}
QDialogButtonBox QPushButton[text="Cancel"] {{
    background-color: transparent;
    color: {_SUBTEXT};
    border: 1.5px solid {_BORDER};
}}
QDialogButtonBox QPushButton[text="Cancel"]:hover {{
    color: {_TEXT};
    border-color: {_BORDER_FOCUS};
    background-color: {_SURFACE};
}}

/* ── error message box ── */
QMessageBox {{
    background-color: {_CARD};
    color: {_TEXT};
}}
QMessageBox QLabel {{ color: {_TEXT}; font-size: 13px; }}
QMessageBox QPushButton {{
    background-color: {_ACCENT};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 6px 20px;
    font-size: 13px;
}}
"""


# ── participant ID helpers ─────────────────────────────────────────────────

def _detect_next_participant(data_root: Path) -> str:
    """
    Scan *data_root* for files matching ``{id}_laserTask_*`` and return
    the next sequential participant ID (zero-padded to 3 digits).

    Falls back to ``"001"`` if no files are found or the directory
    does not exist.
    """
    if not data_root.is_dir():
        return "001"

    seen: set[int] = set()
    pattern = re.compile(r"^(\d+)_laserTask_")
    for f in data_root.iterdir():
        m = pattern.match(f.name)
        if m:
            seen.add(int(m.group(1)))

    if not seen:
        return "001"
    return str(max(seen) + 1).zfill(3)


# ── dialog class ───────────────────────────────────────────────────────────

class SessionDialog(QDialog):
    """
    Pre-experiment dialog that collects session metadata.

    Parameters
    ----------
    fields : dict
        Keys are field names; values are either a str (free-text) or a
        list (dropdown — first item is the placeholder).
    title : str
        Window title and header text.
    """

    def __init__(
        self,
        fields: dict,
        title: str = "Session Setup",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setStyleSheet(_STYLESHEET)

        self._fields = fields
        self._widgets: dict[str, QLineEdit | QComboBox] = {}
        self._build_ui(title)

    # ── layout ─────────────────────────────────────────────────────────────

    def _build_ui(self, title: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(12)

        # ── Header ──
        hdr = QVBoxLayout()
        hdr.setSpacing(3)
        lbl_title = QLabel(title)
        lbl_title.setObjectName("title")
        lbl_sub = QLabel("Complete all fields before starting the session.")
        lbl_sub.setObjectName("subtitle")
        hdr.addWidget(lbl_title)
        hdr.addWidget(lbl_sub)
        root.addLayout(hdr)

        # ── Card ──
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)
        form.setHorizontalSpacing(16)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        for name, value in self._fields.items():
            lbl = QLabel(name.replace("_", " ").capitalize() + ":")
            lbl.setObjectName("field_label")

            if isinstance(value, list):
                widget: QLineEdit | QComboBox = QComboBox()
                for item in value:
                    widget.addItem(str(item))
                widget.setCurrentIndex(0)
                # Grey out the placeholder item visually
                widget.model().item(0).setForeground(QColor(_PLACEHOLDER))
            else:
                widget = QLineEdit(str(value))
                widget.setPlaceholderText("Enter value…")

            self._widgets[name] = widget
            form.addRow(lbl, widget)

        card_layout.addLayout(form)
        root.addWidget(card)

        # ── Buttons ──
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(buttons)
        root.addLayout(btn_row)

    # ── validation ─────────────────────────────────────────────────────────

    def _on_accept(self) -> None:
        errors = []
        for name, widget in self._widgets.items():
            if isinstance(widget, QComboBox):
                if widget.currentText().startswith("-- select"):
                    errors.append(f"  • {name.replace('_', ' ').capitalize()}")
            elif isinstance(widget, QLineEdit):
                if not widget.text().strip():
                    errors.append(f"  • {name.replace('_', ' ').capitalize()}")
        if errors:
            msg = QMessageBox(self)
            msg.setWindowTitle("Incomplete")
            msg.setText("Please complete the following fields:\n" + "\n".join(errors))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setStyleSheet(self.styleSheet())
            msg.exec()
            return
        self.accept()

    # ── result ─────────────────────────────────────────────────────────────

    def get_values(self) -> dict:
        result = {}
        for name, widget in self._widgets.items():
            if isinstance(widget, QComboBox):
                result[name] = widget.currentText()
            else:
                result[name] = widget.text().strip()
        return result


# ── public helper ──────────────────────────────────────────────────────────

def show_session_dialog(
    fields: dict,
    title: str = "Session Setup",
    data_root: Optional[Path] = None,
) -> Optional[dict]:
    """
    Show the session setup dialog and return the filled-in values.

    Parameters
    ----------
    fields : dict
        Same format as psychopy.gui.DlgFromDict — keys are field names,
        values are either a str (free text) or list (dropdown).
    title : str
        Window title.
    data_root : Path, optional
        Path to the data directory.  If provided, the last participant
        number is auto-detected and the ``participant`` field is
        pre-filled with ``last + 1``.

    Returns
    -------
    dict
        Populated field values, or None if the user cancelled.
    """
    app = QApplication.instance() or QApplication([])

    # Force Fusion so the system GTK/KDE theme doesn't override our styles
    app.setStyle("Fusion")

    # Dark palette covers areas stylesheets can't reach (e.g. scrollbars,
    # combo popup shadow on some compositors)
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(_BG))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(_TEXT))
    pal.setColor(QPalette.ColorRole.Base,            QColor(_SURFACE))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(_BG))
    pal.setColor(QPalette.ColorRole.Text,            QColor(_TEXT))
    pal.setColor(QPalette.ColorRole.Button,          QColor(_SURFACE))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(_TEXT))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(_ACCENT))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    pal.setColor(QPalette.ColorRole.ToolTipBase,     QColor(_SURFACE))
    pal.setColor(QPalette.ColorRole.ToolTipText,     QColor(_TEXT))
    app.setPalette(pal)

    # Auto-fill participant with next ID if data_root is given
    if data_root is not None and "participant" in fields:
        fields = dict(fields)  # don't mutate caller's dict
        fields["participant"] = _detect_next_participant(data_root)

    dlg = SessionDialog(fields, title=title)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        return dlg.get_values()
    return None
