from typing import List, Literal, Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QBrush
import numpy as np
import math

from sprintify.navigation.rulers.number import NumberRuler
from sprintify.navigation.colors.modes import ColorMap


class NumberRulerWidget(QWidget):
    def __init__(self, ruler: NumberRuler, color_map: ColorMap, orientation: Literal['x', 'y'] = 'x', parent: Optional[QWidget] = None) -> None:
        """Create numeric ruler widget with auto-generated tick labels and SI unit formatting."""
        super().__init__(parent)
        self.ruler: NumberRuler = ruler
        self.color_map: ColorMap = color_map
        self.orientation: Literal['x', 'y'] = orientation

        if orientation == 'x':
            self.setFixedHeight(20)
        else:
            self.setFixedWidth(20)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.ruler.length = self.width() if self.orientation == 'x' else self.height()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(self.color_map.get_object_color("surface-base")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())

        pixels_per_unit = 100
        painter.setPen(QPen(self.color_map.get_object_color("text-base"), 1))

        for ticker in self._get_tickers():
            pos = self.ruler.transform(ticker)
            text = self._format_ticker(ticker)

            if self.orientation == 'x':
                painter.drawText(QRectF(pos - pixels_per_unit / 2, 0, pixels_per_unit, 20), Qt.AlignmentFlag.AlignCenter, text)
                painter.drawLine(int(pos), 17, int(pos), 20)
            else:
                painter.save()
                painter.rotate(-90)
                painter.drawText(QRectF(-pos - pixels_per_unit / 2, 0, pixels_per_unit, 20), Qt.AlignmentFlag.AlignCenter, text)
                painter.restore()
                painter.drawLine(17, int(pos), 20, int(pos))

    def _get_tickers(self) -> np.ndarray:
        y_range = self.ruler.visible_stop - self.ruler.visible_start
        if y_range == 0:
            return [self.ruler.visible_start]

        raw_step = y_range / 3
        magnitude = 10 ** np.floor(np.log10(raw_step))
        if raw_step / magnitude < 2:
            step = magnitude
        elif raw_step / magnitude < 5:
            step = 2 * magnitude
        else:
            step = 5 * magnitude

        return np.arange(
            np.floor(self.ruler.visible_start / step) * step,
            np.ceil(self.ruler.visible_stop / step) * step + step,
            step
        )

    def _format_ticker(self, ticker: float) -> str:
        if ticker == 0:
            return "0"
        magnitude = int(math.floor(math.log10(abs(ticker)) / 3) * 3)
        suffixes = {15: 'P', 12: 'T', 9: 'G', 6: 'M', 3: 'k', 0: '', -3: 'm', -6: 'µ', -9: 'n'}
        value = ticker / (10 ** magnitude)
        suffix = suffixes.get(magnitude, '')
        return f"{int(value)}{suffix}" if value.is_integer() else f"{value:.6g}{suffix}"

    def wheelEvent(self, event):
        zoom_in = event.angleDelta().y() > 0
        mouse_pos = event.position().x() if self.orientation == 'x' else event.position().y()

        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.ruler.zoom(zoom_in, mouse_pos)
        else:
            delta = event.angleDelta().x() if self.orientation == 'x' else -event.angleDelta().y()
            self.ruler.pan(delta)

        self.update()
        if self.parent() and hasattr(self.parent(), 'canvas'):
            self.parent().canvas.update()
        event.accept()
