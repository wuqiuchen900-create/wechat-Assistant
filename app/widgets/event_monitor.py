# app/widgets/event_monitor.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QScrollArea, QFrame, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon
from core.event_tracker import get_all_active_events, get_all_events
from core.smart_reminder import count_pending_smart_reminders
from debug_log import logger

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


class MonitorEventCard(QFrame):
    clicked = pyqtSignal(dict)

    def __init__(self, event_data, parent=None):
        super().__init__(parent)
        self.event_data = event_data
        self.setObjectName("monitorCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QFrame#monitorCard {
                background: #3a3a3a;
                border: 1px solid #4a4a4a;
                border-radius: 8px;
                padding: 10px;
            }
            QFrame#monitorCard:hover {
                border-color: #5b9bd5;
                background: #444444;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        cat = event_data.get('event_category', 'general')
        icon = CATEGORY_ICONS.get(cat, '\U0001f4ac')
        color = CATEGORY_COLORS.get(cat, '#6b7280')

        title = QLabel(f"{icon} {event_data.get('event_title', '未命名')}")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {color};")
        title.setWordWrap(True)
        header.addWidget(title)
        header.addStretch()

        msg_count = event_data.get('message_count', 0)
        count_label = QLabel(f"{msg_count}条")
        count_label.setStyleSheet("color: #888888; font-size: 10px;")
        header.addWidget(count_label)
        layout.addLayout(header)

        chat_label = QLabel(f"\U0001f4ac {event_data.get('chat', '')}")
        chat_label.setStyleSheet("color: #999999; font-size: 11px;")
        layout.addWidget(chat_label)

        date_range = f"{event_data.get('start_time', '?')} ~ {event_data.get('end_time', '?')}"
        date_label = QLabel(f"\U0001f4c5 {date_range}")
        date_label.setStyleSheet("color: #777777; font-size: 10px;")
        layout.addWidget(date_label)

        last_activity = event_data.get('last_activity', '')
        if last_activity:
            active_label = QLabel(f"\U0001f552 最近: {last_activity}")
            active_label.setStyleSheet("color: #666666; font-size: 10px;")
            layout.addWidget(active_label)

    def mousePressEvent(self, event):
        self.clicked.emit(self.event_data)
        super().mousePressEvent(event)


class EventMonitorWindow(QWidget):
    navigate_to_event = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("事件监控面板")
        self.setMinimumSize(380, 500)
        self.resize(420, 650)

        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #e0e0e0;
            }
        """)

        self.setWindowFlags(
            Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("\U0001f50d 事件监控")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #e0e0e0;")
        header.addWidget(title)
        header.addStretch()

        self._pending_badge = QLabel("")
        self._pending_badge.setStyleSheet("""
            background: #ef4444;
            color: white;
            border-radius: 8px;
            padding: 3px 8px;
            font-size: 10px;
            font-weight: bold;
        """)
        self._pending_badge.hide()
        header.addWidget(self._pending_badge)

        refresh_btn = QPushButton("\U0001f504")
        refresh_btn.setFixedSize(32, 32)
        refresh_btn.setToolTip("刷新")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #3d3d3d;
                color: #b0b0b0;
                border: 1px solid #555555;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover { background: #4a4a4a; border-color: #5b9bd5; }
        """)
        refresh_btn.clicked.connect(self.refresh_events)
        header.addWidget(refresh_btn)

        pin_btn = QPushButton("\U0001f4cc")
        pin_btn.setFixedSize(32, 32)
        pin_btn.setToolTip("置顶")
        pin_btn.setCheckable(True)
        pin_btn.setStyleSheet("""
            QPushButton {
                background: #3d3d3d;
                color: #b0b0b0;
                border: 1px solid #555555;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover { background: #4a4a4a; border-color: #5b9bd5; }
            QPushButton:checked { background: #5b9bd5; color: white; border-color: #5b9bd5; }
        """)
        pin_btn.clicked.connect(self._toggle_pin)
        header.addWidget(pin_btn)
        layout.addLayout(header)

        self._filter_row = QHBoxLayout()
        self._filter_row.setSpacing(6)

        self._filter_buttons = []
        all_btn = QPushButton("全部")
        all_btn.setCheckable(True)
        all_btn.setChecked(True)
        all_btn.clicked.connect(lambda: self._apply_filter(None))
        self._make_filter_btn(all_btn)
        self._filter_row.addWidget(all_btn)
        self._filter_buttons.append((all_btn, None))

        for cat_key in ['urgent', 'meeting', 'finance', 'task', 'document', 'delivery']:
            cat_label = CATEGORY_ICONS.get(cat_key, '') + ' ' + {
                'urgent': '紧急', 'meeting': '会议', 'finance': '财务',
                'task': '任务', 'document': '文件', 'delivery': '物流'
            }.get(cat_key, cat_key)
            btn = QPushButton(cat_label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, c=cat_key: self._apply_filter(c))
            self._make_filter_btn(btn)
            self._filter_row.addWidget(btn)
            self._filter_buttons.append((btn, cat_key))

        self._filter_row.addStretch()
        layout.addLayout(self._filter_row)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: #2b2b2b;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #777777; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(8)
        self.cards_layout.addStretch()

        self.scroll_area.setWidget(self.cards_container)
        layout.addWidget(self.scroll_area)

        self._current_filter = None
        self._all_events = []

        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self.refresh_events)
        self._refresh_timer.start(30000)

        self.refresh_events()

    def _make_filter_btn(self, btn):
        btn.setFixedHeight(26)
        btn.setStyleSheet("""
            QPushButton {
                background: #333333;
                color: #999999;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                padding: 2px 10px;
                font-size: 11px;
            }
            QPushButton:hover { background: #3d3d3d; color: #b0b0b0; }
            QPushButton:checked { background: #5b9bd5; color: white; border-color: #5b9bd5; }
        """)

    def _apply_filter(self, category):
        for btn, cat in self._filter_buttons:
            btn.setChecked(cat == category)
        self._current_filter = category
        self._render_events()

    def _toggle_pin(self, checked):
        if checked:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.show()

    def refresh_events(self):
        try:
            self._all_events = get_all_active_events(200)
            pending = count_pending_smart_reminders()
            if pending > 0:
                self._pending_badge.setText(f"\U0001f514 {pending}")
                self._pending_badge.show()
            else:
                self._pending_badge.hide()
            self._render_events()
        except Exception as e:
            logger.error(f"[事件监控] 刷新失败: {e}")

    def _render_events(self):
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        filtered = self._all_events
        if self._current_filter:
            filtered = [e for e in self._all_events if e.get('event_category') == self._current_filter]

        if not filtered:
            empty = QLabel("\U0001f4ad 暂无活跃事件\n\n同步完成后系统会自动分析追踪")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color: #666666; font-size: 12px; padding: 30px;")
            self.cards_layout.insertWidget(0, empty)
            return

        for event in filtered:
            card = MonitorEventCard(event)
            card.clicked.connect(self._on_event_clicked)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

    def _on_event_clicked(self, event_data):
        chat = event_data.get('chat', '')
        if chat:
            self.navigate_to_event.emit(chat)
            logger.info(f"[事件监控] 点击事件 -> {chat}")

    def closeEvent(self, event):
        self._refresh_timer.stop()
        super().closeEvent(event)
