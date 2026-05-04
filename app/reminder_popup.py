# app/reminder_popup.py
from PyQt5.QtWidgets import QFrame, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QPoint
from PyQt5.QtGui import QFont

class ReminderPopup(QFrame):
    def __init__(self, message_data, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 2px solid #e74c3c;
                border-radius: 10px;
            }
            QLabel {
                font-size: 14px;
                color: #333;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
            }
            #closeBtn {
                background: #e74c3c;
                color: white;
            }
            #closeBtn:hover {
                background: #c0392b;
            }
            #ignoreBtn {
                background: #ecf0f1;
                color: #333;
            }
            #ignoreBtn:hover {
                background: #bdc3c7;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(12)

        # 标题
        title = QLabel(f"🔔 提醒：{message_data.get('chat', '未知会话')}")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #e74c3c;")
        layout.addWidget(title)

        # 消息内容
        content_text = message_data.get('content', '')
        if len(content_text) > 150:
            content_text = content_text[:150] + "..."
        content = QLabel(content_text)
        content.setWordWrap(True)
        layout.addWidget(content)

        # 发送者和时间
        info = QLabel(f"来自：{message_data.get('sender', '未知')} | 时间：{message_data.get('time', '')}")
        info.setStyleSheet("font-size: 11px; color: #888;")
        layout.addWidget(info)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        ignore_btn = QPushButton("忽略")
        ignore_btn.setObjectName("ignoreBtn")
        ignore_btn.clicked.connect(self.close)
        btn_layout.addWidget(ignore_btn)

        close_btn = QPushButton("知道了")
        close_btn.setObjectName("closeBtn")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)
        self.setFixedSize(400, 220)

    def show_popup(self):
        """在屏幕右下角显示弹窗"""
        from PyQt5.QtWidgets import QDesktopWidget
        desktop = QDesktopWidget().availableGeometry()
        self.move(desktop.right() - self.width() - 20, desktop.bottom() - self.height() - 20)
        self.show()