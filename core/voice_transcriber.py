# core/voice_transcriber.py
import os
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from debug_log import logger

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'message_data', 'cache.db')
VOICE_CACHE_DIR = os.path.join(BASE_DIR, 'message_data', 'voice_cache')

_local = threading.local()


def _get_conn():
    if not hasattr(_local, 'conn') or _local.conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return _local.conn


def init_voice_table():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS voice_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_id TEXT NOT NULL UNIQUE,
            chat TEXT DEFAULT '',
            sender TEXT DEFAULT '',
            time TEXT DEFAULT '',
            timestamp INTEGER DEFAULT 0,
            duration INTEGER DEFAULT 0,
            voice_xml TEXT DEFAULT '',
            transcribed_text TEXT DEFAULT '',
            transcription_model TEXT DEFAULT '',
            transcription_confidence REAL DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now'))
        );
        CREATE INDEX IF NOT EXISTS idx_voice_status ON voice_messages(status);
        CREATE INDEX IF NOT EXISTS idx_voice_chat ON voice_messages(chat);
        CREATE INDEX IF NOT EXISTS idx_voice_time ON voice_messages(timestamp);
    """)
    conn.commit()
    os.makedirs(VOICE_CACHE_DIR, exist_ok=True)


def save_voice_message(msg):
    conn = _get_conn()
    msg_id = f"{msg.get('chat','')}|{msg.get('sender','')}|{msg.get('time','')}|voice|{msg.get('voice_duration',0)}"
    try:
        conn.execute("""
            INSERT OR IGNORE INTO voice_messages
            (msg_id, chat, sender, time, timestamp, duration, voice_xml, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            msg_id,
            msg.get('chat', ''),
            msg.get('sender', ''),
            msg.get('time', ''),
            msg.get('timestamp', 0),
            msg.get('voice_duration', 0),
            msg.get('voice_xml', '')
        ))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"[语音] 保存失败: {e}")
        return False


def get_pending_voice_messages(limit=50):
    conn = _get_conn()
    rows = conn.execute("""
        SELECT * FROM voice_messages
        WHERE status = 'pending' AND transcribed_text = ''
        ORDER BY timestamp ASC
        LIMIT ?
    """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def update_voice_transcription(msg_id, text, model_name, confidence=0.0):
    conn = _get_conn()
    conn.execute("""
        UPDATE voice_messages
        SET transcribed_text = ?, transcription_model = ?,
            transcription_confidence = ?, status = 'done',
            updated_at = strftime('%s', 'now')
        WHERE msg_id = ?
    """, (text, model_name, confidence, msg_id))
    conn.commit()


def mark_voice_failed(msg_id):
    conn = _get_conn()
    conn.execute("""
        UPDATE voice_messages SET status = 'failed', updated_at = strftime('%s', 'now')
        WHERE msg_id = ?
    """, (msg_id,))
    conn.commit()


def get_voice_by_chat(chat, limit=100):
    conn = _get_conn()
    rows = conn.execute("""
        SELECT * FROM voice_messages
        WHERE chat = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (chat, limit)).fetchall()
    return [dict(r) for r in rows]


def count_pending_voices():
    conn = _get_conn()
    row = conn.execute(
        "SELECT COUNT(*) FROM voice_messages WHERE status = 'pending' AND transcribed_text = ''"
    ).fetchone()
    return row[0] if row else 0


class BaseVoiceTranscriber(ABC):
    """语音转文字模型抽象基类，所有模型实现需继承此类"""

    @abstractmethod
    def model_name(self):
        """返回模型名称"""
        pass

    @abstractmethod
    def transcribe(self, voice_xml, duration):
        """转写语音，返回 (text, confidence)"""
        pass

    @abstractmethod
    def is_available(self):
        """检查模型是否可用"""
        pass


class PlaceholderTranscriber(BaseVoiceTranscriber):
    """占位转写器，在未配置实际模型时使用"""

    @property
    def model_name(self):
        return "placeholder"

    def transcribe(self, voice_xml, duration):
        return (f"[语音消息 {duration}秒 - 待转写]", 0.0)

    def is_available(self):
        return True


class VoiceTranscriptionManager:
    """语音转写管理器，管理转写队列和模型切换"""

    def __init__(self):
        init_voice_table()
        self._transcriber = PlaceholderTranscriber()
        self._running = False
        self._batch_size = 10

    def set_transcriber(self, transcriber):
        if not isinstance(transcriber, BaseVoiceTranscriber):
            raise TypeError("转写器必须继承 BaseVoiceTranscriber")
        self._transcriber = transcriber
        logger.info(f"[语音转写] 已切换到模型: {transcriber.model_name}")

    def get_transcriber(self):
        return self._transcriber

    def process_pending(self):
        pending = get_pending_voice_messages(self._batch_size)
        if not pending:
            return 0

        count = 0
        for voice in pending:
            try:
                text, confidence = self._transcriber.transcribe(
                    voice.get('voice_xml', ''),
                    voice.get('duration', 0)
                )
                update_voice_transcription(
                    voice['msg_id'], text,
                    self._transcriber.model_name, confidence
                )
                count += 1
            except Exception as e:
                logger.error(f"[语音转写] 转写失败 {voice['msg_id']}: {e}")
                mark_voice_failed(voice['msg_id'])

        if count > 0:
            logger.info(f"[语音转写] 本批次完成 {count} 条")
        return count

    def transcribe_single(self, voice_msg):
        try:
            text, confidence = self._transcriber.transcribe(
                voice_msg.get('voice_xml', ''),
                voice_msg.get('duration', 0)
            )
            update_voice_transcription(
                voice_msg['msg_id'], text,
                self._transcriber.model_name, confidence
            )
            return text
        except Exception as e:
            logger.error(f"[语音转写] 单条转写失败: {e}")
            mark_voice_failed(voice_msg['msg_id'])
            return None


_voice_manager = None


def get_voice_manager():
    global _voice_manager
    if _voice_manager is None:
        _voice_manager = VoiceTranscriptionManager()
    return _voice_manager
