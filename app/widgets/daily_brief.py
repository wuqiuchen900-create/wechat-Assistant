# app/widgets/daily_brief.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QFrame, QScrollArea, QGridLayout)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from core.data_manager import count_messages, get_urgent_messages


class DailyBriefPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #2b2b2b;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #2b2b2b; }")

        self.inner = QWidget()
        self.inner.setStyleSheet("background: #2b2b2b;")
        self.layout = QVBoxLayout(self.inner)
        self.layout.setContentsMargins(24, 20, 24, 20)
        self.layout.setSpacing(16)

        self._build_header()
        self._build_summary_cards()
        self._build_urgent_section()
        self._build_category_section()

        self.layout.addStretch()
        scroll.setWidget(self.inner)
        outer.addWidget(scroll)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(60000)

    def _build_header(self):
        title = QLabel("\U0001f4ca 每日简报")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #e0e0e0; padding: 0;")
        self.layout.addWidget(title)

        subtitle = QLabel("自动汇总今日消息动态与待处理事项")
        subtitle.setStyleSheet("color: #888888; font-size: 13px; padding: 0;")
        self.layout.addWidget(subtitle)

    def _build_summary_cards(self):
        cards = QHBoxLayout()
        cards.setSpacing(12)

        self.card_total = self._make_card("\U0001f4e8", "总消息", "0", "#5b9bd5")
        self.card_today = self._make_card("\U0001f4c5", "今日", "0", "#10b981")
        self.card_urgent = self._make_card("\U0001f534", "紧急", "0", "#ef4444")
        self.card_session = self._make_card("\U0001f4ac", "活跃会话", "0", "#f59e0b")

        for c in [self.card_total, self.card_today, self.card_urgent, self.card_session]:
            cards.addWidget(c)
        self.layout.addLayout(cards)

    def _make_card(self, icon, label, value, color):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: #333333;
                border-radius: 12px;
                border-left: 4px solid {color};
                padding: 0;
            }}
        """)
        card.setFixedHeight(90)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(4)

        icon_lbl = QLabel(f"{icon}  {label}")
        icon_lbl.setStyleSheet("color: #888888; font-size: 12px;")
        cl.addWidget(icon_lbl)

        val_lbl = QLabel(value)
        val_font = QFont()
        val_font.setPointSize(22)
        val_font.setBold(True)
        val_lbl.setFont(val_font)
        val_lbl.setStyleSheet(f"color: {color};")
        val_lbl.setObjectName(f"card_{label}")
        cl.addWidget(val_lbl)

        card.val_label = val_lbl
        return card

    def _build_urgent_section(self):
        section = QLabel("\U0001f514 紧急待处理")
        section_font = QFont()
        section_font.setPointSize(14)
        section_font.setBold(True)
        section.setFont(section_font)
        section.setStyleSheet("color: #e0e0e0; padding: 0; margin-top: 8px;")
        self.layout.addWidget(section)

        self.urgent_container = QVBoxLayout()
        self.urgent_container.setSpacing(6)
        self.layout.addLayout(self.urgent_container)

        self.urgent_empty = QLabel("暂无紧急事项 \u2728")
        self.urgent_empty.setStyleSheet("color: #666666; font-size: 13px; padding: 12px;")
        self.urgent_container.addWidget(self.urgent_empty)

    def _build_category_section(self):
        section = QLabel("\U0001f4ca 分类统计")
        section_font = QFont()
        section_font.setPointSize(14)
        section_font.setBold(True)
        section.setFont(section_font)
        section.setStyleSheet("color: #e0e0e0; padding: 0; margin-top: 8px;")
        self.layout.addWidget(section)

        self.cat_grid = QGridLayout()
        self.cat_grid.setSpacing(8)
        self.layout.addLayout(self.cat_grid)

    def refresh(self):
        total = count_messages()
        urgent_msgs = get_urgent_messages(limit=20)

        import time as _time
        today_str = _time.strftime('%Y-%m-%d')
        today_count = 0
        sessions = set()
        cat_counts = {}

        for m in urgent_msgs:
            if m.get('time', '').startswith(today_str):
                today_count += 1
            sessions.add(m.get('chat', ''))
            cat = m.get('category', 'other')
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        self.card_total.val_label.setText(str(total))
        self.card_today.val_label.setText(str(today_count))
        self.card_urgent.val_label.setText(str(len(urgent_msgs)))
        self.card_session.val_label.setText(str(len(sessions)))

        while self.urgent_container.count() > 0:
            item = self.urgent_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if urgent_msgs:
            for m in urgent_msgs[:8]:
                row = self._make_urgent_row(m)
                self.urgent_container.addWidget(row)
        else:
            self.urgent_empty = QLabel("暂无紧急事项 \u2728")
            self.urgent_empty.setStyleSheet("color: #666666; font-size: 13px; padding: 12px;")
            self.urgent_container.addWidget(self.urgent_empty)

        while self.cat_grid.count() > 0:
            item = self.cat_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cat_names = {'finance': '财务', 'meeting': '会议', 'task': '任务',
                     'document': '文档', 'personal': '个人', 'urgent': '紧急'}
        cat_colors = {'finance': '#f59e0b', 'meeting': '#8b5cf6', 'task': '#3b82f6',
                      'document': '#10b981', 'personal': '#ec4899', 'urgent': '#ef4444'}
        row_idx = 0
        for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
            name = cat_names.get(cat, cat)
            color = cat_colors.get(cat, '#6c757d')
            tag = QLabel(f"  {name}  ")
            tag.setStyleSheet(f"""
                background: {color}22;
                color: {color};
                font-size: 12px;
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 8px;
            """)
            cnt = QLabel(str(count))
            cnt.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold;")
            self.cat_grid.addWidget(tag, row_idx, 0)
            self.cat_grid.addWidget(cnt, row_idx, 1)
            row_idx += 1

    def _make_urgent_row(self, msg):
        row = QFrame()
        priority = msg.get('priority_level', 0)
        colors = {5: "#ef4444", 4: "#f97316", 3: "#f59e0b", 2: "#3b82f6", 1: "#6b7280", 0: "#9ca3af"}
        color = colors.get(priority, "#ef4444")
        row.setStyleSheet(f"""
            QFrame {{
                background: #333333;
                border-radius: 8px;
                border-left: 3px solid {color};
                padding: 0;
            }}
        """)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(12, 8, 12, 8)

        chat = msg.get('chat', '')[:20]
        content = msg.get('content', '')[:50]
        lbl = QLabel(f"{chat}  |  {content}")
        lbl.setStyleSheet("color: #d0d0d0; font-size: 12px;")
        lbl.setWordWrap(True)
        rl.addWidget(lbl)
        rl.addStretch()

        time_lbl = QLabel(msg.get('time', '')[-8:] if msg.get('time') else '')
        time_lbl.setStyleSheet("color: #666666; font-size: 11px;")
        rl.addWidget(time_lbl)

        return row
