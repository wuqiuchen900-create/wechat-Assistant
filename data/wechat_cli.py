# data/wechat_cli.py
import subprocess
import json
import os

def run_wechat_cli(command):
    """执行 wechat-cli 命令并返回 JSON 结果"""
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
            return None
        return json.loads(result.stdout)
    except Exception as e:
        print(f"[错误] 执行命令失败: {e}")
        return None


def get_unread_messages():
    """获取所有未读会话的消息"""
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


def get_chat_history(chat_name, limit=50):
    """获取指定会话的历史消息"""
    data = run_wechat_cli(f'wechat-cli history "{chat_name}" --limit {limit}')
    if not isinstance(data, list):
        return []
    return data