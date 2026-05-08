# app/widgets/smart_popup.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QFrame, QGraphicsOpacityEffect)
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont

CATEGORY_ICONS = {
    'meeting': '\U0001f4cb', 'document': '\U0001f4c4', 'finance': '\U0001f4b0',
    'task': '\U0001f4cc', 'schedule': '\U0001f4c5', 'delivery': '\U0001f4e6',
    'borrow': '\U0001f4e5', 'personal': '\U0001f464', 'general': '\U0001f4ac',
    'urgent': '\U0001f6a8'
}

CATEGORY_COLORS = {
    'meeting': '#5b9bd5', 'document': '#f59e0b', 'finance': '#10b981',
    'task': '#8b5cf6', 'schedule': '#f97316', 'delivery': '#06b6d4',
    'borrow': '#ec4899', 'personal': '#84cc16', 'general': '#6b7280',
    'urgent': '#ef4444'
}

URGENCY_COLORS = [
    (0.8, '#ef4444', '\U0001f534 高度紧急'),
    (0.6, '#f97316', '\U0001f7e0 较为紧急'),
    (0.4, '#f59e0b', '\U0001f7e1 需要关注'),
    (0.0, '#3b82f6', '\U0001f535 一般提醒'),
]

SNOOZE_OPTIONS = [
    ('5分钟', 5), ('10分钟', 10), ('30分钟', 30),
    ('1小时', 60), ('3小时', 180), ('1天后', 1440),
]


class SmartPopup(QWidget):
    acknowledged = pyqtSignal(int)
    snoozed = pyqtSignal(int, int)
    dismissed = pyqtSignal(int)
    view_detail = pyqtSignal(dict)

    def __init__(self, analysis_result, parent=None):
        super().__init__(parent)
        self.reminder_id = analysis_result.get('id', 0)
        self.analysis = analysis_result

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.Tool | Qt.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_DeleteOnClose)

        from PyQt5.QtWidgets import QDesktopWidget
        desktop = QDesktopWidget().availableGeometry()
        self.setGeometry(desktop)

        self._overlay = QWidget(self)
        self._overlay.setGeometry(self.rect())
        self._overlay.setStyleSheet("background: rgba(0, 0, 0, 0.55);")
        self._overlay.mousePressEvent = self._on_overlay_click

        self._panel = QFrame(self)
        self._panel.setObjectName("smartPopupPanel")
        self._panel.setFixedWidth(480)
        self._panel.setStyleSheet("""
            QFrame#smartPopupPanel {
                background: #2d2d2d;
                border: 1px solid #4a4a4a;
                border-radius: 16px;
            }
        """)

        self._build_panel_content()

        panel_height = self._panel.sizeHint().height()
        panel_height = min(panel_height, desktop.height() - 40)
        self._panel.setFixedHeight(panel_height)
        self._panel.move(desktop.right() - 500, (desktop.height() - panel_height) // 2)

        self._fade_in()

    def _build_panel_content(self):
        layout = QVBoxLayout(self._panel)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        cat = self.analysis.get('event_category', 'general')
        icon = CATEGORY_ICONS.get(cat, '\U0001f4ac')
        color = CATEGORY_COLORS.get(cat, '#6b7280')

        title_text = self.analysis.get('event_title', '')
        if not title_text:
            title_text = f"{self.analysis.get('chat', '未知会话')} 的新消息"

        title = QLabel(f"{icon} {title_text}")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {color};")
        title.setWordWrap(True)
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        urgency = self.analysis.get('urgency_score', 0)
        urgency_color = '#3b82f6'
        urgency_label_text = '\U0001f535 一般提醒'
        for threshold, ucolor, ulabel in URGENCY_COLORS:
            if urgency >= threshold:
                urgency_color = ucolor
                urgency_label_text = ulabel
                break

        urgency_row = QHBoxLayout()
        urgency_badge = QLabel(urgency_label_text)
        urgency_badge.setStyleSheet(f"""
            background: {urgency_color}22;
            color: {urgency_color};
            border: 1px solid {urgency_color}44;
            border-radius: 8px;
            padding: 4px 12px;
            font-size: 12px;
            font-weight: bold;
        """)
        urgency_row.addWidget(urgency_badge)

        score_label = QLabel(f"紧急指数 {urgency:.0%}")
        score_label.setStyleSheet(f"color: {urgency_color}; font-size: 12px; font-weight: bold;")
        urgency_row.addWidget(score_label)
        urgency_row.addStretch()
        layout.addLayout(urgency_row)

        reason = self.analysis.get('urgency_reason', '')
        if reason:
            reason_label = QLabel(f"\U0001f4dd {reason}")
            reason_label.setWordWrap(True)
            reason_label.setStyleSheet("color: #b0b0b0; font-size: 12px; line-height: 1.5;")
            layout.addWidget(reason_label)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setStyleSheet("background: #4a4a4a; max-height: 1px;")
        layout.addWidget(sep1)

        chat_label = QLabel(f"\U0001f4ac 会话: {self.analysis.get('chat', '')}")
        chat_label.setStyleSheet("color: #d0d0d0; font-size: 13px; font-weight: bold;")
        layout.addWidget(chat_label)

        sender = self.analysis.get('sender', '')
        if sender:
            sender_label = QLabel(f"\U0001f464 发送者: {sender}")
            sender_label.setStyleSheet("color: #b0b0b0; font-size: 12px;")
            layout.addWidget(sender_label)

        msg_time = self.analysis.get('message_time', '')
        if msg_time:
            time_label = QLabel(f"\U0001f552 时间: {msg_time}")
            time_label.setStyleSheet("color: #888888; font-size: 11px;")
            layout.addWidget(time_label)

        content = self.analysis.get('content', '')
        if content:
            if len(content) > 500:
                content = content[:500] + '...'
            content_box = QLabel(content)
            content_box.setWordWrap(True)
            content_box.setStyleSheet("""
                background: #333333;
                color: #e0e0e0;
                border: 1px solid #4a4a4a;
                border-radius: 10px;
                padding: 14px;
                font-size: 13px;
                line-height: 1.6;
            """)
            layout.addWidget(content_box)

        event_start = self.analysis.get('event_start', '')
        event_end = self.analysis.get('event_end', '')
        if event_start or event_end:
            date_label = QLabel(f"\U0001f4c5 事件周期: {event_start or '?'} ~ {event_end or '?'}")
            date_label.setStyleSheet("color: #888888; font-size: 11px;")
            layout.addWidget(date_label)

        participants = self.analysis.get('event_participants', '')
        if participants:
            part_label = QLabel(f"\U0001f465 参与人: {participants}")
            part_label.setStyleSheet("color: #888888; font-size: 11px;")
            layout.addWidget(part_label)

        event_summary = self.analysis.get('event_summary', '')
        if event_summary:
            sum_label = QLabel(f"\U0001f4cb {event_summary}")
            sum_label.setWordWrap(True)
            sum_label.setStyleSheet("color: #999999; font-size: 11px; line-height: 1.4;")
            layout.addWidget(sum_label)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("background: #4a4a4a; max-height: 1px;")
        layout.addWidget(sep2)

        snooze_label = QLabel("\u23f0 稍后提醒")
        snooze_label.setStyleSheet("color: #888888; font-size: 11px; font-weight: bold;")
        layout.addWidget(snooze_label)

        snooze_rows = []
        row = QHBoxLayout()
        row.setSpacing(6)
        for i, (text, minutes) in enumerate(SNOOZE_OPTIONS):
            if i > 0 and i % 3 == 0:
                snooze_rows.append(row)
                row = QHBoxLayout()
                row.setSpacing(6)
            btn = QPushButton(text)
            btn.setFixedHeight(30)
            btn.setStyleSheet("""
                QPushButton {
                    background: #3d3d3d;
                    color: #b0b0b0;
                    border: 1px solid #555555;
                    border-radius: 8px;
                    padding: 4px 12px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background: #4a4a4a;
                    border-color: #5b9bd5;
                    color: #5b9bd5;
                }
            """)
            btn.clicked.connect(lambda checked, m=minutes: self._on_snooze(m))
            row.addWidget(btn)
        row.addStretch()
        snooze_rows.append(row)

        for r in snooze_rows:
            layout.addLayout(r)

        layout.addSpacing(6)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        view_btn = QPushButton("\U0001f50d 查看详情")
        view_btn.setStyleSheet("""
            QPushButton {
                background: #3d3d3d;
                color: #b0b0b0;
                border: 1px solid #555555;
                border-radius: 10px;
                padding: 10px 18px;
                font-size: 13px;
            }
            QPushButton:hover { background: #4a4a4a; border-color: #5b9bd5; color: #5b9bd5; }
        """)
        view_btn.clicked.connect(self._on_view_detail)
        btn_layout.addWidget(view_btn)

        btn_layout.addStretch()

        dismiss_btn = QPushButton("\u274c 忽略")
        dismiss_btn.setStyleSheet("""
            QPushButton {
                background: #3d3d3d;
                color: #888888;
                border: 1px solid #555555;
                border-radius: 10px;
                padding: 10px 18px;
                font-size: 13px;
            }
            QPushButton:hover { background: #4a4a4a; border-color: #ef4444; color: #ef4444; }
        """)
        dismiss_btn.clicked.connect(self._on_dismiss)
        btn_layout.addWidget(dismiss_btn)

        ack_btn = QPushButton("\u2705 已处理")
        ack_btn.setStyleSheet("""
            QPushButton {
                background: #10b981;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px 22px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background: #059669; }
        """)
        ack_btn.clicked.connect(self._on_acknowledge)
        btn_layout.addWidget(ack_btn)

        layout.addLayout(btn_layout)

    def _fade_in(self):
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)

        self._anim = QPropertyAnimation(self._opacity, b"opacity")
        self._anim.setDuration(300)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()

    def _on_overlay_click(self, event):
        pass

    def _on_acknowledge(self):
        self.acknowledged.emit(self.reminder_id)
        self._fade_out()

    def _on_snooze(self, minutes):
        self.snoozed.emit(self.reminder_id, minutes)
        self._fade_out()

    def _on_dismiss(self):
        self.dismissed.emit(self.reminder_id)
        self._fade_out()

    def _on_view_detail(self):
        self.view_detail.emit(self.analysis)
        self._fade_out()

    def _fade_out(self):
        self._anim2 = QPropertyAnimation(self._opacity, b"opacity")
        self._anim2.setDuration(200)
        self._anim2.setStartValue(1.0)
        self._anim2.setEndValue(0.0)
        self._anim2.setEasingCurve(QEasingCurve.InCubic)
        self._anim2.finished.connect(self.close)
        self._anim2.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_overlay'):
            self._overlay.setGeometry(self.rect())
