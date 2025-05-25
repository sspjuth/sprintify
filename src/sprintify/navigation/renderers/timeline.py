from datetime import timedelta
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPen

class TimelineRulerRenderer:
    def __init__(self, ruler, color_map, orientation='x'):
        self.ruler = ruler
        self.color_map = color_map
        self.orientation = orientation

    def draw_ruler(self, painter, widget_width):
        pixels_per_day = int(widget_width / ((self.ruler.visible_stop - self.ruler.visible_start).total_seconds() / 86400))
        if pixels_per_day > 50*24:
            p_major, p_minor = "D", "H"
        elif pixels_per_day > 25:
            p_major, p_minor = "M", "D"
        #elif 30 < pixels_per_day*7:
        #            #p_major, p_minor = "M", "W"
        elif 30 < pixels_per_day*30:
            p_major, p_minor = "Y", "M"
        else:
            p_major, p_minor = None, "Y"
        self.draw_period_ruler(p_minor, painter, widget_width)

    def draw_period_ruler(self, period,  painter, widget_width):
        for period_start, period_end in periods(self.ruler.window_start, self.ruler.window_stop, period):
            x1 = max(self.ruler.transform(period_start, widget_width), self.ruler.offset_start)
            x2 = min(self.ruler.transform(period_end, widget_width), widget_width)
            txt = period_txt(period_start, period)

            if x1 != self.ruler.offset_start:
                painter.setPen(QPen(self.color_map.get_object_color("border-intense"), 1))
                painter.drawLine(int(x1), 13, int(x1), 20)
            if (x2 - x1) > painter.fontMetrics().horizontalAdvance(txt) + 8:
                painter.setPen(QPen(self.color_map.get_object_color("text-base"), 1))
                painter.drawText(QRectF(x1, 0, x2 - x1, 20), Qt.AlignmentFlag.AlignCenter, txt)


# Some utility functions for  timeline handling
def overlap(period1, period2):
    start= max(period1[0], period2[0])
    stop = min(period1[1], period2[1])
    if start >= stop:
        return None
    return (start, stop)

def periods(start_date, end_date, period):
    current_date = round_down(start_date, period)
    while current_date < end_date:
        next_date = round_up(current_date, period)
        yield (current_date, next_date)
        current_date = next_date

def round_down(time, period):
    if period == "Y":  # Yearly
        return time.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "M":  # Monthly
        return time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "W":  # Weekly
        return time.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=time.weekday())
    elif period == "D":  # Daily
        return time.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "H":  # Hourly
        return time.replace(minute=0, second=0, microsecond=0)
    else:
        raise ValueError("Invalid period. Use 'Y', 'M', 'W', 'D', or 'H'.")

def round_up(time, period):
    if period == "Y":  # Yearly
        return time.replace(year=time.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "M":  # Monthly
        next_month = time.month % 12 + 1
        year = time.year + (time.month // 12)
        return time.replace(year=year, month=next_month, day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "W":  # Weekly
        return (time + timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0, day=(time + timedelta(days=7)).day - time.weekday())
    elif period == "D":  # Daily
        return (time+timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "H":  # Hourly
        return (time+timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    else:
        raise ValueError("Invalid period. Use 'Y', 'M', 'W', 'D', or 'H'.")

def period_txt(time, period, major=False):
    if period == "Y":  # Yearly
        return time.strftime("%Y")
    elif period == "M":  # Monthly
        return time.strftime("%b %Y" if major else "%b")
    elif period == "W":  # Weekly
        return f"W{time.isocalendar()[1]} {time.year}" if major else f"W{time.isocalendar()[1]}"
    elif period == "D":  # Daily
        return time.strftime("%Y-%m-%d") if major else time.strftime("%d")
    elif period == "H":  # Hourly
        return time.strftime("%Y-%m-%d %H:00") if major else time.strftime("%H:00")
    else:
        raise ValueError("Invalid period. Use 'Y', 'M', 'W', 'D', or 'H'.")