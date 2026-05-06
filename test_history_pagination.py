# test_history_pagination.py
import subprocess
import json
import datetime
import os
import re

CHAT_NAME = "OpenClaw.CN龙虾中文社区13"
LIMIT = 500
OUTPUT_FILE = "test_history_output.txt"

def parse_msg_time(msg_line):
    """从 wechat-cli 返回的字符串消息中提取时间，返回 datetime 对象或 None"""
    # 匹配格式：[2026-05-06 16:03] 或 [05-06 16:03]
    match = re.match(r'\[([^\]]+)\]', msg_line)
    if not match:
        return None
    time_str = match.group(1).strip()
    if not time_str:
        return None
    try:
        if time_str[:4].isdigit() and len(time_str) >= 16:
            return datetime.datetime.strptime(time_str[:16], '%Y-%m-%d %H:%M')
        if len(time_str) >= 11 and time_str[:2].isdigit():
            dt = datetime.datetime.strptime(time_str, '%m-%d %H:%M')
            return dt.replace(year=datetime.datetime.now().year)
        # 纯时间 16:03
        parts = time_str.split(':')
        if 2 <= len(parts) <= 3:
            now = datetime.datetime.now()
            hour = int(parts[0])
            minute = int(parts[1])
            second = int(parts[2]) if len(parts) > 2 else 0
            return datetime.datetime(now.year, now.month, now.day, hour, minute, second)
    except:
        pass
    return None

def get_oldest_time_from_strings(messages):
    """从字符串消息列表中找到最早的时间，返回 (时间字符串, Unix时间戳)"""
    oldest_dt = None
    oldest_str = None
    for msg_line in messages:
        if not isinstance(msg_line, str):
            continue
        dt = parse_msg_time(msg_line)
        if dt and (oldest_dt is None or dt < oldest_dt):
            oldest_dt = dt
            oldest_str = dt.strftime('%Y-%m-%d %H:%M')
    if oldest_dt:
        return oldest_str, int(oldest_dt.timestamp())
    return None, None

def run_wechat_cli(cmd):
    full_cmd = f'wechat-cli {cmd}'
    print(f"    执行: {full_cmd[:80]}...")
    try:
        result = subprocess.run(
            full_cmd, shell=True, capture_output=True, text=True,
            timeout=180, encoding='utf-8', errors='replace'
        )
        data = json.loads(result.stdout)
        return data
    except Exception as e:
        print(f"    [错误] {e}")
        return None

def main():
    print(f"\n{'='*60}")
    print(f"测试: {CHAT_NAME} | 每次{LIMIT}条 | 输出: {OUTPUT_FILE}")
    print(f"{'='*60}\n")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(f"wechat-cli 分页测试\n群名: {CHAT_NAME}\n{'='*60}\n\n")

    total = 0
    page = 0
    after_ts = None

    while True:
        page += 1
        if after_ts:
            cmd = f'history "{CHAT_NAME}" --limit {LIMIT} --after {after_ts}'
        else:
            cmd = f'history "{CHAT_NAME}" --limit {LIMIT}'

        print(f"[第{page}页] 拉取中...")
        data = run_wechat_cli(cmd)
        if not data:
            print("  拉取失败，测试终止\n")
            break

        messages = data.get('messages', [])
        if not isinstance(messages, list):
            print("  消息格式异常\n")
            break

        count = len(messages)
        total += count
        oldest_str, oldest_ts = get_oldest_time_from_strings(messages)

        status = f"✅ 第{page}页: +{count}条"
        if oldest_str:
            status += f" | 最早: {oldest_str}"
        status += f" | 累计: {total}条"
        print(f"  {status}\n")
        with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
            f.write(status + "\n")

        if count == 0:
            print("📭 已翻到底！\n")
            break
        if oldest_ts is None:
            print("⚠️ 无法识别时间戳，测试终止\n")
            break

        after_ts = oldest_ts

    summary = f"\n{'='*60}\n总计 {page} 次拉取，共 {total} 条消息\n{'='*60}"
    print(summary)
    with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
        f.write(summary + "\n")
    print(f"详细日志: {os.path.abspath(OUTPUT_FILE)}")

if __name__ == "__main__":
    main()