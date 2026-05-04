# app/settings_page.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QListWidget, QListWidgetItem,
                             QComboBox)
from data.storage import get_all_keywords, add_keyword, delete_keyword

class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # 标题
        title = QLabel("⚙️ 关键词管理")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #212529;")
        layout.addWidget(title)
        layout.addWidget(QLabel("添加或删除工作/紧急关键词，修改后自动生效"))

        # 添加新关键词
        add_layout = QHBoxLayout()
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("输入新关键词...")
        self.keyword_input.setStyleSheet("padding: 6px 10px; border: 1px solid #ced4da; border-radius: 6px;")
        add_layout.addWidget(self.keyword_input)

        self.category_combo = QComboBox()
        self.category_combo.addItems(["工作关键词", "紧急关键词"])
        self.category_combo.setStyleSheet("padding: 6px; border: 1px solid #ced4da; border-radius: 6px;")
        add_layout.addWidget(self.category_combo)

        add_btn = QPushButton("添加")
        add_btn.setStyleSheet("""
            QPushButton {
                background: #1971c2; color: white; padding: 6px 16px;
                border: none; border-radius: 6px; font-weight: bold;
            }
            QPushButton:hover { background: #1864ab; }
        """)
        add_btn.clicked.connect(self._add_keyword)
        add_layout.addWidget(add_btn)
        layout.addLayout(add_layout)

        # 关键词列表
        layout.addWidget(QLabel("当前关键词（双击可删除）："))
        self.keyword_list = QListWidget()
        self.keyword_list.setAlternatingRowColors(True)
        self.keyword_list.itemDoubleClicked.connect(self._delete_keyword)
        layout.addWidget(self.keyword_list)

        self._refresh_list()

    def _refresh_list(self):
        """刷新关键词列表"""
        self.keyword_list.clear()
        work_kw, urgent_kw = get_all_keywords()
        for kw in work_kw:
            item = QListWidgetItem(f"📋 工作  |  {kw}")
            item.setData(1, ('work', kw))
            self.keyword_list.addItem(item)
        for kw in urgent_kw:
            item = QListWidgetItem(f"🔴 紧急  |  {kw}")
            item.setData(1, ('urgent', kw))
            self.keyword_list.addItem(item)

    def _add_keyword(self):
        """添加关键词"""
        kw = self.keyword_input.text().strip()
        if not kw:
            return
        category = 'urgent' if self.category_combo.currentIndex() == 1 else 'work'
        add_keyword(kw, category)
        self.keyword_input.clear()
        self._refresh_list()

    def _delete_keyword(self, item):
        """删除关键词"""
        data = item.data(1)
        if data:
            category, kw = data
            delete_keyword(kw)
            self._refresh_list()