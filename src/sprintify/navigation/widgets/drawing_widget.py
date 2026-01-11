from typing import Callable, Tuple, List, Optional, Union
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QPointF, QLineF, QEvent, QSize
from PySide6.QtWidgets import QAbstractScrollArea
from PySide6.QtGui import QPainter, QBrush, QPen, QFont, QPixmap
import math
from datetime import timedelta  # ADDED import

from sprintify.navigation.rulers.base import BaseRuler
from sprintify.navigation.colors.modes import ColorMap


class DrawingWidget(QAbstractScrollArea):
    """
    Drawing canvas that shares ruler model instances, with scrollbar support.

    Scrollbars appear when visible_length < window_length (i.e., when zoomed in).
    The scrollbars control the ruler's visible_start/stop values.
    """

    def __init__(self, h_ruler: BaseRuler, v_ruler: BaseRuler, color_map: ColorMap, background_image: Optional[Union[str, Path, QPixmap]] = None, parent=None) -> None:
        """Create drawing canvas that shares ruler instances for coordinate transformation."""
        super().__init__(parent)

        # IMPORTANT: Qt may call event() during initialization (e.g. via setMouseTracking),
        # so initialize scrub-zoom state BEFORE any QWidget calls that can trigger events.
        self.scrub_zoom_enabled: bool = True
        self._scrub_zoom_pressed: bool = False
        self._scrub_zooming: bool = False
        self._scrub_press_px: Optional[QPointF] = None
        self._scrub_last_px: Optional[QPointF] = None
        self.scrub_deadzone_px: float = 6.0
        self._scrub_mouse_grabbed: bool = False

        self.h_ruler: BaseRuler = h_ruler
        self.v_ruler: BaseRuler = v_ruler
        self.color_map: ColorMap = color_map
        self.draw_commands: dict[str, Callable[[QPainter], None]] = {}

        # Background image support
        self.background_pixmap: Optional[QPixmap] = None
        self.set_background_image(background_image)

        # Setup viewport for drawing
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.viewport().installEventFilter(self)

        # Configure scrollbars
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Connect scrollbar changes to ruler updates
        self.horizontalScrollBar().valueChanged.connect(self._on_hscroll_changed)
        self.verticalScrollBar().valueChanged.connect(self._on_vscroll_changed)

        # Block recursive updates
        self._updating_scrollbars = False

        # factors for converting float/timedelta to scrollbar int (dynamic to prevent overflow)
        self._h_scroll_factor = 1000.0
        self._v_scroll_factor = 1000.0

    def sizeHint(self) -> QSize:
        return QSize(800, 600)

    def minimumSizeHint(self) -> QSize:
        return QSize(200, 150)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Update ruler lengths based on viewport size
        self.h_ruler.length = self.viewport().width()
        self.v_ruler.length = self.viewport().height()
        self._update_scrollbars()

    def _update_scrollbars(self):
        """Update scrollbar ranges based on ruler window/visible ranges."""
        if self._updating_scrollbars:
            return

        self._updating_scrollbars = True

        # REMOVED: blockSignals(True).
        # QAbstractScrollArea needs signals (rangeChanged) to layout scrollbars properly.
        # Infinite loops are already prevented by the _updating_scrollbars flag above.

        MAX_SCROLL = 2147483647  # Signed 32-bit integer max

        try:
            # Horizontal scrollbar
            w_len = self._to_float(self.h_ruler.window_length)
            v_len = self._to_float(self.h_ruler.visible_length)

            if w_len is not None and v_len is not None and w_len > v_len > 0:
                # Dynamic scaling to avoid OverflowError on large ranges
                raw_max = w_len - v_len
                self._h_scroll_factor = 1000.0
                if (raw_max * self._h_scroll_factor) > MAX_SCROLL:
                    self._h_scroll_factor = MAX_SCROLL / raw_max

                # Calculate scrollbar range and position
                max_val = int(raw_max * self._h_scroll_factor)

                # Calculate offset from window_start
                # FIX: Subtract first (returns number or timedelta), then convert to float
                raw_diff = self.h_ruler.visible_start - self.h_ruler.window_start
                start_offset = self._to_float(raw_diff) or 0.0

                current_val = int(start_offset * self._h_scroll_factor)

                # Page step (visual page size) -- also constrained
                page_step = int(v_len * self._h_scroll_factor)
                if page_step > MAX_SCROLL:
                    page_step = MAX_SCROLL

                self.horizontalScrollBar().setRange(0, max_val)
                self.horizontalScrollBar().setPageStep(page_step)
                self.horizontalScrollBar().setSingleStep(max(1, int(page_step / 10)))
                self.horizontalScrollBar().setValue(current_val)
            else:
                self.horizontalScrollBar().setRange(0, 0)

            # Vertical scrollbar
            w_len_y = self._to_float(self.v_ruler.window_length)
            v_len_y = self._to_float(self.v_ruler.visible_length)

            if w_len_y is not None and v_len_y is not None and w_len_y > v_len_y > 0:
                raw_max_y = w_len_y - v_len_y
                self._v_scroll_factor = 1000.0
                if (raw_max_y * self._v_scroll_factor) > MAX_SCROLL:
                    self._v_scroll_factor = MAX_SCROLL / raw_max_y

                max_val = int(raw_max_y * self._v_scroll_factor)

                # FIX: Subtract first (returns number or timedelta), then convert to float
                raw_diff_y = self.v_ruler.visible_start - self.v_ruler.window_start
                start_offset = self._to_float(raw_diff_y) or 0.0

                current_val = int(start_offset * self._v_scroll_factor)

                page_step = int(v_len_y * self._v_scroll_factor)
                if page_step > MAX_SCROLL:
                    page_step = MAX_SCROLL

                self.verticalScrollBar().setRange(0, max_val)
                self.verticalScrollBar().setPageStep(page_step)
                self.verticalScrollBar().setSingleStep(max(1, int(page_step / 10)))
                self.verticalScrollBar().setValue(current_val)
            else:
                self.verticalScrollBar().setRange(0, 0)

        finally:
            self._updating_scrollbars = False

    def _to_float(self, value) -> Optional[float]:
        """Convert ruler value (int, float, timedelta) to float for scrollbar calcs."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, timedelta):
            return value.total_seconds()
        return None

    def _from_float_offset(self, original_start, offset_float: float):
        """Add float offset to original start value (handles numbers and datetime)."""
        if isinstance(original_start, (int, float)):
            return original_start + offset_float
        # data start is likely datetime if window_length was timedelta
        return original_start + timedelta(seconds=offset_float)

    def _on_hscroll_changed(self, value):
        """Handle horizontal scrollbar changes."""
        if self._updating_scrollbars:
            return

        w_len = self._to_float(self.h_ruler.window_length)
        v_len = self._to_float(self.h_ruler.visible_length)

        if w_len is not None and v_len is not None and w_len > v_len > 0:
            # Use dynamic factor provided by _update_scrollbars
            offset = value / self._h_scroll_factor

            # Use helper to apply offset correctly to either float or datetime types
            new_start = self._from_float_offset(self.h_ruler.window_start, offset)

            # Determine length in original type
            length_val = self.h_ruler.visible_length

            self.h_ruler.visible_start = new_start
            self.h_ruler.visible_stop = new_start + length_val

            self.viewport().update()
            if self.parent() and hasattr(self.parent(), "_notify_linked"):
                self.parent()._notify_linked()

    def _on_vscroll_changed(self, value):
        """Handle vertical scrollbar changes."""
        if self._updating_scrollbars:
            return

        w_len = self._to_float(self.v_ruler.window_length)
        v_len = self._to_float(self.v_ruler.visible_length)

        if w_len is not None and v_len is not None and w_len > v_len > 0:
            # Use dynamic factor provided by _update_scrollbars
            offset = value / self._v_scroll_factor
            new_start = self._from_float_offset(self.v_ruler.window_start, offset)
            length_val = self.v_ruler.visible_length

            self.v_ruler.visible_start = new_start
            self.v_ruler.visible_stop = new_start + length_val

            self.viewport().update()
            if self.parent() and hasattr(self.parent(), "_notify_linked"):
                self.parent()._notify_linked()

    def paintEvent(self, event):
        # Paint on the viewport
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw background color first
        painter.setBrush(QBrush(self.color_map.get_object_color("surface-lower")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.viewport().rect())

        # Draw background image if present (stretched to window bounds, following pan/zoom)
        if self.background_pixmap:
            # Get pixel coordinates of window bounds
            x1_px = self.h_ruler.transform(self.h_ruler.window_start)
            x2_px = self.h_ruler.transform(self.h_ruler.window_stop)
            y1_px = self.v_ruler.transform(self.v_ruler.window_start)
            y2_px = self.v_ruler.transform(self.v_ruler.window_stop)

            # Draw the pixmap stretched to fill the window bounds
            target_rect = QRectF(x1_px, y1_px, x2_px - x1_px, y2_px - y1_px)
            source_rect = QRectF(0, 0, self.background_pixmap.width(), self.background_pixmap.height())
            painter.drawPixmap(target_rect, self.background_pixmap, source_rect)

        # Paint normal commands then overlay commands
        items = list(self.draw_commands.items())
        normal = [cmd for name, cmd in items if not name.startswith("__overlay__")]
        overlay = [cmd for name, cmd in items if name.startswith("__overlay__")]

        # Protect against errors in custom draw commands freezing the UI
        try:
            for command in normal:
                command(painter)
            for command in overlay:
                command(painter)
        except Exception as e:
            print(f"Drawing error: {e}")

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

        # Update scrollbars after zoom/pan
        self._update_scrollbars()

        # repaint self + linked widgets (if any)
        self.viewport().update()
        if self.parent() and hasattr(self.parent(), "_notify_linked"):
            self.parent()._notify_linked()

        event.accept()

    def _end_scrub_zoom(self) -> None:
        """Reset scrub-zoom state; safe to call multiple times."""
        if self._scrub_mouse_grabbed:
            self.viewport().releaseMouse()
            self._scrub_mouse_grabbed = False
        self._scrub_zoom_pressed = False
        self._scrub_zooming = False
        self._scrub_press_px = None
        self._scrub_last_px = None

    def eventFilter(self, source, event):
        """Handle events on the viewport."""
        if source != self.viewport():
            return super().eventFilter(source, event)

        if self.scrub_zoom_enabled:
            et = event.type()

            if (
                et == QEvent.Type.MouseButtonPress
                and getattr(event, "button", None)
                and event.button() == Qt.MouseButton.RightButton
            ):
                self._scrub_zoom_pressed = True
                self._scrub_zooming = False
                self._scrub_press_px = event.position()
                self._scrub_last_px = event.position()
                # Only consume the right-button press (scrub-zoom start)
                event.accept()
                return True

            if et == QEvent.Type.MouseMove and self._scrub_zoom_pressed and self._scrub_last_px is not None:
                cur = event.position()

                # If right button is no longer held, end scrub-zoom and stop consuming.
                if not (event.buttons() & Qt.MouseButton.RightButton):
                    self._end_scrub_zoom()
                    return False

                if not self._scrub_zooming:
                    if self._scrub_press_px is None:
                        self._scrub_press_px = cur
                    dx0 = cur.x() - self._scrub_press_px.x()
                    dy0 = cur.y() - self._scrub_press_px.y()
                    if (dx0 * dx0 + dy0 * dy0) < (self.scrub_deadzone_px * self.scrub_deadzone_px):
                        # Not zooming yet; don't block other interactions
                        return False

                    self._scrub_zooming = True
                    self._scrub_last_px = cur
                    if not self._scrub_mouse_grabbed:
                        self.viewport().grabMouse()
                        self._scrub_mouse_grabbed = True

                    event.accept()
                    return True

                dx = cur.x() - self._scrub_last_px.x()
                dy = cur.y() - self._scrub_last_px.y()
                self._scrub_last_px = cur

                if dx:
                    self.h_ruler.zoom(dx > 0.0, cur.x())
                if dy:
                    self.v_ruler.zoom(dy < 0.0, cur.y())

                self._update_scrollbars()
                self.viewport().update()
                if self.parent() and hasattr(self.parent(), "_notify_linked"):
                    self.parent()._notify_linked()

                event.accept()
                return True

            if et == QEvent.Type.MouseButtonRelease and self._scrub_zoom_pressed:
                released_right = getattr(event, "button", lambda: None)() == Qt.MouseButton.RightButton
                right_still_down = bool(event.buttons() & Qt.MouseButton.RightButton)

                if released_right or not right_still_down:
                    was_zooming = self._scrub_zooming
                    self._end_scrub_zoom()
                    # Only consume the release if we were actually scrub-zooming;
                    # otherwise let other handlers (like drag/drop) see it.
                    if was_zooming:
                        event.accept()
                        return True
                    return False

        return super().eventFilter(source, event)

    # Keep these for compatibility; core handling is in event()
    def mousePressEvent(self, event):
        event.ignore()

    def mouseMoveEvent(self, event):
        event.ignore()

    def mouseReleaseEvent(self, event):
        event.ignore()

    # --- small validation helpers (cheap; only used when executing draw commands) ---
    @staticmethod
    def _check_finite(name: str, v) -> None:
        if isinstance(v, (int, float)):
            if not math.isfinite(v):
                raise ValueError(f"{name}: expected finite number, got {v!r}")
        # datetime/timedelta etc. are fine (TimelineRuler handles them)

    @staticmethod
    def _ensure_list(name: str, obj) -> list:
        if obj is None:
            return []
        if isinstance(obj, list):
            return obj
        # Allow any iterable, but make error messages predictable
        try:
            return list(obj)
        except TypeError as e:
            raise TypeError(f"{name}: expected an iterable, got {type(obj).__name__}") from e

    def add_draw_command(self, name: str, command: Callable[[QPainter], None]) -> None:
        """Register a named drawing function. Replaces existing command with same name."""
        if not callable(command):
            raise TypeError(f"Command '{name}' must be callable")
        self.draw_commands[name] = command
        self.viewport().update()

    def remove_draw_command(self, name: str) -> None:
        """Remove a draw command by name (no-op if missing)."""
        self.draw_commands.pop(name, None)
        self.viewport().update()

    def clear_draw_commands(self) -> None:
        """Clear all registered draw commands."""
        self.draw_commands.clear()
        self.viewport().update()

    def _register_shape(self, name, getter, xform, draw_type, brush=None, pen=None, font=None):
        """Generic helper to register batched shape commands."""
        if not callable(getter):
            raise TypeError(f"Getter for '{name}' must be callable")

        def command(p: QPainter):
            p.setPen(
                pen
                or (
                    Qt.PenStyle.NoPen
                    if draw_type not in ("lines", "points", "text")
                    else Qt.PenStyle.SolidLine
                )
            )
            p.setBrush(
                brush
                or (
                    Qt.BrushStyle.NoBrush
                    if draw_type not in ("lines", "points", "text")
                    else Qt.BrushStyle.SolidPattern
                )
            )
            if font:
                p.setFont(font)

            items = []
            for raw in self._ensure_list(name, getter()):
                try:
                    items.append(xform(*raw))
                except (TypeError, ValueError):
                    continue

            if not items:
                return

            if draw_type == "rects":
                p.drawRects(items)
            elif draw_type == "lines":
                p.drawLines(items)
            elif draw_type == "points":
                p.drawPoints(items)
            elif draw_type == "ellipses":
                for rect in items:
                    p.drawEllipse(rect)
            elif draw_type == "text":
                for pt, txt in items:
                    p.drawText(pt, txt)

        self.add_draw_command(name, command)

    def draw_rects(self, name, get_rects_func, brush=None, pen=None) -> None:
        self._register_shape(name, get_rects_func,
            lambda x, y, w, h: QRectF(self.h_ruler.transform(x), self.v_ruler.transform(y),
                                    self.h_ruler.transform(x+w)-self.h_ruler.transform(x),
                                    self.v_ruler.transform(y+h)-self.v_ruler.transform(y)),
            'rects', brush, pen)

    def draw_lines(self, name, get_lines_func, pen=None) -> None:
        self._register_shape(name, get_lines_func,
            lambda x1, y1, x2, y2: QLineF(self.h_ruler.transform(x1), self.v_ruler.transform(y1),
                                        self.h_ruler.transform(x2), self.v_ruler.transform(y2)),
            'lines', None, pen)

    def draw_ellipses(self, name, get_ellipses_func, brush=None, pen=None) -> None:
        self._register_shape(name, get_ellipses_func,
            lambda x, y, w, h: QRectF(self.h_ruler.transform(x), self.v_ruler.transform(y),
                                    self.h_ruler.transform(x+w)-self.h_ruler.transform(x),
                                    self.v_ruler.transform(y+h)-self.v_ruler.transform(y)),
            'ellipses', brush, pen)

    def draw_texts(self, name, get_texts_func, pen=None, font=None) -> None:
        self._register_shape(name, get_texts_func,
            lambda t, x, y: (QPointF(self.h_ruler.transform(x), self.v_ruler.transform(y)), str(t)),
            'text', None, pen, font)

    def draw_points(self, name, get_points_func, pen=None) -> None:
        self._register_shape(name, get_points_func,
            lambda x, y: QPointF(self.h_ruler.transform(x), self.v_ruler.transform(y)),
            'points', None, pen)

    def set_background_image(self, background_image: Optional[Union[str, Path, QPixmap]]) -> None:
        """Update background image at runtime. Pass None to clear."""
        self.background_pixmap = self._load_background_pixmap(background_image)
        self.viewport().update()

    def _load_background_pixmap(self, background_image: Optional[Union[str, Path, QPixmap]]) -> Optional[QPixmap]:
        """Normalize background input into a QPixmap (or None)."""
        if background_image is None:
            return None

        if isinstance(background_image, QPixmap):
            return background_image if not background_image.isNull() else None

        if isinstance(background_image, (str, Path)):
            pixmap = QPixmap(str(background_image))
            if pixmap.isNull():
                print(f"Warning: Could not load background image from {background_image}")
                return None
            return pixmap

        raise TypeError(f"set_background_image: expected str|Path|QPixmap|None, got {type(background_image).__name__}")
