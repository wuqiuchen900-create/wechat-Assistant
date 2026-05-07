# core/reminder_manager.py
import sqlite3
import os
import time
import threading
from debug_log import logger

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'message_data', 'cache.db')

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


def init_reminders_table():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_id TEXT NOT NULL UNIQUE,
            chat TEXT DEFAULT '',
            sender TEXT DEFAULT '',
            content TEXT DEFAULT '',
            time TEXT DEFAULT '',
            source_person TEXT DEFAULT '',
            deadline TEXT DEFAULT '',
            category TEXT DEFAULT '',
            priority_level INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            snooze_until REAL DEFAULT 0,
            acknowledged INTEGER DEFAULT 0,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now'))
        );
        CREATE INDEX IF NOT EXISTS idx_reminders_status ON reminders(status);
        CREATE INDEX IF NOT EXISTS idx_reminders_priority ON reminders(priority_level);
    """)
    conn.commit()


def add_reminder(msg):
    conn = _get_conn()
    msg_id = f"{msg.get('chat','')}|{msg.get('sender','')}|{msg.get('time','')}|{msg.get('content','')[:40]}"
    try:
        conn.execute("""
            INSERT OR REPLACE INTO reminders
            (msg_id, chat, sender, content, time, source_person, deadline, category, priority_level, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            msg_id,
            msg.get('chat', ''),
            msg.get('sender', ''),
            msg.get('content', ''),
            msg.get('time', ''),
            msg.get('source_person', ''),
            msg.get('deadline', ''),
            msg.get('category', ''),
            msg.get('priority_level', 0)
        ))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"[提醒] 添加失败: {e}")
        return False


def get_pending_reminders():
    conn = _get_conn()
    now = time.time()
    rows = conn.execute("""
        SELECT * FROM reminders
        WHERE status = 'pending'
        AND acknowledged = 0
        AND (snooze_until = 0 OR snooze_until <= ?)
        ORDER BY priority_level DESC, created_at DESC
    """, (now,)).fetchall()
    return [dict(r) for r in rows]


def get_all_reminders(limit=100):
    conn = _get_conn()
    rows = conn.execute("""
        SELECT * FROM reminders
        ORDER BY priority_level DESC, created_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def acknowledge_reminder(reminder_id):
    conn = _get_conn()
    conn.execute("""
        UPDATE reminders SET acknowledged = 1, status = 'done', updated_at = strftime('%s', 'now')
        WHERE id = ?
    """, (reminder_id,))
    conn.commit()


def snooze_reminder(reminder_id, minutes):
    conn = _get_conn()
    snooze_until = time.time() + minutes * 60
    conn.execute("""
        UPDATE reminders SET snooze_until = ?, updated_at = strftime('%s', 'now')
        WHERE id = ?
    """, (snooze_until, reminder_id))
    conn.commit()


def dismiss_reminder(reminder_id):
    conn = _get_conn()
    conn.execute("""
        UPDATE reminders SET status = 'dismissed', acknowledged = 1, updated_at = strftime('%s', 'now')
        WHERE id = ?
    """, (reminder_id,))
    conn.commit()


def count_pending_reminders():
    conn = _get_conn()
    now = time.time()
    row = conn.execute("""
        SELECT COUNT(*) FROM reminders
        WHERE status = 'pending' AND acknowledged = 0
        AND (snooze_until = 0 OR snooze_until <= ?)
    """, (now,)).fetchone()
    return row[0] if row else 0


def has_reminder_for_msg(msg_id):
    conn = _get_conn()
    row = conn.execute("SELECT id FROM reminders WHERE msg_id = ?", (msg_id,)).fetchone()
    return row is not None
