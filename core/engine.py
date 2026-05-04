# core/engine.py
from PyQt5.QtCore import QThread, pyqtSignal
from data.wechat_cli import get_sessions_list, get_history_since, get_unread_messages
from data.storage import init_db, save_messages_batch, get_message_count, is_db_initialized, update_sync_progress, get_all_messages
import time

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
        self._initial_sync = False  # 是否需要首次全量同步

    def configure(self, poll_interval=30, blacklist=None, work_keywords=None, urgent_keywords=None):
        self._poll_interval = poll_interval
        self._blacklist = blacklist or []
        self._work_keywords = work_keywords or []
        self._urgent_keywords = urgent_keywords or []

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
        """首次全量同步：逐会话拉取历史，平稳不抢CPU"""
        init_db()
        sessions = get_sessions_list(limit=200)
        total = len(sessions)
        batch_buffer = []
        BATCH_SIZE = 10  # 每处理10个会话才更新一次界面
        
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
            
            filtered = self._filter_and_tag(msgs)
            
            # 找出新增的，加入缓冲区
            for msg in filtered:
                msg_id = self._make_message_id(msg)
                if msg_id not in self._known_message_ids:
                    self._known_message_ids.add(msg_id)
                    batch_buffer.append(msg)
            
            # 每处理 BATCH_SIZE 个会话，或最后一个会话时，才存入数据库并通知界面
            if len(batch_buffer) >= BATCH_SIZE * 5 or i == total - 1:
                if batch_buffer:
                    save_messages_batch(batch_buffer)
                    self.new_messages_signal.emit(batch_buffer[:50])  # 只发最近50条给界面，避免卡顿
                    batch_buffer.clear()
            
            # 更新进度
            self.sync_progress_signal.emit(i + 1, total)
            
            # 停顿，让CPU喘口气
            time.sleep(0.2)
        
        # 全量同步结束，发信号通知界面从数据库加载全部历史
        self.sync_finished_signal.emit()

    def run(self):
        init_db()
        
        # 首次全量同步
        if not is_db_initialized():
            self._do_full_sync()
        
        # 后续增量轮询
        while self._running:
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
                    save_messages_batch(new_msgs)
                    self.new_messages_signal.emit(new_msgs)
                for msg in urgent_msgs:
                    self.urgent_message_signal.emit(msg)
                    
            except Exception as e:
                print(f"[引擎错误] {e}")
            
            time.sleep(self._poll_interval)

    def stop(self):
        self._running = False