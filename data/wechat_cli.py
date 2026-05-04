# data/wechat_cli.py
import subprocess
import json
import os
import re
import sys
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

# ========== 自动适配 wechat-cli 命令 ==========
def _get_wechat_cli_cmd():
    """返回执行 wechat-cli 的命令前缀字符串"""
    # 1. 优先尝试命令行直接调用 wechat-cli
    if shutil.which('wechat-cli'):
        return 'wechat-cli'
    # 2. 尝试通过 python -m wechat_cli 调用
    try:
        subprocess.run(
            [sys.executable, '-m', 'wechat_cli', '--help'],
            capture_output=True, timeout=5
        )
        return f'"{sys.executable}" -m wechat_cli'
    except:
        pass
    # 3. 如果都不行，返回默认的 wechat-cli，留着手动调试
    return 'wechat-cli'

WECHAT_CLI_CMD = _get_wechat_cli_cmd()
print(f"[自动检测] wechat-cli 调用命令: {WECHAT_CLI_CMD}")

# ========== 原有缓存和函数 ==========
_sessions_cache = []
_sessions_cache_time = 0

def run_wechat_cli(command):
    """执行 wechat-cli 命令并返回 JSON 结果"""
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        full_cmd = f'{WECHAT_CLI_CMD} {command}'
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            shell=True,
            timeout=30,
            env=env,
            encoding='utf-8',
            errors='replace'
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except Exception:
        return None

def get_contact_detail(username):
    """获取联系人详情，包含头像 URL"""
    data = run_wechat_cli(f'contacts --detail "{username}"')
    if isinstance(data, dict):
        return data
    return None
def get_unread_messages():
    data = run_wechat_cli("unread")
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
                'is_group': session.get('is_group', False),
                'username': session.get('username', ''),
            })
    return messages


def _parse_history_text(text):
    match = re.match(r'\[(.+?)\]\s*(.+?):\s*(.*)', text)
    if match:
        return {
            'time': match.group(1),
            'sender': match.group(2),
            'content': match.group(3)
        }
    return None


def get_sessions_list(limit=200):
    global _sessions_cache, _sessions_cache_time
    import time as _time
    now = _time.time()
    if not _sessions_cache or (now - _sessions_cache_time) > 300:
        data = run_wechat_cli(f"sessions --limit {limit}")
        if isinstance(data, list):
            _sessions_cache = data
            _sessions_cache_time = now
    return _sessions_cache


def get_history_since(chat_name, start_time=None, limit=50):
    cmd = f'history "{chat_name}" --limit {limit}'
    if start_time:
        cmd += f' --start-time "{start_time}"'
    data = run_wechat_cli(cmd)
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
            parsed['is_group'] = False
            result.append(parsed)
    return result
def _scan_wechat_dirs():
    import os
    possible_roots = [
        r"D:\xwechat_files",
        r"C:\xwechat_files",
        os.path.expanduser(r"~\Documents\WeChat Files"),
        r"D:\Documents\WeChat Files",
    ]
    for root in possible_roots:
        if os.path.exists(root):
            for folder in os.listdir(root):
                full_path = os.path.join(root, folder)
                if os.path.isdir(full_path) and os.path.exists(os.path.join(full_path, 'db_storage')):
                    return full_path, folder
    return None, None    
def get_wechat_data_dir():
    try:
        from pywxdump.wx_core import get_wx_info
        info = get_wx_info()
        if info and isinstance(info, dict):
            wxid = info.get('wxid', '')
            data_dir = info.get('data_dir', '')
            if not data_dir:
                # 其他可能字段
                for key in ['file_path', 'wx_path', 'dir']:
                    if key in info:
                        data_dir = info[key]
                        break
            if data_dir and os.path.exists(data_dir):
                return data_dir, wxid
            # 根据 wxid 尝试拼接
            if wxid:
                base_dirs = [r"D:\xwechat_files", r"C:\xwechat_files"]
                for base in base_dirs:
                    potential = os.path.join(base, wxid)
                    if os.path.exists(potential):
                        return potential, wxid
    except Exception:
        pass
    
    # 如果 pywxdump 失败，扫描目录
    return _scan_wechat_dirs()
