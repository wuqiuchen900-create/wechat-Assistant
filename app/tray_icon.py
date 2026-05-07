# app/tray_icon.py
import os
import time
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSlot, QTimer
from app.reminder_popup import ReminderPopup
from app.main_window import MainWindow
from core.engine import MessageEngine
from core.reminder_manager import (
    init_reminders_table, add_reminder, get_pending_reminders,
    acknowledge_reminder, snooze_reminder, dismiss_reminder,
    count_pending_reminders
)
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

        self._reminder_timer = QTimer()
        self._reminder_timer.timeout.connect(self._check_pending_reminders)
        self._reminder_timer.start(30000)

        QTimer.singleShot(5000, self._check_pending_reminders)

        self.menu = QMenu()
        self.show_action = QAction("显示主面板")
        self.show_action.triggered.connect(self.show_main_window)
        self.menu.addAction(self.show_action)

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
        priority = msg.get('priority_level', 0)
        if priority >= 3:
            add_reminder(msg)

    def _check_pending_reminders(self):
        try:
            pending = get_pending_reminders()
            if not pending:
                return

            for reminder in pending:
                already_showing = any(
                    hasattr(p, 'reminder_id') and p.reminder_id == reminder['id']
                    for p in self._active_popups
                )
                if not already_showing:
                    self._show_reminder_popup(reminder)
        except Exception as e:
            logger.error(f"[提醒检查] 错误: {e}")

    def _show_reminder_popup(self, reminder_data):
        popup = ReminderPopup(reminder_data)
        popup.acknowledged.connect(self._on_reminder_acknowledged)
        popup.snoozed.connect(self._on_reminder_snoozed)
        popup.dismissed.connect(self._on_reminder_dismissed)
        popup.show_popup()
        self._active_popups.append(popup)

    def _on_reminder_acknowledged(self, reminder_id):
        acknowledge_reminder(reminder_id)
        self._cleanup_popup(reminder_id)
        logger.info(f"[提醒] 已确认处理 #{reminder_id}")

    def _on_reminder_snoozed(self, reminder_id, minutes):
        snooze_reminder(reminder_id, minutes)
        self._cleanup_popup(reminder_id)
        logger.info(f"[提醒] 已延时 #{reminder_id}，{minutes}分钟后再次提醒")

    def _on_reminder_dismissed(self, reminder_id):
        dismiss_reminder(reminder_id)
        self._cleanup_popup(reminder_id)
        logger.info(f"[提醒] 已忽略 #{reminder_id}")

    def _cleanup_popup(self, reminder_id):
        self._active_popups = [
            p for p in self._active_popups
            if not (hasattr(p, 'reminder_id') and p.reminder_id == reminder_id)
        ]

    def quit_app(self):
        self._reminder_timer.stop()
        self.engine.stop()
        self.engine.wait(2000)
        self.main_window.close()
        self.hide()
        QApplication.instance().quit()
