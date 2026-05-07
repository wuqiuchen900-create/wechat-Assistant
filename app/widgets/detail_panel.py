# app/widgets/detail_panel.py
from PyQt5.QtWidgets import (QFrame, QVBoxLayout, QLabel, QPlainTextEdit,
                             QHBoxLayout, QWidget)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt


class DetailPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("detailPanel")
        self.setMinimumWidth(300)
        self.setMaximumWidth(650)

        self.setStyleSheet("""
            #detailPanel {
                background: #ffffff;
                border-left: 1px solid #e5e7eb;
                border-radius: 0;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        self.title_label = QLabel("\U0001f4ac 消息详情")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: #111827;")
        layout.addWidget(self.title_label)

        self.meta_bar = QLabel("")
        self.meta_bar.setStyleSheet("color: #9ca3af; font-size: 11px;")
        self.meta_bar.setWordWrap(True)
        layout.addWidget(self.meta_bar)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background: #e5e7eb; max-height: 1px;")
        layout.addWidget(line)

        self.content_edit = QPlainTextEdit()
        self.content_edit.setReadOnly(True)
        self.content_edit.setStyleSheet("""
            QPlainTextEdit {
                border: none;
                background: transparent;
                font-size: 13px;
                color: #374151;
                line-height: 1.6;
            }
        """)
        self.content_edit.setPlaceholderText("点击左侧会话查看聊天记录...")
        layout.addWidget(self.content_edit)

    def show_session(self, data):
        chat = data.get('chat', '')
        msgs = data.get('messages', [])
        self.title_label.setText(f"\U0001f4ac {chat}")

        urgent_count = sum(1 for m in msgs if m.get('is_urgent'))
        work_count = sum(1 for m in msgs if m.get('is_work'))
        meta = f"共 {len(msgs)} 条消息"
        if urgent_count:
            meta += f"  |  \U0001f534 紧急 {urgent_count} 条"
        if work_count:
            meta += f"  |  \U0001f4cb 工作 {work_count} 条"
        self.meta_bar.setText(meta)

        text = ""
        for m in msgs[-80:]:
            time_str = m.get('time', '')
            sender = m.get('sender', '')
            content = m.get('content', '')
            prefix = ""
            if m.get('is_urgent'):
                prefix = "\U0001f534 "
            elif m.get('is_work'):
                prefix = "\U0001f4cb "
            line = f"{prefix}[{time_str}] {sender}: {content}"
            text += line + "\n"
        self.content_edit.setPlainText(text or "暂无消息")

    def clear(self):
        self.title_label.setText("\U0001f4ac 消息详情")
        self.meta_bar.setText("")
        self.content_edit.clear()
