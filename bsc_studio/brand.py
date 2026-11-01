from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import __version__
from .storage import resource_dir


class BrandHeader(QFrame):
    """Native vector waves recall the violet masthead on brewerssocialclub.com."""

    def __init__(self):
        super().__init__()
        self.setObjectName("masthead")
        self.setFixedHeight(126)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(30, 16, 30, 16)
        layout.setSpacing(22)
        logo = QLabel()
        logo.setFixedSize(94, 94)
        pixmap = QPixmap(str(resource_dir() / "brand" / "bsc-logo.png"))
        logo.setPixmap(pixmap.scaled(94, 94, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        logo.setAccessibleName("Logo Brewers Social Club")
        layout.addWidget(logo)
        titles = QVBoxLayout()
        titles.setContentsMargins(0, 0, 0, 0)
        titles.setSpacing(5)
        eyebrow = QLabel("BREWERS SOCIAL CLUB")
        eyebrow.setObjectName("mastheadBrand")
        title = QLabel("LE STUDIO DES COPAINS")
        title.setObjectName("mastheadTitle")
        titles.addStretch()
        titles.addWidget(eyebrow)
        titles.addWidget(title)
        titles.addStretch()
        layout.addLayout(titles, 1)
        info = QVBoxLayout()
        badge = QLabel("RADIO / PODCASTS")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setObjectName("mastheadPill")
        note = QLabel(f"STUDIO WINDOWS  ·  {__version__}")
        note.setObjectName("mastheadNote")
        note.setAlignment(Qt.AlignmentFlag.AlignRight)
        info.addStretch()
        info.addWidget(badge)
        info.addWidget(note)
        info.addStretch()
        layout.addLayout(info)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width(), self.height()
        gradient = QLinearGradient(0, 0, width, height)
        gradient.setColorAt(0, QColor("#8d2bf3"))
        gradient.setColorAt(0.52, QColor("#9b32f7"))
        gradient.setColorAt(1, QColor("#8428ed"))
        painter.fillRect(self.rect(), gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        for index in range(-2, 8):
            x = width * (index * 0.19)
            path = QPainterPath()
            path.moveTo(x + 200, -30)
            path.cubicTo(x + 130, height * 0.3, x + 110, height * 0.65, x + 15, height + 30)
            path.lineTo(x + 145, height + 30)
            path.cubicTo(x + 225, height * 0.68, x + 235, height * 0.25, x + 340, -30)
            path.closeSubpath()
            painter.fillPath(path, QColor(221, 136, 230, 45 if index % 2 else 29))
        painter.end()


class BrandNavigation(QWidget):
    currentRowChanged = Signal(int)

    def __init__(self):
        super().__init__()
        self.setObjectName("navigation")
        self._current = -1
        self.buttons = []
        self.setFixedHeight(54)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 0, 22, 0)
        layout.setSpacing(0)
        for index, name in enumerate(("MES ÉPISODES", "IMPORTS", "STUDIO", "MISES À JOUR", "PARAMÈTRES", "TOUT BSC")):
            button = QPushButton(name + "   +")
            button.setObjectName("navTab")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, selected=index: self.setCurrentRow(selected))
            self.buttons.append(button)
            layout.addWidget(button, 1)

    def currentRow(self):
        return self._current

    def setCurrentRow(self, index):
        if not 0 <= index < len(self.buttons):
            return
        if index == self._current:
            self.buttons[index].setChecked(True)
            return
        self._current = index
        for position, button in enumerate(self.buttons):
            button.setChecked(position == index)
        self.currentRowChanged.emit(index)
