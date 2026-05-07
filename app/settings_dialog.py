# app/settings_dialog.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                             QListWidgetItem, QStackedWidget, QWidget,
                             QLabel, QPushButton, QFrame, QComboBox, QCheckBox,
                             QLineEdit, QSpinBox, QGroupBox, QFormLayout)
from PyQt5.QtCore import Qt
from core.data_manager import (get_all_settings, save_setting, get_all_keywords,
                               add_keyword, delete_keyword, get_all_blacklist,
                               add_blacklist, delete_blacklist)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("\u2699\ufe0f 设置")
        self.setMinimumSize(720, 520)
        self.setStyleSheet("""
            QDialog { background-color: #f3f4f6; }
            #categoryList {
                background: #ffffff;
                border-right: 1px solid #e5e7eb;
                min-width: 170px;
                max-width: 170px;
                font-size: 13px;
                outline: none;
            }
            #categoryList::item {
                padding: 14px 18px;
                border-bottom: 1px solid #f3f4f6;
            }
            #categoryList::item:selected {
                background-color: #eff6ff;
                color: #2563eb;
                font-weight: 600;
            }
            #contentArea {
                background: #ffffff;
                border-radius: 12px;
                margin: 10px;
            }
            QGroupBox {
                font-size: 13px;
                font-weight: bold;
                color: #374151;
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                margin-top: 12px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 8px;
            }
            QLineEdit, QSpinBox, QComboBox {
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                background: #f9fafb;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border-color: #2563eb;
                background: #ffffff;
            }
            QPushButton {
                padding: 8px 18px;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
            }
            #primaryBtn { background: #2563eb; color: white; border: none; }
            #primaryBtn:hover { background: #1d4ed8; }
            #dangerBtn { background: #ef4444; color: white; border: none; }
            #dangerBtn:hover { background: #dc2626; }
            #secondaryBtn { background: #f3f4f6; color: #374151; border: 1px solid #d1d5db; }
            #secondaryBtn:hover { background: #e5e7eb; }
            QCheckBox { font-size: 12px; color: #374151; spacing: 8px; }
            QLabel { color: #374151; font-size: 12px; }
        """)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.category_list = QListWidget()
        self.category_list.setObjectName("categoryList")
        categories = ["\U0001f4e1 消息监控", "\U0001f50d 信息过滤", "\U0001f514 提醒方式",
                      "\U0001f916 AI 配置", "\U0001f4ca 数据管理", "\U0001f3a8 界面设置", "\u2139\ufe0f 关于"]
        for cat in categories:
            self.category_list.addItem(QListWidgetItem(cat))
        self.category_list.setCurrentRow(0)
        self.category_list.currentRowChanged.connect(self._on_category_changed)

        main_layout.addWidget(self.category_list)

        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("contentArea")

        self.content_stack.addWidget(self._create_monitor_page())
        self.content_stack.addWidget(self._create_filter_page())
        self.content_stack.addWidget(self._create_reminder_page())
        self.content_stack.addWidget(self._create_ai_page())
        self.content_stack.addWidget(self._create_data_page())
        self.content_stack.addWidget(self._create_ui_page())
        self.content_stack.addWidget(self._create_about_page())

        main_layout.addWidget(self.content_stack)
        self.setAttribute(Qt.WA_DeleteOnClose)

    def _on_category_changed(self, index):
        self.content_stack.setCurrentIndex(index)

    def _make_page(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(24, 20, 24, 20)
        l.setSpacing(14)
        return w, l

    def _section_title(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #111827;")
        return lbl

    def _create_monitor_page(self):
        w, l = self._make_page()
        l.addWidget(self._section_title("\U0001f4e1 消息监控设置"))

        gb = QGroupBox("轮询与同步")
        fl = QFormLayout(gb)
        fl.setSpacing(10)

        self.poll_spin = QSpinBox()
        self.poll_spin.setRange(5, 300)
        self.poll_spin.setSuffix(" 秒")
        fl.addRow("轮询间隔:", self.poll_spin)

        self.full_sync_cb = QCheckBox("启动时全量同步历史消息")
        fl.addRow(self.full_sync_cb)

        l.addWidget(gb)

        btn = QPushButton("\U0001f4be 保存设置")
        btn.setObjectName("primaryBtn")
        btn.clicked.connect(self._save_monitor)
        l.addWidget(btn)
        l.addStretch()

        settings = get_all_settings()
        self.poll_spin.setValue(int(settings.get('poll_interval', '30')))
        self.full_sync_cb.setChecked(settings.get('enable_full_sync', '1') == '1')
        return w

    def _save_monitor(self):
        save_setting('poll_interval', str(self.poll_spin.value()))
        save_setting('enable_full_sync', '1' if self.full_sync_cb.isChecked() else '0')

    def _create_filter_page(self):
        w, l = self._make_page()
        l.addWidget(self._section_title("\U0001f50d 信息过滤"))

        gb1 = QGroupBox("关键词管理")
        f1 = QVBoxLayout(gb1)
        f1.setSpacing(8)

        row = QHBoxLayout()
        self.kw_input = QLineEdit()
        self.kw_input.setPlaceholderText("输入关键词...")
        row.addWidget(self.kw_input)
        self.kw_cat = QComboBox()
        self.kw_cat.addItems(["工作关键词", "紧急关键词"])
        row.addWidget(self.kw_cat)
        add_btn = QPushButton("+ 添加")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self._add_kw)
        row.addWidget(add_btn)
        f1.addLayout(row)

        self.kw_list = QListWidget()
        self.kw_list.setAlternatingRowColors(True)
        self.kw_list.itemDoubleClicked.connect(self._del_kw)
        self.kw_list.setStyleSheet("QListWidget::item { padding: 6px 10px; }")
        f1.addWidget(self.kw_list)
        l.addWidget(gb1)

        gb2 = QGroupBox("黑名单（屏蔽会话）")
        f2 = QVBoxLayout(gb2)
        f2.setSpacing(8)
        row2 = QHBoxLayout()
        self.bl_input = QLineEdit()
        self.bl_input.setPlaceholderText("输入会话名称关键词...")
        row2.addWidget(self.bl_input)
        bl_add = QPushButton("+ 添加")
        bl_add.setObjectName("dangerBtn")
        bl_add.clicked.connect(self._add_bl)
        row2.addWidget(bl_add)
        f2.addLayout(row2)

        self.bl_list = QListWidget()
        self.bl_list.itemDoubleClicked.connect(self._del_bl)
        self.bl_list.setStyleSheet("QListWidget::item { padding: 6px 10px; }")
        f2.addWidget(self.bl_list)
        l.addWidget(gb2)

        self._refresh_kw()
        self._refresh_bl()
        return w

    def _refresh_kw(self):
        self.kw_list.clear()
        work, urgent = get_all_keywords()
        for kw in work:
            item = QListWidgetItem(f"\U0001f4cb 工作  |  {kw}")
            item.setData(1, ('work', kw))
            self.kw_list.addItem(item)
        for kw in urgent:
            item = QListWidgetItem(f"\U0001f534 紧急  |  {kw}")
            item.setData(1, ('urgent', kw))
            self.kw_list.addItem(item)

    def _add_kw(self):
        kw = self.kw_input.text().strip()
        if not kw:
            return
        cat = 'urgent' if self.kw_cat.currentIndex() == 1 else 'work'
        add_keyword(kw, cat)
        self.kw_input.clear()
        self._refresh_kw()

    def _del_kw(self, item):
        data = item.data(1)
        if data:
            delete_keyword(data[1])
            self._refresh_kw()

    def _refresh_bl(self):
        self.bl_list.clear()
        for name in get_all_blacklist():
            self.bl_list.addItem(QListWidgetItem(name))

    def _add_bl(self):
        name = self.bl_input.text().strip()
        if not name:
            return
        add_blacklist(name)
        self.bl_input.clear()
        self._refresh_bl()

    def _del_bl(self, item):
        delete_blacklist(item.text())
        self._refresh_bl()

    def _create_reminder_page(self):
        w, l = self._make_page()
        l.addWidget(self._section_title("\U0001f514 提醒方式"))

        gb = QGroupBox("弹窗提醒")
        fl = QFormLayout(gb)
        fl.setSpacing(10)

        self.popup_cb = QCheckBox("启用紧急消息弹窗提醒")
        fl.addRow(self.popup_cb)

        l.addWidget(gb)

        btn = QPushButton("\U0001f4be 保存设置")
        btn.setObjectName("primaryBtn")
        btn.clicked.connect(self._save_reminder)
        l.addWidget(btn)
        l.addStretch()

        settings = get_all_settings()
        self.popup_cb.setChecked(settings.get('enable_popup', '1') == '1')
        return w

    def _save_reminder(self):
        save_setting('enable_popup', '1' if self.popup_cb.isChecked() else '0')

    def _create_ai_page(self):
        w, l = self._make_page()
        l.addWidget(self._section_title("\U0001f916 AI 配置"))

        gb = QGroupBox("API 设置（支持 OpenAI 兼容接口）")
        fl = QFormLayout(gb)
        fl.setSpacing(10)

        self.ai_provider = QComboBox()
        self.ai_provider.addItems(["OpenAI", "Ollama (本地)", "自定义"])
        fl.addRow("服务商:", self.ai_provider)

        self.ai_url = QLineEdit()
        self.ai_url.setPlaceholderText("https://api.openai.com/v1/chat/completions")
        fl.addRow("API 地址:", self.ai_url)

        self.ai_key = QLineEdit()
        self.ai_key.setEchoMode(QLineEdit.Password)
        self.ai_key.setPlaceholderText("sk-...")
        fl.addRow("API Key:", self.ai_key)

        self.ai_model = QLineEdit()
        self.ai_model.setPlaceholderText("gpt-3.5-turbo / llama3")
        fl.addRow("模型名称:", self.ai_model)

        l.addWidget(gb)

        btn = QPushButton("\U0001f4be 保存 AI 配置")
        btn.setObjectName("primaryBtn")
        btn.clicked.connect(self._save_ai)
        l.addWidget(btn)

        hint = QLabel("\U0001f4a1 提示：本地模型推荐使用 Ollama，安装后 API 地址填 http://localhost:11434/v1/chat/completions")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #9ca3af; font-size: 11px;")
        l.addWidget(hint)
        l.addStretch()

        settings = get_all_settings()
        self.ai_url.setText(settings.get('ai_api_url', ''))
        self.ai_key.setText(settings.get('ai_api_key', ''))
        self.ai_model.setText(settings.get('ai_model', ''))
        return w

    def _save_ai(self):
        save_setting('ai_api_url', self.ai_url.text().strip())
        save_setting('ai_api_key', self.ai_key.text().strip())
        save_setting('ai_model', self.ai_model.text().strip())

    def _create_data_page(self):
        w, l = self._make_page()
        l.addWidget(self._section_title("\U0001f4ca 数据管理"))

        gb = QGroupBox("数据库信息")
        fl = QFormLayout(gb)
        fl.setSpacing(10)

        from core.data_manager import count_messages
        total = count_messages()
        fl.addRow("总消息数:", QLabel(f"{total:,} 条"))

        import os
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'message_data', 'cache.db')
        if os.path.exists(db_path):
            size_mb = os.path.getsize(db_path) / (1024 * 1024)
            fl.addRow("数据库大小:", QLabel(f"{size_mb:.1f} MB"))
        fl.addRow("数据库路径:", QLabel(db_path))

        l.addWidget(gb)
        l.addStretch()
        return w

    def _create_ui_page(self):
        w, l = self._make_page()
        l.addWidget(self._section_title("\U0001f3a8 界面设置"))

        gb = QGroupBox("显示选项")
        fl = QFormLayout(gb)
        fl.setSpacing(10)

        self.start_minimized = QCheckBox("启动时最小化到托盘")
        fl.addRow(self.start_minimized)

        self.show_avatars = QCheckBox("显示用户头像")
        self.show_avatars.setChecked(True)
        fl.addRow(self.show_avatars)

        l.addWidget(gb)

        btn = QPushButton("\U0001f4be 保存设置")
        btn.setObjectName("primaryBtn")
        btn.clicked.connect(self._save_ui)
        l.addWidget(btn)
        l.addStretch()
        return w

    def _save_ui(self):
        save_setting('start_minimized', '1' if self.start_minimized.isChecked() else '0')
        save_setting('show_avatars', '1' if self.show_avatars.isChecked() else '0')

    def _create_about_page(self):
        w, l = self._make_page()
        l.addWidget(self._section_title("\u2139\ufe0f 关于"))

        info = QLabel("""
        <h2 style='color:#111827;'>微信信息管家 v0.6</h2>
        <p style='color:#6b7280; line-height:1.8;'>
        \u2705 实时消息监控与智能归类<br>
        \u2705 紧急消息弹窗提醒（持久化）<br>
        \u2705 每日简报自动汇总<br>
        \u2705 历史消息全文检索<br>
        \u2705 AI 智能分析（支持本地/云端模型）<br>
        \u2705 延时提醒（10分钟/30分钟/1小时/3小时/1天）<br>
        </p>
        <p style='color:#9ca3af; font-size:11px;'>
        本地运行 \u00b7 数据不上传 \u00b7 隐私安全
        </p>
        """)
        info.setWordWrap(True)
        l.addWidget(info)
        l.addStretch()
        return w
