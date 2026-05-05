# core/sync_worker.py
import time
from PyQt5.QtCore import QObject, pyqtSignal
from data.wechat_cli import get_sessions_list, get_history_since
from data.storage import get_conn, save_messages_batch_with_conn, update_sync_progress

class SyncWorker(QObject):
    """独立的同步工作器，运行在子线程中，负责全量/增量同步"""
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal()
    messages_ready = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self._running = True

    def stop(self):
        self._running = False

    def do_full_sync(self):
        """执行全量同步：拉取所有会话的历史消息"""
        sessions = get_sessions_list(limit=300)
        total = len(sessions)
        db_conn = get_conn()
        
        for i, session in enumerate(sessions):
            if not self._running:
                break
            
            chat_name = session.get('chat', '')
            if not chat_name:
                continue
            
            # 1. 拉取数据
            msgs = get_history_since(chat_name, limit=20)
            if not msgs:
                continue
            
            # 2. 补充信息
            is_group = session.get('is_group', False)
            username = session.get('username', '')
            for m in msgs:
                m['is_group'] = is_group
                m['username'] = username
            
            # 3. 快速入库（不在此线程做UI标记）
            new_count = save_messages_batch_with_conn(db_conn, msgs)
            
            # 4. 更新同步进度
            if msgs:
                last_msg_time = msgs[-1].get('time', '')
                try:
                    import datetime
                    dt = datetime.datetime.strptime(last_msg_time, '%Y-%m-%d %H:%M')
                    last_ts = int(dt.timestamp())
                except:
                    last_ts = 0
                update_sync_progress(chat_name, last_msg_time, last_ts)
            
            # 5. 发送进度和消息
            self.progress_signal.emit(i + 1, total)
            self.messages_ready.emit(msgs)
            
            # 6. 温柔地跑，避免CPU猛冲
            time.sleep(0.3)
        
        db_conn.close()
        self.finished_signal.emit()