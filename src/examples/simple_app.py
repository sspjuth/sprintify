import sys
from datetime import datetime, timedelta

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QApplication, QMainWindow

from sprintify.navigation import (
    NavigationWidget, ColorMap, TimelineRuler, NumberRuler,
    InteractionHandler, InteractiveItem
)


class MyWindow(QMainWindow):
    """Minimal example showing rectangles and interaction in data coordinates."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sprintify Navigation - Simple App")

        # Create navigation widget with timeline (X) and number (Y) rulers
        self.nav = NavigationWidget(
            top_ruler=TimelineRuler(datetime(2024, 1, 1), datetime(2024, 12, 31)),
            left_ruler=NumberRuler(0, 100, reverse=True),
            color_map=ColorMap(darkmode=True)
        )
        self.setCentralWidget(self.nav)

        # Draw some static rectangles using data coordinates
        self.nav.draw_rects(
            "my_rects",
            lambda: [
                (datetime(2024, 3, 1), 20, timedelta(days=30), 15),
                (datetime(2024, 6, 1), 50, timedelta(days=45), 20),
            ],
            brush=QBrush(self.nav.color_map.get_saturated_color("blue", "fill")),
        )

        # Add an interactive item (can be moved and resized)
        self.interaction = InteractionHandler(self.nav.canvas,
                                             xr=self.nav.top_ruler,
                                             yr=self.nav.left_ruler)

        # Create interactive item with custom color
        item = InteractiveItem(
            data="My Task",  # Can be any object
            x=datetime(2024, 9, 1),
            y=30,
            width=timedelta(days=60),
            height=25
        )
        item.visuals.fill_color = QColor(self.nav.color_map.get_saturated_color("green", "fill"))
        item.visuals.label = "Drag me!"
        item.tooltip = "Click and drag to move, drag edges to resize"

        self.interaction.add_item(item)

        # Optional: React when item is moved/resized
        self.interaction.on_drop = lambda items: print(f"Item dropped at: {items[0].x}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyWindow()
    window.show()
    sys.exit(app.exec())
