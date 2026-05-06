# core/sync_worker.py
import time
import datetime
from PyQt5.QtCore import QObject, pyqtSignal
from data.wechat_cli import get_sessions_list, get_history_since
from data.storage import get_conn, save_messages_batch_with_conn, update_sync_progress, get_last_sync_time
from debug_log import logger
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime as dt, timedelta
def _normalize_time(time_str):
    """
    把微信返回的各种时间格式统一转成 '2026-05-05 21:38' 标准格式
    """
    if not time_str:
        return datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

    # 已经带完整日期（如 '2026-05-05 21:38'）
    try:
        if len(time_str) >= 16 and time_str[:4].isdigit():
            dt = datetime.datetime.strptime(time_str[:16], '%Y-%m-%d %H:%M')
            return dt.strftime('%Y-%m-%d %H:%M')
    except:
        pass

    # 只有月-日 时:分（如 '05-05 18:07'）
    try:
        dt = datetime.datetime.strptime(time_str, '%m-%d %H:%M')
        dt = dt.replace(year=datetime.datetime.now().year)
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        pass
    # 只有时间（如 '21:52:19' 或 '21:52'）
    try:
        now = datetime.datetime.now()
        parts = time_str.split(':')
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) > 2 else 0
        dt = datetime.datetime(now.year, now.month, now.day, hour, minute, second)
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        pass

    # 实在解析不了，用当前时间
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M')


class SyncWorker(QObject):
    """
    首次全量同步工作器
    - 拉取 500 个会话
    - 每个会话拉最近 300 条消息
    - 10 个工人并行拉取
    - 拉完后把每个会话的最后消息时间写入 sync_progress
    """
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal()
    messages_ready = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.silent_mode = True   # 全量同步时不发送消息信号
        self.changed_chats = set()  # 收集本次同步有变化的会话
        self._running = True
        self.finished_callback = None
    def stop(self):
        self._running = False

    def do_full_sync(self):
        sessions = get_sessions_list(limit=500)
        total = len(sessions)
        logger.info(f"[SyncWorker] 开始全量同步，共 {total} 个会话")
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {}
            for session in sessions:
                chat_name = session.get('chat', '')
                if not chat_name:
                    continue
                future = executor.submit(
                    self._fetch_one_chat,
                    chat_name,
                    session.get('is_group', False),
                    session.get('username', '')
                )
                futures[future] = chat_name

            completed = 0
            for future in as_completed(futures):
                if not self._running:
                    break
                completed += 1
                msgs = future.result()
                if msgs: 
                    last_msg_time = msgs[0].get('time', '')
                    normalized_time = _normalize_time(last_msg_time)
                    try:
                        dt = datetime.datetime.strptime(normalized_time, '%Y-%m-%d %H:%M')
                        last_ts = int(dt.timestamp())
                    except:
                        last_ts = 0
                    sync_chat_name = msgs[0].get('chat', '')
                    update_sync_progress(sync_chat_name,normalized_time,last_ts)
                    # 写入数据库
                    db_conn = get_conn()
                    save_messages_batch_with_conn(db_conn, msgs)
                    db_conn.close()
                    # 发送消息信号
                    if not self.silent_mode:
                        self.messages_ready.emit(msgs)
                    
                    # 【关键】写入该会话最后一条消息的时间，用于增量同步
                    last_msg_time = msgs[0].get('time', '')
                    normalized_time = _normalize_time(last_msg_time)
                    try:
                        dt = datetime.datetime.strptime(normalized_time, '%Y-%m-%d %H:%M')
                        last_ts = int(dt.timestamp())
                    except:
                        last_ts = 0
                    update_sync_progress(sync_chat_name,normalized_time,last_ts)
                                # 每完成 20% 或最后一个时打印一次进度
                if completed == 1 or completed == total or completed % max(1, total // 5) == 0:
                    percent = int(completed / total * 100)
                    logger.info(f"[SyncWorker] 进度 {completed}/{total} ({percent}%)")
                # 发进度信号
                self.progress_signal.emit(completed, total)
                time.sleep(0.1)
        logger.info(f"[SyncWorker] 全量同步完成, completed={completed}, total={total}, 即将发射 finished_signal")
        logger.info(f"[SyncWorker] 全量同步结束，处理完成")
        self.finished_signal.emit()
        logger.info("[SyncWorker] finished_signal 已发射")
        if self.finished_callback:
            self.finished_callback()
    def _fetch_one_chat(self, chat_name, is_group, username):
        """拉取单个会话的历史消息（在子线程中执行）"""
        from data.wechat_cli import run_wechat_cli, _parse_history_text

        cmd = f'history "{chat_name}" --limit 50000'
        data = run_wechat_cli(cmd)
        if not isinstance(data, dict):
            return []

        raw_messages = data.get('messages', [])
        if not isinstance(raw_messages, list):
            return []

        result = []
        for msg_text in raw_messages:
            if not isinstance(msg_text, str):
                continue
            parsed = _parse_history_text(msg_text)
            if parsed:
                parsed['chat'] = chat_name
                parsed['is_group'] = is_group
                parsed['username'] = username
                result.append(parsed)
        return result


class IncrementalSyncWorker(QObject):
    """
    增量同步工作器（后续启动时使用）
    - 遍历所有会话
    - 只拉取上次同步时间之后的新消息
    - 轻量快速
    """
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal()
    messages_ready = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.changed_chats = set()  # 收集本次同步有变化的会话
        self._running = True

    def stop(self):
        self._running = False

    def do_incremental_sync(self):
        sessions = get_sessions_list(limit=500)
        total = len(sessions)
        db_conn = get_conn()
        logger.info(f"[IncWorker] 开始增量同步，共 {total} 个会话")  # ← 紧接在后
        for i, session in enumerate(sessions):
            if not self._running:
                break

            chat_name = session.get('chat', '')
            if not chat_name:
                continue

            # 从数据库获取上次同步时间
            last_time = get_last_sync_time(chat_name)
            # === 新增：先筛选，再同步 ===
            # sessions 列表自带该会话最后一条消息的时间
            session_last_msg_time = session.get('time', '')
            if last_time and session_last_msg_time:
                # 如果微信端的最后消息时间不晚于我们记录的时间，跳过
                if session_last_msg_time <= last_time:
                    continue  # 没有新消息，不调 wechat-cli         
            time_after = None
            if last_time:
                try:
                    time_after = (dt.strptime(last_time, '%Y-%m-%d %H:%M') + timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M')
                except:
                    time_after = last_time
            msgs = get_history_since(chat_name, start_time=time_after)
            if not msgs:
                continue

            is_group = session.get('is_group', False)
            username = session.get('username', '')
            for m in msgs:
                m['is_group'] = is_group
                m['username'] = username

            # 写入数据库
            save_messages_batch_with_conn(db_conn, msgs)

            # 更新同步进度
            if msgs:
                logger.info(f"[IncWorker·拉取] {chat_name}: +{len(msgs)}条, "
                f"首条时间={msgs[0].get('time','?')}, "
                f"末条时间={msgs[-1].get('time','?')}, "
                f"传入的last_time={last_time}")
                last_msg_time = msgs[0].get('time', '')
                normalized_time = _normalize_time(last_msg_time)
                try:
                    dt = datetime.datetime.strptime(normalized_time, '%Y-%m-%d %H:%M')
                    last_ts = int(dt.timestamp())
                except:
                    last_ts = 0
                sync_chat_name = msgs[0].get('chat', '')
                update_sync_progress(sync_chat_name,normalized_time,last_ts)
            self.changed_chats.add(chat_name)
            completed = i + 1
            if completed == 1 or completed == total or completed % max(1, total // 5) == 0:
                percent = int(completed / total * 100)
                logger.info(f"[IncWorker] 进度 {completed}/{total} ({percent}%)")
            self.progress_signal.emit(i + 1, total)
            self.messages_ready.emit(msgs)
            time.sleep(0.1)

        db_conn.close()
        logger.info(f"[IncWorker] 增量同步完成, 即将发射 finished_signal")
        self.finished_signal.emit()
        logger.info("[IncWorker] finished_signal 已发射")
        if self.finished_callback:
            self.finished_callback()