# app/widgets/event_panel.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QScrollArea, QFrame, QListWidget,
                             QListWidgetItem, QSplitter, QTextEdit)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont
from core.event_tracker import (get_all_events, get_events_by_chat,
                                delete_event, run_analysis_now)
from core.smart_reminder import count_pending_smart_reminders
from debug_log import logger

CATEGORY_ICONS = {
    'meeting': '\U0001f4cb', 'document': '\U0001f4c4', 'finance': '\U0001f4b0',
    'task': '\U0001f4cc', 'schedule': '\U0001f4c5', 'delivery': '\U0001f4e6',
    'borrow': '\U0001f4e5', 'personal': '\U0001f464', 'general': '\U0001f4ac'
}

CATEGORY_COLORS = {
    'meeting': '#5b9bd5', 'document': '#f59e0b', 'finance': '#10b981',
    'task': '#8b5cf6', 'schedule': '#f97316', 'delivery': '#06b6d4',
    'borrow': '#ec4899', 'personal': '#84cc16', 'general': '#6b7280'
}


class EventCard(QFrame):
    def __init__(self, event_data, parent=None):
        super().__init__(parent)
        self.event_data = event_data
        self.setObjectName("eventCard")
        self.setStyleSheet("""
            QFrame#eventCard {
                background: #3d3d3d;
                border: 1px solid #4a4a4a;
                border-radius: 10px;
                padding: 12px;
            }
            QFrame#eventCard:hover {
                border-color: #5b9bd5;
                background: #444444;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        cat = event_data.get('event_category', 'general')
        icon = CATEGORY_ICONS.get(cat, '\U0001f4ac')
        color = CATEGORY_COLORS.get(cat, '#6b7280')

        title = QLabel(f"{icon} {event_data.get('event_title', '未命名事件')}")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {color};")
        header.addWidget(title)
        header.addStretch()

        confidence = event_data.get('confidence', 0)
        conf_label = QLabel(f"{confidence:.0%}")
        conf_label.setStyleSheet(f"color: {'#10b981' if confidence > 0.7 else '#f59e0b'}; font-size: 11px;")
        header.addWidget(conf_label)
        layout.addLayout(header)

        chat_label = QLabel(f"\U0001f4ac {event_data.get('chat', '')}")
        chat_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(chat_label)

        date_range = f"\U0001f4c5 {event_data.get('start_time', '?')} ~ {event_data.get('end_time', '?')}"
        date_label = QLabel(date_range)
        date_label.setStyleSheet("color: #b0b0b0; font-size: 11px;")
        layout.addWidget(date_label)

        summary = event_data.get('event_summary', '')
        if summary:
            sum_label = QLabel(summary)
            sum_label.setWordWrap(True)
            sum_label.setStyleSheet("color: #d0d0d0; font-size: 12px; line-height: 1.5;")
            layout.addWidget(sum_label)

        if event_data.get('key_participants'):
            part_label = QLabel(f"\U0001f465 {event_data.get('key_participants')}")
            part_label.setStyleSheet("color: #888888; font-size: 11px;")
            layout.addWidget(part_label)

        info_row = QHBoxLayout()
        msg_count = QLabel(f"\U0001f4e8 {event_data.get('message_count', 0)} 条消息")
        msg_count.setStyleSheet("color: #888888; font-size: 11px;")
        info_row.addWidget(msg_count)
        info_row.addStretch()

        if event_data.get('keywords'):
            kw_label = QLabel(f"\U0001f3f7\ufe0f {event_data.get('keywords', '')}")
            kw_label.setStyleSheet("color: #666666; font-size: 10px;")
            kw_label.setWordWrap(True)
            info_row.addWidget(kw_label)
        layout.addLayout(info_row)


class EventPanel(QWidget):
    event_selected = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_events = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("\U0001f50d 事件追踪")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #e0e0e0;")
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QPushButton("\U0001f504 刷新分析")
        refresh_btn.setObjectName("secondaryBtn")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #3d3d3d;
                color: #b0b0b0;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
            }
            QPushButton:hover { background: #4a4a4a; border-color: #5b9bd5; color: #5b9bd5; }
        """)
        refresh_btn.clicked.connect(self._on_refresh)
        header.addWidget(refresh_btn)

        monitor_btn = QPushButton("\U0001f4cb 监控面板")
        monitor_btn.setObjectName("secondaryBtn")
        monitor_btn.setStyleSheet("""
            QPushButton {
                background: #3d3d3d;
                color: #b0b0b0;
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
            }
            QPushButton:hover { background: #4a4a4a; border-color: #5b9bd5; color: #5b9bd5; }
        """)
        monitor_btn.clicked.connect(self._on_open_monitor)
        header.addWidget(monitor_btn)

        self._pending_badge = QLabel("")
        self._pending_badge.setStyleSheet("""
            background: #ef4444;
            color: white;
            border-radius: 10px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: bold;
        """)
        self._pending_badge.hide()
        header.addWidget(self._pending_badge)
        layout.addLayout(header)

        hint = QLabel("自动识别每个会话中的不同事件，按时间线和主题智能归类。分析在后台空闲时自动运行。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(hint)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: #2b2b2b;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover { background: #777777; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch()

        self.scroll_area.setWidget(self.cards_container)
        layout.addWidget(self.scroll_area)

        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self.load_events)
        self._refresh_timer.start(60000)

    def load_events(self, chat_filter=None):
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        pending_count = count_pending_smart_reminders()
        if pending_count > 0:
            self._pending_badge.setText(f"\U0001f514 {pending_count} 条待处理提醒")
            self._pending_badge.show()
        else:
            self._pending_badge.hide()

        if chat_filter:
            events = get_events_by_chat(chat_filter)
        else:
            events = get_all_events(200)

        self._all_events = events

        if not events:
            empty = QLabel("\U0001f4ad 暂无追踪到的事件\n\n同步完成后系统会自动分析，也可点击「刷新分析」立即分析")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color: #666666; font-size: 13px; padding: 40px;")
            self.cards_layout.insertWidget(0, empty)
            return

        for event in events:
            card = EventCard(event)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

    def _on_refresh(self):
        logger.info("[事件面板] 手动触发分析...")
        count = run_analysis_now()
        self.load_events()
        logger.info(f"[事件面板] 分析完成，发现 {count} 个事件")

    def _on_open_monitor(self):
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        monitor = getattr(app, '_event_monitor', None)
        if monitor:
            monitor.show()
            monitor.raise_()
            monitor.activateWindow()
            monitor.refresh_events()

    def showEvent(self, event):
        super().showEvent(event)
        self.load_events()
