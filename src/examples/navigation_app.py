from datetime import datetime, timedelta
import random

from PySide6.QtGui import QBrush, QPen
from PySide6.QtWidgets import QMainWindow

from sprintify.navigation.colors.modes import ColorMap
from sprintify.navigation.rulers import NumberRuler, TimelineRuler
from sprintify.navigation.navigation_widget import NavigationWidget

class NavigationWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.rects = None
        self.lines = None
        self.setWindowTitle("Navigation App")
        self.setMinimumSize(800, 420)
        self.top_ruler = TimelineRuler(datetime(2022, 4, 1), datetime(2024, 5, 1))
        self.left_ruler = NumberRuler(0, 50000, reverse=True)
        self.color_map = ColorMap(darkmode=True)

        self.ruler_widget = NavigationWidget(self.top_ruler, self.left_ruler, self.color_map, parent=self)
        self.setCentralWidget(self.ruler_widget)

        self.draw_random_shapes()

    def draw_random_shapes(self):
        green = self.color_map.get_saturated_color("green", "border")
        blue = self.color_map.get_saturated_color("blue", "fill")
        self.ruler_widget.draw_rects(self.get_random_rects, brush=QBrush(blue))
        self.ruler_widget.draw_lines(self.get_random_lines, pen=QPen(green, 1))
        self.ruler_widget.update()

    def get_random_rects(self):
        if self.rects:
            return self.rects
        rects = []
        for _ in range(70):
            x = self.random_datetime()
            y = random.uniform(0, 50000)
            width = self.random_timedelta()
            height = random.uniform(100, 500)
            rects.append((x, y, width, height))
        self.rects = rects
        return rects

    def get_random_lines(self):
        if self.lines:
            return self.lines
        lines = []
        for _ in range(4000):
            x1 = self.random_datetime()
            y1 = random.uniform(0, 50000)
            x2 = self.random_datetime()
            y2 = random.uniform(0, 50000)
            lines.append((x1, y1, x2, y2))
        self.lines = lines
        return lines

    def random_datetime(self):
        start = datetime(2023, 4, 1)
        end = datetime(2024, 5, 1)
        return start + timedelta(seconds=random.randint(0, int((end - start).total_seconds())))

    def random_timedelta(self):
        return timedelta(seconds=random.randint(0, 3600 * 24 * 7))  # Up to 7 days

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = NavigationWindow()
    window.show()
    sys.exit(app.exec())