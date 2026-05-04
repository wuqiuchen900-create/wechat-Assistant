# app/main_window.py
from PyQt5.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("微信信息管家")
        self.setMinimumSize(800, 600)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        label = QLabel("🚀 欢迎使用微信信息管家！\n主界面正在建设中...")
        label.setStyleSheet("font-size: 18px; padding: 20px;")
        layout.addWidget(label)
        
        # 后续可以在这里添加标签页：实时监控、历史检索、简报中心