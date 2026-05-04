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

def get_all_messages(limit=1000):
    """获取所有已缓存的消息"""
    conn = get_conn()
    rows = conn.execute("SELECT chat, sender, content, time, timestamp, is_group, is_urgent, is_work, matched_keywords FROM messages ORDER BY timestamp ASC LIMIT ?", (limit,)).fetchall()
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
    """判断数据库是否已完成首次全量拉取"""
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) FROM sync_progress").fetchone()
    conn.close()
    return (row[0] or 0) > 10
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