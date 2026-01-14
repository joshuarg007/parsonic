"""Dark theme stylesheet for Parsonic."""

DARK_THEME = """
QMainWindow, QDialog, QWidget {
    background-color: #1e1e1e;
    color: #d4d4d4;
    font-family: 'Segoe UI', 'Ubuntu', sans-serif;
    font-size: 13px;
}

QTabWidget::pane {
    border: 1px solid #3c3c3c;
    background-color: #252526;
    border-radius: 4px;
}

QTabBar::tab {
    background-color: #2d2d2d;
    color: #969696;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background-color: #1e1e1e;
    color: #ffffff;
    border-bottom: 2px solid #007acc;
}

QTabBar::tab:hover:!selected {
    background-color: #383838;
}

QPushButton {
    background-color: #0e639c;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #1177bb;
}

QPushButton:pressed {
    background-color: #0d5a8c;
}

QPushButton:disabled {
    background-color: #3c3c3c;
    color: #6c6c6c;
}

QPushButton[secondary="true"] {
    background-color: #3c3c3c;
    color: #d4d4d4;
}

QPushButton[secondary="true"]:hover {
    background-color: #4a4a4a;
}

QPushButton[danger="true"] {
    background-color: #c42b1c;
}

QPushButton[danger="true"]:hover {
    background-color: #d64040;
}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #3c3c3c;
    border: 1px solid #4a4a4a;
    border-radius: 4px;
    padding: 6px 10px;
    color: #d4d4d4;
    selection-background-color: #264f78;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #007acc;
}

QLineEdit:disabled, QTextEdit:disabled {
    background-color: #2d2d2d;
    color: #6c6c6c;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #d4d4d4;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #3c3c3c;
    border: 1px solid #4a4a4a;
    selection-background-color: #094771;
    color: #d4d4d4;
}

QTableWidget, QTableView {
    background-color: #1e1e1e;
    alternate-background-color: #252526;
    gridline-color: #3c3c3c;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
}

QTableWidget::item, QTableView::item {
    padding: 6px;
}

QTableWidget::item:selected, QTableView::item:selected {
    background-color: #094771;
}

QHeaderView::section {
    background-color: #2d2d2d;
    color: #d4d4d4;
    padding: 8px;
    border: none;
    border-right: 1px solid #3c3c3c;
    border-bottom: 1px solid #3c3c3c;
    font-weight: 600;
}

QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 12px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #4a4a4a;
    min-height: 30px;
    border-radius: 6px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: #5a5a5a;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #1e1e1e;
    height: 12px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #4a4a4a;
    min-width: 30px;
    border-radius: 6px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #5a5a5a;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QGroupBox {
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 8px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 5px;
    color: #d4d4d4;
}

QCheckBox {
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 3px;
    border: 1px solid #4a4a4a;
    background-color: #3c3c3c;
}

QCheckBox::indicator:checked {
    background-color: #007acc;
    border-color: #007acc;
}

QCheckBox::indicator:hover {
    border-color: #007acc;
}

QLabel {
    color: #d4d4d4;
}

QLabel[heading="true"] {
    font-size: 16px;
    font-weight: 600;
    color: #ffffff;
}

QLabel[subheading="true"] {
    font-size: 12px;
    color: #969696;
}

QSplitter::handle {
    background-color: #3c3c3c;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QSplitter::handle:vertical {
    height: 2px;
}

QStatusBar {
    background-color: #007acc;
    color: white;
}

QMenuBar {
    background-color: #2d2d2d;
    color: #d4d4d4;
    padding: 2px;
}

QMenuBar::item:selected {
    background-color: #3c3c3c;
}

QMenu {
    background-color: #2d2d2d;
    border: 1px solid #3c3c3c;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px;
    border-radius: 2px;
}

QMenu::item:selected {
    background-color: #094771;
}

QMenu::separator {
    height: 1px;
    background-color: #3c3c3c;
    margin: 4px 8px;
}

QProgressBar {
    background-color: #3c3c3c;
    border-radius: 4px;
    text-align: center;
    color: white;
}

QProgressBar::chunk {
    background-color: #007acc;
    border-radius: 4px;
}

QToolTip {
    background-color: #2d2d2d;
    color: #d4d4d4;
    border: 1px solid #3c3c3c;
    padding: 4px;
}

/* Log Panel Styles */
QPlainTextEdit[logPanel="true"] {
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 12px;
    background-color: #1e1e1e;
    border: 1px solid #3c3c3c;
}
"""
