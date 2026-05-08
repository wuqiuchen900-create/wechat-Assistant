# core/engine.py
import re
import time
import datetime
from PyQt5.QtCore import QThread, pyqtSignal
from data.wechat_cli import get_new_messages
from core.data_manager import (
    init_db, count_messages, get_all_messages,
    commit_messages, update_sync_progress, get_all_settings,
    get_all_keywords, get_all_blacklist, is_db_initialized,
    save_messages_batch_fast, update_message_meta,
    get_all_reminder_keywords
)
from core.sync_worker import SyncWorker, IncrementalSyncWorker
from concurrent.futures import ThreadPoolExecutor
from debug_log import logger


DEADLINE_PATTERNS = [
    (re.compile(r'(截止|deadline|ddl|到期|之前|之前完成)[\s：:]*(\d{1,2}月\d{1,2}[日号]|\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}|周[一二三四五六日]|明天|后天|下周[一二三四五六日]|下周一|下周二|下周三|下周四|下周五|下周六|下周日)'), 4),
    (re.compile(r'(今天|明天|后天|下周|本周|这周)\s*(完成|处理|搞定|提交|交付|做完|弄完)'), 3),
    (re.compile(r'(尽快|asap|urgent|紧急|加急|马上|立刻|立即)'), 5),
    (re.compile(r'(\d{1,2})[点.](\d{0,2})\s*(之前|前|之前完成|截止)'), 4),
    (re.compile(r'(这周|本周|下周|下个月|本月)\s*(内|之前|完成)'), 3),
]

AMOUNT_PATTERN = re.compile(r'(\d+\.?\d*)\s*(万|w|k|千|百|元|块|块钱|万元|亿|美金|美元|欧元|日元|港币|英镑|rmb|RMB|¥|\$|€|£|￥)', re.IGNORECASE)

PERSON_PATTERNS = [
    re.compile(r'(@[\w\u4e00-\u9fff]+|[\u4e00-\u9fff]{2,4}\s*(说|提出|要求|让|叫|安排|交代|吩咐|指示))'),
    re.compile(r'(来自|from|by)[\s：:]*([\u4e00-\u9fff]{2,4})'),
    re.compile(r'([\u4e00-\u9fff]{2,4})\s*(的|之)\s*(需求|要求|任务|安排|事情)'),
]

CATEGORY_KEYWORDS = {
    'finance': ['报销', '发票', '预算', '费用', '付款', '收款', '账单', '金额', '工资', '奖金', '扣款', '转账', '汇款', '理财', '投资', '贷款', '还款'],
    'meeting': ['会议', '开会', '讨论', '评审', '汇报', '演示', 'ppt', 'PPT', '周会', '例会', '站会', '复盘'],
    'task': ['任务', '需求', '功能', 'bug', 'BUG', '修复', '开发', '测试', '上线', '发布', '部署', '版本', '迭代'],
    'document': ['文档', '报告', '方案', '计划', '总结', '周报', '日报', '月报', '合同', '协议', '申请', '审批'],
    'personal': ['请假', '调休', '加班', '出差', '团建', '聚餐', '生日', '聚会', '活动'],
    'urgent': ['紧急', '加急', '马上', '立刻', '立即', '尽快', 'asap', 'urgent', '火速', '速回', '急'],
}


class MessageEngine(QThread):
    new_messages_signal = pyqtSignal(list)
    urgent_message_signal = pyqtSignal(dict)
    sync_progress_signal = pyqtSignal(int, int)
    sync_finished_signal = pyqtSignal(object)
    sync_error_signal = pyqtSignal(str)
    sync_worker_ready = pyqtSignal(object)
    reminder_signal = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._poll_interval = 30
        self._known_message_ids = set()
        self._blacklist = []
        self._work_keywords = []
        self._urgent_keywords = []
        self._reminder_keywords = []
        self._enable_full_sync = True
        self._write_pool = ThreadPoolExecutor(max_workers=2)
        self._enable_popup = True

    def configure(self):
        init_db()
        settings = get_all_settings()
        self._poll_interval = int(settings.get('poll_interval', '30'))
        self._enable_full_sync = settings.get('enable_full_sync', '1') == '1'
        self._enable_popup = settings.get('enable_popup', '1') == '1'
        self._work_keywords, self._urgent_keywords = get_all_keywords()
        self._reminder_keywords = get_all_reminder_keywords()
        self._blacklist = get_all_blacklist()

    def _reload_keywords(self):
        self._work_keywords, self._urgent_keywords = get_all_keywords()
        self._reminder_keywords = get_all_reminder_keywords()

    def _reload_blacklist(self):
        self._blacklist = get_all_blacklist()

    def _reload_reminder_settings(self):
        settings = get_all_settings()
        self._enable_popup = settings.get('enable_popup', '1') == '1'

    def _make_message_id(self, msg):
        return f"{msg.get('chat','')}|{msg.get('sender','')}|{msg.get('time','')}|{msg.get('content','')[:30]}"

    def _is_blacklisted(self, msg):
        chat = msg.get('chat', '')
        return any(kw in chat for kw in self._blacklist if kw)

    def _filter_and_tag(self, messages):
        result = []
        for msg in messages:
            if self._is_blacklisted(msg):
                continue
            content = msg.get('content', '')
            msg['is_urgent'] = any(kw in content for kw in self._urgent_keywords)
            msg['is_work'] = any(kw in content for kw in self._work_keywords)
            msg['matched_keywords'] = [kw for kw in self._work_keywords if kw in content]
            self._smart_categorize(msg)

            for rk in self._reminder_keywords:
                kw = rk.get('keyword', '')
                if kw and kw in content:
                    msg['is_reminder'] = True
                    msg['reminder_keyword'] = kw
                    self.reminder_signal.emit(msg)
                    break

            result.append(msg)
        return result

    def _smart_categorize(self, msg):
        content = msg.get('content', '')
        sender = msg.get('sender', '')
        chat = msg.get('chat', '')

        source_person = sender or ''
        deadline = ''
        category = ''
        priority_level = 0

        for pattern, prio in DEADLINE_PATTERNS:
            m = pattern.search(content)
            if m:
                deadline = m.group(0)[:40]
                priority_level = max(priority_level, prio)
                break

        amount_match = AMOUNT_PATTERN.search(content)
        if amount_match:
            priority_level = max(priority_level, 3)

        for pattern in PERSON_PATTERNS:
            m = pattern.search(content)
            if m:
                extracted = m.group(0)
                for name_part in re.findall(r'[\u4e00-\u9fff]{2,4}', extracted):
                    if name_part not in ('提出', '要求', '让', '叫', '安排', '交代', '吩咐', '指示', '来自', '的', '之', '需求', '任务', '安排', '事情'):
                        source_person = name_part
                        break
                break

        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in content for kw in keywords):
                category = cat
                if cat == 'urgent':
                    priority_level = max(priority_level, 5)
                elif cat in ('finance', 'meeting'):
                    priority_level = max(priority_level, 3)
                elif cat in ('task', 'document'):
                    priority_level = max(priority_level, 2)
                break

        if msg.get('is_urgent'):
            priority_level = max(priority_level, 5)
        elif msg.get('is_work'):
            priority_level = max(priority_level, 2)

        msg['source_person'] = source_person
        msg['deadline'] = deadline
        msg['category'] = category
        msg['priority_level'] = priority_level

        if priority_level >= 4:
            msg['is_urgent'] = True

    def run(self):
        logger.info("[引擎] 线程开始运行")
        init_db()

        if is_db_initialized():
            logger.info("[引擎] 数据库已初始化，发射快照信号 (-2,-2)")
            self.sync_progress_signal.emit(-2, -2)
        else:
            logger.info("[引擎] 数据库未初始化，跳过快照")
            total_cached = count_messages()
            page_size = 100
            offset = 0
            while offset < total_cached:
                cached = get_all_messages(limit=99999)
                batch = cached[offset:offset + page_size]
                if batch:
                    tagged = self._filter_and_tag(batch)
                    self.new_messages_signal.emit(tagged)
                    time.sleep(0.05)
                offset += page_size

        if self._enable_full_sync and not is_db_initialized():
            logger.info("[引擎] 进入全量同步")
            self.sync_progress_signal.emit(-1, -1)
            self._sync_thread = QThread()
            self._sync_worker = SyncWorker()
            self.sync_worker_ready.emit(self._sync_worker)
            self._sync_worker.moveToThread(self._sync_thread)
            self._sync_worker.finished_callback = lambda: (
                logger.info("[引擎] worker 回调触发，转发 sync_finished_signal"),
                self.sync_finished_signal.emit(
                    self._sync_worker.changed_chats if hasattr(self._sync_worker, 'changed_chats') else set()
                )
            )
            self._sync_worker.messages_ready.connect(self._process_synced_messages)
            self._sync_thread.started.connect(self._sync_worker.do_full_sync)
            self._sync_thread.finished.connect(lambda: (
                logger.info("[引擎·兜底] 同步线程 finished，补发 sync_finished_signal"),
                self.sync_finished_signal.emit()
            ))
            self._sync_thread.start()
        else:
            logger.info("[引擎] 进入增量同步")
            self.sync_progress_signal.emit(-1, -1)
            self._sync_thread = QThread()
            self._sync_worker = IncrementalSyncWorker()
            self.sync_worker_ready.emit(self._sync_worker)
            self._sync_worker.moveToThread(self._sync_thread)
            self._sync_worker.finished_callback = lambda: (
                logger.info("[引擎] worker 回调触发，转发 sync_finished_signal"),
                self.sync_finished_signal.emit(
                    self._sync_worker.changed_chats if hasattr(self._sync_worker, 'changed_chats') else set()
                )
            )
            self._sync_worker.messages_ready.connect(self._process_synced_messages)
            self._sync_thread.started.connect(self._sync_worker.do_incremental_sync)
            self._sync_thread.finished.connect(lambda: (
                logger.info("[引擎·兜底] 增量同步线程已结束，补发完成信号"),
                self.sync_finished_signal.emit()
            ))
            self._sync_thread.start()

        loop_count = 0
        while self._running:
            loop_count += 1
            if loop_count % 5 == 0:
                self._reload_keywords()
                self._reload_blacklist()
                self._reload_reminder_settings()
            try:
                new_msgs = []
                latest_msgs = get_new_messages()
                if latest_msgs:
                    filtered = self._filter_and_tag(latest_msgs)
                    new_count = commit_messages(filtered)
                    if new_count > 0:
                        for m in filtered:
                            mid = self._make_message_id(m)
                            if mid not in self._known_message_ids:
                                self._known_message_ids.add(mid)
                                new_msgs.append(m)
                    if new_msgs:
                        self._write_pool.submit(save_messages_batch_fast, new_msgs)
                        self.new_messages_signal.emit(new_msgs)
                    if self._enable_popup:
                        for m in filtered:
                            if m.get('is_urgent') or m.get('priority_level', 0) >= 4:
                                self.urgent_message_signal.emit(m)
                                self.reminder_signal.emit(m)
            except Exception as e:
                logger.error(f"[实时轮询错误] {e}")
            time.sleep(self._poll_interval)

        self._sync_worker.stop()
        self._sync_thread.quit()
        self._sync_thread.wait()

    def _process_synced_messages(self, messages):
        tagged = self._filter_and_tag(messages)
        if tagged:
            self.new_messages_signal.emit(tagged)

    def stop(self):
        self._running = False
        self._write_pool.shutdown(wait=False)
