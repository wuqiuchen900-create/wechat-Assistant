# app/settings_dialog.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                             QListWidgetItem, QStackedWidget, QWidget,
                             QLabel, QPushButton, QFrame, QComboBox, QCheckBox, QLineEdit)
from PyQt5.QtCore import Qt

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 设置")
        self.setMinimumSize(700, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            #categoryList {
                background: #ffffff;
                border-right: 1px solid #e9ecef;
                min-width: 160px;
                max-width: 160px;
                font-size: 13px;
            }
            #categoryList::item {
                padding: 12px 16px;
                border-bottom: 1px solid #f1f3f5;
            }
            #categoryList::item:selected {
                background-color: #e7f5ff;
                color: #1971c2;
                font-weight: bold;
            }
            #contentArea {
                background: #ffffff;
                border-radius: 10px;
                margin: 10px;
            }
            QPushButton {
                padding: 8px 20px;
                border-radius: 6px;
                font-size: 13px;
            }
            #primaryBtn {
                background: #1971c2;
                color: white;
                border: none;
            }
            #primaryBtn:hover {
                background: #1864ab;
            }
            #dangerBtn {
                background: #e74c3c;
                color: white;
                border: none;
            }
            #dangerBtn:hover {
                background: #c0392b;
            }
        """)

        # ===== 主布局 =====
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== 左侧分类列表 =====
        self.category_list = QListWidget()
        self.category_list.setObjectName("categoryList")
        categories = ["📡 消息监控", "🔍 信息过滤", "🔔 提醒方式", "📊 数据管理", "🎨 界面设置", "ℹ️ 关于"]
        for cat in categories:
            item = QListWidgetItem(cat)
            self.category_list.addItem(item)
        self.category_list.setCurrentRow(0)
        self.category_list.currentRowChanged.connect(self._on_category_changed)

        main_layout.addWidget(self.category_list)

        # ===== 右侧内容区 =====
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("contentArea")

        # 创建各分类页面
        self.page_monitor = self._create_monitor_page()
        self.page_filter = self._create_filter_page()
        self.page_reminder = self._create_reminder_page()
        self.page_data = self._create_data_page()
        self.page_ui = self._create_ui_page()
        self.page_about = self._create_about_page()

        self.content_stack.addWidget(self.page_monitor)    # index 0
        self.content_stack.addWidget(self.page_filter)     # index 1
        self.content_stack.addWidget(self.page_reminder)   # index 2
        self.content_stack.addWidget(self.page_data)       # index 3
        self.content_stack.addWidget(self.page_ui)         # index 4
        self.content_stack.addWidget(self.page_about)      # index 5

        main_layout.addWidget(self.content_stack)
        self.setAttribute(Qt.WA_DeleteOnClose)  # 关闭时自动销毁
    # ===== 分类切换 =====
    def _on_category_changed(self, index):
        self.content_stack.setCurrentIndex(index)

    # ========== 各分类页面创建 ==========

    def _create_section_frame(self, title, content_widget):
        """创建一个带标题的板块框架"""
        frame = QFrame()
        frame.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #e9ecef; border-radius: 8px; margin-bottom: 10px; }")
        layout = QVBoxLayout(frame)
        label = QLabel(title)
        label.setStyleSheet("font-size: 14px; font-weight: bold; color: #212529; padding-bottom: 8px; border-bottom: 1px solid #f1f3f5;")
        layout.addWidget(label)
        layout.addWidget(content_widget)
        return frame

    # --- 消息监控 ---
    def _create_monitor_page(self):
        from data.storage import get_all_settings, save_setting

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("📡 消息监控")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #212529;")
        layout.addWidget(title)

        settings = get_all_settings()
        # 深度检查间隔
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("深度检查间隔："))
        self.cb_deep_check = QComboBox()
        self.cb_deep_check.addItems(["1小时", "3小时", "5小时", "8小时", "12小时"])
        deep_map = {"60": 0, "180": 1, "300": 2, "480": 3, "720": 4}
        current_deep = settings.get('deep_check_interval', '180')
        self.cb_deep_check.setCurrentIndex(deep_map.get(current_deep, 1))
        self.cb_deep_check.currentIndexChanged.connect(lambda: self._save_deep_check())
        row4.addWidget(self.cb_deep_check)
        row4.addStretch()
        layout.addLayout(row4)
        # 轮询间隔
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("轮询间隔："))
        self.cb_poll_interval = QComboBox()
        self.cb_poll_interval.addItems(["10秒", "30秒", "1分钟", "5分钟", "10分钟"])
        # 设置当前值
        interval_map = {"10": 0, "30": 1, "60": 2, "300": 3, "600": 4}
        current_interval = settings.get('poll_interval', '30')
        self.cb_poll_interval.setCurrentIndex(interval_map.get(current_interval, 1))
        self.cb_poll_interval.currentIndexChanged.connect(lambda: self._save_poll_interval())
        row1.addWidget(self.cb_poll_interval)
        row1.addStretch()
        layout.addLayout(row1)

        # 每次拉取条数
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("每次拉取条数："))
        self.cb_history_limit = QComboBox()
        self.cb_history_limit.addItems(["20条", "50条", "100条", "200条"])
        limit_map = {"20": 0, "50": 1, "100": 2, "200": 3}
        current_limit = settings.get('history_limit', '50')
        self.cb_history_limit.setCurrentIndex(limit_map.get(current_limit, 1))
        self.cb_history_limit.currentIndexChanged.connect(lambda: self._save_history_limit())
        row2.addWidget(self.cb_history_limit)
        row2.addStretch()
        layout.addLayout(row2)

        # 首次启动全量同步
        row3 = QHBoxLayout()
        self.chk_full_sync = QCheckBox("首次启动全量同步")
        self.chk_full_sync.setChecked(settings.get('enable_full_sync', '1') == '1')
        self.chk_full_sync.toggled.connect(lambda checked: save_setting('enable_full_sync', '1' if checked else '0'))
        row3.addWidget(self.chk_full_sync)
        row3.addStretch()
        layout.addLayout(row3)

        layout.addStretch()
        return page
    def _save_deep_check(self):
        from data.storage import save_setting
        deep_map = {0: "60", 1: "180", 2: "300", 3: "480", 4: "720"}
        val = deep_map.get(self.cb_deep_check.currentIndex(), "180")
        save_setting('deep_check_interval', val)
    def _save_poll_interval(self):
        from data.storage import save_setting
        interval_map = {0: "10", 1: "30", 2: "60", 3: "300", 4: "600"}
        val = interval_map.get(self.cb_poll_interval.currentIndex(), "30")
        save_setting('poll_interval', val)

    def _save_history_limit(self):
        from data.storage import save_setting
        limit_map = {0: "20", 1: "50", 2: "100", 3: "200"}
        val = limit_map.get(self.cb_history_limit.currentIndex(), "50")
        save_setting('history_limit', val)
    # --- 信息过滤 ---
    def _create_filter_page(self):
        from data.storage import get_all_keywords, add_keyword, delete_keyword
        from data.storage import get_all_blacklist, add_blacklist, delete_blacklist

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        title = QLabel("🔍 信息过滤")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #212529;")
        layout.addWidget(title)

        # ===== 关键词管理板块 =====
        kw_frame = QFrame()
        kw_frame.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #e9ecef; border-radius: 8px; }")
        kw_layout = QVBoxLayout(kw_frame)

        kw_title = QLabel("🔑 关键词管理")
        kw_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #212529; padding-bottom: 8px; border-bottom: 1px solid #f1f3f5;")
        kw_layout.addWidget(kw_title)

        # 添加关键词行
        add_kw_layout = QHBoxLayout()
        self.kw_input = QLineEdit()
        self.kw_input.setPlaceholderText("输入新关键词...")
        self.kw_input.setStyleSheet("padding: 6px 10px; border: 1px solid #ced4da; border-radius: 6px;")
        add_kw_layout.addWidget(self.kw_input)

        self.kw_category = QComboBox()
        self.kw_category.addItems(["工作关键词", "紧急关键词"])
        self.kw_category.setStyleSheet("padding: 6px; border: 1px solid #ced4da; border-radius: 6px;")
        add_kw_layout.addWidget(self.kw_category)

        kw_add_btn = QPushButton("添加")
        kw_add_btn.setStyleSheet("""
            QPushButton { background: #1971c2; color: white; padding: 6px 16px;
            border: none; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background: #1864ab; }
        """)
        kw_add_btn.clicked.connect(self._add_keyword)
        add_kw_layout.addWidget(kw_add_btn)
        kw_layout.addLayout(add_kw_layout)

        # 关键词列表
        kw_layout.addWidget(QLabel("当前关键词（双击可删除）："))
        self.kw_list = QListWidget()
        self.kw_list.setAlternatingRowColors(True)
        self.kw_list.setMaximumHeight(150)
        self.kw_list.itemDoubleClicked.connect(self._delete_keyword)
        kw_layout.addWidget(self.kw_list)

        self._refresh_keyword_list()
        layout.addWidget(kw_frame)

        # ===== 黑名单管理板块 =====
        bl_frame = QFrame()
        bl_frame.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #e9ecef; border-radius: 8px; }")
        bl_layout = QVBoxLayout(bl_frame)

        bl_title = QLabel("🚫 黑名单管理")
        bl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #212529; padding-bottom: 8px; border-bottom: 1px solid #f1f3f5;")
        bl_layout.addWidget(bl_title)

        # 添加黑名单行
        add_bl_layout = QHBoxLayout()
        self.bl_input = QLineEdit()
        self.bl_input.setPlaceholderText("输入要屏蔽的会话名称...")
        self.bl_input.setStyleSheet("padding: 6px 10px; border: 1px solid #ced4da; border-radius: 6px;")
        add_bl_layout.addWidget(self.bl_input)

        bl_add_btn = QPushButton("添加")
        bl_add_btn.setStyleSheet("""
            QPushButton { background: #e74c3c; color: white; padding: 6px 16px;
            border: none; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background: #c0392b; }
        """)
        bl_add_btn.clicked.connect(self._add_blacklist)
        add_bl_layout.addWidget(bl_add_btn)
        bl_layout.addLayout(add_bl_layout)

        # 黑名单列表
        bl_layout.addWidget(QLabel("当前黑名单（双击可删除）："))
        self.bl_list = QListWidget()
        self.bl_list.setAlternatingRowColors(True)
        self.bl_list.setMaximumHeight(150)
        self.bl_list.itemDoubleClicked.connect(self._delete_blacklist)
        bl_layout.addWidget(self.bl_list)

        self._refresh_blacklist_list()
        layout.addWidget(bl_frame)

        layout.addStretch()
        return page

    def _refresh_keyword_list(self):
        from data.storage import get_all_keywords
        self.kw_list.clear()
        work_kw, urgent_kw = get_all_keywords()
        for kw in work_kw:
            self.kw_list.addItem(f"📋 工作  |  {kw}")
        for kw in urgent_kw:
            self.kw_list.addItem(f"🔴 紧急  |  {kw}")

    def _add_keyword(self):
        from data.storage import add_keyword
        kw = self.kw_input.text().strip()
        if not kw:
            return
        category = 'urgent' if self.kw_category.currentIndex() == 1 else 'work'
        add_keyword(kw, category)
        self.kw_input.clear()
        self._refresh_keyword_list()

    def _delete_keyword(self, item):
        from data.storage import delete_keyword
        text = item.text()
        # 从 "📋 工作  |  报价" 中提取关键词
        kw = text.split("|")[-1].strip()
        delete_keyword(kw)
        self._refresh_keyword_list()

    def _refresh_blacklist_list(self):
        from data.storage import get_all_blacklist
        self.bl_list.clear()
        for name in get_all_blacklist():
            self.bl_list.addItem(f"⛔ {name}")

    def _add_blacklist(self):
        from data.storage import add_blacklist
        name = self.bl_input.text().strip()
        if not name:
            return
        add_blacklist(name)
        self.bl_input.clear()
        self._refresh_blacklist_list()

    def _delete_blacklist(self, item):
        from data.storage import delete_blacklist
        name = item.text().replace("⛔ ", "")
        delete_blacklist(name)
        self._refresh_blacklist_list()

    # --- 提醒方式 ---
    def _create_reminder_page(self):
        from data.storage import get_all_settings, save_setting

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("🔔 提醒方式")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #212529;")
        layout.addWidget(title)

        settings = get_all_settings()

        # 弹窗提醒
        self.chk_popup = QCheckBox("弹窗提醒（紧急消息在右下角弹出提醒窗口）")
        self.chk_popup.setChecked(settings.get('enable_popup', '1') == '1')
        self.chk_popup.toggled.connect(lambda checked: save_setting('enable_popup', '1' if checked else '0'))
        layout.addWidget(self.chk_popup)

        # 声音提醒
        self.chk_sound = QCheckBox("声音提醒（收到紧急消息时播放提示音）")
        self.chk_sound.setChecked(settings.get('enable_sound', '0') == '1')
        self.chk_sound.toggled.connect(lambda checked: save_setting('enable_sound', '1' if checked else '0'))
        layout.addWidget(self.chk_sound)

        # 托盘图标闪烁
        self.chk_tray_flash = QCheckBox("托盘图标闪烁（有新消息时托盘图标闪烁提醒）")
        self.chk_tray_flash.setChecked(settings.get('enable_tray_flash', '1') == '1')
        self.chk_tray_flash.toggled.connect(lambda checked: save_setting('enable_tray_flash', '1' if checked else '0'))
        layout.addWidget(self.chk_tray_flash)

        # 提醒时间段（占位，后续完善）
        time_label = QLabel("⏰ 提醒时间段：全天（后续版本将支持自定义时间段）")
        time_label.setStyleSheet("color: #868e96; font-size: 12px; padding-top: 10px;")
        layout.addWidget(time_label)

        layout.addStretch()
        return page
    # --- 数据管理 ---
    def _create_data_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("📊 数据管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #212529;")
        layout.addWidget(title)

        layout.addWidget(QLabel("缓存消息数：5874 条"))

        btn_sync = QPushButton("🔄 重新全量同步")
        btn_sync.setObjectName("primaryBtn")
        layout.addWidget(btn_sync)

        btn_clear = QPushButton("🗑️ 清空缓存数据")
        btn_clear.setObjectName("dangerBtn")
        layout.addWidget(btn_clear)

        btn_export = QPushButton("📥 导出消息备份")
        layout.addWidget(btn_export)

        layout.addStretch()
        return page

    # --- 界面设置 ---
    def _create_ui_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("🎨 界面设置")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #212529;")
        layout.addWidget(title)

        layout.addWidget(QLabel("启动最小化到托盘：" + "开启"))
        layout.addWidget(QLabel("新消息自动置顶：" + "开启"))

        layout.addStretch()
        return page

    # --- 关于 ---
    def _create_about_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("ℹ️ 关于")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #212529;")
        layout.addWidget(title)

        layout.addWidget(QLabel("微信信息管家 v0.5"))
        layout.addWidget(QLabel("一个本地运行的微信消息管理工具"))
        layout.addWidget(QLabel("数据只存储在你的电脑上，不经过任何第三方服务器"))

        layout.addStretch()
        return page