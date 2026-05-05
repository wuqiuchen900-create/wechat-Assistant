# core/ai_analyzer.py
from PyQt5.QtCore import QThread, pyqtSignal
import time

class AIAnalyzer(QThread):
    """独立的AI分析线程：从队列中取消息，慢慢分析，不阻塞主流程"""
    result_signal = pyqtSignal(dict)  # 分析完成后，发回主线程更新界面

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue = []          # 待分析的消息队列
        self._running = True
        self._results_cache = {}  # 缓存分析结果，避免重复分析

    def add_messages(self, messages):
        """外部调用：把新消息加入分析队列"""
        for msg in messages:
            msg_id = f"{msg.get('chat','')}|{msg.get('sender','')}|{msg.get('time','')}"
            if msg_id not in self._results_cache:
                self._queue.append(msg)

    def run(self):
        """后台线程：慢慢处理队列里的消息"""
        while self._running:
            if self._queue:
                msg = self._queue.pop(0)
                msg_id = f"{msg.get('chat','')}|{msg.get('sender','')}|{msg.get('time','')}"
                
                # ===== 核心分析逻辑（当前用关键词，未来可替换为AI）=====
                content = msg.get('content', '')
                analysis = {
                    'msg_id': msg_id,
                    'is_urgent': False,
                    'is_work': False,
                    'matched_keywords': [],
                    'summary': content[:100]  # 简单摘要
                }
                # (这里暂时用关键词判断，未来可接入AI API)
                # ...

                self._results_cache[msg_id] = analysis
                self.result_signal.emit(analysis)
            else:
                time.sleep(0.5)  # 没消息时休息一下

    def stop(self):
        self._running = False