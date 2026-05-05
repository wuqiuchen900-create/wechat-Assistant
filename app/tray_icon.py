# app/tray_icon.py
import os
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSlot, QTimer
from app.reminder_popup import ReminderPopup
from app.main_window import MainWindow
from core.engine import MessageEngine


class WeChatAssistantTray(QSystemTrayIcon):
    def __init__(self):
        super().__init__()
        
        # 图标
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'resources', 'icon.png')
        if os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
        else:
            self.setIcon(QIcon())
        self.setToolTip("微信信息管家")
        
        # 主窗口
        self.main_window = MainWindow()
        
        # 消息引擎
        self.engine = MessageEngine()
        self.engine.configure()
        # 连接信号
        self.engine.new_messages_signal.connect(self.main_window.add_new_messages)
        self.engine.urgent_message_signal.connect(self.on_urgent_message)
        # 启动引擎
        self.engine.sync_progress_signal.connect(self.main_window.update_sync_progress)
        self.engine.sync_finished_signal.connect(self.main_window.on_sync_finished)
        self.engine.start()
        
        # 延迟连接 SyncWorker 的进度信号到主窗口，确保 SyncWorker 已创建
        QTimer.singleShot(1000, self._connect_sync_progress)

        # 右键菜单（只创建一次）
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

    def _connect_sync_progress(self):
        if hasattr(self.engine, '_sync_worker'):
            self.engine._sync_worker.progress_signal.connect(self.main_window.update_sync_progress)
            self.engine._sync_worker.finished_signal.connect(self.main_window.on_sync_finished)
            print("[tray] 成功连接 SyncWorker 信号到主窗口")
        else:
            print("[tray] 1秒后仍未找到 _sync_worker，再等1秒")
            QTimer.singleShot(500, self._connect_sync_progress)
    
    def show_main_window(self):
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()
    
    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_main_window()
    
    @pyqtSlot(dict)
    def on_urgent_message(self, msg):
        """处理紧急消息：弹出置顶提醒窗口"""
        self.popup = ReminderPopup(msg)
        self.popup.show_popup()
    
    def quit_app(self):
        self.engine.stop()
        self.engine.wait(2000)  # 等待引擎线程结束
        self.main_window.close()
        self.hide()
        QApplication.instance().quit()