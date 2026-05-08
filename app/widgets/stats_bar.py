# app/widgets/stats_bar.py
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel


class StatsBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statsPanel")

        self.setStyleSheet("""
            #statsPanel {
                background: #2d2d2d;
                border-top: 1px solid #4a4a4a;
                border-bottom: 1px solid #4a4a4a;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(20)

        self.today_label = QLabel("\U0001f4c5 今日: 0")
        self.today_label.setStyleSheet("font-size: 12px; color: #b0b0b0;")
        self.active_label = QLabel("\U0001f4ac 会话: 0")
        self.active_label.setStyleSheet("font-size: 12px; color: #b0b0b0;")
        self.urgent_label = QLabel("\U0001f534 紧急: 0")
        self.urgent_label.setStyleSheet("font-size: 12px; color: #ef4444; font-weight: 600;")
        self.total_label = QLabel("\U0001f4e6 缓存: 0")
        self.total_label.setStyleSheet("font-size: 12px; color: #888888;")

        layout.addWidget(self.today_label)
        layout.addWidget(self.active_label)
        layout.addWidget(self.urgent_label)
        layout.addWidget(self.total_label)
        layout.addStretch()

    def update_stats(self, today, active, urgent, total):
        self.today_label.setText(f"\U0001f4c5 今日: {today}")
        self.active_label.setText(f"\U0001f4ac 会话: {active}")
        self.urgent_label.setText(f"\U0001f534 紧急: {urgent}")
        self.total_label.setText(f"\U0001f4e6 缓存: {total}")
