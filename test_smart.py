from core.engine import MessageEngine

e = MessageEngine()
e._work_keywords = ['需求', 'bug']
e._urgent_keywords = ['紧急', '马上']

msgs = [
    {'chat': '项目群', 'sender': '张三', 'content': '这个需求周五之前完成，涉及金额5000元预算', 'time': '2026-05-07 10:00', 'username': 'wxid_abc'},
    {'chat': '项目群', 'sender': '李四', 'content': '@王五 说紧急修复这个bug，尽快处理', 'time': '2026-05-07 10:05', 'username': 'wxid_def'},
    {'chat': '项目群', 'sender': '赵六', 'content': '下午3点开会讨论方案', 'time': '2026-05-07 10:10', 'username': 'wxid_ghi'},
]

result = e._filter_and_tag(msgs)
for m in result:
    print(f"chat={m['chat']}, sender={m['sender']}, urgent={m['is_urgent']}, work={m['is_work']}, source={m['source_person']}, deadline={m['deadline']}, cat={m['category']}, prio={m['priority_level']}")
