# app/tray_icon.py
import os
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QIcon
from app.main_window import MainWindow

class WeChatAssistantTray(QSystemTrayIcon):
    def __init__(self):
        super().__init__()
        # 设置图标（使用我们准备的图标文件）
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'resources', 'icon.png')
        if os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
        else:
            # 如果没有图标文件，就用系统样式
            self.setIcon(QIcon())
        
        self.setToolTip("微信信息管家")
        
        # 主窗口
        self.main_window = MainWindow()
        
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
        
        # 双击托盘图标打开主面板
        self.activated.connect(self.on_tray_activated)
    
    def show_main_window(self):
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()
    
    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_main_window()
    
    def quit_app(self):
        self.main_window.close()
        self.hide()
        from PyQt5.QtWidgets import QApplication
        QApplication.instance().quit()