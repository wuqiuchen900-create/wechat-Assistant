# app/tray_icon.py
import os
import time
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSlot, QTimer
from app.reminder_popup import ReminderPopup
from app.widgets.smart_popup import SmartPopup
from app.widgets.event_monitor import EventMonitorWindow
from app.main_window import MainWindow
from core.engine import MessageEngine
from core.reminder_manager import (
    init_reminders_table, add_reminder, get_pending_reminders,
    acknowledge_reminder, snooze_reminder, dismiss_reminder,
    count_pending_reminders
)
from core.smart_reminder import (
    get_pending_smart_reminders, acknowledge_smart_reminder,
    snooze_smart_reminder, dismiss_smart_reminder,
    count_pending_smart_reminders
)
from core.event_tracker import start_event_tracker, run_analysis_now
from debug_log import logger


class WeChatAssistantTray(QSystemTrayIcon):
    def __init__(self):
        super().__init__()

        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'resources', 'icon.png')
        if os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
        else:
            self.setIcon(QIcon())
        self.setToolTip("微信信息管家")

        init_reminders_table()

        self.main_window = MainWindow()

        self.engine = MessageEngine()
        self.engine.configure()
        QApplication.instance().engine = self.engine
        logger.info("[托盘] 开始连接信号...")
        self.engine.start()
        logger.info("[托盘] 引擎线程已启动")

        self.engine.sync_progress_signal.connect(self.main_window.update_sync_progress)
        self.engine.sync_finished_signal.connect(self.main_window.on_sync_finished)
        self.engine.new_messages_signal.connect(self.main_window.add_new_messages)
        self.engine.sync_worker_ready.connect(self._on_sync_worker_ready)
        self.engine.urgent_message_signal.connect(self.on_urgent_message)
        self.engine.reminder_signal.connect(self.on_urgent_message)
        logger.info("[托盘] 信号连接完成，启动引擎")

        self._active_popups = []

        self._event_monitor = EventMonitorWindow()
        self._event_monitor.navigate_to_event.connect(self._on_monitor_navigate)
        QApplication.instance()._event_monitor = self._event_monitor

        self._reminder_timer = QTimer()
        self._reminder_timer.timeout.connect(self._check_pending_reminders)
        self._reminder_timer.start(30000)

        QTimer.singleShot(5000, self._check_pending_reminders)

        start_event_tracker(interval_minutes=30)
        QTimer.singleShot(120000, lambda: run_analysis_now())

        self.menu = QMenu()
        self.menu.setStyleSheet("""
            QMenu {
                background-color: #333333;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 24px;
                color: #d0d0d0;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #3d4a5c;
                color: #5b9bd5;
            }
            QMenu::separator {
                height: 1px;
                background: #4a4a4a;
                margin: 4px 8px;
            }
        """)
        self.show_action = QAction("显示主面板")
        self.show_action.triggered.connect(self.show_main_window)
        self.menu.addAction(self.show_action)

        self.monitor_action = QAction("事件监控面板")
        self.monitor_action.triggered.connect(self._show_event_monitor)
        self.menu.addAction(self.monitor_action)

        self.menu.addSeparator()
        self.quit_action = QAction("退出")
        self.quit_action.triggered.connect(self.quit_app)
        self.menu.addAction(self.quit_action)

        self.setContextMenu(self.menu)
        self.activated.connect(self.on_tray_activated)

    def _on_sync_worker_ready(self, worker):
        logger.info("[托盘] 收到 sync_worker_ready，连接 worker 进度信号")
        worker.progress_signal.connect(self.main_window.update_sync_progress)

    def show_main_window(self):
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_main_window()

    @pyqtSlot(dict)
    def on_urgent_message(self, msg):
        if msg.get('is_genuine_urgent'):
            from core.smart_reminder import save_smart_reminder
            save_smart_reminder(msg)

    def _check_pending_reminders(self):
        try:
            pending = get_pending_smart_reminders()
            if not pending:
                return

            for reminder in pending:
                already_showing = any(
                    hasattr(p, 'reminder_id') and p.reminder_id == reminder['id']
                    for p in self._active_popups
                )
                if not already_showing:
                    self._show_smart_popup(reminder)
        except Exception as e:
            logger.error(f"[提醒检查] 错误: {e}")

    def _show_smart_popup(self, reminder_data):
        popup = SmartPopup(reminder_data)
        popup.acknowledged.connect(self._on_smart_acknowledged)
        popup.snoozed.connect(self._on_smart_snoozed)
        popup.dismissed.connect(self._on_smart_dismissed)
        popup.view_detail.connect(self._on_smart_view_detail)
        popup.show()
        self._active_popups.append(popup)

    def _on_smart_acknowledged(self, reminder_id):
        acknowledge_smart_reminder(reminder_id)
        self._cleanup_popup(reminder_id)
        logger.info(f"[智能提醒] 已确认处理 #{reminder_id}")

    def _on_smart_snoozed(self, reminder_id, minutes):
        snooze_smart_reminder(reminder_id, minutes)
        self._cleanup_popup(reminder_id)
        logger.info(f"[智能提醒] 已延时 #{reminder_id}，{minutes}分钟后再次提醒")

    def _on_smart_dismissed(self, reminder_id):
        dismiss_smart_reminder(reminder_id)
        self._cleanup_popup(reminder_id)
        logger.info(f"[智能提醒] 已忽略 #{reminder_id}")

    def _on_smart_view_detail(self, analysis):
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()
        self.main_window._switch_page(3)
        logger.info(f"[智能提醒] 查看详情 -> 事件追踪页面")

    def _cleanup_popup(self, reminder_id):
        self._active_popups = [
            p for p in self._active_popups
            if not (hasattr(p, 'reminder_id') and p.reminder_id == reminder_id)
        ]

    def _show_event_monitor(self):
        self._event_monitor.show()
        self._event_monitor.raise_()
        self._event_monitor.activateWindow()
        self._event_monitor.refresh_events()

    def _on_monitor_navigate(self, chat_name):
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()
        self.main_window._switch_page(3)
        logger.info(f"[事件监控] 导航到事件追踪页面，会话: {chat_name}")

    def quit_app(self):
        self._reminder_timer.stop()
        self.engine.stop()
        self.engine.wait(2000)
        self.main_window.close()
        self.hide()
        QApplication.instance().quit()
