# data/storage.py
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'message_data', 'cache.db')

def get_conn():
    """获取数据库连接"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

def init_db():
    """初始化表结构和索引"""
    conn = get_conn()
    try:
        conn.execute("""
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
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_progress (
                chat TEXT PRIMARY KEY,
                last_sync_time TEXT DEFAULT '',
                last_timestamp INTEGER DEFAULT 0
            )
        """)
        # 关键词表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL UNIQUE,
                category TEXT DEFAULT 'work',  -- 'work' 或 'urgent'
                enabled INTEGER DEFAULT 1,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
                # 应用设置表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT DEFAULT '',
                updated_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
                # 黑名单表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)
        # 添加索引，提升查询速度
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_time ON messages(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sync_chat ON sync_progress(chat)")
        conn.commit()
    finally:
        conn.close()

def save_message(msg):
    """保存单条消息到数据库"""
    conn = get_conn()
    msg_id = f"{msg.get('chat','')}|{msg.get('sender','')}|{msg.get('time','')}|{msg.get('content','')[:40]}"
    try:
        conn.execute("""
            INSERT OR IGNORE INTO messages (id, chat, sender, content, time, timestamp, is_group, is_urgent, is_work, matched_keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            msg_id,
            msg.get('chat', ''),
            msg.get('sender', ''),
            msg.get('content', ''),
            msg.get('time', ''),
            msg.get('timestamp', 0),
            1 if msg.get('is_group') else 0,
            1 if msg.get('is_urgent') else 0,
            1 if msg.get('is_work') else 0,
            ','.join(msg.get('matched_keywords', []))
        ))
        conn.commit()
    except:
        pass
    finally:
        conn.close()

def save_messages_batch(msgs):
    """批量保存消息"""
    conn = get_conn()
    for msg in msgs:
        msg_id = f"{msg.get('chat','')}|{msg.get('sender','')}|{msg.get('time','')}|{msg.get('content','')[:40]}"
        try:
            conn.execute("""
                INSERT OR IGNORE INTO messages (id, chat, sender, content, time, timestamp, is_group, is_urgent, is_work, matched_keywords)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                msg_id,
                msg.get('chat', ''),
                msg.get('sender', ''),
                msg.get('content', ''),
                msg.get('time', ''),
                msg.get('timestamp', 0),
                1 if msg.get('is_group') else 0,
                1 if msg.get('is_urgent') else 0,
                1 if msg.get('is_work') else 0,
                ','.join(msg.get('matched_keywords', []))
            ))
        except:
            pass
    conn.commit()
    conn.close()

def save_messages_batch_fast(msgs):
    """快速批量保存（使用大事务）"""
    conn = get_conn()
    try:
        conn.execute("BEGIN TRANSACTION")
        for msg in msgs:
            msg_id = f"{msg.get('chat','')}|{msg.get('sender','')}|{msg.get('time','')}|{msg.get('content','')[:40]}"
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO messages (id, chat, sender, content, time, timestamp, is_group, is_urgent, is_work, matched_keywords)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    msg_id,
                    msg.get('chat', ''),
                    msg.get('sender', ''),
                    msg.get('content', ''),
                    msg.get('time', ''),
                    msg.get('timestamp', 0),
                    1 if msg.get('is_group') else 0,
                    1 if msg.get('is_urgent') else 0,
                    1 if msg.get('is_work') else 0,
                    ','.join(msg.get('matched_keywords', []))
                ))
            except:
                pass
        conn.execute("COMMIT")
    except:
        conn.execute("ROLLBACK")
    finally:
        conn.close()

def get_all_messages(limit=1000, offset=0):
    """分页获取已缓存的消息"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT chat, sender, content, time, timestamp, is_group, is_urgent, is_work, matched_keywords FROM messages ORDER BY timestamp ASC LIMIT ? OFFSET ?",
        (limit, offset)
    ).fetchall()
    conn.close()
    return [
        {
            'chat': r[0],
            'sender': r[1],
            'content': r[2],
            'time': r[3],
            'timestamp': r[4],
            'is_group': bool(r[5]),
            'is_urgent': bool(r[6]),
            'is_work': bool(r[7]),
            'matched_keywords': r[8].split(',') if r[8] else []
        }
        for r in rows
    ]

def get_last_sync_time(chat):
    """获取某个会话的最后同步时间"""
    conn = get_conn()
    row = conn.execute("SELECT last_sync_time FROM sync_progress WHERE chat = ?", (chat,)).fetchone()
    conn.close()
    return row[0] if row else None

def update_sync_progress(chat, last_time, last_timestamp):
    """更新某个会话的同步进度"""
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO sync_progress (chat, last_sync_time, last_timestamp) VALUES (?, ?, ?)", (chat, last_time, last_timestamp))
    conn.commit()
    conn.close()

def get_message_count():
    """获取已缓存的消息总数"""
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) FROM messages").fetchone()
    conn.close()
    return row[0] if row else 0

def is_db_initialized():
    """只要 messages 表有数据，就认为数据库已初始化，无需全量同步"""
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) FROM messages").fetchone()
    conn.close()
    return (row[0] or 0) > 0
def get_all_keywords():
    """获取所有启用的关键词，返回 (work_keywords, urgent_keywords)"""
    conn = get_conn()
    work = [r[0] for r in conn.execute(
        "SELECT keyword FROM keywords WHERE category='work' AND enabled=1"
    ).fetchall()]
    urgent = [r[0] for r in conn.execute(
        "SELECT keyword FROM keywords WHERE category='urgent' AND enabled=1"
    ).fetchall()]
    conn.close()
    return work, urgent


def add_keyword(keyword, category='work'):
    """添加关键词"""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO keywords (keyword, category) VALUES (?, ?)",
            (keyword, category)
        )
        conn.commit()
    except:
        pass
    finally:
        conn.close()


def delete_keyword(keyword):
    """删除关键词"""
    conn = get_conn()
    conn.execute("DELETE FROM keywords WHERE keyword = ?", (keyword,))
    conn.commit()
    conn.close()


def toggle_keyword(keyword, enabled):
    """启用/禁用关键词"""
    conn = get_conn()
    conn.execute(
        "UPDATE keywords SET enabled = ? WHERE keyword = ?",
        (1 if enabled else 0, keyword)
    )
    conn.commit()
    conn.close()    
def get_all_settings():
    """获取所有应用设置，返回字典"""
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    conn.close()
    settings = {}
    for r in rows:
        settings[r[0]] = r[1]
    # 默认值
    defaults = {
        'poll_interval': '30',
        'history_limit': '50',
        'enable_full_sync': '1',
        'enable_popup': '1',
        'enable_sound': '0',
        'enable_tray_flash': '1',
        'deep_check_interval': '180',  # ← 新增，单位分钟，默认3小时
    }
    for k, v in defaults.items():
        if k not in settings:
            settings[k] = v
    return settings

def save_setting(key, value):
    """保存单个设置"""
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, strftime('%s', 'now'))",
        (key, str(value))
    )
    conn.commit()
    conn.close()   
def get_all_blacklist():
    """获取所有黑名单"""
    conn = get_conn()
    rows = conn.execute("SELECT name FROM blacklist ORDER BY name").fetchall()
    conn.close()
    return [r[0] for r in rows]

def add_blacklist(name):
    """添加黑名单"""
    conn = get_conn()
    try:
        conn.execute("INSERT OR IGNORE INTO blacklist (name) VALUES (?)", (name,))
        conn.commit()
    except:
        pass
    finally:
        conn.close()

def delete_blacklist(name):
    """删除黑名单"""
    conn = get_conn()
    conn.execute("DELETE FROM blacklist WHERE name = ?", (name,))
    conn.commit()
    conn.close()     
def save_messages_batch_with_conn(conn, msgs):
    """使用已有连接批量保存消息（带预去重）"""
    if not msgs:
        return 0
    
    # 1. 一次性查询所有已有 ID
    ids = [f"{m.get('chat','')}|{m.get('sender','')}|{m.get('time','')}|{m.get('content','')[:40]}" for m in msgs]
    placeholders = ','.join(['?'] * len(ids))
    existing = set()
    try:
        rows = conn.execute(f"SELECT id FROM messages WHERE id IN ({placeholders})", ids).fetchall()
        existing = {r[0] for r in rows}
    except:
        # 如果批量查询失败（比如数量太大），回退到逐条
        pass
    
    # 2. 过滤出新消息
    new_msgs = []
    new_ids = []
    for m, mid in zip(msgs, ids):
        if mid not in existing:
            new_msgs.append(m)
            new_ids.append(mid)
    
    if not new_msgs:
        return 0
    
    # 3. 批量插入新消息
    count = 0
    try:
        conn.execute("BEGIN TRANSACTION")
        for m, mid in zip(new_msgs, new_ids):
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO messages (id, chat, sender, content, time, timestamp, is_group, is_urgent, is_work, matched_keywords)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    mid,
                    m.get('chat', ''),
                    m.get('sender', ''),
                    m.get('content', ''),
                    m.get('time', ''),
                    m.get('timestamp', 0),
                    1 if m.get('is_group') else 0,
                    1 if m.get('is_urgent') else 0,
                    1 if m.get('is_work') else 0,
                    ','.join(m.get('matched_keywords', []))
                ))
                count += 1
            except:
                pass
        conn.execute("COMMIT")
    except:
        conn.execute("ROLLBACK")
    
    return count    