# core/ai_search.py
import json
import re
from debug_log import logger

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    logger.warning("[AI] requests 库未安装，网络 API 不可用")


class AISearchEngine:
    def __init__(self):
        self._provider = None
        self._api_key = None
        self._api_url = None
        self._model = None
        self._local_model = None

    def configure(self, provider=None, api_key=None, api_url=None, model=None):
        self._provider = provider
        self._api_key = api_key
        self._api_url = api_url
        self._model = model

    def search(self, query, messages, use_local=False):
        if not messages:
            return "没有可分析的消息数据。"

        context = self._build_context(messages, query)

        if use_local and self._local_model:
            return self._search_local(query, context)
        elif self._provider and self._api_key:
            return self._search_api(query, context)
        else:
            return self._search_local_fallback(query, context)

    def _build_context(self, messages, query):
        lines = []
        for m in messages[:30]:
            lines.append(f"[{m.get('time','')}] {m.get('chat','')} - {m.get('sender','')}: {m.get('content','')}")
        context = "\n".join(lines)

        prompt = f"""你是一个智能信息助手，帮助用户从微信聊天记录中检索和分析信息。

用户查询: {query}

相关聊天记录:
{context}

请根据聊天记录回答用户的问题。要求:
1. 如果找到相关信息，请清晰列出
2. 标注每条信息的来源（谁说的、什么时间）
3. 如果涉及金额、截止日期、任务分配等，请特别标注
4. 如果没有找到相关信息，请诚实说明
5. 用中文回答，简洁有条理"""
        return prompt

    def _search_api(self, query, context):
        if not HAS_REQUESTS:
            return "网络请求库未安装，无法使用 API 搜索。请安装 requests 库。"

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self._model or "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "你是一个智能信息助手，帮助用户从微信聊天记录中检索和分析信息。"},
                {"role": "user", "content": context}
            ],
            "temperature": 0.3,
            "max_tokens": 1500
        }

        try:
            url = self._api_url or "https://api.openai.com/v1/chat/completions"
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "API 返回为空")
            else:
                logger.error(f"[AI] API 错误: {resp.status_code} {resp.text[:200]}")
                return f"API 请求失败 (状态码: {resp.status_code})"
        except Exception as e:
            logger.error(f"[AI] 请求异常: {e}")
            return f"AI 分析请求失败: {str(e)}"

    def _search_local(self, query, context):
        return self._search_local_fallback(query, context)

    def _search_local_fallback(self, query, context):
        lines = context.split("\n")
        relevant = []
        keywords = self._extract_keywords(query)

        for line in lines:
            if not line.strip():
                continue
            score = 0
            for kw in keywords:
                if kw.lower() in line.lower():
                    score += 1
            if score > 0:
                relevant.append((score, line))

        relevant.sort(key=lambda x: -x[0])

        if not relevant:
            return f"未在聊天记录中找到与 \"{query}\" 相关的信息。\n\n建议：\n- 尝试使用不同的关键词\n- 扩大搜索时间范围\n- 检查消息是否已同步"

        result_lines = [f"\U0001f50d 关于 \"{query}\" 的智能分析结果：\n"]
        result_lines.append(f"共找到 {len(relevant)} 条相关信息：\n")

        for i, (score, line) in enumerate(relevant[:15], 1):
            result_lines.append(f"{i}. {line}")

        if len(relevant) > 15:
            result_lines.append(f"\n... 还有 {len(relevant) - 15} 条相关消息")

        amounts = []
        for line in lines:
            amt = re.findall(r'(\d+\.?\d*)\s*(万|w|k|千|百|元|块|块钱|万元)', line, re.IGNORECASE)
            if amt:
                amounts.extend(amt)

        if amounts:
            result_lines.append(f"\n\U0001f4b0 涉及金额相关: {len(amounts)} 处")

        deadlines = []
        for line in lines:
            dl = re.findall(r'(截止|deadline|ddl|到期|之前|尽快|asap|urgent|紧急)', line, re.IGNORECASE)
            if dl:
                deadlines.extend(dl)
        if deadlines:
            result_lines.append(f"\U0001f514 涉及截止/紧急: {len(deadlines)} 处")

        return "\n".join(result_lines)

    def _extract_keywords(self, query):
        keywords = [query]
        for kw in re.split(r'[\s,，、]+', query):
            kw = kw.strip()
            if kw and len(kw) >= 1:
                keywords.append(kw)
        return list(set(keywords))
