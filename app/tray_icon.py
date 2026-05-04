# app/tray_icon.py
import os
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSlot

from app.main_window import MainWindow
from core.engine import MessageEngine
from config import BLACKLIST, WORK_KEYWORDS, URGENT_KEYWORDS, POLL_INTERVAL


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
        self.engine.configure(
            poll_interval=POLL_INTERVAL,
            blacklist=BLACKLIST,
            work_keywords=WORK_KEYWORDS,
            urgent_keywords=URGENT_KEYWORDS
        )
        # 连接信号
        self.engine.new_messages_signal.connect(self.main_window.add_new_messages)
        self.engine.urgent_message_signal.connect(self.on_urgent_message)
        # 启动引擎
        self.engine.sync_progress_signal.connect(self.main_window.update_sync_progress)
        self.engine.sync_finished_signal.connect(self.main_window.on_sync_finished)
        self.engine.start()
        
        # 右键菜单
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
    
    def show_main_window(self):
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()
    
    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_main_window()
    
    @pyqtSlot(dict)
    def on_urgent_message(self, msg):
        """处理紧急消息：弹窗提醒"""
        chat = msg.get('chat', '')
        content = msg.get('content', '')
        self.showMessage(
            f"🔴 紧急消息 - {chat}",
            content[:100],
            QSystemTrayIcon.Warning,
            5000
        )
    
    def quit_app(self):
        self.engine.stop()
        self.engine.wait(2000)  # 等待引擎线程结束
        self.main_window.close()
        self.hide()
        QApplication.instance().quit()