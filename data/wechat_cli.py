# data/wechat_cli.py
# 全局缓存
_sessions_cache = []
_sessions_cache_time = 0
import subprocess
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

def run_wechat_cli(command):
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            shell=True,
            timeout=30,
            env=env,
            encoding='utf-8',
            errors='replace'
        )
        if result.returncode != 0:
            # 静默处理，不再打印到终端
            # print(f"[wechat-cli] 命令失败: {command[:60]}")
            # print(f"[wechat-cli] stderr: {result.stderr[:200]}")
            return None
        return json.loads(result.stdout)
    except Exception as e:
        # print(f"[错误] 执行命令失败: {e}")
        return None

def get_unread_messages():
    data = run_wechat_cli("wechat-cli unread")
    if not isinstance(data, list):
        return []
    messages = []
    for session in data:
        if session.get('unread', 0) > 0:
            messages.append({
                'chat': session.get('chat', ''),
                'sender': session.get('sender', '') or session.get('last_sender', ''),
                'content': session.get('last_message', ''),
                'timestamp': session.get('timestamp', 0),
                'time': session.get('time', ''),
                'unread': session.get('unread', 0),
                'is_group': session.get('is_group', False)
            })
    return messages

def _parse_history_text(text):
    """解析 history 返回的文本格式: '[时间] 发送者: 内容'"""
    match = re.match(r'\[(.+?)\]\s*(.+?):\s*(.*)', text)
    if match:
        return {
            'time': match.group(1),
            'sender': match.group(2),
            'content': match.group(3)
        }
    return None


def _fetch_one_chat(chat_name, limit_per_chat, is_group):
    """拉取单个会话的历史消息"""
    data = run_wechat_cli(f'wechat-cli history "{chat_name}" --limit {limit_per_chat}')
    if not isinstance(data, dict):
        return []
    
    raw_messages = data.get('messages', [])
    if not isinstance(raw_messages, list):
        return []
    
    result = []
    for msg_text in raw_messages:
        if not isinstance(msg_text, str):
            continue
        parsed = _parse_history_text(msg_text)
        if parsed:
            parsed['chat'] = chat_name
            parsed['is_group'] = is_group
            result.append(parsed)
    return result


def get_latest_messages(limit_per_chat=10, max_workers=3):
    global _sessions_cache, _sessions_cache_time
    import time as _time
    
    # 会话列表缓存 5 分钟，避免频繁拉取
    now = _time.time()
    if not _sessions_cache or (now - _sessions_cache_time) > 300:
        sessions_data = run_wechat_cli("wechat-cli sessions --limit 100")
        if isinstance(sessions_data, list):
            _sessions_cache = sessions_data
            _sessions_cache_time = now
    
    if not _sessions_cache:
        return []
    # ... 后续代码保持不变 ...

    all_messages = []
    
    # 使用线程池并行拉取
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        for session in sessions_data:
            chat_name = session.get('chat', '')
            if not chat_name:
                continue
            future = executor.submit(_fetch_one_chat, chat_name, limit_per_chat, session.get('is_group', False))
            futures[future] = chat_name
        
        # 收集结果
        for future in as_completed(futures):
            chat_name = futures[future]
            try:
                messages = future.result()
                all_messages.extend(messages)
            except Exception:
                pass  # 单个会话失败不影响整体

    # 按时间排序
    all_messages.sort(key=lambda m: m.get('time', ''))
    
    # 去重
    seen = set()
    unique_msgs = []
    for m in all_messages:
        mid = f"{m.get('chat','')}|{m.get('sender','')}|{m.get('time','')}|{m.get('content','')[:30]}"
        if mid not in seen:
            seen.add(mid)
            unique_msgs.append(m)
    
    return unique_msgs