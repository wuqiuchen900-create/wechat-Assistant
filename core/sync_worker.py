# core/sync_worker.py
import time
import datetime
from PyQt5.QtCore import QObject, pyqtSignal
from data.wechat_cli import get_sessions_list, get_history_since
from data.storage import get_conn, save_messages_batch_with_conn, update_sync_progress, get_last_sync_time


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
        self._running = True

    def stop(self):
        self._running = False

    def do_full_sync(self):
        from concurrent.futures import ThreadPoolExecutor, as_completed

        sessions = get_sessions_list(limit=500)
        total = len(sessions)

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
                     # 【加这行日志】打印每个会话实际拉取的消息数量
                    print(f"[SyncWorker] 会话 {chat_name} 拉取到 {len(msgs)} 条消息")
                    # 【补上】写入同步进度，否则下次启动无法识别已完成初始化
                    last_msg_time = msgs[-1].get('time', '')
                    normalized_time = _normalize_time(last_msg_time)
                    try:
                        dt = datetime.datetime.strptime(normalized_time, '%Y-%m-%d %H:%M')
                        last_ts = int(dt.timestamp())
                    except:
                        last_ts = 0
                    update_sync_progress(chat_name, normalized_time, last_ts)
                    # 写入数据库
                    db_conn = get_conn()
                    save_messages_batch_with_conn(db_conn, msgs)
                    db_conn.close()
                    # 发送消息信号
                    self.messages_ready.emit(msgs)

                    # 【关键】写入该会话最后一条消息的时间，用于增量同步
                    last_msg_time = msgs[-1].get('time', '')
                    normalized_time = _normalize_time(last_msg_time)
                    try:
                        dt = datetime.datetime.strptime(normalized_time, '%Y-%m-%d %H:%M')
                        last_ts = int(dt.timestamp())
                    except:
                        last_ts = 0
                    update_sync_progress(
                        chat_name,
                        normalized_time,
                        last_ts
                    )

                # 发进度信号
                self.progress_signal.emit(completed, total)
                time.sleep(0.1)

        self.finished_signal.emit()

    def _fetch_one_chat(self, chat_name, is_group, username):
        """拉取单个会话的历史消息（在子线程中执行）"""
        from data.wechat_cli import run_wechat_cli, _parse_history_text

        cmd = f'history "{chat_name}" --limit 300'
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
        self._running = True

    def stop(self):
        self._running = False

    def do_incremental_sync(self):
        sessions = get_sessions_list(limit=500)
        total = len(sessions)
        db_conn = get_conn()

        for i, session in enumerate(sessions):
            if not self._running:
                break

            chat_name = session.get('chat', '')
            if not chat_name:
                continue

            # 从数据库获取上次同步时间
            last_time = get_last_sync_time(chat_name)

            # 只拉取该时间之后的新消息
            msgs = get_history_since(chat_name, start_time=last_time, limit=50)
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
                last_msg_time = msgs[-1].get('time', '')
                normalized_time = _normalize_time(last_msg_time)
                try:
                    dt = datetime.datetime.strptime(normalized_time, '%Y-%m-%d %H:%M')
                    last_ts = int(dt.timestamp())
                except:
                    last_ts = 0
                update_sync_progress(chat_name, normalized_time, last_ts)

            self.progress_signal.emit(i + 1, total)
            self.messages_ready.emit(msgs)
            time.sleep(0.1)

        db_conn.close()
        self.finished_signal.emit()