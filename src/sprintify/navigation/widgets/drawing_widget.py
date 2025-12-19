from typing import Callable, Tuple, List, Optional
from PySide6.QtCore import Qt, QRectF, QPointF, QLineF, QPoint
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QBrush, QPen, QFont

from sprintify.navigation.rulers.base import BaseRuler
from sprintify.navigation.colors.modes import ColorMap


class DrawingWidget(QWidget):
    """
    Standalone drawing widget that shares BaseRuler instances with ruler widgets.

    Key behaviors:
    - Shares the same ruler instances
    - Syncs dimensions with rulers via length attribute (only on resize)
    - Mouse coords are directly in ruler space
    - Delegates all zoom/pan to the shared BaseRuler instances
    """

    def __init__(self, h_ruler: BaseRuler, v_ruler: BaseRuler, color_map: ColorMap, parent: Optional[QWidget] = None) -> None:
        """Create drawing canvas that shares ruler instances for coordinate transformation."""
        super().__init__(parent)
        self.h_ruler: BaseRuler = h_ruler
        self.v_ruler: BaseRuler = v_ruler
        self.color_map: ColorMap = color_map
        self.draw_commands: dict[str, Callable[[QPainter], None]] = {}
        self.panning: bool = False
        self.last_mouse_pos: Optional[QPoint] = None
        self.setMouseTracking(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.h_ruler.length = self.width()
        self.v_ruler.length = self.height()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(self.color_map.get_object_color("surface-lower")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())

        for command in self.draw_commands.values():
            command(painter)

    def wheelEvent(self, event):
        zoom_in = event.angleDelta().y() > 0
        mouse_x = event.position().x()
        mouse_y = event.position().y()

        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.h_ruler.zoom(zoom_in, mouse_x)
        elif event.modifiers() & Qt.KeyboardModifier.AltModifier:
            self.v_ruler.zoom(zoom_in, mouse_y)
        else:
            self.h_ruler.pan(event.angleDelta().x())
            self.v_ruler.pan(event.angleDelta().y())

        # repaint self + linked widgets (if any)
        self.update()
        if self.parent() and hasattr(self.parent(), "_notify_linked"):
            self.parent()._notify_linked()

        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.panning = True
            self.last_mouse_pos = event.pos()

    def mouseMoveEvent(self, event):
        if self.panning and self.last_mouse_pos:
            delta = event.pos() - self.last_mouse_pos
            self.h_ruler.pan(delta.x())
            self.v_ruler.pan(-delta.y())
            self.last_mouse_pos = event.pos()

            self.update()
            if self.parent() and hasattr(self.parent(), "_notify_linked"):
                self.parent()._notify_linked()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.panning = False
            self.last_mouse_pos = None

    def add_draw_command(self, name: str, command: Callable[[QPainter], None]) -> None:
        """Register a named drawing function. Replaces existing command with same name."""
        self.draw_commands[name] = command

    def remove_draw_command(self, name: str) -> None:
        """Remove a drawing command by name. Does nothing if name doesn't exist."""
        self.draw_commands.pop(name, None)

    def draw_rects(
        self,
        name: str,
        get_rects_func: Callable[[], List[Tuple[float, float, float, float]]],
        brush: Optional[QBrush] = None,
        pen: Optional[QPen] = None
    ) -> None:
        """Draw rectangles. get_rects_func returns list of (x, y, width, height) in data coordinates."""
        def command(painter):
            painter.setPen(pen or Qt.PenStyle.NoPen)
            painter.setBrush(brush or Qt.BrushStyle.NoBrush)
            rects = []
            for x, y, width, height in get_rects_func():
                x1 = self.h_ruler.transform(x)
                y1 = self.v_ruler.transform(y)
                x2 = self.h_ruler.transform(x + width)
                y2 = self.v_ruler.transform(y + height)
                rects.append(QRectF(x1, y1, x2 - x1, y2 - y1))
            painter.drawRects(rects)
        self.add_draw_command(name, command)

    def draw_lines(
        self,
        name: str,
        get_lines_func: Callable[[], List[Tuple[float, float, float, float]]],
        pen: Optional[QPen] = None
    ) -> None:
        """Draw lines. get_lines_func returns list of (x1, y1, x2, y2) in data coordinates."""
        def command(painter):
            if pen:
                painter.setPen(pen)
            lines = [
                QLineF(
                    self.h_ruler.transform(x1),
                    self.v_ruler.transform(y1),
                    self.h_ruler.transform(x2),
                    self.v_ruler.transform(y2)
                )
                for x1, y1, x2, y2 in get_lines_func()
            ]
            painter.drawLines(lines)
        self.add_draw_command(name, command)

    def draw_ellipses(
        self,
        name: str,
        get_ellipses_func: Callable[[], List[Tuple[float, float, float, float]]],
        brush: Optional[QBrush] = None,
        pen: Optional[QPen] = None
    ) -> None:
        """Draw ellipses. get_ellipses_func returns list of (x, y, width, height) in data coordinates."""
        def command(painter):
            painter.setPen(pen or Qt.PenStyle.NoPen)
            painter.setBrush(brush or Qt.BrushStyle.NoBrush)
            for x, y, width, height in get_ellipses_func():
                painter.drawEllipse(QRectF(
                    self.h_ruler.transform(x),
                    self.v_ruler.transform(y),
                    width, height
                ))
        self.add_draw_command(name, command)

    def draw_texts(
        self,
        name: str,
        get_texts_func: Callable[[], List[Tuple[str, float, float]]],
        pen: Optional[QPen] = None,
        font: Optional[QFont] = None
    ) -> None:
        """Draw text labels. get_texts_func returns list of (text, x, y) in data coordinates."""
        def command(painter):
            if pen:
                painter.setPen(pen)
            if font:
                painter.setFont(font)
            for text, x, y in get_texts_func():
                painter.drawText(QPointF(
                    self.h_ruler.transform(x),
                    self.v_ruler.transform(y)
                ), text)
        self.add_draw_command(name, command)

    def draw_points(
        self,
        name: str,
        get_points_func: Callable[[], List[Tuple[float, float]]],
        pen: Optional[QPen] = None
    ) -> None:
        """Draw points. get_points_func returns list of (x, y) in data coordinates."""
        def command(painter):
            if pen:
                painter.setPen(pen)
            points = [
                QPointF(
                    self.h_ruler.transform(x),
                    self.v_ruler.transform(y)
                )
                for x, y in get_points_func()
            ]
            painter.drawPoints(points)
        self.add_draw_command(name, command)
