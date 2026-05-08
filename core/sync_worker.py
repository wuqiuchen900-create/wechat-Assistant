# core/sync_worker.py
import time
import datetime
from PyQt5.QtCore import QObject, pyqtSignal
from data.wechat_cli import get_sessions_list, get_history_since
from core.data_manager import _get_conn as get_conn, commit_messages as save_messages_batch_with_conn, update_sync_progress, get_last_sync_time
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
    - 每个会话拉最近 50000 条消息
    - 10 个工人并行拉取
    - 每完成 50 个会话，批量写入一次数据库并通知界面
    """
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal()
    messages_ready = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.changed_chats = set()
        self._running = True
        self.finished_callback = None

    def stop(self):
        self._running = False

    def do_full_sync(self):
        sessions = get_sessions_list(limit=500)
        total = len(sessions)
        logger.info(f"[SyncWorker] 开始全量同步，共 {total} 个会话")
        
        BATCH_SIZE = 50
        synced_chats = set()

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
            batch_msgs = []  # 当前批次的消息
            
            for future in as_completed(futures):
                if not self._running:
                    break
                completed += 1
                chat_name = futures[future]
                msgs = future.result()
                
                if msgs:
                    last_msg_time = msgs[0].get('time', '')
                    normalized_time = _normalize_time(last_msg_time)
                    try:
                        last_ts = int(datetime.datetime.strptime(normalized_time, '%Y-%m-%d %H:%M').timestamp())
                    except:
                        last_ts = 0

                    update_sync_progress(chat_name, normalized_time, last_ts)
                    self.changed_chats.add(chat_name)
                    synced_chats.add(chat_name)

                    batch_msgs.extend(msgs)
                
                # 每完成 BATCH_SIZE 个会话，或者全部完成，就写库并发信号
                if completed % BATCH_SIZE == 0 or completed == total:
                    if batch_msgs:
                        save_messages_batch_with_conn(batch_msgs)          # 不再传 db_conn
                        self.messages_ready.emit(batch_msgs)
                        logger.info(f"[SyncWorker] 批次写入 {len(batch_msgs)} 条消息 (已完成 {completed}/{total})")
                        batch_msgs = []
                
                self.progress_signal.emit(completed, total)
                
                if completed == 1 or completed == total or completed % max(1, total // 5) == 0:
                    percent = int(completed / total * 100)
                    logger.info(f"[SyncWorker] 进度 {completed}/{total} ({percent}%)")
                
                time.sleep(0.05)

        logger.info(f"[SyncWorker] 全量同步完成, completed={completed}, total={total}")
        self._fill_missing_sessions(sessions, synced_chats)
        self.finished_signal.emit()
        if self.finished_callback:
            self.finished_callback()

    def _fill_missing_sessions(self, all_sessions, synced_chats):
        missing = [s for s in all_sessions if s.get('chat', '') not in synced_chats]
        if not missing:
            return
        logger.info(f"[SyncWorker] 发现 {len(missing)} 个遗漏会话，开始补齐...")
        for session in missing:
            chat_name = session.get('chat', '')
            if not chat_name:
                continue
            msgs = self._fetch_one_chat(
                chat_name,
                session.get('is_group', False),
                session.get('username', '')
            )
            if msgs:
                last_msg_time = msgs[0].get('time', '')
                normalized_time = _normalize_time(last_msg_time)
                try:
                    last_ts = int(datetime.datetime.strptime(normalized_time, '%Y-%m-%d %H:%M').timestamp())
                except:
                    last_ts = 0
                update_sync_progress(chat_name, normalized_time, last_ts)
                self.changed_chats.add(chat_name)
                save_messages_batch_with_conn(msgs)
                self.messages_ready.emit(msgs)
                logger.info(f"[SyncWorker] 补齐遗漏会话 {chat_name}: +{len(msgs)}条")
            time.sleep(0.3)

    def _fetch_one_chat(self, chat_name, is_group, username):
        from data.wechat_cli import run_wechat_cli, _parse_history_text

        max_retries = 3
        for attempt in range(max_retries):
            try:
                cmd = f'history "{chat_name}" --limit 50000'
                data = run_wechat_cli(cmd, timeout=90)
                if isinstance(data, dict):
                    raw_messages = data.get('messages', [])
                    if isinstance(raw_messages, list):
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
                        if result:
                            return result

                if attempt < max_retries - 1:
                    wait = (attempt + 1) * 3
                    logger.warning(f"[SyncWorker] {chat_name} 拉取失败，{wait}秒后重试 ({attempt + 1}/{max_retries})")
                    time.sleep(wait)
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = (attempt + 1) * 3
                    logger.warning(f"[SyncWorker] {chat_name} 拉取异常: {e}，{wait}秒后重试 ({attempt + 1}/{max_retries})")
                    time.sleep(wait)

        logger.error(f"[SyncWorker] {chat_name} 拉取最终失败，已重试 {max_retries} 次")
        return []


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
        self.changed_chats = set()
        self._running = True

    def stop(self):
        self._running = False

    def do_incremental_sync(self):
        sessions = get_sessions_list(limit=500)
        total = len(sessions)
        db_conn = get_conn()
        synced_chats = set()
        logger.info(f"[IncWorker] 开始增量同步，共 {total} 个会话")
        
        for i, session in enumerate(sessions):
            if not self._running:
                break

            chat_name = session.get('chat', '')
            if not chat_name:
                continue

            last_time = get_last_sync_time(chat_name)
            
            # 先筛选：用 sessions 自带的时间戳对比
            session_last_msg_time = session.get('time', '')
            if last_time and session_last_msg_time:
                if session_last_msg_time <= last_time:
                    continue
            
            # 加 1 秒偏移避免边界重复
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

            save_messages_batch_with_conn(msgs)

            if msgs:
                logger.info(f"[IncWorker·拉取] {chat_name}: +{len(msgs)}条, "
                            f"首条时间={msgs[0].get('time','?')}, "
                            f"末条时间={msgs[-1].get('time','?')}, "
                            f"传入的last_time={last_time}")
                
                last_msg_time = msgs[0].get('time', '')
                normalized_time = _normalize_time(last_msg_time)
                try:
                    last_ts = int(datetime.datetime.strptime(normalized_time, '%Y-%m-%d %H:%M').timestamp())
                except:
                    last_ts = 0
                update_sync_progress(chat_name, normalized_time, last_ts)
            
            self.changed_chats.add(chat_name)
            synced_chats.add(chat_name)
            self.progress_signal.emit(i + 1, total)
            self.messages_ready.emit(msgs)
            time.sleep(0.1)

        db_conn.close()
        self._fill_missing_sessions(sessions, synced_chats)
        logger.info(f"[IncWorker] 增量同步完成, 即将发射 finished_signal")
        self.finished_signal.emit()
        logger.info("[IncWorker] finished_signal 已发射")
        if self.finished_callback:
            self.finished_callback()

    def _fill_missing_sessions(self, all_sessions, synced_chats):
        missing = [s for s in all_sessions if s.get('chat', '') not in synced_chats]
        if not missing:
            return
        logger.info(f"[IncWorker] 发现 {len(missing)} 个遗漏会话，开始补齐...")
        for session in missing:
            chat_name = session.get('chat', '')
            if not chat_name:
                continue
            msgs = get_history_since(chat_name, limit=50000)
            if msgs:
                is_group = session.get('is_group', False)
                username = session.get('username', '')
                for m in msgs:
                    m['is_group'] = is_group
                    m['username'] = username
                last_msg_time = msgs[0].get('time', '')
                normalized_time = _normalize_time(last_msg_time)
                try:
                    last_ts = int(datetime.datetime.strptime(normalized_time, '%Y-%m-%d %H:%M').timestamp())
                except:
                    last_ts = 0
                update_sync_progress(chat_name, normalized_time, last_ts)
                self.changed_chats.add(chat_name)
                save_messages_batch_with_conn(msgs)
                self.messages_ready.emit(msgs)
                logger.info(f"[IncWorker] 补齐遗漏会话 {chat_name}: +{len(msgs)}条")
            time.sleep(0.3)