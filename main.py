# main.py
import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

# 确保项目根目录在 sys.path 中，方便导入自定义模块
sys.path.insert(0, os.path.dirname(__file__))

from app.tray_icon import WeChatAssistantTray

def main():
    # 高分辨率屏幕适配
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关掉主窗口不退出程序
    
    # 启动托盘主程序
    tray = WeChatAssistantTray()
    tray.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()