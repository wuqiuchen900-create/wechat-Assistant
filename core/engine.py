# core/engine.py
from PyQt5.QtCore import QThread, pyqtSignal
from data.wechat_cli import get_sessions_list, get_history_since, get_unread_messages
from data.storage import init_db, save_messages_batch, get_message_count, is_db_initialized, update_sync_progress, get_all_messages
import time
from data.storage import save_messages_batch_fast

class MessageEngine(QThread):
    new_messages_signal = pyqtSignal(list)
    urgent_message_signal = pyqtSignal(dict)
    sync_progress_signal = pyqtSignal(int, int)  # 当前进度, 总数
    sync_finished_signal = pyqtSignal()          # 全量同步完成

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._poll_interval = 30
        self._known_message_ids = set()
        self._blacklist = []
        self._work_keywords = []
        self._urgent_keywords = []
        self._initial_sync = False
        self._last_ui_update = 0  # 是否需要首次全量同步

    def configure(self, poll_interval=30, blacklist=None):
        self._poll_interval = poll_interval
        self._blacklist = blacklist or []
        self._reload_keywords()
    def _reload_keywords(self):
        """从数据库重新加载关键词"""
        from data.storage import get_all_keywords
        self._work_keywords, self._urgent_keywords = get_all_keywords()
    def _make_message_id(self, msg):
        return f"{msg.get('chat','')}|{msg.get('sender','')}|{msg.get('time','')}|{msg.get('content','')[:30]}"

    def _is_blacklisted(self, msg):
        return msg.get('chat', '') in self._blacklist

    def _filter_and_tag(self, messages):
        result = []
        for msg in messages:
            if self._is_blacklisted(msg):
                continue
            content = msg.get('content', '')
            msg['is_urgent'] = any(kw in content for kw in self._urgent_keywords)
            msg['is_work'] = any(kw in content for kw in self._work_keywords)
            msg['matched_keywords'] = [kw for kw in self._work_keywords if kw in content]
            result.append(msg)
        return result

    def _do_full_sync(self):
        init_db()
        sessions = get_sessions_list(limit=200)
        total = len(sessions)
        batch_buffer = []
        BATCH_SIZE = 10

        for i, session in enumerate(sessions):
            if not self._running:
                break

            chat_name = session.get('chat', '')
            if not chat_name:
                continue

            msgs = get_history_since(chat_name, limit=50)
            if not msgs:
                continue

            is_group = session.get('is_group', False)
            for m in msgs:
                m['is_group'] = is_group
                m['username'] = session.get('username', '')  # 添加这行

            filtered = self._filter_and_tag(msgs)

            for msg in filtered:
                msg_id = self._make_message_id(msg)
                if msg_id not in self._known_message_ids:
                    self._known_message_ids.add(msg_id)
                    batch_buffer.append(msg)

            if len(batch_buffer) >= BATCH_SIZE * 5 or i == total - 1:
                if batch_buffer:
                    # 保存到数据库（用大事务快速写入）
                    save_messages_batch_fast(batch_buffer)
                    # 控制界面刷新频率
                    if time.time() - self._last_ui_update > 2.0:
                        self.new_messages_signal.emit(batch_buffer[:50])
                        self._last_ui_update = time.time()
                    batch_buffer.clear()

            # 记录该会话同步进度，防止下次启动重复全量同步
            if msgs:
                last_msg_time = msgs[-1].get('time', '')
                try:
                    import datetime
                    dt = datetime.datetime.strptime(last_msg_time, '%Y-%m-%d %H:%M')
                    last_ts = int(dt.timestamp())
                except:
                    last_ts = 0
                from data.storage import update_sync_progress
                update_sync_progress(chat_name, last_msg_time, last_ts)

            self.sync_progress_signal.emit(i + 1, total)
            time.sleep(0.2)

        self.sync_finished_signal.emit()

    def run(self):
        init_db()
        
        if not is_db_initialized():
            self._do_full_sync()
        
        # 从本地数据库加载所有缓存消息到界面
        from data.storage import get_all_messages
        cached = get_all_messages(limit=99999)
        if cached:
            self.new_messages_signal.emit(cached)
        # 后续增量轮询
        loop_count = 0
        while self._running:
            loop_count += 1             # ← 新加
            if loop_count % 5 == 0:     # ← 新加（每5轮刷新一次关键词）
                self._reload_keywords() # ← 新加            
            try:
                # 用未读消息做实时增量
                unread = get_unread_messages()
                filtered = self._filter_and_tag(unread)
                
                new_msgs, urgent_msgs = [], []
                for msg in filtered:
                    msg_id = self._make_message_id(msg)
                    if msg_id not in self._known_message_ids:
                        self._known_message_ids.add(msg_id)
                        new_msgs.append(msg)
                        if msg.get('is_urgent'):
                            urgent_msgs.append(msg)
                
                if new_msgs:
                    save_messages_batch_fast(new_msgs)
                    self.new_messages_signal.emit(new_msgs)
                for msg in urgent_msgs:
                    self.urgent_message_signal.emit(msg)
                    
            except Exception as e:
                print(f"[引擎错误] {e}")
            
            time.sleep(self._poll_interval)

    def stop(self):
        self._running = False