"""Keyboard shortcuts configuration for Parsonic."""

from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QWidget


# Default keyboard shortcuts
SHORTCUTS = {
    # File operations
    "new_project": "Ctrl+N",
    "open_project": "Ctrl+O",
    "save_project": "Ctrl+S",
    "save_as": "Ctrl+Shift+S",

    # Run operations
    "test_single": "F5",
    "run_scraper": "F6",
    "stop_scraper": "Escape",

    # Tab navigation
    "tab_target": "Ctrl+1",
    "tab_selectors": "Ctrl+2",
    "tab_auth": "Ctrl+3",
    "tab_results": "Ctrl+4",
    "tab_logs": "Ctrl+5",
    "next_tab": "Ctrl+Tab",
    "prev_tab": "Ctrl+Shift+Tab",

    # Selector builder
    "toggle_select_mode": "Ctrl+E",
    "test_selectors": "Ctrl+T",
    "validate_playwright": "Ctrl+Shift+V",

    # Results
    "export_csv": "Ctrl+Shift+C",
    "export_json": "Ctrl+Shift+J",
    "clear_results": "Ctrl+Shift+X",

    # General
    "focus_url": "Ctrl+L",
    "refresh": "F5",
    "help": "F1",
}


class ShortcutManager:
    """Manages keyboard shortcuts for the application."""

    def __init__(self, parent: QWidget):
        self.parent = parent
        self.shortcuts: dict[str, QShortcut] = {}
        self.callbacks: dict[str, callable] = {}

    def register(self, name: str, callback: callable, key_sequence: str = None):
        """Register a keyboard shortcut."""
        if key_sequence is None:
            key_sequence = SHORTCUTS.get(name)

        if key_sequence is None:
            return

        shortcut = QShortcut(QKeySequence(key_sequence), self.parent)
        shortcut.activated.connect(callback)

        self.shortcuts[name] = shortcut
        self.callbacks[name] = callback

    def unregister(self, name: str):
        """Unregister a keyboard shortcut."""
        if name in self.shortcuts:
            self.shortcuts[name].setEnabled(False)
            del self.shortcuts[name]
            del self.callbacks[name]

    def set_enabled(self, name: str, enabled: bool):
        """Enable or disable a shortcut."""
        if name in self.shortcuts:
            self.shortcuts[name].setEnabled(enabled)

    def get_key_sequence(self, name: str) -> str:
        """Get the key sequence for a shortcut."""
        if name in self.shortcuts:
            return self.shortcuts[name].key().toString()
        return SHORTCUTS.get(name, "")

    def update_key_sequence(self, name: str, key_sequence: str):
        """Update the key sequence for a shortcut."""
        if name in self.shortcuts:
            self.shortcuts[name].setKey(QKeySequence(key_sequence))


def setup_shortcuts(window) -> ShortcutManager:
    """Setup all keyboard shortcuts for the main window."""
    manager = ShortcutManager(window)

    # File operations
    manager.register("new_project", window._new_project)
    manager.register("open_project", window._open_project)
    manager.register("save_project", window._save_project)
    manager.register("save_as", window._save_project_as)

    # Run operations
    manager.register("test_single", window._run_test)
    manager.register("run_scraper", window._run_scraper)
    manager.register("stop_scraper", window._stop_scraper)

    # Tab navigation
    manager.register("tab_target", lambda: window.tabs.setCurrentIndex(0))
    manager.register("tab_selectors", lambda: window.tabs.setCurrentIndex(1))
    manager.register("tab_auth", lambda: window.tabs.setCurrentIndex(2))
    manager.register("tab_results", lambda: window.tabs.setCurrentIndex(3))
    manager.register("tab_logs", lambda: window.tabs.setCurrentIndex(4))

    def next_tab():
        current = window.tabs.currentIndex()
        window.tabs.setCurrentIndex((current + 1) % window.tabs.count())

    def prev_tab():
        current = window.tabs.currentIndex()
        window.tabs.setCurrentIndex((current - 1) % window.tabs.count())

    manager.register("next_tab", next_tab)
    manager.register("prev_tab", prev_tab)

    # Export shortcuts
    manager.register("export_csv", lambda: window._export("csv"))
    manager.register("export_json", lambda: window._export("json"))

    return manager
