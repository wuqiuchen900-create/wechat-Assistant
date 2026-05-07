# app/styles.py

GLOBAL_STYLE = """
QMainWindow {
    background-color: #f0f2f5;
}

QFrame#sideNav {
    background-color: #ffffff;
    border-right: 1px solid #e8eaed;
    min-width: 200px;
    max-width: 200px;
}

QPushButton#navBtn {
    text-align: left;
    padding: 12px 18px;
    border: none;
    border-radius: 10px;
    font-size: 13px;
    color: #5f6368;
    background: transparent;
    margin: 2px 4px;
}

QPushButton#navBtn:hover {
    background-color: #f1f3f4;
    color: #202124;
}

QPushButton#navBtn:checked {
    background-color: #e8f0fe;
    color: #1a73e8;
    font-weight: 600;
}

QFrame#detailPanel {
    background: #ffffff;
    border-left: 1px solid #e8eaed;
    padding: 24px;
}

QLabel#statusBar {
    background: #ffffff;
    border-top: 1px solid #e8eaed;
    padding: 10px 20px;
    color: #5f6368;
    font-size: 12px;
}

QListWidget {
    border: none;
    background: transparent;
    outline: none;
}

QListWidget::item {
    padding: 10px 12px;
    border-bottom: 1px solid #f1f3f4;
    background: transparent;
}

QListWidget::item:hover {
    background-color: #f8f9fa;
}

QListWidget::item:selected {
    background-color: #e8f0fe;
    color: #1a73e8;
}

QScrollBar:vertical {
    width: 8px;
    background: transparent;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #dadce0;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #bdc1c6;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
}

QSplitter::handle {
    background: #e8eaed;
    width: 1px;
    height: 1px;
}

QSplitter::handle:hover {
    background: #dadce0;
}

QFrame#statsPanel {
    background: #f8f9fa;
    border-top: 1px solid #e8eaed;
    padding: 10px 20px;
}

QPlainTextEdit {
    border: none;
    background: transparent;
    font-size: 13px;
    color: #202124;
    selection-background-color: #e8f0fe;
}

QProgressBar {
    background-color: #f1f3f4;
    border: none;
    border-radius: 2px;
}

QProgressBar::chunk {
    background: transparent;
}
"""
