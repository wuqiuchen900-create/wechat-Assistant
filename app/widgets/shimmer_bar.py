# app/widgets/shimmer_bar.py
from PyQt5.QtWidgets import QProgressBar
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt5.QtGui import QPainter, QBrush, QColor, QRadialGradient


class ShimmerProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0, 0)
        self.setTextVisible(False)
        self.setFixedHeight(4)
        self._shimmer_pos = 0.0

        self.setStyleSheet("""
            QProgressBar {
                background-color: #3d3d3d;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: transparent;
            }
        """)

        self._anim = QPropertyAnimation(self, b"shimmerPos")
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(1500)
        self._anim.setLoopCount(-1)
        self._anim.setEasingCurve(QEasingCurve.InOutSine)
        self._anim.start()

    @pyqtProperty(float)
    def shimmerPos(self):
        return self._shimmer_pos

    @shimmerPos.setter
    def shimmerPos(self, value):
        self._shimmer_pos = value
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        bar_width = self.width()
        bar_height = self.height()
        shimmer_width = 800

        x_start = self._shimmer_pos * (bar_width + shimmer_width) - shimmer_width
        center_x = x_start + shimmer_width / 2
        center_y = bar_height / 2

        gradient = QRadialGradient(center_x, center_y, shimmer_width / 1.5)
        core_color = QColor(218, 165, 32, 150)
        edge_color = QColor(218, 165, 32, 0)
        gradient.setColorAt(0.0, core_color)
        gradient.setColorAt(1.0, edge_color)

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRect(int(x_start), 0, shimmer_width, bar_height)
        painter.end()
