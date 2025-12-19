from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QGridLayout
from PySide6.QtGui import QPainter

from sprintify.navigation.rulers import NumberRuler, TimelineRuler, ItemRuler
from sprintify.navigation.widgets import NumberRulerWidget, TimelineRulerWidget, DrawingWidget, ItemRulerWidget


class NavigationWidget(QWidget):
    """
    Main composite navigation widget.

    Uses a QGridLayout to arrange:
    - Top ruler widget (horizontal timeline or number ruler)
    - Left ruler widget (vertical number ruler)
    - Main canvas area (for drawing data)

    The ruler widgets handle their own rendering and zoom/pan interactions
    by delegating to the underlying ruler models (NumberRuler, TimelineRuler).
    """

    def __init__(self, top_ruler, left_ruler, color_map, right_ruler=None, bottom_ruler=None, parent=None):
        super().__init__(parent)
        self.color_map = color_map
        self.top_ruler = top_ruler
        self.left_ruler = left_ruler
        self.right_ruler = right_ruler
        self.bottom_ruler = bottom_ruler

        # Create ruler widgets (share the BaseRuler instances)
        if isinstance(top_ruler, TimelineRuler):
            self.top_ruler_widget = TimelineRulerWidget(top_ruler, color_map, self)
        elif isinstance(top_ruler, ItemRuler):
            self.top_ruler_widget = ItemRulerWidget(top_ruler, color_map, orientation='x', parent=self)
        else:
            self.top_ruler_widget = NumberRulerWidget(top_ruler, color_map, 'x', self)

        if isinstance(left_ruler, ItemRuler):
            self.left_ruler_widget = ItemRulerWidget(left_ruler, color_map, orientation='y', parent=self)
        else:
            self.left_ruler_widget = NumberRulerWidget(left_ruler, color_map, 'y', self)

        # Create drawing widget (shares the same BaseRuler instances)
        self.canvas = DrawingWidget(top_ruler, left_ruler, color_map, self)

        # Layout
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Corner size matches the ruler dimensions
        corner_height = 30 if isinstance(top_ruler, TimelineRuler) else (80 if isinstance(top_ruler, ItemRuler) else 20)
        corner_width = 80 if isinstance(left_ruler, ItemRuler) else 20
        corner = QWidget()
        corner.setFixedSize(corner_width, corner_height)
        corner.paintEvent = lambda e: QPainter(corner).fillRect(corner.rect(), color_map.get_object_color("surface-base"))

        layout.addWidget(corner, 0, 0)
        layout.addWidget(self.top_ruler_widget, 0, 1)
        layout.addWidget(self.left_ruler_widget, 1, 0)
        layout.addWidget(self.canvas, 1, 1)

        self.setMouseTracking(True)

        self._linked_widgets: set["NavigationWidget"] = set()

    def link_widget(self, other: "NavigationWidget") -> None:
        """Link two NavigationWidgets so they repaint together (useful when sharing ruler instances)."""
        if other is self:
            return
        self._linked_widgets.add(other)
        other._linked_widgets.add(self)

    def _notify_linked(self) -> None:
        """Repaint this widget and any linked widgets (and their rulers)."""
        self.update()
        for w in list(self._linked_widgets):
            w.update()
            # ensure their canvas repaints even if only rulers changed
            if hasattr(w, "canvas"):
                w.canvas.update()

    # Delegate drawing API to canvas
    def add_draw_command(self, name, command):
        self.canvas.add_draw_command(name, command)

    def remove_draw_command(self, name):
        self.canvas.remove_draw_command(name)

    def clear_draw_commands(self):
        """Clear all registered draw commands on the canvas."""
        self.canvas.draw_commands.clear()

    def draw_rects(self, name, get_rects_func, brush=None, pen=None):
        self.canvas.draw_rects(name, get_rects_func, brush, pen)

    def draw_lines(self, name, get_lines_func, pen=None):
        self.canvas.draw_lines(name, get_lines_func, pen)

    def draw_ellipses(self, name, get_ellipses_func, brush=None, pen=None):
        self.canvas.draw_ellipses(name, get_ellipses_func, brush, pen)

    def draw_texts(self, name, get_texts_func, pen=None, font=None):
        self.canvas.draw_texts(name, get_texts_func, pen, font)

    def draw_points(self, name, get_points_func, pen=None):
        self.canvas.draw_points(name, get_points_func, pen)
