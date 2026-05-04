# core/engine.py
from PyQt5.QtCore import QThread, pyqtSignal
from data.wechat_cli import get_latest_messages
import time

class MessageEngine(QThread):
    new_messages_signal = pyqtSignal(list)
    urgent_message_signal = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._poll_interval = 10
        self._known_message_ids = set()
        self._blacklist = []
        self._work_keywords = []
        self._urgent_keywords = []

    def configure(self, poll_interval=10, blacklist=None, work_keywords=None, urgent_keywords=None):
        self._poll_interval = poll_interval
        self._blacklist = blacklist or []
        self._work_keywords = work_keywords or []
        self._urgent_keywords = urgent_keywords or []

    def _make_message_id(self, msg):
        return f"{msg.get('chat','')}|{msg.get('sender','')}|{msg.get('timestamp',0)}|{msg.get('content','')[:30]}"

    def _is_blacklisted(self, msg):
        return msg.get('chat', '') in self._blacklist

    def _filter_and_tag(self, messages):
        result = []
        for msg in messages:
            if self._is_blacklisted(msg):
                continue
            content = msg.get('content', '')
            msg['is_urgent'] = any(kw in content for kw in self._urgent_keywords)
            msg['is_work'] = any(kw in content for kw in self._work_keywords)
            msg['matched_keywords'] = [kw for kw in self._work_keywords if kw in content]
            result.append(msg)
        return result

    def run(self):
        while self._running:
            try:
                all_msgs = get_latest_messages(limit_per_chat=5)
                filtered = self._filter_and_tag(all_msgs)
                new_msgs, urgent_msgs = [], []
                for msg in filtered:
                    msg_id = self._make_message_id(msg)
                    if msg_id not in self._known_message_ids:
                        self._known_message_ids.add(msg_id)
                        new_msgs.append(msg)
                        if msg.get('is_urgent'):
                            urgent_msgs.append(msg)
                if new_msgs:
                    self.new_messages_signal.emit(new_msgs)
                for msg in urgent_msgs:
                    self.urgent_message_signal.emit(msg)
            except Exception as e:
                print(f"[引擎错误] {e}")
            time.sleep(self._poll_interval)

    def stop(self):
        self._running = False