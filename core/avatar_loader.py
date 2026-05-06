# core/avatar_loader.py
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QPixmap
from data.wechat_cli import get_contact_detail
import requests
import os


class AvatarLoader(QThread):
    """独立头像加载线程，不阻塞主界面"""
    avatar_ready = pyqtSignal(dict)  # {username: QPixmap or None}

    def __init__(self, avatar_cache, avatar_dir, usernames):
        super().__init__()
        self.avatar_cache = avatar_cache
        self.avatar_dir = avatar_dir
        self.usernames = usernames

    def run(self):
        result = {}
        for username in self.usernames:
            if username in self.avatar_cache:
                continue
            pixmap = self._load_avatar(username)
            self.avatar_cache[username] = pixmap
            result[username] = pixmap
        if result:
            self.avatar_ready.emit(result)

    def _load_avatar(self, username):
        # 1. 先尝试从本地文件加载（灵活匹配，不限定后缀）
        if self.avatar_dir and os.path.exists(self.avatar_dir):
            for filename in os.listdir(self.avatar_dir):
                if username in filename:
                    filepath = os.path.join(self.avatar_dir, filename)
                    pixmap = QPixmap(filepath)
                    if not pixmap.isNull():
                        return pixmap.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    else:
                        # 文件损坏，跳出循环去尝试网络下载
                        break

        # 2. 本地没找到，尝试从网络下载
        try:
            detail = get_contact_detail(username)
            if detail and detail.get('avatar'):
                resp = requests.get(detail['avatar'], timeout=5)
                if resp.status_code == 200:
                    pixmap = QPixmap()
                    pixmap.loadFromData(resp.content)
                    if not pixmap.isNull():
                        return pixmap.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        except:
            pass
        
        # 3. 都找不到，返回 None（界面会显示灰色圆圈）
        return None