# core/engine.py
from PyQt5.QtCore import QThread, pyqtSignal
from data.wechat_cli import get_unread_messages
import time

class MessageEngine(QThread):
    """后台消息轮询引擎"""
    
    # 定义信号：有新消息时发出
    new_messages_signal = pyqtSignal(list)      # 所有新消息
    urgent_message_signal = pyqtSignal(dict)    # 紧急消息
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._poll_interval = 10  # 轮询间隔（秒）
        self._known_message_ids = set()  # 已处理的消息ID
        self._blacklist = []     # 黑名单
        self._work_keywords = [] # 工作关键词
        self._urgent_keywords = [] # 紧急关键词
    
    def configure(self, poll_interval=10, blacklist=None, work_keywords=None, urgent_keywords=None):
        """配置引擎参数"""
        self._poll_interval = poll_interval
        self._blacklist = blacklist or []
        self._work_keywords = work_keywords or []
        self._urgent_keywords = urgent_keywords or []
    
    def _make_message_id(self, msg):
        """生成消息唯一标识"""
        return f"{msg.get('chat', '')}|{msg.get('sender', '')}|{msg.get('timestamp', 0)}|{msg.get('content', '')[:30]}"
    
    def _is_blacklisted(self, msg):
        """检查是否在黑名单中"""
        chat = msg.get('chat', '')
        return chat in self._blacklist
    
    def _is_urgent(self, msg):
        """检查是否紧急"""
        content = msg.get('content', '')
        for kw in self._urgent_keywords:
            if kw in content:
                return True
        return False
    
    def _filter_and_tag(self, messages):
        """过滤黑名单，并标记工作相关、紧急"""
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
        """线程主循环"""
        while self._running:
            try:
                # 获取未读消息
                all_msgs = get_unread_messages()
                
                # 过滤和标记
                filtered = self._filter_and_tag(all_msgs)
                
                # 找出新增消息
                new_msgs = []
                urgent_msgs = []
                for msg in filtered:
                    msg_id = self._make_message_id(msg)
                    if msg_id not in self._known_message_ids:
                        self._known_message_ids.add(msg_id)
                        new_msgs.append(msg)
                        if msg.get('is_urgent'):
                            urgent_msgs.append(msg)
                
                # 发出信号
                if new_msgs:
                    self.new_messages_signal.emit(new_msgs)
                for msg in urgent_msgs:
                    self.urgent_message_signal.emit(msg)
                    
            except Exception as e:
                print(f"[引擎错误] {e}")
            
            # 等待下一轮
            time.sleep(self._poll_interval)
    
    def stop(self):
        """停止引擎"""
        self._running = False