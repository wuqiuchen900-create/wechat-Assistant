"""
私人信息助理 v1.0
一站式管理所有待办事项和信息监控

启动：python assistant.py
浏览器打开：http://localhost:8080

pip install fastapi uvicorn watchdog jinja2
"""
import os
import re
import json
import time
import uuid
import sqlite3
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("assistant")

# ============================================================
#  数据模型
# ============================================================

class Priority(Enum):
    URGENT = 3    # 紧急
    HIGH = 2      # 重要
    NORMAL = 1    # 普通
    LOW = 0       # 低


class TaskStatus(Enum):
    PENDING = "pending"
    DONE = "done"
    SNOOZED = "snoozed"


@dataclass
class Task:
    id: str = ""
    title: str = ""
    detail: str = ""
    source: str = ""          # 来源: dingtalk / file / manual / wechat
    source_file: str = ""     # 来源文件路径
    priority: int = 1         # 0-3
    status: str = "pending"
    tags: str = ""            # 逗号分隔的标签
    created_at: str = ""
    updated_at: str = ""
    due_date: str = ""        # 截止日期
    done_at: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = uuid.uuid4().hex[:12]
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not self.updated_at:
            self.updated_at = self.created_at


@dataclass
class InfoItem:
    """信息条目（非任务，但需要记录）"""
    id: str = ""
    content: str = ""
    source: str = ""
    source_file: str = ""
    category: str = ""        # 分类: 数据/合同/通知/其他
    created_at: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = uuid.uuid4().hex[:12]
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class AlertRule:
    """告警规则"""
    id: str = ""
    name: str = ""
    keywords: str = ""        # 逗号分隔
    regex_pattern: str = ""
    priority: int = 2
    enabled: bool = True
    action: str = "task"      # task / alert / log

    def __post_init__(self):
        if not self.id:
            self.id = uuid.uuid4().hex[:12]


# ============================================================
#  数据库
# ============================================================

class Database:
    def __init__(self, db_path: str = "assistant.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                detail TEXT DEFAULT '',
                source TEXT DEFAULT '',
                source_file TEXT DEFAULT '',
                priority INTEGER DEFAULT 1,
                status TEXT DEFAULT 'pending',
                tags TEXT DEFAULT '',
                created_at TEXT,
                updated_at TEXT,
                due_date TEXT DEFAULT '',
                done_at TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS info_items (
                id TEXT PRIMARY KEY,
                content TEXT,
                source TEXT DEFAULT '',
                source_file TEXT DEFAULT '',
                category TEXT DEFAULT '',
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS alert_rules (
                id TEXT PRIMARY KEY,
                name TEXT,
                keywords TEXT DEFAULT '',
                regex_pattern TEXT DEFAULT '',
                priority INTEGER DEFAULT 2,
                enabled INTEGER DEFAULT 1,
                action TEXT DEFAULT 'task'
            );

            CREATE TABLE IF NOT EXISTS scan_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT,
                matched_rules TEXT,
                created_at TEXT
            );
        """)
        self.conn.commit()

    # ── 任务 ──

    def add_task(self, task: Task):
        self.conn.execute(
            """INSERT OR REPLACE INTO tasks
               (id,title,detail,source,source_file,priority,status,tags,
                created_at,updated_at,due_date,done_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (task.id, task.title, task.detail, task.source, task.source_file,
             task.priority, task.status, task.tags, task.created_at,
             task.updated_at, task.due_date, task.done_at)
        )
        self.conn.commit()

    def get_tasks(self, status: str = None, limit: int = 200) -> list[Task]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM tasks WHERE status=? ORDER BY priority DESC, created_at DESC LIMIT ?",
                (status, limit)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM tasks ORDER BY status, priority DESC, created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [Task(**dict(r)) for r in rows]

    def update_task_status(self, task_id: str, status: str):
        done_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == "done" else ""
        self.conn.execute(
            "UPDATE tasks SET status=?, done_at=?, updated_at=? WHERE id=?",
            (status, done_at, done_at, task_id)
        )
        self.conn.commit()

    def delete_task(self, task_id: str):
        self.conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        self.conn.commit()

    def count_tasks(self, status: str = None) -> int:
        if status:
            return self.conn.execute(
                "SELECT count(*) FROM tasks WHERE status=?", (status,)
            ).fetchone()[0]
        return self.conn.execute("SELECT count(*) FROM tasks").fetchone()[0]

    # ── 信息条目 ──

    def add_info(self, item: InfoItem):
        self.conn.execute(
            """INSERT INTO info_items (id,content,source,source_file,category,created_at)
               VALUES (?,?,?,?,?,?)""",
            (item.id, item.content, item.source, item.source_file,
             item.category, item.created_at)
        )
        self.conn.commit()

    def get_infos(self, limit: int = 100) -> list[InfoItem]:
        rows = self.conn.execute(
            "SELECT * FROM info_items ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [InfoItem(**dict(r)) for r in rows]

    # ── 规则 ──

    def add_rule(self, rule: AlertRule):
        self.conn.execute(
            """INSERT OR REPLACE INTO alert_rules
               (id,name,keywords,regex_pattern,priority,enabled,action)
               VALUES (?,?,?,?,?,?,?)""",
            (rule.id, rule.name, rule.keywords, rule.regex_pattern,
             rule.priority, int(rule.enabled), rule.action)
        )
        self.conn.commit()

    def get_rules(self) -> list[AlertRule]:
        rows = self.conn.execute("SELECT * FROM alert_rules").fetchall()
        rules = []
        for r in rows:
            d = dict(r)
            d["enabled"] = bool(d["enabled"])
            rules.append(AlertRule(**d))
        return rules

    def delete_rule(self, rule_id: str):
        self.conn.execute("DELETE FROM alert_rules WHERE id=?", (rule_id,))
        self.conn.commit()

    # ── 扫描日志 ──

    def log_scan(self, file_path: str, matched: str):
        self.conn.execute(
            "INSERT INTO scan_log (file_path, matched_rules, created_at) VALUES (?,?,?)",
            (file_path, matched, datetime.now().isoformat())
        )
        self.conn.commit()

    def close(self):
        self.conn.close()


# ============================================================
#  规则引擎
# ============================================================

class RuleEngine:
    def __init__(self, db: Database):
        self.db = db
        self._compiled_cache = {}
        self._last_reload = 0

    def _reload_rules(self):
        now = time.time()
        if now - self._last_reload < 5:  # 5秒缓存
            return
        self._last_reload = now
        rules = self.db.get_rules()
        self._compiled_cache = {}
        for rule in rules:
            if not rule.enabled:
                continue
            compiled = []
            if rule.keywords:
                compiled.extend([("keyword", kw.strip()) for kw in rule.keywords.split(",") if kw.strip()])
            if rule.regex_pattern:
                try:
                    compiled.append(("regex", re.compile(rule.regex_pattern)))
                except re.error:
                    pass
            if compiled:
                self._compiled_cache[rule.id] = {
                    "rule": rule,
                    "patterns": compiled,
                }

    def scan_text(self, text: str, source: str = "", file_path: str = "") -> list[dict]:
        """扫描文本，返回匹配的规则"""
        self._reload_rules()
        matches = []

        for rule_id, entry in self._compiled_cache.items():
            rule = entry["rule"]
            for ptype, pattern in entry["patterns"]:
                hit = False
                if ptype == "keyword" and pattern in text:
                    hit = True
                elif ptype == "regex" and pattern.search(text):
                    hit = True

                if hit:
                    matches.append({
                        "rule": rule,
                        "pattern": pattern if ptype == "keyword" else pattern.pattern,
                        "source": source,
                        "file_path": file_path,
                    })
                    break

        return matches

    def process_file(self, file_path: str, source: str = "file") -> list[dict]:
        """扫描文件内容"""
        content = self._read_file(file_path)
        if not content:
            return []

        matches = self.scan_text(content, source, file_path)

        # 自动创建任务或记录信息
        for match in matches:
            rule = match["rule"]

            # 提取上下文
            keyword = match["pattern"]
            context = self._extract_context(content, keyword) if isinstance(keyword, str) else ""

            if rule.action == "task":
                task = Task(
                    title=f"[{rule.name}] {Path(file_path).name}",
                    detail=context[:500] if context else f"文件 {Path(file_path).name} 命中规则 [{rule.name}]",
                    source=source,
                    source_file=file_path,
                    priority=rule.priority,
                    tags=rule.name,
                )
                self.db.add_task(task)
                logger.info(f"📋 新任务: {task.title}")

            elif rule.action == "alert":
                task = Task(
                    title=f"🚨 [{rule.name}] {Path(file_path).name}",
                    detail=context[:500] if context else "",
                    source=source,
                    source_file=file_path,
                    priority=max(rule.priority, 2),
                    tags=f"告警,{rule.name}",
                )
                self.db.add_task(task)
                logger.warning(f"🚨 告警: {task.title}")

            elif rule.action == "log":
                info = InfoItem(
                    content=f"[{rule.name}] {context[:200]}" if context else f"[{rule.name}] {Path(file_path).name}",
                    source=source,
                    source_file=file_path,
                    category=rule.name,
                )
                self.db.add_info(info)
                logger.info(f"📝 记录: {info.content[:60]}")

        return matches

    def _read_file(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        text_exts = {".txt", ".log", ".csv", ".json", ".xml", ".md", ".ini",
                     ".conf", ".cfg", ".py", ".java", ".sql", ".html", ".yaml"}
        if ext in text_exts:
            for enc in ["utf-8", "gbk", "gb2312", "latin-1"]:
                try:
                    with open(file_path, "r", encoding=enc) as f:
                        return f.read()
                except (UnicodeDecodeError, UnicodeError):
                    continue
        if ext == ".docx":
            try:
                import docx
                return "\n".join(p.text for p in docx.Document(file_path).paragraphs)
            except:
                pass
        if ext in (".xlsx", ".xls"):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(file_path, read_only=True)
                texts = []
                for ws in wb.worksheets:
                    for row in ws.iter_rows(values_only=True):
                        texts.extend(str(c) for c in row if c is not None)
                return "\n".join(texts)
            except:
                pass
        if ext == ".pdf":
            try:
                import fitz
                return "\n".join(page.get_text() for page in fitz.open(file_path))
            except:
                pass
        return ""

    def _extract_context(self, content: str, keyword: str, ctx_len: int = 80) -> str:
        idx = content.find(keyword)
        if idx == -1:
            return ""
        start = max(0, idx - ctx_len)
        end = min(len(content), idx + len(keyword) + ctx_len)
        return content[start:end].replace("\n", " ").strip()


# ============================================================
#  文件夹监控
# ============================================================

class FileMonitor:
    def __init__(self, engine: RuleEngine, db: Database):
        self.engine = engine
        self.db = db
        self._watched_dirs = []
        self._processed = set()  # 已处理的文件

    def add_directory(self, dir_path: str, source: str = "file"):
        self._watched_dirs.append((dir_path, source))

    def scan_existing(self):
        """扫描已有文件"""
        count = 0
        for dir_path, source in self._watched_dirs:
            if not Path(dir_path).exists():
                continue
            for f in Path(dir_path).rglob("*"):
                if f.is_file() and f.stat().st_size < 50 * 1024 * 1024:
                    key = str(f)
                    if key not in self._processed:
                        self._processed.add(key)
                        matches = self.engine.process_file(str(f), source)
                        if matches:
                            count += 1
        return count

    def start_watching(self):
        """启动实时监控"""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            logger.warning("watchdog 未安装，跳过实时监控: pip install watchdog")
            return

        handler = FileHandler(self.engine, self.db, self._processed)
        observer = Observer()
        for dir_path, source in self._watched_dirs:
            if Path(dir_path).exists():
                observer.schedule(handler, dir_path, recursive=True)
                logger.info(f"  实时监控: {dir_path}")
        observer.start()
        return observer


class FileHandler:
    def __init__(self, engine, db, processed):
        self.engine = engine
        self.db = db
        self._processed = processed

    def on_created(self, event):
        if event.is_directory:
            return
        time.sleep(1)  # 等文件写完
        key = event.src_path
        if key not in self._processed:
            self._processed.add(key)
            self.engine.process_file(key, "file_realtime")

    def on_modified(self, event):
        if event.is_directory:
            return
        time.sleep(1)
        self.engine.process_file(event.src_path, "file_realtime")


# ============================================================
#  钉钉 API 集成（可选）
# ============================================================

class DingTalkIntegration:
    """
    钉钉开放平台集成
    如果配置了就启用，没配置就跳过
    """

    def __init__(self, engine: RuleEngine, db: Database):
        self.engine = engine
        self.db = db
        self.enabled = False
        self.app_key = ""
        self.app_secret = ""

    def configure(self, app_key: str, app_secret: str):
        self.app_key = app_key
        self.app_secret = app_secret
        if app_key and app_secret:
            self.enabled = True
            logger.info("钉钉 API 已配置")

    def on_dingtalk_message(self, title: str, content: str):
        """处理钉钉消息"""
        text = f"{title}: {content}"
        matches = self.engine.scan_text(text, "dingtalk")
        for match in matches:
            rule = match["rule"]
            if rule.action in ("task", "alert"):
                task = Task(
                    title=f"[钉钉] {title}",
                    detail=content[:500],
                    source="dingtalk",
                    priority=rule.priority,
                    tags=rule.name,
                )
                self.db.add_task(task)
                logger.info(f"📋 钉钉任务: {task.title}")


# ============================================================
#  Web 界面
# ============================================================

def create_app(db: Database, engine: RuleEngine, monitor: FileMonitor,
               dingtalk: DingTalkIntegration) -> FastAPI:

    app = FastAPI(title="私人信息助理")

    # ── 首页看板 ──

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        pending = db.get_tasks("pending")
        done_today = db.get_tasks("done")
        today = datetime.now().strftime("%Y-%m-%d")
        done_today = [t for t in done_today if t.done_at and t.done_at.startswith(today)]
        infos = db.get_infos(20)
        rules = db.get_rules()

        urgent = [t for t in pending if t.priority >= 3]
        high = [t for t in pending if t.priority == 2]
        normal = [t for t in pending if t.priority <= 1]

        html = render_dashboard(pending, urgent, high, normal, done_today, infos, rules)
        return html

    # ── 任务操作 ──

    @app.post("/task/done/{task_id}")
    async def done_task(task_id: str):
        db.update_task_status(task_id, "done")
        return RedirectResponse("/", status_code=303)

    @app.post("/task/delete/{task_id}")
    async def delete_task(task_id: str):
        db.delete_task(task_id)
        return RedirectResponse("/", status_code=303)

    @app.post("/task/add")
    async def add_task(
        title: str = Form(...),
        detail: str = Form(""),
        priority: int = Form(1),
        tags: str = Form(""),
    ):
        task = Task(title=title, detail=detail, source="manual", priority=priority, tags=tags)
        db.add_task(task)
        return RedirectResponse("/", status_code=303)

    # ── 规则管理 ──

    @app.post("/rule/add")
    async def add_rule(
        name: str = Form(...),
        keywords: str = Form(""),
        regex_pattern: str = Form(""),
        priority: int = Form(2),
        action: str = Form("task"),
    ):
        rule = AlertRule(
            name=name, keywords=keywords, regex_pattern=regex_pattern,
            priority=priority, action=action
        )
        db.add_rule(rule)
        return RedirectResponse("/", status_code=303)

    @app.post("/rule/delete/{rule_id}")
    async def delete_rule(rule_id: str):
        db.delete_rule(rule_id)
        return RedirectResponse("/", status_code=303)

    # ── API 接口 ──

    @app.get("/api/tasks")
    async def api_tasks(status: str = None):
        tasks = db.get_tasks(status)
        return {"tasks": [asdict(t) for t in tasks]}

    @app.post("/api/message")
    async def api_message(request: Request):
        """外部消息接入接口（钉钉回调、通知转发等）"""
        data = await request.json()
        title = data.get("title", "")
        content = data.get("content", "")
        source = data.get("source", "api")

        text = f"{title}: {content}"
        matches = engine.scan_text(text, source)
        created = []
        for match in matches:
            rule = match["rule"]
            if rule.action in ("task", "alert"):
                task = Task(
                    title=f"[{source}] {title}" if title else f"[{source}] {content[:30]}",
                    detail=content[:500],
                    source=source,
                    priority=rule.priority,
                    tags=rule.name,
                )
                db.add_task(task)
                created.append(task.title)

        return {"status": "ok", "tasks_created": created}

    @app.get("/api/scan")
    async def api_scan():
        """手动触发全盘扫描"""
        count = monitor.scan_existing()
        return {"scanned": count}

    return app


# ============================================================
#  HTML 模板
# ============================================================

def render_dashboard(pending, urgent, high, normal, done_today, infos, rules):
    def task_card(task, show_done=True):
        priority_colors = {3: "#e74c3c", 2: "#f39c12", 1: "#3498db", 0: "#95a5a6"}
        priority_names = {3: "紧急", 2: "重要", 1: "普通", 0: "低"}
        color = priority_colors.get(task.priority, "#3498db")
        pname = priority_names.get(task.priority, "普通")
        source_icons = {
            "dingtalk": "钉钉", "wechat": "微信", "file": "文件",
            "manual": "手动", "api": "API", "file_realtime": "文件",
        }
        src = source_icons.get(task.source, task.source)
        tags_html = ""
        if task.tags:
            for tag in task.tags.split(","):
                if tag.strip():
                    tags_html += f'<span class="tag">{tag.strip()}</span>'

        done_btn = ""
        if show_done:
            done_btn = f'''
            <form method="post" action="/task/done/{task.id}" style="display:inline">
                <button class="btn-done" type="submit">✓ 完成</button>
            </form>
            <form method="post" action="/task/delete/{task.id}" style="display:inline">
                <button class="btn-del" type="submit">✕</button>
            </form>
            '''

        detail_html = ""
        if task.detail:
            detail_html = f'<div class="detail">{task.detail[:200]}</div>'
        file_html = ""
        if task.source_file:
            fname = Path(task.source_file).name
            file_html = f'<span class="file-badge">📎 {fname}</span>'

        return f'''
        <div class="task-card" style="border-left: 4px solid {color}">
            <div class="task-header">
                <span class="priority-badge" style="background:{color}">{pname}</span>
                <span class="source-badge">{src}</span>
                {tags_html}
                {file_html}
                <span class="time">{task.created_at}</span>
            </div>
            <div class="task-title">{task.title}</div>
            {detail_html}
            <div class="task-actions">{done_btn}</div>
        </div>
        '''

    urgent_html = "".join(task_card(t) for t in urgent) or '<div class="empty">没有紧急任务</div>'
    high_html = "".join(task_card(t) for t in high) or '<div class="empty">没有重要任务</div>'
    normal_html = "".join(task_card(t) for t in normal[:10]) or '<div class="empty">没有普通任务</div>'
    done_html = "".join(task_card(t, show_done=False) for t in done_today[:5])

    rules_html = ""
    for r in rules:
        rules_html += f'''
        <div class="rule-item">
            <b>{r.name}</b> [{r.action}]
            <span class="rule-kw">{r.keywords}</span>
            <form method="post" action="/rule/delete/{r.id}" style="display:inline">
                <button class="btn-del" type="submit">✕</button>
            </form>
        </div>
        '''

    infos_html = ""
    for info in infos[:10]:
        infos_html += f'''
        <div class="info-item">
            <span class="time">{info.created_at}</span>
            <span class="category">{info.category}</span>
            {info.content[:100]}
        </div>
        '''

    return f'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>私人信息助理</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, 
                 "PingFang SC", "Microsoft YaHei", "Helvetica Neue", sans-serif;
}
<style>
:root {{
    --bg: #0f0f13;
    --surface: #1a1a24;
    --surface2: #22222e;
    --accent: #6c5ce7;
    --accent2: #a29bfe;
    --urgent: #e74c3c;
    --high: #f39c12;
    --normal: #3498db;
    --low: #636e72;
    --text: #e8e8e8;
    --text2: #8e8e9e;
    --green: #00b894;
    --border: #2d2d3d;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, 
                 "PingFang SC", "Microsoft YaHei", "Helvetica Neue", sans-serif;}}
.header {{
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    padding: 24px 32px;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
}}
.header h1 {{
    font-size: 22px;
    font-weight: 500;
    color: var(--accent2);
}}
.stats {{
    display: flex;
    gap: 24px;
}}
.stat {{
    text-align: center;
}}
.stat-num {{
    font-size: 28px;
    font-weight: 700;
    color: var(--accent2);
}}
.stat-label {{
    font-size: 12px;
    color: var(--text2);
}}
.container {{
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px;
    display: grid;
    grid-template-columns: 1fr 360px;
    gap: 24px;
}}
.main {{ display: flex; flex-direction: column; gap: 20px; }}
.sidebar {{ display: flex; flex-direction: column; gap: 20px; }}
.section {{
    background: var(--surface);
    border-radius: 12px;
    padding: 20px;
    border: 1px solid var(--border);
}}
.section-title {{
    font-size: 15px;
    font-weight: 500;
    color: var(--text2);
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
}}
.section-title .count {{
    background: var(--accent);
    color: white;
    padding: 1px 8px;
    border-radius: 10px;
    font-size: 12px;
}}
.task-card {{
    background: var(--surface2);
    padding: 14px 16px;
    border-radius: 8px;
    margin-bottom: 10px;
    transition: transform 0.15s;
}}
.task-card:hover {{ transform: translateX(4px); }}
.task-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    flex-wrap: wrap;
}}
.priority-badge {{
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 4px;
    color: white;
    font-weight: 500;
}}
.source-badge {{
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 4px;
    background: var(--surface);
    color: var(--text2);
    border: 1px solid var(--border);
}}
.tag {{
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 3px;
    background: rgba(108,92,231,0.2);
    color: var(--accent2);
}}
.file-badge {{
    font-size: 10px;
    color: var(--text2);
}}
.time {{
    font-size: 11px;
    color: var(--low);
    margin-left: auto;
}}
.task-title {{
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 6px;
    line-height: 1.5;
}}
.detail {{
    font-size: 12px;
    color: var(--text2);
    margin-bottom: 8px;
    line-height: 1.5;
}}
.task-actions {{
    display: flex;
    gap: 8px;
}}
.btn-done {{
    background: var(--green);
    color: white;
    border: none;
    padding: 4px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
}}
.btn-done:hover {{ opacity: 0.8; }}
.btn-del {{
    background: transparent;
    color: var(--low);
    border: 1px solid var(--border);
    padding: 4px 10px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
}}
.btn-del:hover {{ color: var(--urgent); border-color: var(--urgent); }}
.empty {{
    color: var(--low);
    font-size: 13px;
    text-align: center;
    padding: 20px;
}}
.form-group {{
    margin-bottom: 10px;
}}
.form-group label {{
    display: block;
    font-size: 12px;
    color: var(--text2);
    margin-bottom: 4px;
}}
.form-group input, .form-group textarea, .form-group select {{
    width: 100%;
    background: var(--surface2);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 8px 10px;
    border-radius: 6px;
    font-size: 13px;
    font-family: inherit;
}}
.form-group input:focus, .form-group textarea:focus {{
    outline: none;
    border-color: var(--accent);
}}
.btn-primary {{
    background: var(--accent);
    color: white;
    border: none;
    padding: 8px 20px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    width: 100%;
}}
.btn-primary:hover {{ opacity: 0.85; }}
.rule-item {{
    padding: 8px 10px;
    background: var(--surface2);
    border-radius: 6px;
    margin-bottom: 6px;
    font-size: 13px;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}}
.rule-kw {{
    font-size: 11px;
    color: var(--accent2);
}}
.info-item {{
    padding: 8px 10px;
    background: var(--surface2);
    border-radius: 6px;
    margin-bottom: 6px;
    font-size: 12px;
    color: var(--text2);
}}
.category {{
    font-size: 10px;
    background: var(--surface);
    padding: 1px 6px;
    border-radius: 3px;
    margin-right: 6px;
}}
.done-section .task-card {{ opacity: 0.6; }}
.done-section .task-title {{ text-decoration: line-through; }}
</style>
</head>
<body>

<div class="header">
    <h1>📋 私人信息助理</h1>
    <div class="stats">
        <div class="stat">
            <div class="stat-num" style="color:var(--urgent)">{len(urgent)}</div>
            <div class="stat-label">紧急</div>
        </div>
        <div class="stat">
            <div class="stat-num" style="color:var(--high)">{len(high)}</div>
            <div class="stat-label">重要</div>
        </div>
        <div class="stat">
            <div class="stat-num" style="color:var(--normal)">{len(normal)}</div>
            <div class="stat-label">待办</div>
        </div>
        <div class="stat">
            <div class="stat-num" style="color:var(--green)">{len(done_today)}</div>
            <div class="stat-label">今日完成</div>
        </div>
    </div>
</div>

<div class="container">
    <div class="main">
        <div class="section">
            <div class="section-title">🚨 紧急任务 <span class="count">{len(urgent)}</span></div>
            {urgent_html}
        </div>
        <div class="section">
            <div class="section-title">📌 重要任务 <span class="count">{len(high)}</span></div>
            {high_html}
        </div>
        <div class="section">
            <div class="section-title">📋 待办事项 <span class="count">{len(normal)}</span></div>
            {normal_html}
        </div>
        <div class="section done-section">
            <div class="section-title">✅ 今日完成 <span class="count">{len(done_today)}</span></div>
            {done_html or '<div class="empty">今天还没有完成任务</div>'}
        </div>
    </div>

    <div class="sidebar">
        <div class="section">
            <div class="section-title">➕ 添加任务</div>
            <form method="post" action="/task/add">
                <div class="form-group">
                    <label>任务标题</label>
                    <input name="title" required placeholder="输入任务...">
                </div>
                <div class="form-group">
                    <label>详情</label>
                    <textarea name="detail" rows="2" placeholder="补充说明..."></textarea>
                </div>
                <div class="form-group">
                    <label>优先级</label>
                    <select name="priority">
                        <option value="3">🚨 紧急</option>
                        <option value="2">📌 重要</option>
                        <option value="1" selected>📋 普通</option>
                        <option value="0">📝 低</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>标签</label>
                    <input name="tags" placeholder="用逗号分隔">
                </div>
                <button class="btn-primary" type="submit">添加任务</button>
            </form>
        </div>

        <div class="section">
            <div class="section-title">⚡ 监控规则</div>
            {rules_html or '<div class="empty">暂无规则</div>'}
            <form method="post" action="/rule/add" style="margin-top:12px">
                <div class="form-group">
                    <input name="name" placeholder="规则名称" required>
                </div>
                <div class="form-group">
                    <input name="keywords" placeholder="关键词(逗号分隔)">
                </div>
                <div class="form-group">
                    <input name="regex_pattern" placeholder="正则表达式(可选)">
                </div>
                <div class="form-group">
                    <select name="action">
                        <option value="task">创建任务</option>
                        <option value="alert">紧急告警</option>
                        <option value="log">仅记录</option>
                    </select>
                </div>
                <button class="btn-primary" type="submit">添加规则</button>
            </form>
        </div>

        <div class="section">
            <div class="section-title">📝 最近信息</div>
            {infos_html or '<div class="empty">暂无信息</div>'}
        </div>
    </div>
</div>

</body>
</html>'''


# ============================================================
#  启动
# ============================================================

def init_default_rules(db: Database):
    """初始化默认规则"""
    existing = db.get_rules()
    if existing:
        return

    defaults = [
        AlertRule(name="紧急事项", keywords="紧急,故障,报警,P0,P1,宕机", priority=3, action="alert"),
        AlertRule(name="任务提取", keywords="请,帮忙,处理,跟进,确认,尽快,记得,务必,待办", priority=2, action="task"),
        AlertRule(name="合同财务", keywords="合同,报价,发票,付款,预算,成本", priority=2, action="task"),
        AlertRule(name="数据报表", keywords="报表,统计,分析,指标,KPI,数据", priority=1, action="task"),
        AlertRule(name="会议相关", keywords="会议,开会,日程,约,讨论", priority=1, action="task"),
        AlertRule(name="手机号码", regex_pattern=r"1[3-9]\\d{9}", priority=0, action="log"),
        AlertRule(name="金额", regex_pattern=r"[\\d,]+\\.?\\d*元|¥[\\d,]+", priority=1, action="log"),
    ]
    for rule in defaults:
        db.add_rule(rule)
    logger.info(f"已初始化 {len(defaults)} 条默认规则")


def auto_discover_dirs() -> list[tuple[str, str]]:
    """自动发现可监控的目录"""
    dirs = []
    base = Path(os.environ.get("APPDATA", "")) / "Tencent" / "xwechat"
    if base.exists():
        for d in base.rglob("*"):
            if d.is_dir() and len(d.name) >= 20:
                for sub in ["File", "Msg", "Files"]:
                    p = d / sub
                    if p.exists():
                        dirs.append((str(p), "wechat"))

    dd = Path(os.environ.get("USERPROFILE", "")) / "Documents" / "DingTalk"
    if dd.exists():
        dirs.append((str(dd), "dingtalk"))

    downloads = Path(os.environ.get("USERPROFILE", "")) / "Downloads"
    if downloads.exists():
        dirs.append((str(downloads), "download"))

    return dirs


def main():
    print("=" * 55)
    print("  私人信息助理 v1.0")
    print("=" * 55)

    db = Database()
    engine = RuleEngine(db)
    monitor = FileMonitor(engine, db)
    dingtalk = DingTalkIntegration(engine, db)

    # 初始化默认规则
    init_default_rules(db)

    # 自动发现目录
    dirs = auto_discover_dirs()
    for dir_path, source in dirs:
        monitor.add_directory(dir_path, source)
        logger.info(f"  发现目录 [{source}]: {dir_path}")

    # 扫描已有文件
    print("\n扫描已有文件...")
    count = monitor.scan_existing()
    print(f"  扫描完成: {count} 个文件命中规则")

    # 启动文件监控
    print("\n启动文件监控...")
    observer = monitor.start_watching()

    # 创建 Web 应用
    app = create_app(db, engine, monitor, dingtalk)

    import socket
    ip = socket.gethostbyname(socket.gethostname())
    print(f"\n{'='*55}")
    print(f"  ✓ 服务已启动!")
    print(f"  浏览器打开: http://localhost:8080")
    print(f"  局域网访问: http://{ip}:8080")
    print(f"{'='*55}\n")

    uvicorn.run(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
