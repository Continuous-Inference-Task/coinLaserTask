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
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)


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
        self.setMinimumWidth(400)

        self._widgets: dict[str, QLineEdit | QComboBox] = {}
        self._build_ui(title, fields)

    # ── layout ─────────────────────────────────────────────────────────────

    def _build_ui(self, title: str, fields: dict) -> None:
        root = QVBoxLayout(self)

        # ── Header ──
        lbl_title = QLabel(title)
        font = lbl_title.font()
        font.setPointSize(font.pointSize() + 4)
        font.setBold(True)
        lbl_title.setFont(font)
        root.addWidget(lbl_title)

        lbl_sub = QLabel("Complete all fields before starting the session.")
        root.addWidget(lbl_sub)
        root.addSpacing(8)

        # ── Form ──
        form = QFormLayout()
        form.setSpacing(6)

        for name, value in fields.items():
            lbl = QLabel(name.replace("_", " ").capitalize() + ":")

            if isinstance(value, list):
                widget: QLineEdit | QComboBox = QComboBox()
                for item in value:
                    widget.addItem(str(item))
                widget.setCurrentIndex(0)
            else:
                widget = QLineEdit(str(value))
                widget.setPlaceholderText("Enter value…")

            self._widgets[name] = widget
            form.addRow(lbl, widget)

        root.addLayout(form)
        root.addSpacing(8)

        # ── Buttons ──
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

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
    QApplication.instance() or QApplication([])

    # Auto-fill participant with next ID if data_root is given
    if data_root is not None and "participant" in fields:
        fields = dict(fields)  # don't mutate caller's dict
        fields["participant"] = _detect_next_participant(data_root)

    dlg = SessionDialog(fields, title=title)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        return dlg.get_values()
    return None
