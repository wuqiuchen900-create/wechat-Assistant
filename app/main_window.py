# app/main_window.py
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QTextEdit, QFrame,
                             QSplitter, QListWidget, QListWidgetItem,
                             QSizePolicy, QAbstractItemView, QPlainTextEdit,
                             QStyledItemDelegate, QStyle, QButtonGroup, QProgressBar,QStackedWidget)
from PyQt5.QtCore import Qt, pyqtSlot, QRect, QRectF
from PyQt5.QtGui import QFont, QPainter, QBrush, QColor, QPen, QPainterPath, QPixmap
import time
import os
from data.wechat_cli import get_wechat_data_dir
import requests
from data.wechat_cli import get_contact_detail
from app.settings_page import SettingsPage
from PyQt5.QtWidgets import QApplication
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("微信信息管家")
        self.setMinimumSize(1000, 680)

        self.setStyleSheet("""
            QMainWindow { background-color: #f8f9fa; }
            #sideNav { background-color: #ffffff; border-right: 1px solid #e9ecef; min-width: 180px; max-width: 180px; }
            #navBtn { text-align: left; padding: 14px 20px; border: none; border-radius: 8px; font-size: 13px; color: #495057; background: transparent; }
            #navBtn:hover { background-color: #f1f3f5; }
            #navBtn:checked { background-color: #e7f5ff; color: #1971c2; font-weight: bold; }
            #detailPanel { background: #ffffff; border-left: 1px solid #e9ecef; padding: 20px; }
            #statusBar { background: #ffffff; border-top: 1px solid #e9ecef; padding: 8px 16px; color: #6c757d; font-size: 12px; }
            QListWidget { border: none; background: transparent; }
            QListWidget::item { padding: 8px 10px; border-bottom: 1px solid #f1f3f5; }
            QListWidget::item:hover { background-color: #f8f9fa; }
            QListWidget::item:selected { background-color: #e7f5ff; color: #1971c2; }
            QScrollBar:vertical { width: 12px; background: transparent; }
            QScrollBar::handle:vertical { background: #adb5bd; border-radius: 4px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: #6c757d; }
            QSplitter::handle { background: #dee2e6; width: 6px; height: 6px; }
            QSplitter::handle:hover { background: #adb5bd; }
            #statsPanel { background: #f8f9fa; border-top: 1px solid #e9ecef; padding: 10px 16px; }
        """)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === 左侧导航 ===
        self.nav = QFrame()
        self.nav.setObjectName("sideNav")
        nav_layout = QVBoxLayout(self.nav)
        nav_layout.setContentsMargins(10, 20, 10, 20)
        nav_layout.setSpacing(6)

        logo = QLabel("📋 信息管家")
        logo_font = QFont()
        logo_font.setPointSize(15)
        logo_font.setBold(True)
        logo.setFont(logo_font)
        logo.setStyleSheet("padding: 10px 14px; color: #212529;")
        nav_layout.addWidget(logo)
        nav_layout.addSpacing(20)

        self.btn_realtime = QPushButton("📩 实时消息")
        self.btn_realtime.setObjectName("navBtn")
        self.btn_realtime.setCheckable(True)
        self.btn_realtime.setChecked(True)
        self.btn_report = QPushButton("📊 每日简报")
        self.btn_report.setObjectName("navBtn")
        self.btn_report.setCheckable(True)
        self.btn_history = QPushButton("🔍 历史检索")
        self.btn_history.setObjectName("navBtn")
        self.btn_history.setCheckable(True)
        self.btn_settings = QPushButton("⚙️ 设置")
        self.btn_settings.setObjectName("navBtn")
        self.btn_settings.setCheckable(True)

        for btn in [self.btn_realtime, self.btn_report, self.btn_history, self.btn_settings]:
            nav_layout.addWidget(btn)
        nav_layout.addStretch()
                # 按钮组：实现导航按钮单选
        self.nav_group = QButtonGroup()
        self.nav_group.addButton(self.btn_realtime)
        self.nav_group.addButton(self.btn_report)
        self.nav_group.addButton(self.btn_history)
        self.nav_group.addButton(self.btn_settings)
        self.nav_group.setExclusive(True)
        self.btn_realtime.clicked.connect(lambda: self._switch_page(0))
        self.btn_report.clicked.connect(lambda: self._switch_page(1))
        self.btn_history.clicked.connect(lambda: self._switch_page(2))
        self.btn_settings.clicked.connect(self._open_settings)  # 组内按钮互斥

        footer = QLabel("v0.4 · 本地运行")
        footer.setStyleSheet("color: #adb5bd; font-size: 11px; padding: 10px;")
        nav_layout.addWidget(footer)
        main_layout.addWidget(self.nav)

        # === 右侧区域 ===
        right_outer = QVBoxLayout()
        right_outer.setContentsMargins(0, 0, 0, 0)
        right_outer.setSpacing(0)

        h_splitter = QSplitter(Qt.Horizontal)

        # ---------- 创建会话列表 ----------
        self.session_list = QListWidget()
        self.session_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.session_list.itemClicked.connect(self.on_session_clicked)

        # ---------- 统计面板 ----------
        self.stats_panel = QFrame()
        self.stats_panel.setObjectName("statsPanel")
        stats_layout = QHBoxLayout(self.stats_panel)
        stats_layout.setContentsMargins(16, 8, 16, 8)

        self.stats_today = QLabel("📊 今日: 0 条")
        self.stats_today.setStyleSheet("font-size: 12px;")
        self.stats_active = QLabel("💬 活跃会话: 0 个")
        self.stats_active.setStyleSheet("font-size: 12px;")
        self.stats_urgent = QLabel("🔴 紧急: 0 条")
        self.stats_urgent.setStyleSheet("font-size: 12px; color: #e74c3c;")
        self.stats_total = QLabel("📦 缓存: 0 条")
        self.stats_total.setStyleSheet("font-size: 12px;")

        stats_layout.addWidget(self.stats_today)
        stats_layout.addWidget(self.stats_active)
        stats_layout.addWidget(self.stats_urgent)
        stats_layout.addWidget(self.stats_total)
        stats_layout.addStretch()

        # ---------- 状态栏区域（普通状态）----------
        self.status_bar = QLabel("就绪 | 等待新消息...")
        self.status_bar.setObjectName("statusBar")

        # ---------- 进度条区域（同步时显示）----------
        self.sync_progress_bar = QProgressBar()
        self.sync_progress_bar.setRange(0, 100)
        self.sync_progress_bar.setValue(0)
        self.sync_progress_bar.setTextVisible(False)  # 不显示文字
        self.sync_progress_bar.setFixedHeight(4)       # 细线高度
        self.sync_progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background: transparent;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6c5ce7, stop:0.5 #a29bfe, stop:1 #6c5ce7);
                border-radius: 2px;
            }
        """)

        # ---------- 用 QStackedWidget 切换显示 ----------
        self.status_stack = QStackedWidget()
        self.status_stack.addWidget(self.sync_progress_bar)  # index 0: 进度条
        self.status_stack.addWidget(self.status_bar)         # index 1: 状态栏
        self.status_stack.setCurrentIndex(1)                 # 默认显示状态栏

        # ---------- 垂直分割器 ----------
        v_splitter = QSplitter(Qt.Vertical)
        v_splitter.setHandleWidth(8)
        v_splitter.addWidget(self.session_list)
        v_splitter.addWidget(self.stats_panel)
        v_splitter.addWidget(self.status_stack)      # ← 只加这一个
        v_splitter.setSizes([380, 80, 30])
        v_splitter.setStretchFactor(0, 5)
        v_splitter.setStretchFactor(1, 1)
        v_splitter.setStretchFactor(2, 0)
        self.sync_progress_bar.hide()  # 默认隐藏

        # ---------- 垂直分割器 ----------
        v_splitter = QSplitter(Qt.Vertical)
        v_splitter.addWidget(self.session_list)       # 0: 消息列表
        v_splitter.addWidget(self.stats_panel)        # 1: 统计面板
        v_splitter.addWidget(self.sync_progress_bar)   # 2: 进度条
        v_splitter.addWidget(self.status_bar)          # 3: 状态栏

        # 四个控件，四个高度值
        v_splitter.setSizes([350, 80, 20, 30])

        # 拉伸因子
        v_splitter.setStretchFactor(0, 5)   # 消息列表可拉伸
        v_splitter.setStretchFactor(1, 1)   # 统计面板微拉伸
        v_splitter.setStretchFactor(2, 0)   # 进度条固定高度
        v_splitter.setStretchFactor(3, 0)   # 状态栏固定高度

        # 关键：禁止子控件折叠到0高度
        v_splitter.setCollapsible(0, False)
        v_splitter.setCollapsible(1, False)
        v_splitter.setCollapsible(2, False)
        v_splitter.setCollapsible(3, False)        # 状态栏（不自动拉伸）

        # ---------- 将垂直分割器放入左侧消息容器 ----------
        self.msg_container = QWidget()
        msg_layout = QVBoxLayout(self.msg_container)
        msg_layout.setContentsMargins(0, 0, 0, 0)
        msg_layout.setSpacing(0)
        msg_layout.addWidget(v_splitter)

        h_splitter.addWidget(self.msg_container)

        # ---------- 右侧详情面板 ----------
        self.detail_panel = QFrame()
        self.detail_panel.setObjectName("detailPanel")
        self.detail_panel.setMinimumWidth(300)
        self.detail_panel.setMaximumWidth(650)
        detail_layout = QVBoxLayout(self.detail_panel)

        self.detail_title = QLabel("消息详情")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        self.detail_title.setFont(title_font)
        detail_layout.addWidget(self.detail_title)

        self.detail_content = QPlainTextEdit()
        self.detail_content.setReadOnly(True)
        self.detail_content.setStyleSheet("border: none; background: transparent; font-size: 12px;")
        self.detail_content.setPlaceholderText("点击左侧会话查看聊天记录...")
        detail_layout.addWidget(self.detail_content)

        h_splitter.addWidget(self.detail_panel)
        h_splitter.setSizes([400, 400])
        # 设置页面（默认隐藏）
        right_outer.addWidget(h_splitter)
        main_layout.addLayout(right_outer)

        # ========== 内部数据 ==========
        self.session_data = {}
        self.all_messages_list = []
        self.msg_count = 0

        # ========== 头像相关初始化 ==========
        self.avatar_cache = {}
        self.wx_data_dir, self.wxid = get_wechat_data_dir()
        if self.wx_data_dir:
            self.avatar_dir = os.path.join(self.wx_data_dir, 'FileStorage', 'General', 'HDHeadImage')
            if not os.path.exists(self.avatar_dir):
                self.avatar_dir = None
        else:
            self.avatar_dir = None

        # 设置头像委托（必须在 avatar_cache 和 avatar_dir 之后）
        self.avatar_delegate = AvatarDelegate(self.avatar_cache, self.avatar_dir)
        self.session_list.setItemDelegate(self.avatar_delegate)

    # ---------- 排序与时间解析 ----------
    def _update_session_list(self):
        self.session_list.clear()
        
        # 直接用缓存，不每次查数据库
        blacklist = getattr(self, '_blacklist_cache', [])
        
        # 直接从 all_messages_list 聚合每个会话的最后一条消息
        chat_last_msg = {}
        for msg in self.all_messages_list:
            chat = msg.get('chat', '')
            # 模糊匹配：只要会话名包含黑名单中的任一关键词，就屏蔽
            if any(kw in chat for kw in blacklist if kw):
                continue
            time_ts = self._parse_time(msg.get('time', ''))
            if chat not in chat_last_msg or time_ts > chat_last_msg[chat][0]:
                chat_last_msg[chat] = (time_ts, msg)
        
        # 按时间戳降序排序（最新在最上面）
        sorted_chats = sorted(chat_last_msg.items(), key=lambda kv: kv[1][0], reverse=True)
        
        for chat, (ts, last_msg) in sorted_chats:
            sender = last_msg.get('sender', '')
            content = last_msg.get('content', '')
            time_str = last_msg.get('time', '')
            count = sum(1 for m in self.all_messages_list if m.get('chat') == chat)
            display_name = self._shorten_name(chat, 18)
            display = f"{time_str}  {display_name}"
            if sender:
                display += f"  ({sender})"
            display += f"  : {content[:40]}"
            
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, chat)
            username = last_msg.get('username', '')
            item.setData(Qt.UserRole + 1, username)
            if last_msg.get('is_urgent'):
                item.setForeground(Qt.red)
            elif last_msg.get('is_work'):
                item.setForeground(Qt.darkBlue)
            self.session_list.addItem(item)
    def _parse_time(self, time_str):
        import datetime
        if not time_str:
            return 0
        try:
            if time_str[:4].isdigit() and len(time_str) >= 16:
                dt = datetime.datetime.strptime(time_str[:16], '%Y-%m-%d %H:%M')
            else:
                dt = datetime.datetime.strptime(time_str, '%m-%d %H:%M')
                dt = dt.replace(year=2026)
            return dt.timestamp()
        except:
            try:
                dt = datetime.datetime.strptime(time_str, '%m-%d %H:%M')
                return dt.replace(year=2026).timestamp()
            except:
                # 纯时间格式，如 "10:21:56" 或 "10:21"
                try:
                    today = datetime.date.today()
                    parts = time_str.split(':')
                    hour = int(parts[0])
                    minute = int(parts[1])
                    second = int(parts[2]) if len(parts) > 2 else 0
                    dt = datetime.datetime(today.year, today.month, today.day, hour, minute, second)
                    return dt.timestamp()
                except:
                    return 0

    def _shorten_name(self, name, max_len):
        return name if len(name) <= max_len else name[:max_len - 2] + '..'
    def _switch_page(self, index):
        for btn in [self.btn_realtime, self.btn_report, self.btn_history, self.btn_settings]:
            btn.setChecked(False)
        [self.btn_realtime, self.btn_report, self.btn_history, self.btn_settings][index].setChecked(True)

        # 页面切换
        is_settings = (index == 3)
        self.msg_container.setVisible(not is_settings)
        self.detail_panel.setVisible(not is_settings)      
    def _open_settings(self):
        """打开独立设置窗口"""
        from app.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self)
        dialog.exec_()
        # 刷新黑名单缓存
        self._refresh_blacklist_cache()
        # 立即刷新会话列表
        self._update_session_list()
    # ---------- 消息输入 ----------
    @pyqtSlot(list)
    def add_new_messages(self, messages):
        # 存入我们自己的数据库（关键新增）
        from data.storage import save_messages_batch_fast
        save_messages_batch_fast(messages)   # ← 加这一行        
        today_count = 0
        urgent_count = 0
        for msg in messages:
            self.msg_count += 1
            chat = msg.get('chat', '未知')
            time_str = msg.get('time', '')
            
            # 统一用时间戳比较，避免字符串比较的不确定性
            new_ts = self._parse_time(time_str)
            
            if chat not in self.session_data:
                self.session_data[chat] = {'last_msg': msg, 'count': 0, 'last_ts': new_ts}
            else:
                old_ts = self.session_data[chat].get('last_ts', 0)
                if new_ts >= old_ts:
                    self.session_data[chat]['last_msg'] = msg
                    self.session_data[chat]['last_ts'] = new_ts
            
            self.session_data[chat]['count'] += 1
            self.all_messages_list.append(msg)
            
            if msg.get('is_urgent'):
                urgent_count += 1
            if time_str.startswith(time.strftime('%Y-%m-%d')):
                today_count += 1

        self._update_session_list()
        self.stats_today.setText(f"📊 今日: {today_count} 条")
        self.stats_active.setText(f"💬 活跃会话: {len(self.session_data)} 个")
        self.stats_urgent.setText(f"🔴 紧急: {urgent_count} 条")
        self.stats_total.setText(f"📦 缓存: {self.msg_count} 条")
        if messages:
            self.status_bar.setText(f"最新: {messages[-1].get('content', '')[:40]}...")
    # ---------- 点击会话查看详情 ----------
    def on_session_clicked(self, item):
        chat = item.data(Qt.UserRole)
        msgs = [m for m in self.all_messages_list if m.get('chat') == chat]
        msgs.sort(key=lambda x: self._parse_time(x.get('time', '')))
        self.detail_title.setText(f"💬 {chat}")
        text = ""
        for m in msgs[-50:]:
            time_str = m.get('time', '')
            sender = m.get('sender', '')
            content = m.get('content', '')
            line = f"[{time_str}] {sender}: {content}"
            if m.get('is_urgent'):
                line = f"🔴 {line}"
            text += line + "\n"
        self.detail_content.setPlainText(text or "暂无消息")
    def _refresh_blacklist_cache(self):
        """刷新黑名单缓存"""
        from data.storage import get_all_blacklist
        self._blacklist_cache = get_all_blacklist()
    def clear_messages(self):
        self.session_list.clear()
        self.session_data.clear()
        self.all_messages_list.clear()
        self.msg_count = 0
        self._blacklist_cache = []  # 黑名单缓存
        self._refresh_blacklist_cache()
        self.stats_today.setText("📊 今日: 0 条")
        self.stats_active.setText("💬 活跃会话: 0 个")
        self.stats_urgent.setText("🔴 紧急: 0 条")
        self.stats_total.setText("📦 缓存: 0 条")
        self.status_bar.setText("列表已清空 | 等待新消息...")
    def _load_avatars(self):
        """通过 contacts 命令建立 username ↔ 数字ID 的映射，再匹配本地头像文件"""
        if not self.avatar_dir:
            return
        
        # 收集所有唯一的 username
        usernames = set()
        for msg in self.all_messages_list:
            u = msg.get('username', '')
            if u:
                usernames.add(u)
        
        # 逐个获取联系人详情，匹配本地头像文件
        for username in usernames:
            if username in self.avatar_cache:
                continue
            
            try:
                detail = get_contact_detail(username)
                if detail:
                    matched_pixmap = self._find_local_avatar(username)
                    if matched_pixmap:
                        self.avatar_cache[username] = matched_pixmap
                    else:
                        self.avatar_cache[username] = None
                else:
                    self.avatar_cache[username] = None
            except:
                self.avatar_cache[username] = None
        
        self._update_session_list()
                # 让界面及时响应，避免假死
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()

    def _find_local_avatar(self, username):
        """在本地头像目录中查找匹配的头像文件"""
        if not self.avatar_dir:
            return None
        
        # 微信4.x头像存放在 all_users/head_imgs/ 下，文件名为数字ID
        head_imgs_dir = os.path.join(os.path.dirname(self.avatar_dir), 'head_imgs')
        if not os.path.exists(head_imgs_dir):
            return None
        
        # 遍历 head_imgs 下的所有文件
        for root, dirs, files in os.walk(head_imgs_dir):
            for filename in files:
                if username in filename:
                    filepath = os.path.join(root, filename)
                    pixmap = QPixmap(filepath)
                    if not pixmap.isNull():
                        return pixmap.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return None        

    @pyqtSlot(int, int)
    def update_sync_progress(self, current, total):
        if total == -1:
            # 百分比模式：切换到进度条，更新百分比
            self.status_stack.setCurrentIndex(0)
            self.sync_progress_bar.setValue(current)
        elif total > 0:
            # 数字模式（兼容老逻辑）
            self.status_stack.setCurrentIndex(0)
            percent = int(current / total * 100)
            self.sync_progress_bar.setValue(percent)
        # 不需要 show()，QStackedWidget 已经完成了显示切换

    @pyqtSlot()
    def on_sync_finished(self):
        # 切换回状态栏
        self.status_stack.setCurrentIndex(1)
        from data.storage import get_message_count
        self.status_bar.setText(f"就绪 | 缓存消息: {get_message_count()} 条")
        # ... 后面的头像加载代码可选择性保留

        # 收集所有唯一的 username
        usernames = set()
        for msg in self.all_messages_list:
            u = msg.get('username', '')
            if u:
                usernames.add(u)

        # 逐个获取头像 URL 并下载
        for username in usernames:
            if username in self.avatar_cache:
                continue
            try:
                detail = get_contact_detail(username)
                if detail and detail.get('avatar'):
                    avatar_url = detail['avatar']
                    resp = requests.get(avatar_url, timeout=5)
                    if resp.status_code == 200:
                        pixmap = QPixmap()
                        pixmap.loadFromData(resp.content)
                        # 缩放成头像尺寸
                        pixmap = pixmap.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.avatar_cache[username] = pixmap
                    else:
                        self.avatar_cache[username] = None
                else:
                    self.avatar_cache[username] = None
            except:
                self.avatar_cache[username] = None

        # 刷新会话列表（这时头像已就位）
        self._update_session_list()
        self.status_bar.setText(f"就绪 | 缓存消息: {get_message_count()} 条")


# ---------- 头像委托类 ----------
class AvatarDelegate(QStyledItemDelegate):
    def __init__(self, avatar_cache, avatar_dir, parent=None):
        super().__init__(parent)
        self.avatar_cache = avatar_cache
        self.avatar_dir = avatar_dir

    def paint(self, painter, option, index):
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        else:
            painter.fillRect(option.rect, option.palette.base())

        username = index.data(Qt.UserRole + 1)
        chat_name = index.data(Qt.UserRole)

        avatar_size = 36
        margin = 5
        avatar_rect = QRect(option.rect.left() + margin,
                            option.rect.top() + (option.rect.height() - avatar_size) // 2,
                            avatar_size, avatar_size)

        pixmap = None
        if username:
            # 优先从缓存读取
            if username in self.avatar_cache:
                pixmap = self.avatar_cache[username]
            # 缓存未命中，尝试从本地文件加载
            else:
                # 直接使用已知的绝对路径
                head_imgs_dir = r"D:\xwechat_files\all_users\head_imgs"
                if os.path.exists(head_imgs_dir):
                    for root, dirs, files in os.walk(head_imgs_dir):
                        for filename in files:
                            if filename.endswith(('.jpg', '.png')) and username in filename:
                                filepath = os.path.join(root, filename)
                                pixmap = QPixmap(filepath).scaled(avatar_size, avatar_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                                if not pixmap.isNull():
                                    break
                        if pixmap:
                            break
                # 如果本地也没找到，存入 None 避免重复搜索
                if not pixmap:
                    self.avatar_cache[username] = None
        if pixmap:
            painter.save()
            path = QPainterPath()
            path.addEllipse(QRectF(avatar_rect))
            painter.setClipPath(path)
            painter.drawPixmap(avatar_rect, pixmap)
            painter.restore()
        else:
            painter.setBrush(QBrush(QColor("#cccccc")))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(avatar_rect)
            painter.setPen(QPen(QColor("#ffffff")))
            painter.drawText(avatar_rect, Qt.AlignCenter, chat_name[0] if chat_name else "?")

        text_rect = QRect(avatar_rect.right() + margin * 2, option.rect.top(),
                          option.rect.width() - avatar_rect.width() - margin * 3,
                          option.rect.height())
        painter.setPen(QPen(QColor("#333333")))
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, index.data(Qt.DisplayRole))