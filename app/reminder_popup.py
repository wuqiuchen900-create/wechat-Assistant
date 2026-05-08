# app/reminder_popup.py
from PyQt5.QtWidgets import (QFrame, QVBoxLayout, QLabel, QPushButton,
                             QHBoxLayout, QWidget)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont

PRIORITY_COLORS = {5: "#ef4444", 4: "#f97316", 3: "#f59e0b", 2: "#3b82f6", 1: "#6b7280", 0: "#9ca3af"}
PRIORITY_LABELS = {5: "\U0001f534 紧急", 4: "\U0001f7e0 高优先", 3: "\U0001f7e1 重要", 2: "\U0001f535 普通", 1: "\u26aa 低优先", 0: "\u26ab 信息"}

SNOOZE_OPTIONS = [
    ("10分钟", 10),
    ("30分钟", 30),
    ("1小时", 60),
    ("3小时", 180),
    ("1天后", 1440),
]


class ReminderPopup(QFrame):
    acknowledged = pyqtSignal(int)
    snoozed = pyqtSignal(int, int)
    dismissed = pyqtSignal(int)

    def __init__(self, reminder_data, parent=None):
        super().__init__(parent)
        self.reminder_id = reminder_data.get('id', 0)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.setStyleSheet("""
            QFrame#reminderPopup {
                background: #333333;
                border: 2px solid #4a4a4a;
                border-radius: 16px;
            }
        """)
        self.setObjectName("reminderPopup")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)

        priority = reminder_data.get('priority_level', 0)
        color = PRIORITY_COLORS.get(priority, "#ef4444")
        label = PRIORITY_LABELS.get(priority, "\U0001f514 提醒")

        title = QLabel(f"{label}  {reminder_data.get('chat', '未知会话')}")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {color};")
        layout.addWidget(title)

        content_text = reminder_data.get('content', '')
        if len(content_text) > 200:
            content_text = content_text[:200] + "..."
        content = QLabel(content_text)
        content.setWordWrap(True)
        content.setStyleSheet("color: #d0d0d0; font-size: 13px; line-height: 1.5;")
        layout.addWidget(content)

        info_parts = []
        if reminder_data.get('sender'):
            info_parts.append(f"\U0001f464 {reminder_data.get('sender')}")
        if reminder_data.get('source_person') and reminder_data.get('source_person') != reminder_data.get('sender'):
            info_parts.append(f"\U0001f4dd 提出: {reminder_data.get('source_person')}")
        if reminder_data.get('time'):
            info_parts.append(f"\U0001f552 {reminder_data.get('time')}")
        if reminder_data.get('deadline'):
            info_parts.append(f"\u23f0 截止: {reminder_data.get('deadline')}")
        if reminder_data.get('category'):
            cat_names = {'finance': '\U0001f4b0 财务', 'meeting': '\U0001f4cb 会议', 'task': '\U0001f4cc 任务',
                         'document': '\U0001f4c4 文档', 'personal': '\U0001f464 个人', 'urgent': '\U0001f6a8 紧急'}
            info_parts.append(cat_names.get(reminder_data.get('category'), reminder_data.get('category')))

        info = QLabel("  |  ".join(info_parts))
        info.setStyleSheet("color: #888888; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        snooze_row = QHBoxLayout()
        snooze_row.setSpacing(6)
        snooze_label = QLabel("\u23f0 稍后提醒:")
        snooze_label.setStyleSheet("color: #888888; font-size: 11px;")
        snooze_row.addWidget(snooze_label)
        for text, minutes in SNOOZE_OPTIONS:
            btn = QPushButton(text)
            btn.setFixedHeight(28)
            btn.setStyleSheet("""
                QPushButton {
                    background: #3d3d3d;
                    color: #b0b0b0;
                    border: 1px solid #555555;
                    border-radius: 6px;
                    padding: 2px 10px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background: #4a4a4a;
                    border-color: #888888;
                }
            """)
            btn.clicked.connect(lambda checked, m=minutes: self._on_snooze(m))
            snooze_row.addWidget(btn)
        snooze_row.addStretch()
        layout.addLayout(snooze_row)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        dismiss_btn = QPushButton("忽略")
        dismiss_btn.setStyleSheet("""
            QPushButton {
                background: #3d3d3d;
                color: #888888;
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 12px;
            }
            QPushButton:hover { background: #4a4a4a; }
        """)
        dismiss_btn.clicked.connect(self._on_dismiss)
        btn_layout.addWidget(dismiss_btn)

        ack_btn = QPushButton("\u2705 确认处理")
        ack_btn.setStyleSheet("""
            QPushButton {
                background: #10b981;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: #059669; }
        """)
        ack_btn.clicked.connect(self._on_acknowledge)
        btn_layout.addWidget(ack_btn)

        layout.addLayout(btn_layout)
        self.setFixedWidth(440)
        self.adjustSize()

    def show_popup(self):
        from PyQt5.QtWidgets import QDesktopWidget
        desktop = QDesktopWidget().availableGeometry()
        self.move(desktop.right() - self.width() - 20, desktop.bottom() - self.height() - 20)
        self.show()

    def _on_acknowledge(self):
        self.acknowledged.emit(self.reminder_id)
        self.close()

    def _on_snooze(self, minutes):
        self.snoozed.emit(self.reminder_id, minutes)
        self.close()

    def _on_dismiss(self):
        self.dismissed.emit(self.reminder_id)
        self.close()
