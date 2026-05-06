# core/engine.py
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from data.wechat_cli import get_new_messages
from data.storage import (
    init_db, get_message_count, get_all_messages,
    get_conn, save_messages_batch_with_conn, update_sync_progress,
    get_all_settings, get_all_keywords, get_all_blacklist, is_db_initialized
)
import time
from core.sync_worker import SyncWorker, IncrementalSyncWorker
from concurrent.futures import ThreadPoolExecutor
from data.storage import save_messages_batch_fast
from debug_log import logger

class MessageEngine(QThread):
    new_messages_signal = pyqtSignal(list)
    urgent_message_signal = pyqtSignal(dict)
    sync_progress_signal = pyqtSignal(int, int)
    sync_finished_signal = pyqtSignal(object)
    sync_error_signal = pyqtSignal(str)
    sync_worker_ready = pyqtSignal(object)  # 新增：告诉外界同步工作器已创建，把工作器对象传出去

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._poll_interval = 30
        self._known_message_ids = set()
        self._blacklist = []
        self._work_keywords = []
        self._urgent_keywords = []
        self._enable_full_sync = True
        self._write_pool = ThreadPoolExecutor(max_workers=2)
        self._last_ui_update = 0
        self._enable_popup = True

    def configure(self):
        """初始化数据库并加载所有设置"""
        init_db()
        settings = get_all_settings()
        self._poll_interval = int(settings.get('poll_interval', '30'))
        self._enable_full_sync = settings.get('enable_full_sync', '1') == '1'
        self._enable_popup = settings.get('enable_popup', '1') == '1'
        self._work_keywords, self._urgent_keywords = get_all_keywords()
        self._blacklist = get_all_blacklist()

    def _reload_keywords(self):
        self._work_keywords, self._urgent_keywords = get_all_keywords()

    def _reload_blacklist(self):
        self._blacklist = get_all_blacklist()

    def _reload_reminder_settings(self):
        settings = get_all_settings()
        self._enable_popup = settings.get('enable_popup', '1') == '1'

    def _make_message_id(self, msg):
        return f"{msg.get('chat','')}|{msg.get('sender','')}|{msg.get('time','')}|{msg.get('content','')[:30]}"

    def _is_blacklisted(self, msg):
        chat = msg.get('chat', '')
        return any(kw in chat for kw in self._blacklist if kw)

    def _filter_and_tag(self, messages):
        """快速过滤和打标签"""
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

    def run(self):
        logger.info("[引擎] 线程开始运行")
        """主引擎线程入口"""
        init_db()

        # ===== 快照恢复模式：如果已有缓存，通知界面恢复快照并跳过全量重新加载 =====
        if is_db_initialized():
            logger.info("[引擎] 数据库已初始化，发射快照信号 (-2,-2)")
            self.sync_progress_signal.emit(-2, -2)
        else:
            logger.info("[引擎] 数据库未初始化，跳过快照")
            total_cached = get_message_count()
            page_size = 100
            offset = 0
            while offset < total_cached:
                cached = get_all_messages(limit=99999)
                batch = cached[offset:offset + page_size]
                if batch:
                    tagged = self._filter_and_tag(batch)
                    self.new_messages_signal.emit(tagged)
                    time.sleep(0.05)
                offset += page_size

        # ===== 第二层：根据是否有缓存，选择同步策略 =====
        if self._enable_full_sync and not is_db_initialized():
            logger.info("[引擎] 进入全量同步")
            # 首次启动：全量同步（10个工人并行拉500个会话）
            self.sync_progress_signal.emit(-1, -1)
            self._sync_thread = QThread()
            self._sync_worker = SyncWorker()
            self.sync_worker_ready.emit(self._sync_worker)
            logger.info("[引擎] 已发射 sync_worker_ready")  # 新增：通知外界，工作器来了
            self._sync_worker.moveToThread(self._sync_thread)
            self._sync_worker.finished_callback = lambda: (
                logger.info("[引擎] worker 回调触发，转发 sync_finished_signal"),
                self.sync_finished_signal.emit(self._sync_worker.changed_chats if hasattr(self._sync_worker, 'changed_chats') else set())
            )
            self._sync_worker.messages_ready.connect(self._process_synced_messages)
            self._sync_thread.started.connect(self._sync_worker.do_full_sync)
            # 兜底：线程结束时，如果还没收到完成信号，就补发一次
            self._sync_thread.finished.connect(lambda: (
                logger.info("[引擎·兜底] 同步线程 finished，补发 sync_finished_signal"),
                print("[引擎·保底] 全量同步线程已结束，补发完成信号"),
                self.sync_finished_signal.emit()
            ))
            self._sync_thread.start()
            print("[引擎] 首次启动，执行全量同步...")
        else:
            logger.info("[引擎] 进入增量同步")
            # 后续启动：轻量增量同步
            self.sync_progress_signal.emit(-1, -1)
            self._sync_thread = QThread()
            self._sync_worker = IncrementalSyncWorker()
            self.sync_worker_ready.emit(self._sync_worker)  # 新增
            self._sync_worker.moveToThread(self._sync_thread)
            self._sync_worker.finished_callback = lambda: (
                logger.info("[引擎] worker 回调触发，转发 sync_finished_signal"),
                self.sync_finished_signal.emit(self._sync_worker.changed_chats if hasattr(self._sync_worker, 'changed_chats') else set())
            )
            self._sync_worker.messages_ready.connect(self._process_synced_messages)
            self._sync_thread.started.connect(self._sync_worker.do_incremental_sync)
            # 同样的兜底
            self._sync_thread.finished.connect(lambda: (
                print("[引擎·保底] 增量同步线程已结束，补发完成信号"),
                self.sync_finished_signal.emit()
            ))
            self._sync_thread.start()
            print("[引擎] 已有缓存，执行增量同步...")
        # ===== 第三层：轻量实时轮询 =====
        db_conn = get_conn()
        loop_count = 0
        while self._running:
            loop_count += 1
            if loop_count % 5 == 0:
                self._reload_keywords()
                self._reload_blacklist()
                self._reload_reminder_settings()
            try:
                new_msgs = []
                latest_msgs = get_new_messages()
                if latest_msgs:
                    filtered = self._filter_and_tag(latest_msgs)
                    new_count = save_messages_batch_with_conn(db_conn, filtered)
                    if new_count > 0:
                        for m in filtered:
                            mid = self._make_message_id(m)
                            if mid not in self._known_message_ids:
                                self._known_message_ids.add(mid)
                                new_msgs.append(m)
                    if new_msgs:
                        self._write_pool.submit(save_messages_batch_fast, new_msgs)
                        self.new_messages_signal.emit(new_msgs)
                    if self._enable_popup:
                        for m in filtered:
                            if m.get('is_urgent'):
                                self.urgent_message_signal.emit(m)
            except Exception as e:
                print(f"[实时轮询错误] {e}")
            time.sleep(self._poll_interval)
        # 退出清理
        self._sync_worker.stop()
        self._sync_thread.quit()
        self._sync_thread.wait()
        db_conn.close()
    def _process_synced_messages(self, messages):
        """接收后台同步的消息，打标签后发给界面"""
        tagged = self._filter_and_tag(messages)
        if tagged:
            self.new_messages_signal.emit(tagged)

    def stop(self):
        self._running = False
        self._write_pool.shutdown(wait=False)