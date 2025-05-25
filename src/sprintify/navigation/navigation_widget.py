from datetime import datetime

from PySide6.QtCore import Qt, QRectF, QPoint, QPointF, QLineF
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QBrush

from sprintify.navigation.renderers import TimelineRulerRenderer, NumberRulerRenderer
from sprintify.navigation.rulers import NumberRuler, TimelineRuler

class NavigationWidget(QWidget):
    def __init__(self, top_ruler, left_ruler, color_map, right_ruler=None, bottom_ruler=None, parent=None):
        super().__init__(parent)
        self.color_map = color_map
        self.top_ruler = top_ruler
        self.left_ruler = left_ruler
        self.right_ruler = right_ruler
        self.bottom_ruler = bottom_ruler
        self.last_full_zoom = datetime.now()
        self.panning = False
        self.last_mouse_pos = QPoint()
        self.last_full_zoom = datetime.now()
        self.setMouseTracking(True)

        self.top_renderer = self.create_renderer(top_ruler)
        self.left_renderer = self.create_renderer(left_ruler, orientation='y')
        self.bottom_renderer = None
        self.right_renderer = None
        self.draw_commands = {}

    def create_renderer(self, ruler, orientation='x'):
        if isinstance(ruler, NumberRuler):
            return NumberRulerRenderer(ruler, self.color_map, orientation)
        elif isinstance(ruler, TimelineRuler):
            return TimelineRulerRenderer(ruler, self.color_map, orientation)
        return None

    def add_draw_command(self, name, command):
        self.draw_commands[name] = command

    def remove_draw_command(self, name):
        if name in self.draw_commands:
            del self.draw_commands[name]

    def draw_rects(self, name, get_rects_func, brush=None, pen=None):
        def command(painter):
            rects = get_rects_func()
            if pen:
                painter.setPen(pen)
            else:
                painter.setPen(Qt.PenStyle.NoPen)
            if brush:
                painter.setBrush(brush)
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
            def transform_rect(x, y, width, height):
                x1 = self.top_ruler.transform(x, self.width())
                y1 = self.left_ruler.transform(y, self.height())
                x2 = self.top_ruler.transform(x+width, self.width())
                y2 = self.left_ruler.transform(y+height, self.height())
                return QRectF(x1, y1, x2-x1, y2-y1)
            painter.drawRects([QRectF(transform_rect(x, y, width, height)) for x, y, width, height in rects])
        self.add_draw_command(name, command)

    def draw_lines(self, name, get_lines_func, pen=None):
        def command(painter):
            lines = get_lines_func()
            if pen:
                painter.setPen(pen)
            qlines = [QLineF(self.top_ruler.transform(x1, self.width()), self.left_ruler.transform(y1, self.height()), self.top_ruler.transform(x2, self.width()), self.left_ruler.transform(y2, self.height())) for x1, y1, x2, y2 in lines]
            painter.drawLines(qlines)
        self.add_draw_command(name, command)

    def draw_ellipses(self, name, get_ellipses_func, brush=None, pen=None):
        def command(painter):
            ellipses = get_ellipses_func()
            if pen:
                painter.setPen(pen)
            else:
                painter.setPen(Qt.PenStyle.NoPen)
            if brush:
                painter.setBrush(brush)
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
            for x, y, width, height in ellipses:
                painter.drawEllipse(QRectF(self.top_ruler.transform(x, self.width()), self.left_ruler.transform(y, self.height()), width, height))
        self.add_draw_command(name, command)

    def draw_texts(self, name, get_texts_func, pen=None, font=None):
        def command(painter):
            texts = get_texts_func()
            if pen:
                painter.setPen(pen)
            if font:
                painter.setFont(font)
            for text, x, y in texts:
                painter.drawText(QPointF(self.top_ruler.transform(x, self.width()), self.left_ruler.transform(y, self.height())), text)
        self.add_draw_command(name, command)

    def draw_points(self, name, get_points_func, pen=None):
        def command(painter):
            points = get_points_func()
            if pen:
                painter.setPen(pen)
            painter.drawPoints([QPointF(self.top_ruler.transform(x, self.width()), self.left_ruler.transform(y, self.height())) for x, y in points])
        self.add_draw_command(name, command)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setBrush(QBrush(self.color_map.get_object_color("surface-lower")))
        rect = QRectF(0, 0, self.width(), self.height())
        painter.drawRect(rect)

        for command in self.draw_commands.values():
            command(painter)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.color_map.get_object_color("surface-base")))
        rect = QRectF(0, 0, self.width(), 20)
        painter.drawRect(rect)
        rect = QRectF(0, 0, 20, self.height())
        painter.drawRect(rect)

        self.top_renderer.draw_ruler(painter, self.width())
        self.left_renderer.draw_ruler(painter, self.height())

    def wheelEvent(self, event):
        if (datetime.now() - self.last_full_zoom).total_seconds() < 0.5:
            return
        zoom_in = event.angleDelta().y() > 0
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # X zooming
            mouse_pos = event.position().x()
            self.top_ruler.zoom(zoom_in, mouse_pos, self.width())
            self.update()
            if self.top_ruler.window_length == self.top_ruler.visible_length:
                self.last_full_zoom = datetime.now()
        elif event.modifiers() & Qt.KeyboardModifier.AltModifier:
            # Y zooming
            mouse_pos = event.position().y()
            self.left_ruler.zoom(zoom_in, mouse_pos, self.height())
            self.update()
            if self.left_ruler.window_length == self.left_ruler.visible_length:
                self.last_full_zoom = datetime.now()
            pass
        else:
            # Scroll
            self.top_ruler.pan(event.angleDelta().x(), self.width())
            self.left_ruler.pan(-event.angleDelta().y(), self.height())
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.panning = True
            self.last_mouse_pos = event.pos()

    def mouseMoveEvent(self, event):
        if self.panning:
            delta_x = (event.pos() - self.last_mouse_pos).x()
            delta_y = (event.pos() - self.last_mouse_pos).y()
            self.top_ruler.pan(delta_x, self.width())
            self.left_ruler.pan(-delta_y, self.height())
            self.last_mouse_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.panning = False