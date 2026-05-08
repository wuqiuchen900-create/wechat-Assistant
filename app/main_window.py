# app/main_window.py
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QFrame, QSplitter,
                             QButtonGroup, QApplication, QStackedWidget)
from PyQt5.QtCore import Qt, pyqtSlot, QTimer
from PyQt5.QtGui import QFont
import time
from debug_log import logger
from app.widgets import ShimmerProgressBar, SessionListPanel, DetailPanel, StatsBar
from app.widgets.daily_brief import DailyBriefPanel
from app.widgets.history_search import HistorySearchPanel
from core.data_manager import count_messages, get_all_blacklist
from core.ai_search import AISearchEngine
from app.styles import GLOBAL_STYLE


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("微信信息管家")
        self.setMinimumSize(1050, 700)

        self.ai_engine = AISearchEngine()

        self.setStyleSheet(GLOBAL_STYLE)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._build_nav(main_layout)
        self._build_content(main_layout)

    def _build_nav(self, main_layout):
        self.nav = QFrame()
        self.nav.setObjectName("sideNav")
        nav_layout = QVBoxLayout(self.nav)
        nav_layout.setContentsMargins(10, 20, 10, 20)
        nav_layout.setSpacing(4)

        logo = QLabel("\U0001f4cb 信息管家")
        logo_font = QFont()
        logo_font.setPointSize(16)
        logo_font.setBold(True)
        logo.setFont(logo_font)
        logo.setStyleSheet("padding: 10px 14px; color: #e0e0e0;")
        nav_layout.addWidget(logo)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: #4a4a4a; max-height: 1px; margin: 8px 10px;")
        nav_layout.addWidget(sep)
        nav_layout.addSpacing(8)

        self.btn_realtime = QPushButton("\U0001f4e9  实时消息")
        self.btn_realtime.setObjectName("navBtn")
        self.btn_realtime.setCheckable(True)
        self.btn_realtime.setChecked(True)
        self.btn_report = QPushButton("\U0001f4ca  每日简报")
        self.btn_report.setObjectName("navBtn")
        self.btn_report.setCheckable(True)
        self.btn_history = QPushButton("\U0001f50d  历史检索")
        self.btn_history.setObjectName("navBtn")
        self.btn_history.setCheckable(True)
        self.btn_settings = QPushButton("\u2699\ufe0f  设置")
        self.btn_settings.setObjectName("navBtn")
        self.btn_settings.setCheckable(True)

        for btn in [self.btn_realtime, self.btn_report, self.btn_history, self.btn_settings]:
            nav_layout.addWidget(btn)
        nav_layout.addStretch()

        self.nav_group = QButtonGroup()
        self.nav_group.addButton(self.btn_realtime)
        self.nav_group.addButton(self.btn_report)
        self.nav_group.addButton(self.btn_history)
        self.nav_group.addButton(self.btn_settings)
        self.nav_group.setExclusive(True)

        self.btn_realtime.clicked.connect(lambda: self._switch_page(0))
        self.btn_report.clicked.connect(lambda: self._switch_page(1))
        self.btn_history.clicked.connect(lambda: self._switch_page(2))
        self.btn_settings.clicked.connect(self._open_settings)

        footer = QLabel("v0.6  \u00b7  本地运行")
        footer.setStyleSheet("color: #666666; font-size: 11px; padding: 10px;")
        nav_layout.addWidget(footer)
        main_layout.addWidget(self.nav)

    def _build_content(self, main_layout):
        right_outer = QVBoxLayout()
        right_outer.setContentsMargins(0, 0, 0, 0)
        right_outer.setSpacing(0)

        self.page_stack = QStackedWidget()

        self.realtime_page = self._build_realtime_page()
        self.brief_page = DailyBriefPanel()
        self.history_page = HistorySearchPanel()

        self.page_stack.addWidget(self.realtime_page)
        self.page_stack.addWidget(self.brief_page)
        self.page_stack.addWidget(self.history_page)

        right_outer.addWidget(self.page_stack)
        main_layout.addLayout(right_outer)

        self.history_page.search_requested.connect(self._on_ai_search)

    def _build_realtime_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        h_splitter = QSplitter(Qt.Horizontal)

        self.session_panel = SessionListPanel()
        self.stats_bar = StatsBar()
        self.sync_progress_bar = ShimmerProgressBar()
        self.sync_progress_bar.hide()
        self.status_bar = QLabel("就绪 | 等待新消息...")
        self.status_bar.setObjectName("statusBar")

        v_splitter = QSplitter(Qt.Vertical)
        v_splitter.setHandleWidth(3)
        v_splitter.addWidget(self.session_panel)
        v_splitter.addWidget(self.stats_bar)
        v_splitter.addWidget(self.sync_progress_bar)
        v_splitter.addWidget(self.status_bar)
        v_splitter.setSizes([370, 80, 6, 30])
        v_splitter.setStretchFactor(0, 5)
        v_splitter.setStretchFactor(1, 1)
        v_splitter.setStretchFactor(2, 0)
        v_splitter.setStretchFactor(3, 0)
        for i in range(4):
            v_splitter.setCollapsible(i, False)

        h_splitter.addWidget(v_splitter)

        self.detail_panel = DetailPanel()
        h_splitter.addWidget(self.detail_panel)
        h_splitter.setSizes([420, 400])

        layout.addWidget(h_splitter)

        self.session_panel.session_clicked.connect(self.detail_panel.show_session)
        self.session_panel.stats_updated.connect(self.stats_bar.update_stats)
        self.session_panel.status_changed.connect(self.status_bar.setText)

        return page

    def _switch_page(self, index):
        for btn in [self.btn_realtime, self.btn_report, self.btn_history, self.btn_settings]:
            btn.setChecked(False)
        [self.btn_realtime, self.btn_report, self.btn_history, self.btn_settings][index].setChecked(True)

        if index == 3:
            self._open_settings()
            return

        self.page_stack.setCurrentIndex(index)

        if index == 1:
            self.brief_page.refresh()

    def _open_settings(self):
        from app.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self)
        dialog.exec_()
        self.session_panel._refresh_blacklist_cache()
        self.session_panel._update_session_list()

    def _on_ai_search(self, keyword, filters):
        from core.data_manager import get_all_messages, count_messages
        total = count_messages()
        if total == 0:
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
                if filters.get('category') and m.get('category', '') != filters['category']:
                    continue
                if filters.get('urgent_only') and not m.get('is_urgent'):
                    continue
                results.append(m)
            offset += page_size

        result_text = self.ai_engine.search(keyword, results, use_local=True)

        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton
        dlg = QDialog(self)
        dlg.setWindowTitle(f"\U0001f916 AI 分析: {keyword}")
        dlg.setMinimumSize(550, 400)
        dlg.setStyleSheet("""
            QDialog { background: #333333; border-radius: 12px; }
            QTextEdit { border: 1px solid #4a4a4a; border-radius: 8px; padding: 12px; font-size: 13px; background: #2b2b2b; color: #d0d0d0; }
            QPushButton { background: #5b9bd5; color: white; border: none; border-radius: 8px; padding: 8px 20px; font-weight: bold; }
            QPushButton:hover { background: #4a8ac4; }
        """)
        dl = QVBoxLayout(dlg)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(result_text)
        dl.addWidget(te)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dlg.close)
        dl.addWidget(close_btn)
        dlg.exec_()

    @pyqtSlot(list)
    def add_new_messages(self, messages):
        self.session_panel.add_new_messages(messages)

    @pyqtSlot(int, int)
    def update_sync_progress(self, current, total):
        if current == -2 and total == -2:
            self.session_panel.restore_snapshot()
            self.status_bar.setText("就绪 | 正在从数据库重建内存...")
            QTimer.singleShot(50, self.session_panel.load_cached_messages)
            return
        if current == -1 and total == -1:
            self.status_bar.setText("正在同步历史消息...")
            self.sync_progress_bar.show()
        else:
            self.session_panel.set_sync_in_progress(True)
            self.sync_progress_bar.show()
            if total == -1:
                self.status_bar.setText(f"正在同步历史消息... {current}%")
            elif total > 0:
                percent = int(current / total * 100)
                self.status_bar.setText(f"正在同步历史消息... {percent}%")

    @pyqtSlot(object)
    def on_sync_finished(self, changed_chats=None):
        logger.info("[主窗口] on_sync_finished 被调用，准备隐藏进度条")
        self.sync_progress_bar.hide()
        self.sync_progress_bar.setVisible(False)
        QApplication.processEvents()
        self.status_bar.setText("就绪 | 清理并准备加载头像...")
        QApplication.processEvents()
        self.session_panel.on_sync_finished(changed_chats)

    def closeEvent(self, event):
        self.session_panel.save_snapshot()
        super().closeEvent(event)
