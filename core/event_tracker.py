# core/event_tracker.py
import re
import time
import datetime
import threading
from collections import Counter, defaultdict
from debug_log import logger
from core.data_manager import _get_conn, get_messages_by_chat

EVENT_KEYWORDS = {
    'meeting': ['会议', '开会', '讨论', '评审', '汇报', '演示', '周会', '例会', '复盘', '碰头', '碰面'],
    'document': ['文件', '文档', '报告', '方案', '合同', '协议', '申请', '审批', '签字', '盖章', '修改', '改一下', '改改'],
    'finance': ['报价', '预算', '费用', '付款', '收款', '发票', '报销', '金额', '转账', '汇款', '账单', '结算'],
    'task': ['任务', '需求', '功能', '开发', '测试', '上线', '发布', '版本', '迭代', '修复', '处理', '跟进'],
    'schedule': ['时间', '日期', '安排', '约', '定在', '几点', '什么时候', '下周', '明天', '后天', '今天'],
    'delivery': ['发货', '物流', '快递', '收货', '签收', '送达', '配送', '运输', '订单'],
    'borrow': ['借', '借用', '归还', '还你', '还我', '借一下', '借给你'],
    'personal': ['请假', '调休', '加班', '出差', '团建', '聚餐', '聚会', '活动', '生日'],
}

STOP_WORDS = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
              '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
              '自己', '这', '他', '她', '它', '们', '那', '什么', '怎么', '哪', '吗', '啊',
              '吧', '呢', '哦', '嗯', '哈', '呀', '么', '可以', '这个', '那个', '还是',
              '已经', '因为', '所以', '但是', '然后', '如果', '虽然', '不过', '只是',
              '觉得', '知道', '应该', '可能', '需要', '现在', '今天', '明天', '昨天',
              '一下', '一点', '一些', '有点', '真的', '比较', '非常', '特别', '太',
              '微信', '消息', '图片', '视频', '语音', '文件', '聊天'}


def init_events_table():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tracked_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat TEXT NOT NULL,
            event_title TEXT DEFAULT '',
            event_summary TEXT DEFAULT '',
            event_category TEXT DEFAULT '',
            start_time TEXT DEFAULT '',
            end_time TEXT DEFAULT '',
            message_count INTEGER DEFAULT 0,
            key_participants TEXT DEFAULT '',
            keywords TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            confidence REAL DEFAULT 0,
            last_activity TEXT DEFAULT '',
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now'))
        );
        CREATE INDEX IF NOT EXISTS idx_events_chat ON tracked_events(chat);
        CREATE INDEX IF NOT EXISTS idx_events_status ON tracked_events(status);
        CREATE INDEX IF NOT EXISTS idx_events_time ON tracked_events(start_time);
    """)
    conn.commit()


def save_event(event_data):
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT INTO tracked_events
            (chat, event_title, event_summary, event_category, start_time, end_time,
             message_count, key_participants, keywords, status, confidence, last_activity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
        """, (
            event_data.get('chat', ''),
            event_data.get('event_title', ''),
            event_data.get('event_summary', ''),
            event_data.get('event_category', ''),
            event_data.get('start_time', ''),
            event_data.get('end_time', ''),
            event_data.get('message_count', 0),
            event_data.get('key_participants', ''),
            event_data.get('keywords', ''),
            event_data.get('confidence', 0.0),
            event_data.get('last_activity', '')
        ))
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    except Exception as e:
        logger.error(f"[事件追踪] 保存失败: {e}")
        return None


def update_event(event_id, updates):
    conn = _get_conn()
    fields = []
    values = []
    for k, v in updates.items():
        fields.append(f"{k} = ?")
        values.append(v)
    values.append(event_id)
    values.append(time.time())
    conn.execute(f"UPDATE tracked_events SET {', '.join(fields)}, updated_at = ? WHERE id = ?", values)
    conn.commit()


def get_events_by_chat(chat, limit=50):
    conn = _get_conn()
    rows = conn.execute("""
        SELECT * FROM tracked_events
        WHERE chat = ?
        ORDER BY start_time DESC
        LIMIT ?
    """, (chat, limit)).fetchall()
    return [dict(r) for r in rows]


def get_all_active_events(limit=100):
    conn = _get_conn()
    rows = conn.execute("""
        SELECT * FROM tracked_events
        WHERE status = 'active'
        ORDER BY last_activity DESC
        LIMIT ?
    """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_all_events(limit=200):
    conn = _get_conn()
    rows = conn.execute("""
        SELECT * FROM tracked_events
        ORDER BY last_activity DESC
        LIMIT ?
    """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def delete_event(event_id):
    conn = _get_conn()
    conn.execute("DELETE FROM tracked_events WHERE id = ?", (event_id,))
    conn.commit()


def clear_events_for_chat(chat):
    conn = _get_conn()
    conn.execute("DELETE FROM tracked_events WHERE chat = ?", (chat,))
    conn.commit()


def _parse_time(time_str):
    if not time_str:
        return None
    try:
        if len(time_str) >= 16 and time_str[:4].isdigit():
            return datetime.datetime.strptime(time_str[:16], '%Y-%m-%d %H:%M')
    except:
        pass
    try:
        dt = datetime.datetime.strptime(time_str, '%m-%d %H:%M')
        return dt.replace(year=datetime.datetime.now().year)
    except:
        pass
    try:
        now = datetime.datetime.now()
        parts = time_str.split(':')
        h, m = int(parts[0]), int(parts[1])
        s = int(parts[2]) if len(parts) > 2 else 0
        return datetime.datetime(now.year, now.month, now.day, h, m, s)
    except:
        pass
    return None


def _extract_keywords_from_messages(messages, top_n=8):
    word_counter = Counter()
    for msg in messages:
        content = msg.get('content', '')
        words = re.findall(r'[\u4e00-\u9fff]{2,4}', content)
        for w in words:
            if w not in STOP_WORDS:
                word_counter[w] += 1
    return [w for w, _ in word_counter.most_common(top_n)]


def _categorize_event(keywords):
    scores = defaultdict(int)
    for kw in keywords:
        for cat, cat_kws in EVENT_KEYWORDS.items():
            if kw in cat_kws:
                scores[cat] += 2
            else:
                for ck in cat_kws:
                    if ck in kw or kw in ck:
                        scores[cat] += 1
    if scores:
        return max(scores, key=scores.get)
    return 'general'


def _generate_event_title(keywords, category):
    cat_labels = {
        'meeting': '会议沟通', 'document': '文件对接', 'finance': '财务相关',
        'task': '任务跟进', 'schedule': '日程安排', 'delivery': '物流配送',
        'borrow': '借还事项', 'personal': '个人事务', 'general': '日常沟通'
    }
    base = cat_labels.get(category, '日常沟通')
    if keywords:
        top_kw = keywords[:3]
        return f"{base}（{'/'.join(top_kw)}）"
    return base


def _generate_summary(messages, keywords, category):
    total = len(messages)
    participants = set()
    for m in messages:
        sender = m.get('sender', '')
        if sender:
            participants.add(sender)

    parts = []
    if participants:
        parts.append(f"参与人: {', '.join(list(participants)[:5])}")
    parts.append(f"共 {total} 条消息")

    cat_labels = {
        'meeting': '涉及会议安排与讨论',
        'document': '涉及文件修改与审批',
        'finance': '涉及财务与款项',
        'task': '涉及任务分配与跟进',
        'schedule': '涉及时间安排',
        'delivery': '涉及物流配送',
        'borrow': '涉及物品借还',
        'personal': '涉及个人事务',
        'general': '日常沟通交流'
    }
    parts.append(cat_labels.get(category, ''))

    return '；'.join(parts)


class EventAnalyzer:
    """事件分析器，从消息中智能提取事件"""

    def __init__(self):
        init_events_table()

    def analyze_chat(self, chat_name, messages=None):
        if messages is None:
            messages = get_messages_by_chat(chat_name, limit=99999)

        if not messages:
            return []

        sorted_msgs = sorted(messages, key=lambda m: _parse_time(m.get('time', '')) or datetime.datetime.min)

        groups = self._group_by_time(sorted_msgs)
        events = []

        for group in groups:
            if len(group) < 3:
                continue

            keywords = _extract_keywords_from_messages(group)
            if not keywords:
                continue

            category = _categorize_event(keywords)
            title = _generate_event_title(keywords, category)
            summary = _generate_summary(group, keywords, category)

            start_dt = _parse_time(group[0].get('time', ''))
            end_dt = _parse_time(group[-1].get('time', ''))

            participants = set()
            for m in group:
                sender = m.get('sender', '')
                if sender:
                    participants.add(sender)

            event_data = {
                'chat': chat_name,
                'event_title': title,
                'event_summary': summary,
                'event_category': category,
                'start_time': start_dt.strftime('%Y-%m-%d') if start_dt else '',
                'end_time': end_dt.strftime('%Y-%m-%d') if end_dt else '',
                'message_count': len(group),
                'key_participants': ', '.join(list(participants)[:5]),
                'keywords': ', '.join(keywords[:5]),
                'confidence': min(0.5 + len(group) * 0.02, 0.95),
                'last_activity': end_dt.strftime('%Y-%m-%d %H:%M') if end_dt else ''
            }

            event_id = save_event(event_data)
            if event_id:
                event_data['id'] = event_id
                events.append(event_data)

        return events

    def _group_by_time(self, sorted_messages, gap_days=3):
        if not sorted_messages:
            return []

        groups = []
        current_group = [sorted_messages[0]]

        for i in range(1, len(sorted_messages)):
            prev_dt = _parse_time(sorted_messages[i - 1].get('time', ''))
            curr_dt = _parse_time(sorted_messages[i].get('time', ''))

            if prev_dt and curr_dt:
                gap = (curr_dt - prev_dt).total_seconds() / 86400
                if gap > gap_days:
                    groups.append(current_group)
                    current_group = [sorted_messages[i]]
                    continue

            current_group.append(sorted_messages[i])

        if current_group:
            groups.append(current_group)

        merged_groups = self._merge_related_groups(groups)
        return merged_groups

    def _merge_related_groups(self, groups):
        if len(groups) <= 1:
            return groups

        merged = []
        current = groups[0]

        for i in range(1, len(groups)):
            curr_kws = set(_extract_keywords_from_messages(current, top_n=5))
            next_kws = set(_extract_keywords_from_messages(groups[i], top_n=5))

            overlap = len(curr_kws & next_kws)
            if overlap >= 2:
                current.extend(groups[i])
            else:
                merged.append(current)
                current = groups[i]

        merged.append(current)
        return merged

    def analyze_all_chats(self, chat_list=None):
        if chat_list is None:
            conn = _get_conn()
            rows = conn.execute("SELECT DISTINCT chat FROM messages").fetchall()
            chat_list = [r[0] for r in rows]

        total_events = 0
        for chat in chat_list:
            try:
                clear_events_for_chat(chat)
                events = self.analyze_chat(chat)
                total_events += len(events)
                if events:
                    logger.info(f"[事件分析] {chat}: 发现 {len(events)} 个事件")
            except Exception as e:
                logger.error(f"[事件分析] {chat} 分析失败: {e}")

        logger.info(f"[事件分析] 全部分析完成，共 {total_events} 个事件")
        return total_events


class EventTrackerThread(threading.Thread):
    """后台事件追踪线程，在空闲时运行分析"""

    def __init__(self, interval_minutes=30):
        super().__init__(daemon=True)
        self._interval = interval_minutes * 60
        self._running = True
        self._analyzer = EventAnalyzer()

    def run(self):
        logger.info(f"[事件追踪] 后台线程启动，间隔 {self._interval // 60} 分钟")
        time.sleep(60)
        while self._running:
            try:
                logger.info("[事件追踪] 开始新一轮分析...")
                self._analyzer.analyze_all_chats()
            except Exception as e:
                logger.error(f"[事件追踪] 分析异常: {e}")
            time.sleep(self._interval)

    def stop(self):
        self._running = False


_event_tracker = None


def start_event_tracker(interval_minutes=30):
    global _event_tracker
    if _event_tracker is not None:
        return
    _event_tracker = EventTrackerThread(interval_minutes)
    _event_tracker.start()
    logger.info("[事件追踪] 已启动")


def stop_event_tracker():
    global _event_tracker
    if _event_tracker:
        _event_tracker.stop()
        _event_tracker = None


def run_analysis_now():
    analyzer = EventAnalyzer()
    return analyzer.analyze_all_chats()
