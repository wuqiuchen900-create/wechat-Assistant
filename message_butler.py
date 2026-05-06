# message_butler.py
import subprocess
import json
import os
import time
from datetime import datetime
from plyer import notification
# ====== 配置区 ======

# 黑名单：这些会话的消息直接忽略
BLACKLIST = [
    "顺丰速运", "京东快递", "中国联通", "地下城与勇士",
    "K米", "长安汽车", "木里木外", "系统实用工具",
    "玩转光雾山", "巴中市精神卫生中心", "小鱼",
]

# 工作关键词：包含这些词的消息被认为是工作相关
WORK_KEYWORDS = [
    "报价", "合同", "方案", "会议", "项目", "客户",
    "预算", "付款", "发票", "报告", "审批", "截止",
    "紧急", "马上", "尽快", "今天", "明天", "下午",
    "确认", "安排", "处理", "跟进", "联系", "电话",
    "订单", "发货", "物流", "验收", "结算",
]

# 极高优先级关键词：触发桌面弹窗
URGENT_KEYWORDS = [
    "紧急", "马上", "立刻", "速回", "急急急", "出事了",
]

# 轮询间隔（秒）
POLL_INTERVAL = 10  # 5分钟

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'message_data')
REPORT_DIR = os.path.join(BASE_DIR, 'reports')


# ====== 初始化目录 ======
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)


# ====== 核心函数 ======

def run_new_messages():
    try:
        result = subprocess.run(
            "wechat-cli unread",
            capture_output=True,
            text=True,
            shell=False,
            encoding='utf-8',      # 强制 UTF-8
            errors='replace',      # 万一有极端字符，用 � 替代，不崩溃
            timeout=30
        )
        if result.returncode != 0:
            print(f"[警告] 命令执行异常: {result.stderr}")
            return []
        data = json.loads(result.stdout)
        if isinstance(data, list):
            messages = []
            for session in data:
                if session.get('unread', 0) > 0:
                    messages.append({
                        'chat': session.get('chat', ''),
                        'sender': session.get('last_sender', ''),
                        'last_message': session.get('last_message', ''),
                        'timestamp': session.get('timestamp', 0),
                        'time': session.get('time', ''),
                        'unread': session.get('unread', 0)
                    })
            return messages
        else:
            print(f"[警告] 未知的返回格式: {type(data)}")
            return []
    except Exception as e:
        print(f"[错误] 获取未读消息失败: {e}")
        return []
    
def load_old_messages(filepath):
    """读取旧的导出文件"""
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []


def save_messages(messages, filepath):
    """保存消息到文件"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)


def get_message_id(msg):
    """生成消息的唯一标识，用于去重"""
    chat = msg.get('chat', '')
    sender = msg.get('sender', '') or msg.get('last_sender', '')
    content = msg.get('content', '') or msg.get('last_message', '')
    ts = msg.get('timestamp', 0)
    return f"{chat}|{sender}|{ts}|{content[:30]}"

def filter_messages(messages, blacklist):
    """过滤黑名单会话"""
    result = []
    for msg in messages:
        chat = msg.get('chat', '')
        if chat in blacklist:
            continue
        result.append(msg)
    return result


def find_new_messages(current, old_ids):
    """找出新增消息（与旧记录对比）"""
    new_msgs = []
    for msg in current:
        msg_id = get_message_id(msg)
        if msg_id not in old_ids:
            new_msgs.append(msg)
    return new_msgs


def check_work_relevance(msg):
    """检查消息是否与工作相关"""
    content = msg.get('last_message', '') or msg.get('content', '')
    for kw in WORK_KEYWORDS:
        if kw in content:
            return True, kw
    return False, None


def check_urgent(msg):
    """检查消息是否紧急"""
    content = msg.get('last_message', '') or msg.get('content', '')
    for kw in URGENT_KEYWORDS:
        if kw in content:
            return True, kw
    return False, None


def send_notification(title, message):
    """发送桌面通知"""
    try:
        notification.notify(
            title=title,
            message=message,
            timeout=10
        )
    except:
        print(f"[弹窗] {title}: {message}")


def generate_report(all_new_msgs, work_msgs, urgent_msgs):
    """生成简报，记录所有新增消息，并标注工作相关"""
    today = datetime.now().strftime('%Y%m%d')
    report_path = os.path.join(REPORT_DIR, f'简报_{today}.md')

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = []
    lines.append(f"## 📩 {now_str} 轮询新增 {len(all_new_msgs)} 条消息")
    lines.append("")

    if not all_new_msgs:
        lines.append("✅ 本轮无新增消息。")
        lines.append("")
    else:
        # 先列出紧急消息
        if urgent_msgs:
            lines.append("### 🔴 紧急消息")
            for msg in urgent_msgs:
                chat = msg.get('chat', '未知')
                content = msg.get('last_message', '')
                lines.append(f"- **{chat}**: {content}")
            lines.append("")

        # 列出工作相关消息（不含紧急）
        normal_work = [m for m in work_msgs if m not in urgent_msgs]
        if normal_work:
            lines.append("### 📋 工作相关消息")
            for msg in normal_work:
                chat = msg.get('chat', '未知')
                content = msg.get('last_message', '')
                keywords = [kw for kw in WORK_KEYWORDS if kw in content]
                lines.append(f"- **{chat}** `{', '.join(keywords)}`: {content}")
            lines.append("")

        # 列出其他普通消息
        other_msgs = [m for m in all_new_msgs if m not in work_msgs and m not in urgent_msgs]
        if other_msgs:
            lines.append("### 💬 其他消息")
            for msg in other_msgs:
                chat = msg.get('chat', '未知')
                content = msg.get('last_message', '')
                lines.append(f"- **{chat}**: {content}")
            lines.append("")

    # 追加写入文件
    with open(report_path, 'a', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    return report_path


def main_loop():
    """主循环：轮询 → 对比 → 过滤 → 生成简报"""
    old_file = os.path.join(DATA_DIR, 'last_messages.json')
    all_ids_file = os.path.join(DATA_DIR, 'all_known_ids.json')

    print(f"🚀 微信消息管家启动")
    print(f"   黑名单: {', '.join(BLACKLIST[:5])}... 共 {len(BLACKLIST)} 个")
    print(f"   轮询间隔: {POLL_INTERVAL} 秒")
    print(f"   按 Ctrl+C 停止\n")

    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 正在获取新消息...")

            # 1. 获取当前新消息
            current_msgs = run_new_messages()
            if not current_msgs:
                print("   无新消息或获取失败")
                time.sleep(POLL_INTERVAL)
                continue

            # 2. 过滤黑名单
            filtered = filter_messages(current_msgs, BLACKLIST)
            print(f"   获取到 {len(current_msgs)} 条，过滤后 {len(filtered)} 条")

            # 3. 加载已知消息ID
            known_ids = set(load_old_messages(all_ids_file))

            # 4. 找出真正的新增消息
            new_msgs = find_new_messages(filtered, known_ids)
            print(f"   新增消息: {len(new_msgs)} 条")

            # 5. 更新已知ID文件
            for msg in new_msgs:
                known_ids.add(get_message_id(msg))
            save_messages(list(known_ids), all_ids_file)

            # 6. 分析工作相关和紧急消息
            work_msgs = []
            urgent_msgs = []
            for msg in new_msgs:
                is_work, kw = check_work_relevance(msg)
                if is_work:
                    work_msgs.append(msg)

                is_urgent, kw = check_urgent(msg)
                if is_urgent:
                    urgent_msgs.append(msg)
                    # 弹窗提醒
                    chat = msg.get('chat', '未知')
                    content = msg.get('last_message', '') or msg.get('content', '')
                    send_notification(
                        f"🔴 紧急消息 - {chat}",
                        content[:100]
                    )

            # 7. 生成简报
            if work_msgs or urgent_msgs:
                report = generate_report(new_msgs, work_msgs, urgent_msgs)
                print(f"   简报已更新: {report}")

            if urgent_msgs:
                print(f"   ⚠️ 紧急消息 {len(urgent_msgs)} 条，已弹窗提醒")

            # 8. 等待下一轮
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\n\n👋 已退出。")
            break
        except Exception as e:
            print(f"[错误] {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main_loop()