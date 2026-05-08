# app/delegates/avatar.py
from PyQt5.QtWidgets import QStyledItemDelegate, QStyle
from PyQt5.QtCore import Qt, QRect, QRectF
from PyQt5.QtGui import QPainter, QBrush, QColor, QPen, QPainterPath


class AvatarDelegate(QStyledItemDelegate):
    def __init__(self, avatar_cache, parent=None):
        super().__init__(parent)
        self.avatar_cache = avatar_cache

    def paint(self, painter, option, index):
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        else:
            painter.fillRect(option.rect, option.palette.base())

        username = index.data(Qt.UserRole + 1)
        chat_name = index.data(Qt.UserRole)

        avatar_size = 36
        margin = 5
        avatar_rect = QRect(
            option.rect.left() + margin,
            option.rect.top() + (option.rect.height() - avatar_size) // 2,
            avatar_size, avatar_size
        )

        pixmap = None
        if username and username in self.avatar_cache:
            pixmap = self.avatar_cache[username]

        painter.save()
        if pixmap and not pixmap.isNull():
            path = QPainterPath()
            path.addEllipse(QRectF(avatar_rect))
            painter.setClipPath(path)
            painter.drawPixmap(avatar_rect, pixmap)
        else:
            painter.setBrush(QBrush(QColor("#e0e0e0")))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(avatar_rect)
            painter.setPen(QPen(QColor("#999999")))
            font = painter.font()
            font.setPointSize(12)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(avatar_rect, Qt.AlignCenter, chat_name[0] if chat_name else "?")
        painter.restore()

        text_rect = QRect(
            avatar_rect.right() + margin * 2,
            option.rect.top(),
            option.rect.width() - avatar_rect.width() - margin * 3,
            option.rect.height()
        )
        painter.setPen(QPen(QColor("#d0d0d0")))
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, index.data(Qt.DisplayRole))
