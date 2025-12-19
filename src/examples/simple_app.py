from sprintify.navigation.colors.modes import ColorMap
from sprintify.navigation.rulers import TimelineRuler, NumberRuler
from sprintify.navigation.navigation_widget import NavigationWidget
from PySide6.QtWidgets import QMainWindow, QApplication
from PySide6.QtGui import QBrush, QPen
from datetime import datetime, timedelta


class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.color_map = ColorMap(darkmode=True)

        # Setup rulers
        self.h_ruler = TimelineRuler(datetime(2024, 1, 1), datetime(2024, 12, 31))
        self.v_ruler = NumberRuler(0, 100, reverse=True)

        # Create widget
        self.widget = NavigationWidget(self.h_ruler, self.v_ruler, self.color_map)
        self.setCentralWidget(self.widget)

        # Draw stuff
        blue = self.color_map.get_saturated_color("blue", "fill")
        self.widget.draw_rects(
            "my_rects",
            lambda: [
                (datetime(2024, 3, 1), 20, timedelta(days=30), 15),
                (datetime(2024, 6, 1), 50, timedelta(days=45), 20),
            ],
            brush=QBrush(blue)
        )


if __name__ == "__main__":
    app = QApplication([])
    window = MyWindow()
    window.show()
    app.exec()