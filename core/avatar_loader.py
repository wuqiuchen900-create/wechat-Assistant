# core/avatar_loader.py
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QPixmap
from data.wechat_cli import get_contact_detail
import os
import threading
import requests
from debug_log import logger
from PyQt5.QtCore import Qt

AVATAR_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'message_data', 'avatars')


class AvatarLoadWorker(QThread):
    avatar_ready = pyqtSignal(str, QPixmap)

    def __init__(self):
        super().__init__()
        self._tasks = set()
        self._tasks_lock = threading.Lock()
        self._avatar_dir = None
        self._running = True
        self._id_map = {}
        self._head_imgs_index = {}

    def set_avatar_dir(self, path):
        self._avatar_dir = path
        self._build_head_imgs_index()

    def _build_head_imgs_index(self):
        self._head_imgs_index.clear()
        if not self._avatar_dir or not os.path.exists(self._avatar_dir):
            return
        wx_data_root = os.path.dirname(self._avatar_dir)
        search_dirs = [self._avatar_dir]
        alt_dir = os.path.join(wx_data_root, 'all_users', 'head_imgs') if wx_data_root else None
        if alt_dir and os.path.exists(alt_dir):
            search_dirs.append(alt_dir)

        for base_dir in search_dirs:
            for root, dirs, files in os.walk(base_dir):
                for fn in files:
                    if fn.endswith(('.jpg', '.png', '.jpeg')):
                        full_path = os.path.join(root, fn)
                        for part in fn.replace('.jpg', '').replace('.png', '').replace('.jpeg', '').split('_'):
                            if part and len(part) > 4:
                                self._head_imgs_index[part] = full_path

        logger.info(f"[AvatarWorker] 头像目录索引构建完成，共 {len(self._head_imgs_index)} 个文件")

    def load_id_map_from_db(self):
        if not os.path.exists(AVATAR_CACHE_DIR):
            return
        for fn in os.listdir(AVATAR_CACHE_DIR):
            if fn.endswith('.jpg'):
                username = fn[:-4]
                fp = os.path.join(AVATAR_CACHE_DIR, fn)
                self._id_map[username] = fp
        logger.info(f"[AvatarWorker] 从文件系统加载了 {len(self._id_map)} 条头像缓存")

    def add_tasks(self, usernames):
        with self._tasks_lock:
            self._tasks.update(usernames)

    def run(self):
        logger.info("[AvatarWorker] 工人线程已启动")
        self.load_id_map_from_db()
        os.makedirs(AVATAR_CACHE_DIR, exist_ok=True)

        while self._running:
            username = None
            with self._tasks_lock:
                if self._tasks:
                    username = self._tasks.pop()

            if username:
                pixmap = self._load_avatar(username)
                if pixmap:
                    self.avatar_ready.emit(username, pixmap)
                self.msleep(50)
            else:
                self.msleep(300)

    def _load_avatar(self, username):
        local_path = self._id_map.get(username) or os.path.join(AVATAR_CACHE_DIR, f"{username}.jpg")
        if os.path.exists(local_path):
            pix = QPixmap(local_path)
            if not pix.isNull():
                return pix.scaled(36, 36, transformMode=Qt.SmoothTransformation)

        if username in self._head_imgs_index:
            fp = self._head_imgs_index[username]
            pix = QPixmap(fp)
            if not pix.isNull():
                save_path = os.path.join(AVATAR_CACHE_DIR, f"{username}.jpg")
                try:
                    pix.save(save_path, 'JPG')
                    self._id_map[username] = save_path
                except Exception:
                    pass
                return pix.scaled(36, 36, transformMode=Qt.SmoothTransformation)

        try:
            detail = get_contact_detail(username)
            if detail and detail.get('avatar'):
                resp = requests.get(detail['avatar'], timeout=10)
                if resp.status_code == 200:
                    save_path = os.path.join(AVATAR_CACHE_DIR, f"{username}.jpg")
                    with open(save_path, 'wb') as f:
                        f.write(resp.content)
                    self._id_map[username] = save_path
                    pix = QPixmap(save_path)
                    if not pix.isNull():
                        return pix.scaled(36, 36, transformMode=Qt.SmoothTransformation)
        except Exception:
            pass
        return None

    def stop(self):
        self._running = False
        self.wait()
