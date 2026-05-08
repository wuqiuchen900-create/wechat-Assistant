# app/styles.py

GLOBAL_STYLE = """
QMainWindow {
    background-color: #2b2b2b;
}

QFrame#sideNav {
    background-color: #333333;
    border-right: 1px solid #4a4a4a;
    min-width: 200px;
    max-width: 200px;
}

QPushButton#navBtn {
    text-align: left;
    padding: 12px 18px;
    border: none;
    border-radius: 10px;
    font-size: 13px;
    color: #b0b0b0;
    background: transparent;
    margin: 2px 4px;
}

QPushButton#navBtn:hover {
    background-color: #3d3d3d;
    color: #e0e0e0;
}

QPushButton#navBtn:checked {
    background-color: #3d4a5c;
    color: #5b9bd5;
    font-weight: 600;
}

QFrame#detailPanel {
    background: #333333;
    border-left: 1px solid #4a4a4a;
    padding: 24px;
}

QLabel#statusBar {
    background: #2d2d2d;
    border-top: 1px solid #4a4a4a;
    padding: 10px 20px;
    color: #888888;
    font-size: 12px;
}

QListWidget {
    border: none;
    background: transparent;
    outline: none;
}

QListWidget::item {
    padding: 10px 12px;
    border-bottom: 1px solid #3a3a3a;
    background: transparent;
}

QListWidget::item:hover {
    background-color: #383838;
}

QListWidget::item:selected {
    background-color: #3d4a5c;
    color: #5b9bd5;
}

QScrollBar:vertical {
    width: 8px;
    background: transparent;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #555555;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #666666;
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
    background: #4a4a4a;
    width: 1px;
    height: 1px;
}

QSplitter::handle:hover {
    background: #555555;
}

QFrame#statsPanel {
    background: #2d2d2d;
    border-top: 1px solid #4a4a4a;
    padding: 10px 20px;
}

QPlainTextEdit {
    border: none;
    background: transparent;
    font-size: 13px;
    color: #d0d0d0;
    selection-background-color: #3d4a5c;
}

QProgressBar {
    background-color: #3d3d3d;
    border: none;
    border-radius: 2px;
}

QProgressBar::chunk {
    background: transparent;
}
"""
