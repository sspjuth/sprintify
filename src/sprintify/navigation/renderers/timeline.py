from datetime import timedelta
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen

class TimelineRulerRenderer:
    def __init__(self, ruler, color_map, orientation='x'):
        self.ruler = ruler
        self.color_map = color_map
        self.orientation = orientation

    def draw_ruler(self, painter, widget_width):
        pixels_per_day = int(widget_width / ((self.ruler.visible_stop - self.ruler.visible_start).total_seconds() / 86400))
        if pixels_per_day > 20:
            self.draw_day_ruler(painter, widget_width)
        elif 30 < pixels_per_day*7:
            self.draw_week_ruler(painter, pixels_per_day*7, widget_width)
        else:
            self.draw_year_ruler(painter, widget_width)

    def draw_day_ruler(self, painter, widget_width):
        start = self.ruler.visible_start
        stop = self.ruler.visible_stop
        current_time = self.ruler.window_start
        pixels_per_day = int(widget_width / ((stop - start).total_seconds() / 86400))

        while current_time <= stop:
            x = self.ruler.transform(current_time, widget_width)
            if current_time > start and (current_time.weekday() == 0 or pixels_per_day > 150):
                painter.setPen(QPen(self.color_map.get_object_color("border"), 1))
                painter.drawLine(int(x), 0, int(x), 20)
            if current_time.weekday() == 5:
                font_color = self.color_map.get_saturated_color("blue", "text-base")
            elif current_time.weekday() == 6:
                font_color = self.color_map.get_saturated_color("deep_orange", "text-base")
            else:
                font_color = self.color_map.get_object_color("text-base")
            painter.setPen(QPen(font_color, 1))
            painter.drawText(QRectF(x, 0, pixels_per_day, 20), Qt.AlignmentFlag.AlignCenter, str(current_time.day))
            current_time += timedelta(days=1)

    def draw_week_ruler(self, painter, week_width, widget_width):
        current_time = self.ruler.window_start
        while current_time <= self.ruler.visible_stop:
            if current_time.weekday() == 0:  # Start of the week
                x = self.ruler.transform(current_time, widget_width)
                painter.setPen(QPen(self.color_map.get_object_color("border-intense"), 1))
                if week_width > 150:
                    painter.drawLine(int(x), 0, int(x), 20)
                painter.setPen(QPen(self.color_map.get_object_color("text-base"), 1))
                painter.drawText(QRectF(x, 0, week_width, 20), Qt.AlignmentFlag.AlignCenter,f"w{current_time.isocalendar()[1]}")
            current_time += timedelta(days=1)

    def draw_year_ruler(self, painter, widget_width):
        start = self.ruler.visible_start
        stop = self.ruler.visible_stop
        current_time = self.ruler.window_start

        while current_time <= stop:
            if current_time.month == 1 and current_time.day == 1:  # Start of the year
                x = self.ruler.transform(current_time, widget_width)
                painter.setPen(QPen(self.color_map.get_object_color("border-intense"), 1))
                painter.drawLine(int(x), 0, int(x), 20)
                painter.setPen(QPen(self.color_map.get_object_color("text-base"), 1))
                painter.drawText(QRectF(x, 0, 200, 20), Qt.AlignmentFlag.AlignCenter, str(current_time.year))
            current_time += timedelta(days=1)
