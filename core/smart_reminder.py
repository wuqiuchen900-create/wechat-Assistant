# core/smart_reminder.py
import re
import time
import datetime
from collections import Counter
from debug_log import logger
from core.data_manager import _get_conn, get_messages_by_chat
from core.event_tracker import (
    get_events_by_chat, _parse_time, _extract_keywords_from_messages,
    _categorize_event, EVENT_KEYWORDS, STOP_WORDS
)

URGENCY_ESCALATION = [
    (re.compile(r'(马上|立刻|立即|紧急|加急|火速|速回|急急急|十万火急)'), 5),
    (re.compile(r'(尽快|asap|urgent|快点|赶快|抓紧)'), 4),
    (re.compile(r'(今天|今天内|今日|今晚|今儿)'), 4),
    (re.compile(r'(明天|明日|明早|明晚)'), 3),
    (re.compile(r'(后天|下周|这周|本周)'), 2),
]

DEADLINE_URGENCY = [
    (re.compile(r'(截止|deadline|ddl|到期)[\s：:]*(\d{1,2}月\d{1,2}[日号]|\d{4}-\d{1,2}-\d{1,2})'), 5),
    (re.compile(r'(\d{1,2})[点.](\d{0,2})\s*(之前|前|之前完成|截止)'), 4),
    (re.compile(r'(今天|明天|后天)\s*(完成|处理|搞定|提交|交付|做完|弄完)'), 4),
]

QUESTION_PATTERNS = [
    re.compile(r'(在吗|在不在|有空吗|方便吗|看到回|收到请回|看到请回)'),
    re.compile(r'[?？]$'),
    re.compile(r'(怎么样|如何|行不行|可以吗|好不好|能不能|可不可以)'),
]

NEGLIGIBLE_PATTERNS = [
    re.compile(r'^(好的|ok|OK|收到|知道了|明白|了解|嗯嗯|好的好的|好滴|好嘞)$'),
    re.compile(r'^(表情|图片|视频|语音|文件|链接)$'),
    re.compile(r'^\['),  # system messages
]


def init_smart_reminders_table():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS smart_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat TEXT NOT NULL,
            sender TEXT DEFAULT '',
            content TEXT DEFAULT '',
            message_time TEXT DEFAULT '',
            event_id INTEGER DEFAULT 0,
            event_title TEXT DEFAULT '',
            event_category TEXT DEFAULT '',
            urgency_score REAL DEFAULT 0,
            urgency_reason TEXT DEFAULT '',
            is_genuine_urgent INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            snooze_until REAL DEFAULT 0,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now'))
        );
        CREATE INDEX IF NOT EXISTS idx_sr_status ON smart_reminders(status);
        CREATE INDEX IF NOT EXISTS idx_sr_chat ON smart_reminders(chat);
        CREATE INDEX IF NOT EXISTS idx_sr_event ON smart_reminders(event_id);
    """)
    conn.commit()


def save_smart_reminder(data):
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT INTO smart_reminders
            (chat, sender, content, message_time, event_id, event_title,
             event_category, urgency_score, urgency_reason, is_genuine_urgent, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (
            data.get('chat', ''),
            data.get('sender', ''),
            data.get('content', ''),
            data.get('message_time', ''),
            data.get('event_id', 0),
            data.get('event_title', ''),
            data.get('event_category', ''),
            data.get('urgency_score', 0),
            data.get('urgency_reason', ''),
            data.get('is_genuine_urgent', 0)
        ))
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    except Exception as e:
        logger.error(f"[智能提醒] 保存失败: {e}")
        return None


def get_pending_smart_reminders(limit=10):
    conn = _get_conn()
    now = time.time()
    rows = conn.execute("""
        SELECT * FROM smart_reminders
        WHERE status = 'pending' AND (snooze_until = 0 OR snooze_until <= ?)
        ORDER BY urgency_score DESC, created_at DESC
        LIMIT ?
    """, (now, limit)).fetchall()
    return [dict(r) for r in rows]


def acknowledge_smart_reminder(reminder_id):
    conn = _get_conn()
    conn.execute("UPDATE smart_reminders SET status = 'acknowledged', updated_at = ? WHERE id = ?",
                 (time.time(), reminder_id))
    conn.commit()


def snooze_smart_reminder(reminder_id, minutes):
    conn = _get_conn()
    snooze_until = time.time() + minutes * 60
    conn.execute("UPDATE smart_reminders SET status = 'pending', snooze_until = ?, updated_at = ? WHERE id = ?",
                 (snooze_until, time.time(), reminder_id))
    conn.commit()


def dismiss_smart_reminder(reminder_id):
    conn = _get_conn()
    conn.execute("UPDATE smart_reminders SET status = 'dismissed', updated_at = ? WHERE id = ?",
                 (time.time(), reminder_id))
    conn.commit()


def count_pending_smart_reminders():
    conn = _get_conn()
    now = time.time()
    row = conn.execute("""
        SELECT COUNT(*) FROM smart_reminders
        WHERE status = 'pending' AND (snooze_until = 0 OR snooze_until <= ?)
    """, (now,)).fetchone()
    return row[0] if row else 0


class SmartReminderAnalyzer:
    """智能提醒分析器 —— 结合事件追踪判断消息真实紧急程度"""

    def __init__(self):
        init_smart_reminders_table()

    def analyze_message(self, msg):
        chat = msg.get('chat', '')
        content = msg.get('content', '')
        sender = msg.get('sender', '')
        msg_time = msg.get('time', '')

        if not content or not chat:
            return None

        if self._is_negligible(content):
            return None

        base_priority = msg.get('priority_level', 0)
        if base_priority < 2:
            return None

        events = get_events_by_chat(chat, limit=20)
        matched_event = self._match_event(content, msg_time, events)

        urgency_score = 0.0
        reasons = []

        if matched_event:
            urgency_score += 0.3
            reasons.append(f"属于活跃事件「{matched_event.get('event_title', '')}」")

            event_cat = matched_event.get('event_category', '')
            if event_cat in ('urgent', 'finance', 'meeting'):
                urgency_score += 0.15
                reasons.append(f"事件类别「{event_cat}」本身具有较高优先级")

            msg_count = matched_event.get('message_count', 0)
            if msg_count > 20:
                urgency_score += 0.1
                reasons.append(f"事件已持续沟通 {msg_count} 条消息")

            last_activity = matched_event.get('last_activity', '')
            if last_activity:
                try:
                    last_dt = _parse_time(last_activity)
                    if last_dt:
                        hours_gap = (datetime.datetime.now() - last_dt).total_seconds() / 3600
                        if hours_gap < 2:
                            urgency_score += 0.15
                            reasons.append("最近2小时内有活跃沟通")
                        elif hours_gap < 24:
                            urgency_score += 0.05
                except:
                    pass
        else:
            reasons.append("未匹配到已有事件，可能是新话题")

        escalation_score, esc_reason = self._check_escalation(content)
        urgency_score += escalation_score
        if esc_reason:
            reasons.append(esc_reason)

        deadline_score, dl_reason = self._check_deadline(content)
        urgency_score += deadline_score
        if dl_reason:
            reasons.append(dl_reason)

        question_score, q_reason = self._check_question(content)
        urgency_score += question_score
        if q_reason:
            reasons.append(q_reason)

        if msg.get('is_urgent'):
            urgency_score += 0.2
            reasons.append("匹配到紧急关键词")

        if msg.get('is_reminder'):
            urgency_score += 0.15
            reasons.append("匹配到提醒关键词")

        urgency_score = min(urgency_score, 1.0)

        is_genuine = urgency_score >= 0.4

        result = {
            'chat': chat,
            'sender': sender,
            'content': content,
            'message_time': msg_time,
            'event_id': matched_event.get('id', 0) if matched_event else 0,
            'event_title': matched_event.get('event_title', '') if matched_event else '',
            'event_category': matched_event.get('event_category', '') if matched_event else '',
            'event_summary': matched_event.get('event_summary', '') if matched_event else '',
            'event_start': matched_event.get('start_time', '') if matched_event else '',
            'event_end': matched_event.get('end_time', '') if matched_event else '',
            'event_participants': matched_event.get('key_participants', '') if matched_event else '',
            'urgency_score': round(urgency_score, 2),
            'urgency_reason': '；'.join(reasons) if reasons else '常规提醒',
            'is_genuine_urgent': 1 if is_genuine else 0,
            'original_priority': base_priority,
        }

        if is_genuine:
            save_smart_reminder(result)

        return result

    def _match_event(self, content, msg_time, events):
        if not events:
            return None

        content_words = set(re.findall(r'[\u4e00-\u9fff]{2,4}', content))
        content_words = {w for w in content_words if w not in STOP_WORDS}

        best_event = None
        best_score = 0

        for event in events:
            score = 0
            event_kws = event.get('keywords', '').split(', ')
            for kw in event_kws:
                if kw in content:
                    score += 3
                elif any(kw in cw or cw in kw for cw in content_words for kw in [kw]):
                    score += 1

            if msg_time and event.get('last_activity'):
                try:
                    msg_dt = _parse_time(msg_time)
                    event_dt = _parse_time(event.get('last_activity', ''))
                    if msg_dt and event_dt:
                        gap = abs((msg_dt - event_dt).total_seconds() / 86400)
                        if gap < 7:
                            score += 2
                        elif gap < 30:
                            score += 1
                except:
                    pass

            if score > best_score:
                best_score = score
                best_event = event

        if best_score >= 2:
            return best_event
        return None

    def _is_negligible(self, content):
        for pattern in NEGLIGIBLE_PATTERNS:
            if pattern.match(content.strip()):
                return True
        if len(content.strip()) <= 2:
            return True
        return False

    def _check_escalation(self, content):
        for pattern, score in URGENCY_ESCALATION:
            if pattern.search(content):
                return score / 5.0, f"包含紧急程度词「{pattern.search(content).group(0)}」"
        return 0, ''

    def _check_deadline(self, content):
        for pattern, score in DEADLINE_URGENCY:
            m = pattern.search(content)
            if m:
                return score / 5.0, f"包含截止时间「{m.group(0)[:30]}」"
        return 0, ''

    def _check_question(self, content):
        for pattern in QUESTION_PATTERNS:
            if pattern.search(content):
                return 0.1, "包含提问/等待回复"
        return 0, ''
