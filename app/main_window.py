# app/main_window.py
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QListWidget, QListWidgetItem, QPushButton,
                             QTextEdit, QStackedWidget, QFrame, QScrollArea,
                             QSizePolicy, QSplitter)
from PyQt5.QtCore import Qt, pyqtSlot, QSize
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon


class MessageCard(QFrame):
    """单条消息卡片"""
    def __init__(self, msg, parent=None):
        super().__init__(parent)
        self.msg = msg
        self.setObjectName("messageCard")
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        # 头部：会话名 + 时间
        header = QHBoxLayout()
        chat_label = QLabel(self.msg.get('chat', '未知'))
        chat_font = QFont()
        chat_font.setPointSize(11)
        chat_font.setBold(True)
        chat_label.setFont(chat_font)
        
        # 颜色标记
        if self.msg.get('is_urgent'):
            chat_label.setStyleSheet("color: #e74c3c;")  # 红色
        elif self.msg.get('is_work'):
            chat_label.setStyleSheet("color: #2980b9;")  # 蓝色
        else:
            chat_label.setStyleSheet("color: #2c3e50;")
        
        header.addWidget(chat_label)
        header.addStretch()
        
        time_label = QLabel(self.msg.get('time', ''))
        time_label.setStyleSheet("color: #95a5a6; font-size: 11px;")
        header.addWidget(time_label)
        layout.addLayout(header)
        
        # 发送者
        sender = self.msg.get('sender', '')
        if sender:
            sender_label = QLabel(f"👤 {sender}")
            sender_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
            layout.addWidget(sender_label)
        
        # 消息内容
        content = self.msg.get('content', '')
        if len(content) > 120:
            content = content[:120] + "..."
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("color: #34495e; font-size: 12px; line-height: 1.4;")
        layout.addWidget(content_label)
        
        # 标签行
        tags = []
        if self.msg.get('is_urgent'):
            tags.append(("🔴 紧急", "#e74c3c"))
        if self.msg.get('is_work'):
            keywords = self.msg.get('matched_keywords', [])
            if keywords:
                tags.append((f"📌 {', '.join(keywords[:3])}", "#2980b9"))
        if self.msg.get('is_group'):
            tags.append(("👥 群聊", "#27ae60"))
        
        if tags:
            tag_layout = QHBoxLayout()
            tag_layout.addStretch()
            for text, color in tags:
                tag = QLabel(text)
                tag.setStyleSheet(f"background: {color}15; color: {color}; padding: 2px 8px; "
                                  f"border-radius: 10px; font-size: 10px;")
                tag_layout.addWidget(tag)
            layout.addLayout(tag_layout)
    
    def mousePressEvent(self, event):
        """点击卡片显示详情"""
        # 通过父级找到主窗口并显示详情
        w = self.window()
        if hasattr(w, 'show_message_detail'):
            w.show_message_detail(self.msg)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("微信信息管家")
        self.setMinimumSize(1000, 680)
        
        # 全局样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8f9fa;
            }
            #sideNav {
                background-color: #ffffff;
                border-right: 1px solid #e9ecef;
                min-width: 180px;
                max-width: 180px;
            }
            #navBtn {
                text-align: left;
                padding: 14px 20px;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                color: #495057;
                background: transparent;
            }
            #navBtn:hover {
                background-color: #f1f3f5;
            }
            #navBtn:checked {
                background-color: #e7f5ff;
                color: #1971c2;
                font-weight: bold;
            }
            #messageCard {
                background: #ffffff;
                border-radius: 10px;
                margin: 4px 8px;
                border: 1px solid #e9ecef;
            }
            #messageCard:hover {
                border-color: #adb5bd;
                background: #f8f9fa;
            }
            #detailPanel {
                background: #ffffff;
                border-left: 1px solid #e9ecef;
                padding: 20px;
            }
            #statusBar {
                background: #ffffff;
                border-top: 1px solid #e9ecef;
                padding: 8px 16px;
                color: #6c757d;
                font-size: 12px;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                width: 6px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #ced4da;
                border-radius: 3px;
            }
        """)
        
        # 主布局：左侧导航 + 右侧内容
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
        
        # Logo
        logo = QLabel("📋 信息管家")
        logo_font = QFont()
        logo_font.setPointSize(15)
        logo_font.setBold(True)
        logo.setFont(logo_font)
        logo.setStyleSheet("padding: 10px 14px; color: #212529;")
        nav_layout.addWidget(logo)
        nav_layout.addSpacing(20)
        
        # 导航按钮
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
        
        # 底部信息
        footer = QLabel("v0.2 · 本地运行")
        footer.setStyleSheet("color: #adb5bd; font-size: 11px; padding: 10px;")
        nav_layout.addWidget(footer)
        
        main_layout.addWidget(self.nav)
        
        # === 右侧内容区 ===
        right_splitter = QSplitter(Qt.Horizontal)
        
        # 中间消息列表
        self._setup_realtime_panel()
        right_splitter.addWidget(self.message_scroll)
        
        # 右侧详情面板
        self.detail_panel = QFrame()
        self.detail_panel.setObjectName("detailPanel")
        self.detail_panel.setMinimumWidth(280)
        self.detail_panel.setMaximumWidth(400)
        detail_layout = QVBoxLayout(self.detail_panel)
        
        self.detail_title = QLabel("消息详情")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        self.detail_title.setFont(title_font)
        detail_layout.addWidget(self.detail_title)
        
        self.detail_content = QTextEdit()
        self.detail_content.setReadOnly(True)
        self.detail_content.setStyleSheet("border: none; background: transparent; font-size: 12px;")
        self.detail_content.setPlaceholderText("点击左侧消息卡片查看详情...")
        detail_layout.addWidget(self.detail_content)
        
        right_splitter.addWidget(self.detail_panel)
        right_splitter.setSizes([600, 300])
        
        main_layout.addWidget(right_splitter)
        
        # 状态栏
        self.status_bar = QLabel("就绪 | 等待新消息...")
        self.status_bar.setObjectName("statusBar")
        
        # 整体布局
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(right_splitter)
        outer.addWidget(self.status_bar)
        
        # 把右侧布局放进主布局
        main_layout.addLayout(outer)
        
        # 消息计数
        self.msg_count = 0
        self.all_message_cards = []  # 按时间顺序存储所有卡片

        # 导航切换
        self.btn_realtime.clicked.connect(lambda: self._switch_page(0))
        self.btn_report.clicked.connect(lambda: self._switch_page(1))
        self.btn_history.clicked.connect(lambda: self._switch_page(2))
        self.btn_settings.clicked.connect(lambda: self._switch_page(3))
    
    def _setup_realtime_panel(self):
        """消息列表区域"""
        self.message_container = QWidget()
        self.message_layout = QVBoxLayout(self.message_container)
        self.message_layout.setContentsMargins(8, 8, 8, 8)
        self.message_layout.setSpacing(2)
        self.message_layout.addStretch()
        
        self.message_scroll = QScrollArea()
        self.message_scroll.setWidgetResizable(True)
        self.message_scroll.setWidget(self.message_container)
    
    def _switch_page(self, index):
        """切换导航"""
        for btn in [self.btn_realtime, self.btn_report, self.btn_history, self.btn_settings]:
            btn.setChecked(False)
        [self.btn_realtime, self.btn_report, self.btn_history, self.btn_settings][index].setChecked(True)
        # 后续可扩展多页面
    
    @pyqtSlot(list)
    def add_new_messages(self, messages):
        """接收新消息并添加到列表"""
        for msg in messages:
            self.msg_count += 1
            card = MessageCard(msg)
            self.all_message_cards.append(card)
        
        # 按时间戳从小到大排序（旧消息在上，新消息在下）
        self.all_message_cards.sort(key=lambda c: c.msg.get('timestamp', 0))
        
        # 重建布局
        self._rebuild_message_list()
        
        if messages:
            self.status_bar.setText(f"已捕获 {self.msg_count} 条消息 | 最新: {messages[-1].get('content', '')[:40]}...")

    def _rebuild_message_list(self):
        """清空并重建消息列表，旧消息在上，新消息在下"""
        # 移除所有卡片控件（保留 stretch）
        while self.message_layout.count() > 1:
            item = self.message_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().setParent(None)

        # 依次添加卡片：旧消息添加在前，新消息添加在后
        for card in self.all_message_cards:
            self.message_layout.insertWidget(self.message_layout.count() - 1, card)
            card.show()

        # 自动滚动到底部（最新消息在底部）
        self.message_scroll.verticalScrollBar().setValue(
            self.message_scroll.verticalScrollBar().maximum()
        )
    
    def clear_messages(self):
        """清空消息列表"""
        self.all_message_cards.clear()
        while self.message_layout.count() > 1:
            item = self.message_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self.msg_count = 0
        self.status_bar.setText("列表已清空 | 等待新消息...")