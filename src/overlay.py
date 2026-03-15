"""
Floating prediction overlay. Always on top, keyboard-driven.
Appears at decision points, disappears after selection or timeout.
"""

import os
import sys

# Suppress Qt DPI warning on Windows
os.environ["QT_LOGGING_RULES"] = "qt.qpa.window=false"

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QFrame, QPushButton)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QShortcut, QKeySequence


class PredictionCard(QFrame):
    clicked = pyqtSignal(int)

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.key_label = QLabel(f"[{index}]")
        self.key_label.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        self.key_label.setStyleSheet("color: #4CAF50;")

        self.action_label = QLabel("")
        self.action_label.setFont(QFont("Segoe UI", 10))
        self.action_label.setWordWrap(True)

        self.conf_label = QLabel("")
        self.conf_label.setFont(QFont("Segoe UI", 9))
        self.conf_label.setStyleSheet("color: #888;")

        self.shortcut_label = QLabel("")
        self.shortcut_label.setFont(QFont("Consolas", 9))
        self.shortcut_label.setStyleSheet("color: #6BA4E8;")

        layout.addWidget(self.key_label)
        layout.addWidget(self.action_label, 1)
        layout.addWidget(self.shortcut_label)
        layout.addWidget(self.conf_label)

    def set_prediction(self, name: str, confidence: float, shortcut: str = "",
                       is_guidance: bool = False):
        if is_guidance:
            self.action_label.setText(f"Tip: {name}")
            self.action_label.setStyleSheet("color: #999; font-style: italic;")
            self.shortcut_label.setText("")
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.action_label.setText(name)
            self.action_label.setStyleSheet("color: #E0E0E0;")
            self.shortcut_label.setText(shortcut if shortcut else "")
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.conf_label.setText(f"{confidence:.0%}")
        self.show()

    def clear(self):
        self.action_label.setText("")
        self.conf_label.setText("")
        self.shortcut_label.setText("")
        self.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            print(f"[overlay] Card {self.index} clicked")
            self.clicked.emit(self.index)
            event.accept()  # Stop propagation to parent drag handler


class Overlay(QWidget):
    prediction_selected = pyqtSignal(int)
    dismiss_requested = pyqtSignal()
    manual_trigger = pyqtSignal()
    exit_requested = pyqtSignal()

    AUTO_HIDE_MS = 12000  # Hide after 12s of no interaction
    HAS_PREDICTIONS = False  # Track whether predictions are showing

    def __init__(self):
        super().__init__()
        self._drag_pos = None
        self._setup_window()
        self._build_ui()
        self._setup_shortcuts()

        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.timeout.connect(self._auto_hide)
        self._auto_hide_timer.setSingleShot(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def _setup_window(self):
        self.setWindowTitle("Understudy")
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(480)

    def _build_ui(self):
        container = QFrame(self)
        container.setStyleSheet("""
            QFrame {
                background-color: rgba(25, 25, 25, 235);
                border-radius: 10px;
                border: 1px solid #444;
            }
            QLabel { color: #E0E0E0; }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        # Header
        header = QHBoxLayout()
        self.app_label = QLabel("Understudy")
        self.app_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.status_label = QLabel("Observing...")
        self.status_label.setFont(QFont("Segoe UI", 8))
        self.status_label.setStyleSheet("color: #888;")

        exit_btn = QPushButton("X")
        exit_btn.setFixedSize(20, 20)
        exit_btn.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        exit_btn.setStyleSheet("""
            QPushButton {
                color: #888; background: transparent; border: none; border-radius: 3px;
            }
            QPushButton:hover {
                color: #ff5555; background: rgba(255,85,85,30);
            }
        """)
        exit_btn.clicked.connect(self.exit_requested.emit)

        header.addWidget(self.app_label)
        header.addStretch()
        header.addWidget(self.status_label)
        header.addWidget(exit_btn)
        layout.addLayout(header)

        # Predictions
        self.cards = []
        for i in range(1, 5):
            card = PredictionCard(i)
            card.clicked.connect(self._on_card_clicked)
            card.hide()
            self.cards.append(card)
            layout.addWidget(card)

        # Footer
        self.hint = QLabel("[1-4] Execute  [Esc] Dismiss  [Ctrl+Space] Ask now")
        self.hint.setFont(QFont("Consolas", 7))
        self.hint.setStyleSheet("color: #555;")
        layout.addWidget(self.hint)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)

    def _on_card_clicked(self, index: int):
        """Handle card click - emit signal and clear."""
        self.prediction_selected.emit(index)
        self.clear_predictions()

    def _setup_shortcuts(self):
        for i in range(1, 5):
            QShortcut(QKeySequence(str(i)), self).activated.connect(
                lambda x=i: self._on_card_clicked(x)
            )
        QShortcut(QKeySequence("Escape"), self).activated.connect(
            self.dismiss_requested.emit
        )

    def position_bottom_right(self):
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - self.width() - 20, screen.height() - 300)

    def show_predictions(self, workflows: list):
        """Show workflow suggestions. Each card is a multi-step workflow."""

        for i, card in enumerate(self.cards):
            if i < len(workflows):
                wf = workflows[i]
                card.set_prediction(
                    wf.workflow_name,
                    wf.confidence,
                    f"({len(wf.steps)} steps)"
                )
                card.setStyleSheet("background-color: rgba(76, 175, 80, 30); border-radius: 4px;")
            else:
                card.clear()

        self.hint.setText("[1-3] Run workflow  [Esc] Dismiss  [Ctrl+Space] Ask now")

        self.HAS_PREDICTIONS = True
        self.adjustSize()
        self.show()
        self._auto_hide_timer.start(self.AUTO_HIDE_MS)

    def clear_predictions(self):
        for card in self.cards:
            card.clear()
        self.HAS_PREDICTIONS = False
        self._auto_hide_timer.stop()

    def _auto_hide(self):
        self.clear_predictions()
        self.status_label.setText("Observing...")

    def set_app(self, name: str):
        self.app_label.setText(f"Understudy > {name}")

    def set_status(self, text: str):
        self.status_label.setText(text)


if __name__ == "__main__":
    from dataclasses import dataclass

    @dataclass
    class MockPred:
        action_name: str
        confidence: float
        execution_type: str
        execution_data: str
        reasoning: str = ""

    app = QApplication(sys.argv)
    overlay = Overlay()
    overlay.position_bottom_right()

    mock_preds = [
        MockPred("Feather Selection", 0.87, "shortcut", "Ctrl+Shift+F"),
        MockPred("Invert Selection", 0.74, "shortcut", "Ctrl+I"),
        MockPred("Delete Background", 0.61, "shortcut", "Delete"),
    ]
    overlay.show_predictions(mock_preds)
    overlay.show()

    sys.exit(app.exec())
