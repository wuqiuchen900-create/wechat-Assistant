# app/widgets/session_list.py
import os
import time
import datetime
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView, QApplication
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap
from debug_log import logger
from core.avatar_loader import AvatarLoadWorker
from core.data_manager import count_messages, get_all_messages, get_all_blacklist, save_snapshot, load_snapshot
from app.delegates.avatar import AvatarDelegate


class SessionListPanel(QListWidget):
    session_clicked = pyqtSignal(dict)
    stats_updated = pyqtSignal(int, int, int, int)
    status_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.itemClicked.connect(self._on_item_clicked)

        self.session_data = {}
        self.all_messages_list = []
        self.msg_count = 0
        self._blacklist_cache = []
        self._sync_in_progress = False
        self._last_ui_refresh = 0

        self.avatar_cache = {}
        self._pending_avatar_loaders = []

        from data.wechat_cli import get_wechat_data_dir
        self.wx_data_dir, self.wxid = get_wechat_data_dir()
        if self.wx_data_dir:
            head_imgs = os.path.join(os.path.dirname(self.wx_data_dir), 'all_users', 'head_imgs')
            self.avatar_dir = head_imgs if os.path.exists(head_imgs) else None
        else:
            self.avatar_dir = None

        self.avatar_worker = AvatarLoadWorker()
        self.avatar_worker.set_avatar_dir(self.avatar_dir)
        self.avatar_worker.avatar_ready.connect(self._on_avatar_worker_done)
        self.avatar_worker.start()

        self.avatar_delegate = AvatarDelegate(self.avatar_cache)
        self.setItemDelegate(self.avatar_delegate)

        self._snapshot_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'message_data', 'snapshot.json'
        )

    def _on_avatar_worker_done(self, username, pixmap):
        if not pixmap or pixmap.isNull():
            return
        self.avatar_cache[username] = pixmap
        self.viewport().update()
        for i in range(self.count()):
            item = self.item(i)
            if item and item.data(Qt.UserRole + 1) == username:
                self.update(self.indexFromItem(item))

    def _load_avatars_if_needed(self):
        if not self.avatar_worker:
            return
        tasks = set()
        first_visible = self.indexAt(self.rect().topLeft()).row()
        last_visible = self.indexAt(self.rect().bottomLeft()).row()
        for i in range(max(0, first_visible), min(self.count(), last_visible + 1)):
            item = self.item(i)
            if item:
                username = item.data(Qt.UserRole + 1)
                if username and username not in self.avatar_cache:
                    tasks.add(username)
        if tasks:
            self.avatar_worker.add_tasks(tasks)

    def _collect_all_avatars(self):
        if not self.avatar_dir:
            return
        usernames = set()
        for msg in self.all_messages_list:
            u = msg.get('username', '')
            if u and u not in self.avatar_cache:
                usernames.add(u)
        if usernames:
            logger.info(f"[头像加载] 收集到 {len(usernames)} 个待加载头像")
            self.avatar_worker.add_tasks(usernames)

    def _parse_time(self, time_str):
        if not time_str:
            return 0
        try:
            if time_str[:4].isdigit() and len(time_str) >= 16:
                dt = datetime.datetime.strptime(time_str[:16], '%Y-%m-%d %H:%M')
            else:
                dt = datetime.datetime.strptime(time_str, '%m-%d %H:%M')
                dt = dt.replace(year=datetime.date.today().year)
            return dt.timestamp()
        except:
            try:
                dt = datetime.datetime.strptime(time_str, '%m-%d %H:%M')
                return dt.replace(year=datetime.datetime.now().year).timestamp()
            except:
                try:
                    today = datetime.date.today()
                    parts = time_str.split(':')
                    hour = int(parts[0])
                    minute = int(parts[1])
                    second = int(parts[2]) if len(parts) > 2 else 0
                    dt = datetime.datetime(today.year, today.month, today.day, hour, minute, second)
                    return dt.timestamp()
                except:
                    return 0

    def _shorten_name(self, name, max_len):
        return name if len(name) <= max_len else name[:max_len - 2] + '..'

    def _make_message_id(self, msg):
        return f"{msg.get('chat','')}|{msg.get('sender','')}|{msg.get('time','')}|{msg.get('content','')[:30]}"

    def _refresh_blacklist_cache(self):
        self._blacklist_cache = get_all_blacklist()

    def _update_session_list(self):
        self.clear()
        self.all_messages_list.sort(key=lambda m: self._parse_time(m.get('time', '')), reverse=True)
        blacklist = getattr(self, '_blacklist_cache', [])

        chat_last_msg = {}
        for msg in self.all_messages_list:
            chat = msg.get('chat', '')
            if any(kw in chat for kw in blacklist if kw):
                continue
            time_ts = self._parse_time(msg.get('time', ''))
            if chat not in chat_last_msg or time_ts > chat_last_msg[chat][0]:
                chat_last_msg[chat] = (time_ts, msg)

        sorted_chats = sorted(chat_last_msg.items(), key=lambda kv: kv[1][0], reverse=True)

        for chat, (ts, last_msg) in sorted_chats:
            sender = last_msg.get('sender', '')
            content = last_msg.get('content', '')
            time_str = last_msg.get('time', '')
            display_name = self._shorten_name(chat, 18)
            display = f"{time_str}  {display_name}"
            if sender:
                display += f"  ({sender})"
            display += f"  : {content[:40]}"

            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, chat)
            username = last_msg.get('username', '')
            item.setData(Qt.UserRole + 1, username)
            if last_msg.get('is_urgent'):
                item.setForeground(Qt.red)
            elif last_msg.get('is_work'):
                item.setForeground(Qt.darkBlue)
            self.addItem(item)

    def _refresh_changed_sessions(self, changed_chats):
        if not changed_chats:
            return
        for chat in changed_chats:
            msgs = [m for m in self.all_messages_list if m.get('chat') == chat]
            if not msgs:
                continue
            latest_msg = max(msgs, key=lambda x: self._parse_time(x.get('time', '')))
            sender = latest_msg.get('sender', '')
            content = latest_msg.get('content', '')
            time_str = latest_msg.get('time', '')
            display_name = self._shorten_name(chat, 18)
            display = f"{time_str}  {display_name}"
            if sender:
                display += f"  ({sender})"
            display += f"  : {content[:40]}"

            found = False
            for i in range(self.count()):
                item = self.item(i)
                if item and item.data(Qt.UserRole) == chat:
                    item.setText(display)
                    self.takeItem(i)
                    self.insertItem(0, item)
                    found = True
                    break

            if not found:
                item = QListWidgetItem(display)
                item.setData(Qt.UserRole, chat)
                username = latest_msg.get('username', '')
                item.setData(Qt.UserRole + 1, username)
                if latest_msg.get('is_urgent'):
                    item.setForeground(Qt.red)
                elif latest_msg.get('is_work'):
                    item.setForeground(Qt.darkBlue)
                self.insertItem(0, item)

    def _on_item_clicked(self, item):
        chat = item.data(Qt.UserRole)
        msgs = [m for m in self.all_messages_list if m.get('chat') == chat]
        msgs.sort(key=lambda x: self._parse_time(x.get('time', '')))

        if msgs:
            latest = msgs[-1]
            time_str = latest.get('time', '')
            sender = latest.get('sender', '')
            content = latest.get('content', '')
            display = f"{time_str}  {self._shorten_name(chat, 18)}"
            if sender:
                display += f"  ({sender})"
            display += f"  : {content[:40]}"
            item.setText(display)

        self.session_clicked.emit({'chat': chat, 'messages': msgs})

    def add_new_messages(self, messages):
        existing_ids = {self._make_message_id(m) for m in self.all_messages_list}
        today_count = 0
        urgent_count = 0
        if not hasattr(self, '_last_ui_refresh'):
            self._last_ui_refresh = 0
        need_refresh = (time.time() - self._last_ui_refresh) > 2.0

        for msg in messages:
            mid = self._make_message_id(msg)
            if mid in existing_ids:
                continue
            existing_ids.add(mid)
            self.msg_count += 1
            chat = msg.get('chat', '未知')
            time_str = msg.get('time', '')
            new_ts = self._parse_time(time_str)

            if chat not in self.session_data:
                self.session_data[chat] = {'last_msg': msg, 'count': 0, 'last_ts': new_ts}
            else:
                old_ts = self.session_data[chat].get('last_ts', 0)
                if new_ts >= old_ts:
                    self.session_data[chat]['last_msg'] = msg
                    self.session_data[chat]['last_ts'] = new_ts

            self.session_data[chat]['count'] += 1
            self.all_messages_list.append(msg)

            if msg.get('is_urgent'):
                urgent_count += 1
            if time_str.startswith(time.strftime('%Y-%m-%d')):
                today_count += 1

        active_count = len(self.session_data)
        self.stats_updated.emit(today_count, active_count, urgent_count, self.msg_count)

        if messages and not self._sync_in_progress:
            self.status_changed.emit(f"最新: {messages[-1].get('content', '')[:40]}...")

        if need_refresh:
            changed = {m.get('chat') for m in messages if m.get('chat')}
            self._refresh_changed_sessions(changed)
            self._last_ui_refresh = time.time()

    def load_cached_messages(self):
        self.all_messages_list.clear()
        self.session_data.clear()
        self.msg_count = 0
        total = count_messages()
        if total == 0:
            return

        logger.info(f"[快照恢复] 正在从数据库加载 {total} 条消息...")
        page_size = 500
        offset = 0

        while offset < total:
            batch = get_all_messages(limit=page_size, offset=offset)
            if not batch:
                break
            for msg in batch:
                self.all_messages_list.append(msg)
                chat = msg.get('chat', '')
                time_str = msg.get('time', '')
                new_ts = self._parse_time(time_str)
                if chat not in self.session_data:
                    self.session_data[chat] = {'last_msg': msg, 'count': 0, 'last_ts': new_ts}
                else:
                    old_ts = self.session_data[chat].get('last_ts', 0)
                    if new_ts >= old_ts:
                        self.session_data[chat]['last_msg'] = msg
                        self.session_data[chat]['last_ts'] = new_ts
                self.session_data[chat]['count'] += 1
                self.msg_count += 1
            offset += page_size
            QApplication.processEvents()

        logger.info(f"[内存重建] 加载完成，当前内存总量: {self.msg_count}")
        today_count = sum(1 for m in self.all_messages_list if m.get('time', '').startswith(time.strftime('%Y-%m-%d')))
        urgent_count = sum(1 for m in self.all_messages_list if m.get('is_urgent'))
        self.stats_updated.emit(today_count, len(self.session_data), urgent_count, self.msg_count)

        self._update_session_list()
        self._collect_all_avatars()

    def restore_snapshot(self):
        data = load_snapshot()
        if not data:
            return False
        scroll_pos = 0
        for item_data in data:
            text = item_data.get('text', '')
            chat = item_data.get('chat', '')
            username = item_data.get('username', '')
            scroll_pos = item_data.get('scroll_pos', 0)
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, chat)
            item.setData(Qt.UserRole + 1, username)
            self.addItem(item)
        self.verticalScrollBar().setValue(scroll_pos)
        return True

    def save_snapshot(self):
        save_snapshot(self)

    def clear_all(self):
        self.clear()
        self.session_data.clear()
        self.all_messages_list.clear()
        self.msg_count = 0
        self._blacklist_cache = []
        self._blacklist_cache = get_all_blacklist()
        self.stats_updated.emit(0, 0, 0, 0)
        self.status_changed.emit("列表已清空 | 等待新消息...")

    def on_sync_finished(self, changed_chats=None):
        logger.info("[SessionList] on_sync_finished 被调用")
        self._sync_in_progress = False
        if changed_chats:
            QTimer.singleShot(200, lambda: self._refresh_changed_sessions(changed_chats))
        else:
            QTimer.singleShot(200, self._update_session_list)
        QTimer.singleShot(1000, self._on_sync_cleanup)

    def _on_sync_cleanup(self):
        db_count = count_messages()
        if db_count > 0 and len(self.all_messages_list) < db_count * 0.8:
            logger.info(f"[同步后清理] 内存({len(self.all_messages_list)})与数据库({db_count})差异较大，重新加载")
            self.load_cached_messages()
        elif not self.all_messages_list:
            self.load_cached_messages()
        else:
            self.msg_count = len(self.all_messages_list)

        self.stats_updated.emit(
            sum(1 for m in self.all_messages_list if m.get('time', '').startswith(time.strftime('%Y-%m-%d'))),
            len(self.session_data),
            sum(1 for m in self.all_messages_list if m.get('is_urgent')),
            self.msg_count
        )
        self.status_changed.emit(f"就绪 | 缓存消息: {self.msg_count} 条")
        self._collect_all_avatars()
        self.save_snapshot()
        logger.info(f"[同步后清理] 当前内存消息总数: {self.msg_count}")

    def set_sync_in_progress(self, val):
        self._sync_in_progress = val
