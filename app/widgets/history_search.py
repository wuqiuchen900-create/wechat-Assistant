# app/widgets/history_search.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QFrame, QScrollArea,
                             QComboBox, QDateEdit, QCheckBox)
from PyQt5.QtCore import Qt, QDate, pyqtSignal, QTimer
from PyQt5.QtGui import QFont
from core.data_manager import get_all_messages, count_messages


class HistorySearchPanel(QWidget):
    search_requested = pyqtSignal(str, dict)

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
        self.layout.setSpacing(14)

        self._build_header()
        self._build_search_bar()
        self._build_filters()
        self._build_results_area()

        self.layout.addStretch()
        scroll.setWidget(self.inner)
        outer.addWidget(scroll)

    def _build_header(self):
        title = QLabel("\U0001f50d 历史检索")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #e0e0e0;")
        self.layout.addWidget(title)

        subtitle = QLabel("搜索历史消息，支持关键词、日期、分类筛选")
        subtitle.setStyleSheet("color: #888888; font-size: 13px;")
        self.layout.addWidget(subtitle)

    def _build_search_bar(self):
        bar = QFrame()
        bar.setStyleSheet("""
            QFrame {
                background: #333333;
                border-radius: 12px;
                border: 1px solid #4a4a4a;
            }
        """)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 10, 10, 10)
        bl.setSpacing(10)

        icon = QLabel("\U0001f50d")
        icon.setStyleSheet("font-size: 16px;")
        bl.addWidget(icon)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入关键词搜索历史消息...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: none;
                font-size: 14px;
                color: #d0d0d0;
                background: transparent;
                padding: 4px;
            }
        """)
        self.search_input.returnPressed.connect(self._do_search)
        bl.addWidget(self.search_input)

        search_btn = QPushButton("搜索")
        search_btn.setStyleSheet("""
            QPushButton {
                background: #5b9bd5;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background: #4a8ac4; }
        """)
        search_btn.clicked.connect(self._do_search)
        bl.addWidget(search_btn)

        self.layout.addWidget(bar)

    def _build_filters(self):
        filters = QFrame()
        filters.setStyleSheet("""
            QFrame {
                background: #333333;
                border-radius: 10px;
                border: 1px solid #4a4a4a;
            }
        """)
        fl = QHBoxLayout(filters)
        fl.setContentsMargins(14, 10, 14, 10)
        fl.setSpacing(12)

        fl.addWidget(QLabel("分类:"))
        fl.itemAt(fl.count() - 1).widget().setStyleSheet("color: #b0b0b0;")
        self.cat_combo = QComboBox()
        self.cat_combo.addItems(["全部", "财务", "会议", "任务", "文档", "个人", "紧急"])
        self.cat_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
                min-width: 80px;
                background: #3d3d3d;
                color: #d0d0d0;
            }
            QComboBox QAbstractItemView {
                background: #3d3d3d;
                color: #d0d0d0;
                selection-background-color: #4a4a4a;
            }
        """)
        fl.addWidget(self.cat_combo)

        fl.addWidget(QLabel("日期:"))
        fl.itemAt(fl.count() - 1).widget().setStyleSheet("color: #b0b0b0;")
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addDays(-7))
        self.date_from.setStyleSheet("""
            QDateEdit {
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 4px 6px;
                font-size: 12px;
                background: #3d3d3d;
                color: #d0d0d0;
            }
        """)
        fl.addWidget(self.date_from)

        fl.addWidget(QLabel("至"))
        fl.itemAt(fl.count() - 1).widget().setStyleSheet("color: #b0b0b0;")
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setStyleSheet("""
            QDateEdit {
                border: 1px solid #555555;
                border-radius: 6px;
                padding: 4px 6px;
                font-size: 12px;
                background: #3d3d3d;
                color: #d0d0d0;
            }
        """)
        fl.addWidget(self.date_to)

        self.urgent_only = QCheckBox("仅紧急")
        self.urgent_only.setStyleSheet("font-size: 12px; color: #b0b0b0;")
        fl.addWidget(self.urgent_only)

        fl.addStretch()

        ai_btn = QPushButton("\U0001f916 AI 分析")
        ai_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #667eea, stop:1 #764ba2);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5a6fd6, stop:1 #6a4190); }
        """)
        ai_btn.clicked.connect(self._do_ai_search)
        fl.addWidget(ai_btn)

        self.layout.addWidget(filters)

    def _build_results_area(self):
        self.result_header = QLabel("搜索结果将显示在这里")
        self.result_header.setStyleSheet("color: #888888; font-size: 13px; padding: 8px 0;")
        self.layout.addWidget(self.result_header)

        self.results_container = QVBoxLayout()
        self.results_container.setSpacing(6)
        self.layout.addLayout(self.results_container)

    def _do_search(self):
        keyword = self.search_input.text().strip()
        if not keyword:
            self.result_header.setText("请输入搜索关键词")
            return
        self._execute_search(keyword)

    def _do_ai_search(self):
        keyword = self.search_input.text().strip()
        if not keyword:
            self.result_header.setText("请输入搜索关键词后再使用 AI 分析")
            return
        self.search_requested.emit(keyword, self._get_filter_params())

    def _get_filter_params(self):
        cat_map = {"全部": "", "财务": "finance", "会议": "meeting", "任务": "task",
                   "文档": "document", "个人": "personal", "紧急": "urgent"}
        return {
            'category': cat_map.get(self.cat_combo.currentText(), ''),
            'date_from': self.date_from.date().toString('yyyy-MM-dd'),
            'date_to': self.date_to.date().toString('yyyy-MM-dd'),
            'urgent_only': self.urgent_only.isChecked(),
        }

    def _execute_search(self, keyword):
        filters = self._get_filter_params()
        total = count_messages()
        if total == 0:
            self.result_header.setText("数据库为空，请先同步消息")
            return

        results = []
        page_size = 500
        offset = 0
        while offset < total:
            batch = get_all_messages(limit=page_size, offset=offset)
            if not batch:
                break
            for m in batch:
                content = m.get('content', '')
                chat = m.get('chat', '')
                sender = m.get('sender', '')
                if keyword.lower() not in content.lower() and keyword.lower() not in chat.lower() and keyword.lower() not in sender.lower():
                    continue
                if filters['category'] and m.get('category', '') != filters['category']:
                    continue
                if filters['urgent_only'] and not m.get('is_urgent'):
                    continue
                time_str = m.get('time', '')
                if filters['date_from'] and time_str < filters['date_from']:
                    continue
                if filters['date_to'] and time_str[:10] > filters['date_to']:
                    continue
                results.append(m)
            offset += page_size

        self._display_results(keyword, results)

    def _display_results(self, keyword, results):
        while self.results_container.count() > 0:
            item = self.results_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        count = len(results)
        self.result_header.setText(f"\U0001f50d 搜索 \"{keyword}\" — 找到 {count} 条结果")

        if not results:
            empty = QLabel("未找到匹配的消息")
            empty.setStyleSheet("color: #666666; font-size: 13px; padding: 20px;")
            self.results_container.addWidget(empty)
            return

        for m in results[:50]:
            row = self._make_result_row(m)
            self.results_container.addWidget(row)

        if count > 50:
            more = QLabel(f"... 还有 {count - 50} 条结果未显示，请缩小搜索范围")
            more.setStyleSheet("color: #666666; font-size: 12px; padding: 8px;")
            self.results_container.addWidget(more)

    def _make_result_row(self, msg):
        row = QFrame()
        priority = msg.get('priority_level', 0)
        colors = {5: "#ef4444", 4: "#f97316", 3: "#f59e0b", 2: "#3b82f6", 1: "#6b7280", 0: "#9ca3af"}
        color = colors.get(priority, "#9ca3af")
        row.setStyleSheet(f"""
            QFrame {{
                background: #333333;
                border-radius: 8px;
                border-left: 3px solid {color};
                padding: 0;
            }}
        """)
        rl = QVBoxLayout(row)
        rl.setContentsMargins(12, 8, 12, 8)
        rl.setSpacing(4)

        header = QHBoxLayout()
        chat_lbl = QLabel(msg.get('chat', '')[:25])
        chat_lbl.setStyleSheet("color: #5b9bd5; font-size: 12px; font-weight: bold;")
        header.addWidget(chat_lbl)
        header.addStretch()
        time_lbl = QLabel(msg.get('time', ''))
        time_lbl.setStyleSheet("color: #666666; font-size: 11px;")
        header.addWidget(time_lbl)
        rl.addLayout(header)

        content = msg.get('content', '')[:100]
        content_lbl = QLabel(f"{msg.get('sender', '')}: {content}")
        content_lbl.setStyleSheet("color: #d0d0d0; font-size: 12px;")
        content_lbl.setWordWrap(True)
        rl.addWidget(content_lbl)

        return row
