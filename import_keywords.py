# import_keywords.py
from data.storage import init_db, add_keyword

# 先确保表存在
init_db()

# 从旧的 config.py 导入关键词（这里需要你自己维护）
old_work_keywords = [
    "报价", "合同", "方案", "会议", "项目", "客户",
    "预算", "付款", "发票", "报告", "审批", "截止",
    "紧急", "马上", "尽快", "今天", "明天", "下午",
    "确认", "安排", "处理", "跟进", "联系", "电话",
    "订单", "发货", "物流", "验收", "结算",
]

old_urgent_keywords = [
    "紧急", "马上", "立刻", "速回", "急急急", "出事了",
]

for kw in old_work_keywords:
    add_keyword(kw, 'work')

for kw in old_urgent_keywords:
    add_keyword(kw, 'urgent')

print("旧关键词导入完成！")