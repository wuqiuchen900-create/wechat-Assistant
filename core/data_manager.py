# core/data_manager.py
import sqlite3
import os
import json
import threading
from debug_log import logger

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'message_data', 'cache.db')
SNAPSHOT_PATH = os.path.join(BASE_DIR, 'message_data', 'snapshot.json')
AVATAR_CACHE_DIR = os.path.join(BASE_DIR, 'message_data', 'avatars')

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


def init_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            chat TEXT NOT NULL,
            sender TEXT DEFAULT '',
            content TEXT DEFAULT '',
            time TEXT DEFAULT '',
            timestamp INTEGER DEFAULT 0,
            is_group INTEGER DEFAULT 0,
            is_urgent INTEGER DEFAULT 0,
            is_work INTEGER DEFAULT 0,
            matched_keywords TEXT DEFAULT '',
            username TEXT DEFAULT '',
            source_person TEXT DEFAULT '',
            deadline TEXT DEFAULT '',
            category TEXT DEFAULT '',
            priority_level INTEGER DEFAULT 0,
            created_at REAL DEFAULT (strftime('%s', 'now'))
        );
        CREATE TABLE IF NOT EXISTS sync_progress (
            chat TEXT PRIMARY KEY,
            last_sync_time TEXT DEFAULT '',
            last_timestamp INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL UNIQUE,
            category TEXT DEFAULT 'work',
            enabled INTEGER DEFAULT 1,
            created_at REAL DEFAULT (strftime('%s', 'now'))
        );
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT '',
            updated_at REAL DEFAULT (strftime('%s', 'now'))
        );
        CREATE TABLE IF NOT EXISTS blacklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at REAL DEFAULT (strftime('%s', 'now'))
        );
        CREATE TABLE IF NOT EXISTS avatar_cache (
            username TEXT PRIMARY KEY,
            file_path TEXT DEFAULT '',
            mtime REAL DEFAULT 0,
            updated_at REAL DEFAULT (strftime('%s', 'now'))
        );
        CREATE INDEX IF NOT EXISTS idx_messages_time ON messages(timestamp);
        CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat);
        CREATE INDEX IF NOT EXISTS idx_sync_chat ON sync_progress(chat);
    """)

    try:
        conn.execute("ALTER TABLE messages ADD COLUMN username TEXT DEFAULT ''")
    except:
        pass
    try:
        conn.execute("ALTER TABLE messages ADD COLUMN source_person TEXT DEFAULT ''")
    except:
        pass
    try:
        conn.execute("ALTER TABLE messages ADD COLUMN deadline TEXT DEFAULT ''")
    except:
        pass
    try:
        conn.execute("ALTER TABLE messages ADD COLUMN category TEXT DEFAULT ''")
    except:
        pass
    try:
        conn.execute("ALTER TABLE messages ADD COLUMN priority_level INTEGER DEFAULT 0")
    except:
        pass
    conn.commit()


# ========== 消息存取 ==========

def commit_messages(messages):
    if not messages:
        return 0
    conn = _get_conn()
    ids = [f"{m.get('chat','')}|{m.get('sender','')}|{m.get('time','')}|{m.get('content','')[:40]}" for m in messages]
    placeholders = ','.join(['?'] * len(ids))
    existing = set()
    try:
        rows = conn.execute(f"SELECT id FROM messages WHERE id IN ({placeholders})", ids).fetchall()
        existing = {r[0] for r in rows}
    except:
        pass

    new_msgs, new_ids = [], []
    for m, mid in zip(messages, ids):
        if mid not in existing:
            new_msgs.append(m)
            new_ids.append(mid)
    if not new_msgs:
        return 0

    count = 0
    try:
        conn.execute("BEGIN TRANSACTION")
        for m, mid in zip(new_msgs, new_ids):
            conn.execute("""
                INSERT OR IGNORE INTO messages
                (id, chat, sender, content, time, timestamp, is_group, is_urgent, is_work, matched_keywords, username, source_person, deadline, category, priority_level)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                mid, m.get('chat', ''), m.get('sender', ''), m.get('content', ''),
                m.get('time', ''), m.get('timestamp', 0),
                1 if m.get('is_group') else 0,
                1 if m.get('is_urgent') else 0,
                1 if m.get('is_work') else 0,
                ','.join(m.get('matched_keywords', [])),
                m.get('username', ''),
                m.get('source_person', ''),
                m.get('deadline', ''),
                m.get('category', ''),
                m.get('priority_level', 0)
            ))
            count += 1
        conn.execute("COMMIT")
    except:
        conn.execute("ROLLBACK")
    return count


def get_all_messages(limit=1000, offset=0):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT chat, sender, content, time, timestamp, is_group, is_urgent, is_work, matched_keywords, username, source_person, deadline, category, priority_level FROM messages ORDER BY timestamp ASC LIMIT ? OFFSET ?",
        (limit, offset)
    ).fetchall()
    return [{
        'chat': r[0], 'sender': r[1], 'content': r[2], 'time': r[3],
        'timestamp': r[4], 'is_group': bool(r[5]), 'is_urgent': bool(r[6]),
        'is_work': bool(r[7]), 'matched_keywords': r[8].split(',') if r[8] else [],
        'username': r[9] or '', 'source_person': r[10] or '',
        'deadline': r[11] or '', 'category': r[12] or '',
        'priority_level': r[13] or 0
    } for r in rows]


def count_messages():
    conn = _get_conn()
    row = conn.execute("SELECT COUNT(*) FROM messages").fetchone()
    return row[0] if row else 0


def get_messages_by_chat(chat, limit=200):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT chat, sender, content, time, timestamp, is_group, is_urgent, is_work, matched_keywords, username, source_person, deadline, category, priority_level FROM messages WHERE chat=? ORDER BY timestamp DESC LIMIT ?",
        (chat, limit)
    ).fetchall()
    return [{
        'chat': r[0], 'sender': r[1], 'content': r[2], 'time': r[3],
        'timestamp': r[4], 'is_group': bool(r[5]), 'is_urgent': bool(r[6]),
        'is_work': bool(r[7]), 'matched_keywords': r[8].split(',') if r[8] else [],
        'username': r[9] or '', 'source_person': r[10] or '',
        'deadline': r[11] or '', 'category': r[12] or '',
        'priority_level': r[13] or 0
    } for r in rows]


def get_urgent_messages(limit=50):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT chat, sender, content, time, timestamp, is_group, is_urgent, is_work, matched_keywords, username, source_person, deadline, category, priority_level FROM messages WHERE is_urgent=1 OR priority_level>=3 ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    ).fetchall()
    return [{
        'chat': r[0], 'sender': r[1], 'content': r[2], 'time': r[3],
        'timestamp': r[4], 'is_group': bool(r[5]), 'is_urgent': bool(r[6]),
        'is_work': bool(r[7]), 'matched_keywords': r[8].split(',') if r[8] else [],
        'username': r[9] or '', 'source_person': r[10] or '',
        'deadline': r[11] or '', 'category': r[12] or '',
        'priority_level': r[13] or 0
    } for r in rows]


def update_message_meta(msg_id, source_person=None, deadline=None, category=None, priority_level=None):
    conn = _get_conn()
    fields, values = [], []
    if source_person is not None:
        fields.append("source_person=?")
        values.append(source_person)
    if deadline is not None:
        fields.append("deadline=?")
        values.append(deadline)
    if category is not None:
        fields.append("category=?")
        values.append(category)
    if priority_level is not None:
        fields.append("priority_level=?")
        values.append(priority_level)
    if not fields:
        return
    values.append(msg_id)
    conn.execute(f"UPDATE messages SET {','.join(fields)} WHERE id=?", values)
    conn.commit()


# ========== 同步进度 ==========

def get_last_sync_time(chat):
    conn = _get_conn()
    row = conn.execute("SELECT last_sync_time FROM sync_progress WHERE chat=?", (chat,)).fetchone()
    return row[0] if row else None


def update_sync_progress(chat, last_time, last_ts):
    conn = _get_conn()
    conn.execute("INSERT OR REPLACE INTO sync_progress (chat, last_sync_time, last_timestamp) VALUES (?,?,?)",
                 (chat, last_time, last_ts))
    conn.commit()


def is_db_initialized():
    return count_messages() > 0


# ========== 黑名单 ==========

def get_all_blacklist():
    conn = _get_conn()
    rows = conn.execute("SELECT name FROM blacklist ORDER BY name").fetchall()
    return [r[0] for r in rows]


def add_blacklist(name):
    conn = _get_conn()
    try:
        conn.execute("INSERT OR IGNORE INTO blacklist (name) VALUES (?)", (name,))
        conn.commit()
    except:
        pass


def delete_blacklist(name):
    conn = _get_conn()
    conn.execute("DELETE FROM blacklist WHERE name=?", (name,))
    conn.commit()


# ========== 关键词 ==========

def get_all_keywords():
    conn = _get_conn()
    work = [r[0] for r in conn.execute("SELECT keyword FROM keywords WHERE category='work' AND enabled=1").fetchall()]
    urgent = [r[0] for r in conn.execute("SELECT keyword FROM keywords WHERE category='urgent' AND enabled=1").fetchall()]
    return work, urgent


def add_keyword(keyword, category='work'):
    conn = _get_conn()
    try:
        conn.execute("INSERT OR IGNORE INTO keywords (keyword, category) VALUES (?, ?)", (keyword, category))
        conn.commit()
    except:
        pass


def delete_keyword(keyword):
    conn = _get_conn()
    conn.execute("DELETE FROM keywords WHERE keyword = ?", (keyword,))
    conn.commit()


def toggle_keyword(keyword, enabled):
    conn = _get_conn()
    conn.execute("UPDATE keywords SET enabled = ? WHERE keyword = ?", (1 if enabled else 0, keyword))
    conn.commit()


# ========== 设置 ==========

def get_all_settings():
    conn = _get_conn()
    rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    settings = {r[0]: r[1] for r in rows}
    defaults = {'poll_interval': '30', 'enable_full_sync': '1', 'enable_popup': '1'}
    for k, v in defaults.items():
        if k not in settings:
            settings[k] = v
    return settings


def save_setting(key, value):
    conn = _get_conn()
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?,?,strftime('%s','now'))", (key, value))
    conn.commit()


# ========== 头像缓存 ==========

def get_cached_avatar_path(username):
    conn = _get_conn()
    row = conn.execute("SELECT file_path FROM avatar_cache WHERE username=?", (username,)).fetchone()
    if row and row[0] and os.path.exists(row[0]):
        return row[0]
    return None


def save_avatar_cache(username, file_path):
    conn = _get_conn()
    conn.execute("INSERT OR REPLACE INTO avatar_cache (username, file_path, updated_at) VALUES (?,?,strftime('%s','now'))",
                 (username, file_path))
    conn.commit()


# ========== 快照 ==========

def save_snapshot(session_list):
    snapshot = []
    for i in range(session_list.count()):
        item = session_list.item(i)
        if item:
            snapshot.append({
                'text': item.text(),
                'chat': item.data(1),
                'username': item.data(2) or '',
                'scroll_pos': session_list.verticalScrollBar().value()
            })
    if snapshot:
        os.makedirs(os.path.dirname(SNAPSHOT_PATH), exist_ok=True)
        with open(SNAPSHOT_PATH, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False)


def load_snapshot():
    if not os.path.exists(SNAPSHOT_PATH):
        return None
    try:
        with open(SNAPSHOT_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if data else None
    except:
        return None


def save_messages_batch_fast(msgs):
    if not msgs:
        return 0
    conn = _get_conn()
    count = 0
    try:
        conn.execute("BEGIN TRANSACTION")
        for m in msgs:
            msg_id = f"{m.get('chat','')}|{m.get('sender','')}|{m.get('time','')}|{m.get('content','')[:40]}"
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO messages
                    (id, chat, sender, content, time, timestamp, is_group, is_urgent, is_work, matched_keywords, username, source_person, deadline, category, priority_level)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    msg_id,
                    m.get('chat', ''), m.get('sender', ''), m.get('content', ''),
                    m.get('time', ''), m.get('timestamp', 0),
                    1 if m.get('is_group') else 0,
                    1 if m.get('is_urgent') else 0,
                    1 if m.get('is_work') else 0,
                    ','.join(m.get('matched_keywords', [])),
                    m.get('username', ''),
                    m.get('source_person', ''),
                    m.get('deadline', ''),
                    m.get('category', ''),
                    m.get('priority_level', 0)
                ))
                count += 1
            except:
                pass
        conn.execute("COMMIT")
    except:
        conn.execute("ROLLBACK")
    return count
