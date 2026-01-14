#!/usr/bin/env python3
"""Parsonic - Web Scraper GUI

A powerful, open-source web scraper with visual selector builder.
"""

import sys
import asyncio

# Handle Qt platform plugin for headless environments
import os
if 'QT_QPA_PLATFORM' not in os.environ:
    os.environ['QT_QPA_PLATFORM'] = 'xcb'

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

try:
    import qasync
    HAS_QASYNC = True
except ImportError:
    HAS_QASYNC = False

from src.ui.main_window import MainWindow
from src.ui.theme import DARK_THEME


def main():
    """Application entry point."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)

    # Set application metadata
    app.setApplicationName("Parsonic")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Parsonic")

    # Apply dark theme
    app.setStyleSheet(DARK_THEME)

    # Set default font
    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    # Create main window
    window = MainWindow()
    window.show()

    # Run with qasync if available, otherwise standard event loop
    if HAS_QASYNC:
        loop = qasync.QEventLoop(app)
        asyncio.set_event_loop(loop)
        with loop:
            loop.run_forever()
    else:
        sys.exit(app.exec())


if __name__ == "__main__":
    main()
