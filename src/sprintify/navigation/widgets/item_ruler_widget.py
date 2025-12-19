from typing import Callable, Optional, Literal
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QBrush

from sprintify.navigation.rulers.item import ItemRuler
from sprintify.navigation.colors.modes import ColorMap


class ItemRulerWidget(QWidget):
    """
    Ruler widget showing one band per item (row or column).

    Features:
    - Item labels (via get_label callback or default str(index))
    - Ctrl+wheel zooms, plain wheel pans
    - Supports both vertical ('y') and horizontal ('x') orientation
    """

    def __init__(self, ruler: ItemRuler, color_map: ColorMap, orientation: Literal['x', 'y'] = 'y', get_label: Optional[Callable[[int], str]] = None, parent: Optional[QWidget] = None) -> None:
        """Create item ruler widget. get_label(index) returns label for each item, defaults to str(index)."""
        super().__init__(parent)
        self.ruler: ItemRuler = ruler
        self.color_map: ColorMap = color_map
        self.orientation: Literal['x', 'y'] = orientation
        self.get_label: Callable[[int], str] = get_label or (lambda i: str(i))

        if orientation == 'x':
            self.setFixedHeight(80)
        else:
            self.setFixedWidth(80)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.orientation == 'x':
            self.ruler.length = self.width()
        else:
            self.ruler.length = self.height()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw background
        painter.fillRect(self.rect(), self.color_map.get_object_color("surface-base"))

        # Determine visible item range
        first_visible = int(self.ruler.visible_start)
        last_visible = min(int(self.ruler.visible_stop) + 1, self.ruler.item_count)

        # Draw each visible item
        for item_index in range(first_visible, last_visible):
            start, stop = self.ruler.get_item_bounds(item_index)

            if self.orientation == 'x':
                # Horizontal orientation
                if stop < 0 or start > self.width():
                    continue

                # Draw separator line
                painter.setPen(QPen(self.color_map.get_object_color("border"), 1))
                painter.drawLine(int(start), self.height()-10, int(start), self.height())

                # Draw label (rotated 90 degrees)
                label = self.get_label(item_index)
                painter.setPen(QPen(self.color_map.get_object_color("text-base"), 1))
                painter.save()
                painter.translate(start + (stop - start) / 2, self.height() - 5)
                painter.rotate(-90)
                painter.drawText(
                    QRectF(0, -25, 70, 50),
                    Qt.AlignmentFlag.AlignCenter,
                    label
                )
                painter.restore()
            else:
                # Vertical orientation
                if stop < 0 or start > self.height():
                    continue

                # Draw separator line
                painter.setPen(QPen(self.color_map.get_object_color("border"), 1))
                painter.drawLine(self.width()-5, int(start), self.width(), int(start))

                # Draw label
                label = self.get_label(item_index)
                painter.setPen(QPen(self.color_map.get_object_color("text-base"), 1))
                painter.drawText(
                    QRectF(5, start, self.width() - 10, stop - start),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    label
                )

    def wheelEvent(self, event):
        zoom_in = event.angleDelta().y() > 0

        if self.orientation == 'x':
            mouse_pos = event.position().x()
        else:
            mouse_pos = event.position().y()

        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Zoom
            self.ruler.zoom(zoom_in, mouse_pos)
        else:
        # Pan
            if self.orientation == 'x':
                self.ruler.pan(event.angleDelta().x())
            else:
                self.ruler.pan(-event.angleDelta().y())

        self.update()
        if self.parent() and hasattr(self.parent(), "_notify_linked"):
            self.parent()._notify_linked()
        elif self.parent() and hasattr(self.parent(), 'canvas'):
            self.parent().canvas.update()
        event.accept()
