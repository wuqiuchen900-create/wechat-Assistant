# core/avatar_loader.py
from PyQt5.QtCore import QThread, pyqtSignal
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
        # 先尝试本地文件
        if self.avatar_dir:
            avatar_path = os.path.join(self.avatar_dir, f"{username}.jpg")
            if os.path.exists(avatar_path):
                pixmap = QPixmap(avatar_path)
                if not pixmap.isNull():
                    return pixmap.scaled(36, 36)

        # 再尝试网络下载
        try:
            detail = get_contact_detail(username)
            if detail and detail.get('avatar'):
                resp = requests.get(detail['avatar'], timeout=5)
                if resp.status_code == 200:
                    pixmap = QPixmap()
                    pixmap.loadFromData(resp.content)
                    return pixmap.scaled(36, 36)
        except:
            pass
        return None