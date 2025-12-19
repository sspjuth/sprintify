from typing import Iterator, Tuple, Literal, Optional
from datetime import datetime, timedelta
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QBrush

from sprintify.navigation.rulers.timeline import TimelineRuler
from sprintify.navigation.colors.modes import ColorMap


class TimelineRulerWidget(QWidget):
    def __init__(self, ruler: TimelineRuler, color_map: ColorMap, parent: Optional[QWidget] = None) -> None:
        """Create timeline ruler widget with automatic period detection (years/months/days/hours)."""
        super().__init__(parent)
        self.ruler: TimelineRuler = ruler
        self.color_map: ColorMap = color_map
        self.setFixedHeight(30)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.ruler.length = self.width()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(self.color_map.get_object_color("surface-base")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())

        visible_seconds = (self.ruler.visible_stop - self.ruler.visible_start).total_seconds()
        pixels_per_day = self.width() / (visible_seconds / 86400) if visible_seconds > 0 else float("inf")

        if pixels_per_day > 50 * 24:
            p_major, p_minor = "D", "H"
        elif pixels_per_day > 25:
            p_major, p_minor = "M", "D"
        elif 30 < pixels_per_day * 30:
            p_major, p_minor = "Y", "M"
        else:
            p_major, p_minor = None, "Y"

        # Draw major period in top half (0-15 pixels)
        if p_major:
            self._draw_period(painter, p_major, y_offset=0, height=15, is_major=True)

        # Draw minor period in bottom half (15-30 pixels)
        if p_minor:
            self._draw_period(painter, p_minor, y_offset=15, height=15, is_major=False)

    def _draw_period(self, painter: QPainter, period: Literal['Y', 'M', 'D', 'H'], y_offset: int = 0, height: int = 15, is_major: bool = False) -> None:
        """Draw ticks and labels for a specific time period (Y=year, M=month, D=day, H=hour)."""
        for period_start, period_end in self._periods(period):
            x1 = max(self.ruler.transform(period_start), 0)
            x2 = min(self.ruler.transform(period_end), self.width())
            if x2 <= x1:
                continue

            txt = self._period_txt(period_start, period)
            available = x2 - x1

            if x1 != 0:
                if is_major:
                    # Major separator: shorter, from y=10 to bottom (20 pixels total)
                    painter.setPen(QPen(self.color_map.get_object_color("text-base"), 1))
                    painter.drawLine(int(x1), 10, int(x1), 30)
                else:
                    # Minor separator: just in its own row
                    painter.setPen(QPen(self.color_map.get_object_color("border-intense"), 1))
                    painter.drawLine(int(x1), y_offset + height - 5, int(x1), y_offset + height)

            painter.setPen(QPen(self.color_map.get_object_color("text-base"), 1))
            if available > painter.fontMetrics().horizontalAdvance(txt) + 8:
                painter.drawText(QRectF(x1, y_offset, available, height), Qt.AlignmentFlag.AlignCenter, txt)
            else:
                tick_count = int(available / 50)
                if tick_count > 0:
                    tick_delta = (period_end - period_start) / tick_count
                    painter.setPen(QPen(self.color_map.get_object_color("border-light"), 1))
                    for i in range(1, tick_count):
                        tick_x = self.ruler.transform(period_start + tick_delta * i)
                        painter.drawLine(int(tick_x), y_offset + height - 7, int(tick_x), y_offset + height - 5)

                label_x = self.ruler.transform(period_start + (period_end - period_start) / 2)
                painter.setPen(QPen(self.color_map.get_object_color("text-base"), 1))
                painter.drawText(QRectF(label_x - 20, y_offset, 40, height), Qt.AlignmentFlag.AlignCenter, txt)

    def _periods(self, period: Literal['Y', 'M', 'D', 'H']) -> Iterator[Tuple[datetime, datetime]]:
        current = self._round_down(self.ruler.window_start, period)
        while current < self.ruler.window_stop:
            next_date = self._round_up(current, period)
            yield (current, next_date)
            current = next_date

    def _round_down(self, time: datetime, period: Literal['Y', 'M', 'D', 'H']) -> datetime:
        if period == "Y":
            return time.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == "M":
            return time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == "D":
            return time.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "H":
            return time.replace(minute=0, second=0, microsecond=0)

    def _round_up(self, time: datetime, period: Literal['Y', 'M', 'D', 'H']) -> datetime:
        if period == "Y":
            return time.replace(year=time.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == "M":
            next_month = time.month % 12 + 1
            year = time.year + (time.month // 12)
            return time.replace(year=year, month=next_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == "D":
            return (time + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "H":
            return (time + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

    def _period_txt(self, time: datetime, period: Literal['Y', 'M', 'D', 'H']) -> str:
        if period == "Y":
            return time.strftime("%Y")
        elif period == "M":
            return time.strftime("%b")
        elif period == "D":
            return time.strftime("%d")
        elif period == "H":
            return time.strftime("%H:00")

    def wheelEvent(self, event):
        zoom_in = event.angleDelta().y() > 0

        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.ruler.zoom(zoom_in, event.position().x())
        else:
            self.ruler.pan(event.angleDelta().x())

        self.update()
        if self.parent() and hasattr(self.parent(), 'canvas'):
            self.parent().canvas.update()
        event.accept()
