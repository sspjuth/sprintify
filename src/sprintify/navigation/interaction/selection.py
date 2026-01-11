from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable, Generic, List, Optional, Set, Tuple, TypeVar, Union
from contextlib import contextmanager

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QObject
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QToolTip

from .interaction_item import InteractiveItem, ResizeHandle, ItemShape

T = TypeVar("T")


@dataclass
class SelectionManager(Generic[T]):
    """Manages item selection and rubber-band selection."""

    selected_items: Set[InteractiveItem[T]] = field(default_factory=set)
    banding: bool = False
    band_start: Optional[QPointF] = None
    band_end: Optional[QPointF] = None

    band_color: QColor = field(default_factory=lambda: QColor(80, 120, 255, 40))
    band_border: QColor = field(default_factory=lambda: QColor(180, 200, 255))
    selection_border: QColor = field(default_factory=lambda: QColor(255, 255, 255))

    def clear(self) -> None:
        """Clear all selections."""
        for item in self.selected_items:
            item.selected = False
        self.selected_items.clear()

    def select(self, item: InteractiveItem[T], add: bool = False) -> None:
        """Select an item.

        Args:
            item: Item to select
            add: If True, add to selection. If False, replace selection.
        """
        if not add:
            self.clear()
        self.selected_items.add(item)
        item.selected = True

    def toggle(self, item: InteractiveItem[T]) -> None:
        """Toggle item selection state."""
        if item in self.selected_items:
            self.selected_items.discard(item)
            item.selected = False
        else:
            self.selected_items.add(item)
            item.selected = True

    def start_band(self, pos: QPointF) -> None:
        """Start rubber-band selection at the given position."""
        self.banding = True
        self.band_start = pos
        self.band_end = pos

    def update_band(self, pos: QPointF) -> None:
        """Update the end position of the rubber-band selection."""
        if self.banding:
            self.band_end = pos

    def end_band(self) -> None:
        """Finalize the rubber-band selection."""
        self.banding = False
        self.band_start = None
        self.band_end = None

    def draw(
        self,
        painter: QPainter,
        transform_func: Callable[[InteractiveItem[T]], QRectF],
    ) -> None:
        """Draw selection highlights (using whatever rect the caller provides)."""
        if not self.selected_items:
            return

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(self.selection_border, 2))
        for item in self.selected_items:
            painter.drawRect(transform_func(item))


@dataclass
class DragDropManager(Generic[T]):
    """Manages drag and drop operations (internal use)."""

    dragging: bool = False
    resize_mode: Optional[ResizeHandle] = None
    dragged_items: List[InteractiveItem[T]] = field(default_factory=list)
    original_states: List[Tuple[float, float, float, float]] = field(default_factory=list)

    drag_start_pos: Optional[QPointF] = None

    can_drop: Optional[Callable[[List[InteractiveItem[T]]], bool]] = None
    on_drop: Optional[Callable[[List[InteractiveItem[T]]], None]] = None

    # New: Transform/constrain positions during drag
    on_drag_update: Optional[Callable[[InteractiveItem[T]], Tuple]] = None

    # Snaps for MOVE operations (now support item-aware functions)
    snap_cx_func: Optional[Callable] = None  # Can be (x) -> x or (x, item) -> x
    snap_cy_func: Optional[Callable] = None  # Can be (y) -> y or (y, item) -> y

    # Snaps for RESIZE operations (if None, uses move snaps)
    snap_resize_x_func: Optional[Callable] = None  # Can be (x) -> x or (x, item) -> x
    snap_resize_y_func: Optional[Callable] = None  # Can be (y) -> y or (y, item) -> y

    # Size constraints for resizing (in data units)
    min_width = None
    min_height = None
    max_width = None
    max_height = None

    valid_color: QColor = field(default_factory=lambda: QColor(0, 255, 0, 100))
    invalid_color: QColor = field(default_factory=lambda: QColor(255, 0, 0, 100))

    _last_valid: bool = True

    def _apply_snap(self, snap_func, value, item=None):
        """Apply snap function, handling both simple and item-aware signatures."""
        if not snap_func:
            return value

        # Try item-aware signature first
        import inspect
        try:
            sig = inspect.signature(snap_func)
            if len(sig.parameters) >= 2:
                return snap_func(value, item)
        except:
            pass

        # Fallback to simple signature
        return snap_func(value)

    def start_drag(
        self,
        items: List[InteractiveItem[T]],
        pos: QPointF,
        resize_handle: Optional[ResizeHandle] = None,
    ) -> None:
        """Start a drag operation for the given items."""
        self.dragging = True
        self.resize_mode = resize_handle
        self.dragged_items = items
        self.drag_start_pos = pos
        self.original_states = [(item.x, item.y, item.width, item.height) for item in items]
        self._last_valid = self.can_drop(items) if self.can_drop else True

    def update_drag(self, pos: QPointF, x_ruler, y_ruler) -> None:
        """Update the drag operation with the new mouse position."""
        if not self.dragging or self.drag_start_pos is None:
            return

        current_x = x_ruler.get_value_at(pos.x())
        current_y = y_ruler.get_value_at(pos.y())

        orig_mouse_x = x_ruler.get_value_at(self.drag_start_pos.x())
        orig_mouse_y = y_ruler.get_value_at(self.drag_start_pos.y())

        raw_dx = current_x - orig_mouse_x
        raw_dy = current_y - orig_mouse_y

        for item, (orig_x, orig_y, orig_w, orig_h) in zip(
            self.dragged_items,
            self.original_states,
        ):
            if self.resize_mode:
                resize_snap_x = self.snap_resize_x_func or self.snap_cx_func
                resize_snap_y = self.snap_resize_y_func or self.snap_cy_func

                if self.resize_mode == ResizeHandle.LEFT:
                    new_x = orig_x + raw_dx
                    new_x = self._apply_snap(resize_snap_x, new_x, item)
                    dx = new_x - orig_x
                    self._apply_resize(item, self.resize_mode, dx, 0, orig_x, orig_y, orig_w, orig_h)

                elif self.resize_mode == ResizeHandle.RIGHT:
                    new_x = orig_x + orig_w + raw_dx
                    new_x = self._apply_snap(resize_snap_x, new_x, item)
                    dx = new_x - (orig_x + orig_w)
                    self._apply_resize(item, self.resize_mode, dx, 0, orig_x, orig_y, orig_w, orig_h)

                elif self.resize_mode == ResizeHandle.TOP:
                    new_y = orig_y + raw_dy
                    new_y = self._apply_snap(resize_snap_y, new_y, item)
                    dy = new_y - orig_y
                    self._apply_resize(item, self.resize_mode, 0, dy, orig_x, orig_y, orig_w, orig_h)

                elif self.resize_mode == ResizeHandle.BOTTOM:
                    new_y = orig_y + orig_h + raw_dy
                    new_y = self._apply_snap(resize_snap_y, new_y, item)
                    dy = new_y - (orig_y + orig_h)
                    self._apply_resize(item, self.resize_mode, 0, dy, orig_x, orig_y, orig_w, orig_h)

            else:
                tx = orig_x + raw_dx
                ty = orig_y + raw_dy

                tx = self._apply_snap(self.snap_cx_func, tx, item)
                ty = self._apply_snap(self.snap_cy_func, ty, item)

                item.x = tx
                item.y = ty

            # NEW: Apply drag-time constraints/transforms
            if self.on_drag_update:
                corrected = self.on_drag_update(item)
                if corrected:
                    # Expect (x, y, width, height) or (x, y) tuple
                    if len(corrected) >= 4:
                        item.x, item.y, item.width, item.height = corrected[:4]
                    elif len(corrected) >= 2:
                        item.x, item.y = corrected[:2]

        self._last_valid = self.can_drop(self.dragged_items) if self.can_drop else True

    def _apply_resize(self, item, handle, dx, dy, ox, oy, ow, oh) -> None:
        """Apply resize to an item."""
        # Check item-specific constraints first, then fall back to global
        min_w = item.capabilities.min_width if item.capabilities.min_width is not None else self.min_width
        min_h = item.capabilities.min_height if item.capabilities.min_height is not None else self.min_height
        max_w = item.capabilities.max_width if item.capabilities.max_width is not None else self.max_width
        max_h = item.capabilities.max_height if item.capabilities.max_height is not None else self.max_height

        # Default minimums if nothing specified
        if min_w is None:
            min_w = timedelta(hours=1) if isinstance(ow, timedelta) else 0.1
        if min_h is None:
            min_h = timedelta(hours=1) if isinstance(oh, timedelta) else 0.1

        if handle == ResizeHandle.LEFT:
            new_width = ow - dx
            if new_width < min_w:
                new_width = min_w
                dx = ow - min_w
            elif max_w and new_width > max_w:
                new_width = max_w
                dx = ow - max_w

            item.x = ox + dx
            item.width = new_width

        elif handle == ResizeHandle.RIGHT:
            new_width = ow + dx
            if max_w:
                item.width = min(max_w, max(min_w, new_width))
            else:
                item.width = max(min_w, new_width)

        elif handle == ResizeHandle.TOP:
            new_height = oh - dy
            if new_height < min_h:
                new_height = min_h
                dy = oh - min_h
            elif max_h and new_height > max_h:
                new_height = max_h
                dy = oh - max_h

            item.y = oy + dy
            item.height = new_height

        elif handle == ResizeHandle.BOTTOM:
            new_height = oh + dy
            if max_h:
                item.height = min(max_h, max(min_h, new_height))
            else:
                item.height = max(min_h, new_height)

    def end_drag(self) -> bool:
        """Finalize the drag operation and drop items."""
        if not self.dragging:
            return False

        success = True
        items_to_drop = list(self.dragged_items)

        if self.can_drop and not self.can_drop(items_to_drop):
            for item, state in zip(self.dragged_items, self.original_states):
                item.x, item.y, item.width, item.height = state
            success = False
        else:
            # Clear drag state BEFORE calling on_drop
            self.dragging = False
            self.dragged_items.clear()
            self.original_states.clear()
            self.drag_start_pos = None
            self.resize_mode = None

            if self.on_drop:
                self.on_drop(items_to_drop)
            return success

        self.dragging = False
        self.dragged_items.clear()
        self.original_states.clear()
        self.drag_start_pos = None
        self.resize_mode = None
        return success

    def draw_ghosts(
        self,
        painter: QPainter,
        transform_func: Callable[[InteractiveItem[T]], QRectF],
    ) -> None:
        """Draw semi-transparent ghosts of items being dragged."""
        if not self.dragging or not self.dragged_items:
            return

        valid = self._last_valid

        for item in self.dragged_items:
            rect = transform_func(item)

            # Get the cached color from the item (set during normal drawing)
            fill = getattr(item, "_cached_brush_color", None)
            if isinstance(fill, QColor):
                fill = QColor(fill)  # Make a copy
                fill.setAlpha(100)  # Semi-transparent
            else:
                # Fallback if no cached color
                fill = QColor(160, 160, 160, 100)

            # Tint based on validity
            if not valid:
                # Mix with red for invalid
                fill.setRed(min(255, fill.red() + 100))
                fill.setAlpha(120)
            else:
                # Mix with green for valid
                fill.setGreen(min(255, fill.green() + 50))

            painter.setBrush(QBrush(fill))

            # Outline indicates validity
            outline = QColor(0, 255, 0, 200) if valid else QColor(255, 0, 0, 200)
            painter.setPen(QPen(outline, 2, Qt.PenStyle.DashLine))

            painter.drawRoundedRect(rect, 4, 4)


class InteractionHandler(QObject, Generic[T]):
    """Handles mouse interaction for draggable/resizable items.

    Example:
        handler = InteractionHandler(canvas, xr=h_ruler, yr=v_ruler)

        item = InteractiveItem(
            data=my_object,
            x=10, y=20, width=30, height=15
        )
        handler.add_item(item)

        # Or add multiple items at once
        handler.add_items([item1, item2, item3])

        # Or use batch context for many operations without redraws
        with handler.batch_update():
            for i in range(100):
                handler.add_item(create_item(i))

        handler.on_drop = lambda items: print(f"Dropped {len(items)}")
        handler.set_snap_strategy(snap_x=lambda x: round(x / 10) * 10)
    """

    def __init__(self, canvas_widget, xr=None, yr=None):
        """Initialize interaction handler.

        Args:
            canvas_widget: QWidget to handle interactions on
            xr: Horizontal ruler for coordinate transformation
            yr: Vertical ruler for coordinate transformation
        """
        super().__init__(canvas_widget)
        self.canvas = canvas_widget
        self.items: List[InteractiveItem[T]] = []

        # Internal managers (not part of public API)
        self._selection = SelectionManager[T]()
        self._drag_drop = DragDropManager[T]()

        canvas_widget.viewport().installEventFilter(self)
        canvas_widget.setMouseTracking(True)

        self._press_pos: Optional[QPointF] = None
        self._press_item: Optional[InteractiveItem[T]] = None
        self._press_data_coords = (None, None)
        self._hover_item: Optional[InteractiveItem[T]] = None
        self._hover_handle: Optional[ResizeHandle] = None
        self._last_tooltip_item: Optional[InteractiveItem[T]] = None

        # Batch update state
        self._batch_depth: int = 0

        self.xr = xr
        self.yr = yr

        # Global visual strategies (fallbacks when item doesn't specify)
        self.item_corner_radius: float = 4
        self.get_item_color: Optional[Callable[[InteractiveItem[T]], QColor]] = None
        self.get_item_label: Optional[Callable[[InteractiveItem[T]], str]] = None
        self.get_item_tooltip: Optional[Callable[[InteractiveItem[T]], str]] = None

        # Custom drawing (replaces standard drawing)
        self.draw_custom_item: Optional[
            Callable[[QPainter, InteractiveItem[T], QRectF], None]
        ] = None

        self.show_tooltips: bool = True

        if canvas_widget and hasattr(canvas_widget, "add_draw_command"):
            canvas_widget.add_draw_command("interaction_items", self._draw_items)
            canvas_widget.add_draw_command("__overlay__interaction", self._draw_overlay)

    # --- Public Selection API ---

    @property
    def selection(self) -> SelectionManager[T]:
        """Get selection manager (for advanced use)."""
        return self._selection

    @property
    def selected_items(self) -> Set[InteractiveItem[T]]:
        """Get currently selected items."""
        return self._selection.selected_items

    def clear_selection(self) -> None:
        """Clear all selections."""
        self._selection.clear()
        if self.canvas:
            self.canvas.viewport().update()

    def is_item_hovered(self, item: InteractiveItem[T]) -> bool:
        """Check if an item is currently hovered.

        Args:
            item: Item to check

        Returns:
            True if the item is currently under the mouse cursor
        """
        return self._hover_item == item

    def get_hover_item(self) -> Optional[InteractiveItem[T]]:
        """Get the currently hovered item.

        Returns:
            The item under the mouse cursor, or None
        """
        return self._hover_item

    # --- Public Drag/Drop Configuration API ---

    @property
    def on_drop(self) -> Optional[Callable[[List[InteractiveItem[T]]], None]]:
        """Callback when items are dropped. Signature: (items: List[InteractiveItem]) -> None"""
        return self._drag_drop.on_drop

    @on_drop.setter
    def on_drop(self, callback: Optional[Callable[[List[InteractiveItem[T]]], None]]) -> None:
        self._drag_drop.on_drop = callback

    @property
    def can_drop(self) -> Optional[Callable[[List[InteractiveItem[T]]], bool]]:
        """Validation callback. Return False to reject drop. Signature: (items: List[InteractiveItem]) -> bool"""
        return self._drag_drop.can_drop

    @can_drop.setter
    def can_drop(self, callback: Optional[Callable[[List[InteractiveItem[T]]], bool]]) -> None:
        self._drag_drop.can_drop = callback

    @property
    def on_drag_update(self) -> Optional[Callable[[InteractiveItem[T]], Tuple]]:
        """Constraint hook during drag. Return (x, y) or (x, y, width, height) to override position."""
        return self._drag_drop.on_drag_update

    @on_drag_update.setter
    def on_drag_update(self, callback: Optional[Callable[[InteractiveItem[T]], Tuple]]) -> None:
        self._drag_drop.on_drag_update = callback

    def set_snap_strategy(
        self,
        snap_x: Optional[Callable] = None,
        snap_y: Optional[Callable] = None,
        snap_resize_x: Optional[Callable] = None,
        snap_resize_y: Optional[Callable] = None
    ) -> None:
        """Configure snapping for move/resize.

        Args:
            snap_x: Snap function for x coordinate. Can be:
                    - (x: float) -> float  (simple)
                    - (x: float, item: InteractiveItem) -> float  (item-aware)
            snap_y: Snap function for y coordinate. Same signatures as snap_x
            snap_resize_x: Snap for resize (defaults to snap_x)
            snap_resize_y: Snap for resize (defaults to snap_y)

        Example:
            # Simple snapping
            handler.set_snap_strategy(
                snap_x=lambda x: round(x / 10) * 10
            )

            # Item-aware snapping
            handler.set_snap_strategy(
                snap_x=lambda x, item: item.data.original_x if isinstance(item.data, FixedItem) else x,
                snap_y=lambda y, item: round(y) if item.data.can_move_vertically else item.data.original_y
            )
        """
        self._drag_drop.snap_cx_func = snap_x
        self._drag_drop.snap_cy_func = snap_y
        self._drag_drop.snap_resize_x_func = snap_resize_x
        self._drag_drop.snap_resize_y_func = snap_resize_y

    def set_size_constraints(
        self,
        min_width=None,
        min_height=None,
        max_width=None,
        max_height=None
    ) -> None:
        """Set min/max size constraints for resizing.

        Args:
            min_width: Minimum width in data units
            min_height: Minimum height in data units
            max_width: Maximum width in data units
            max_height: Maximum height in data units
        """
        self._drag_drop.min_width = min_width
        self._drag_drop.min_height = min_height
        self._drag_drop.max_width = max_width
        self._drag_drop.max_height = max_height

    # --- Public Item Management API ---

    @contextmanager
    def batch_update(self):
        """Context manager for batch operations without intermediate redraws.

        Example:
            with handler.batch_update():
                handler.clear_items()
                for item in new_items:
                    handler.add_item(item)
            # Single redraw happens here
        """
        self._batch_depth += 1
        try:
            yield
        finally:
            self._batch_depth -= 1
            if self._batch_depth == 0 and self.canvas:
                self.canvas.viewport().update()

    def add_item(self, item: InteractiveItem[T]) -> InteractiveItem[T]:
        """Add an interactive item to manage.

        Returns:
            The added item (for chaining)
        """
        self.items.append(item)
        if self._batch_depth == 0 and self.canvas:
            self.canvas.viewport().update()
        return item

    def add_items(self, items: Union[List[InteractiveItem[T]], InteractiveItem[T]]) -> List[InteractiveItem[T]]:
        """Add one or more interactive items to manage.

        Args:
            items: Single item or list of items to add

        Returns:
            List of added items
        """
        if not isinstance(items, list):
            items = [items]

        with self.batch_update():
            for item in items:
                self.items.append(item)

        return items

    def remove_item(self, item: InteractiveItem[T]) -> None:
        """Remove an item from management."""
        if item in self.items:
            self.items.remove(item)
            self._selection.selected_items.discard(item)
            if item.selected:
                item.selected = False
            if self._batch_depth == 0 and self.canvas:
                self.canvas.viewport().update()

    def remove_items(self, items: Union[List[InteractiveItem[T]], InteractiveItem[T]]) -> None:
        """Remove one or more items from management.

        Args:
            items: Single item or list of items to remove
        """
        if not isinstance(items, list):
            items = [items]

        with self.batch_update():
            for item in items:
                if item in self.items:
                    self.items.remove(item)
                    self._selection.selected_items.discard(item)
                    if item.selected:
                        item.selected = False

    def clear_items(self) -> None:
        """Remove all items."""
        self._selection.clear()
        self.items.clear()
        if self._batch_depth == 0 and self.canvas:
            self.canvas.viewport().update()

    def find_item_by_data(self, data: T) -> Optional[InteractiveItem[T]]:
        """Find item containing the given data object.

        Args:
            data: The domain object to search for

        Returns:
            InteractiveItem wrapping the data, or None
        """
        for item in self.items:
            if item.data is data:
                return item
        return None

    # --- Internal Drawing Methods ---

    def _draw_items(self, p: QPainter) -> None:
        if not self.xr or not self.yr:
            return

        # Get visible bounds in data coordinates for culling
        viewport_rect = self.canvas.viewport().rect()
        visible_x_min = self.xr.get_value_at(0)
        visible_x_max = self.xr.get_value_at(viewport_rect.width())
        visible_y_min = self.yr.get_value_at(0)
        visible_y_max = self.yr.get_value_at(viewport_rect.height())

        dragged_set = set(self._drag_drop.dragged_items) if self._drag_drop.dragging else set()

        # Only process items that are potentially visible
        for item in self.items:
            if item in dragged_set:
                continue

            # Quick culling check - skip items completely outside viewport
            if (item.x > visible_x_max or
                item.x + item.width < visible_x_min or
                item.y > visible_y_max or
                item.y + item.height < visible_y_min):
                continue

            # Get visual rectangle (may differ from interaction rectangle)
            rect = item.get_interaction_rect_px(self.xr, self.yr)

            # Check if hover or selected for highlight
            highlighted = (self._hover_item == item) or item.selected

            if self.draw_custom_item:
                self.draw_custom_item(p, item, rect)
            else:
                self._draw_standard_item(p, item, rect, highlighted)

    def _draw_standard_item(self, p: QPainter, item: InteractiveItem[T], rect: QRectF, highlighted: bool) -> None:
        """Standard item drawing using static visual properties."""
        visuals = item.visuals

        # Draw glow effect if specified (static values only)
        if visuals.glow_color and visuals.glow_radius > 0:
            gradient = QRadialGradient(rect.center(), rect.width() * visuals.glow_radius)
            gc = QColor(visuals.glow_color)
            gc.setAlpha(120)
            gradient.setColorAt(0, gc)
            gc.setAlpha(0)
            gradient.setColorAt(1, gc)
            p.setBrush(QBrush(gradient))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(rect.center(), rect.width() * visuals.glow_radius, rect.height() * visuals.glow_radius)

        # Determine fill color (hierarchy: item > strategy > default)
        fill = visuals.fill_color
        if not fill and self.get_item_color:
            fill = self.get_item_color(item)
        if not fill:
            fill = QColor(100, 150, 200)

        # Cache for ghost rendering
        setattr(item, "_cached_brush_color", fill)

        # Determine stroke
        stroke = visuals.stroke_color
        stroke_width = 3 if highlighted else visuals.stroke_width

        if highlighted and not stroke:
            stroke = QColor(80, 120, 255)

        # Set painter state
        p.setBrush(QBrush(fill))
        if stroke:
            p.setPen(QPen(stroke, stroke_width))
        else:
            p.setPen(Qt.PenStyle.NoPen)

        # Draw shape
        if visuals.shape == ItemShape.ELLIPSE:
            p.drawEllipse(rect)
        elif visuals.shape == ItemShape.ROUNDED_RECT:
            radius = visuals.corner_radius if visuals.corner_radius else self.item_corner_radius
            p.drawRoundedRect(rect, radius, radius)
        else:  # RECTANGLE
            if self.item_corner_radius > 0:
                p.drawRoundedRect(rect, self.item_corner_radius, self.item_corner_radius)
            else:
                p.drawRect(rect)

        # Draw label (hierarchy: item > strategy > none)
        label = visuals.label
        if not label and self.get_item_label:
            label = self.get_item_label(item)

        if label:
            label_color = visuals.label_color or Qt.GlobalColor.white
            p.setPen(QPen(label_color))
            align = visuals.label_align if visuals.label_align else Qt.AlignmentFlag.AlignCenter

            # Only draw if it fits inside the item rect (avoid clutter at scale)
            fm = p.fontMetrics()
            text = str(label)
            pad = 4
            if (rect.width() - 2 * pad) >= fm.horizontalAdvance(text) and (rect.height() - 2 * pad) >= fm.height():
                p.drawText(rect.adjusted(pad, pad, -pad, -pad), align, text)

    def _draw_overlay(self, p: QPainter) -> None:
        if not self.xr or not self.yr:
            return

        def xform(item: InteractiveItem[T]) -> QRectF:
            return item.get_interaction_rect_px(self.xr, self.yr)

        if self._selection.banding and self._selection.band_start and self._selection.band_end:
            p.setPen(QPen(self._selection.band_border, 1))
            p.setBrush(QBrush(self._selection.band_color))
            p.drawRect(QRectF(self._selection.band_start, self._selection.band_end).normalized())

        self._selection.draw(p, xform)
        self._drag_drop.draw_ghosts(p, xform)

    def eventFilter(self, src, evt) -> bool:
        # Guard against already deleted widgets during shutdown
        try:
            if not self.canvas or not self.canvas.viewport():
                return False
            if src != self.canvas.viewport():
                return super().eventFilter(src, evt)
        except RuntimeError:
            return False

        et = evt.type()

        # Handle mouse events for interaction
        if et == QEvent.Type.MouseButtonPress and evt.button() == Qt.MouseButton.LeftButton:
            return self._press(evt)
        elif et == QEvent.Type.MouseMove:
            return self._move(evt)
        elif et == QEvent.Type.MouseButtonRelease and evt.button() == Qt.MouseButton.LeftButton:
            return self._release(evt)

        return super().eventFilter(src, evt)

    def _press(self, evt) -> bool:
        if evt.button() != Qt.MouseButton.LeftButton: return False
        if not self.xr or not self.yr: return False

        pos = evt.position()
        x, y = self.xr.get_value_at(pos.x()), self.yr.get_value_at(pos.y())
        self._press_data_coords = (x, y)  # Store data coordinates in native types

        self._press_item = next((i for i in self.items if i.contains(x, y)), None)

        if self._press_item:
            if not self._press_item.selected and not (evt.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self.selection.clear()
            self.selection.select(self._press_item, add=True)
        else:
            # Start rubber band selection when clicking in empty space
            # (with or without Shift modifier)
            self.selection.start_band(pos)
            if not (evt.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self.selection.clear()

        self._press_pos = pos
        self.canvas.viewport().update()  # Update viewport to show selection changes
        return True

    def _move(self, evt) -> bool:
        if not self.xr or not self.yr:
            return False

        pos = evt.position()

        # If we're dragging, handle drag update
        if self._drag_drop.dragging:
            self._drag_drop.update_drag(pos, self.xr, self.yr)
            self.canvas.viewport().update()
            return True

        # Rubber band selection (only when not dragging)
        if self._selection.banding:
            self._selection.update_band(pos)
            # Only update items in the band area
            self._update_band()
            self.canvas.viewport().update()
            return True

        # Check for drag initiation
        if self._press_pos and not self._drag_drop.dragging and not self._selection.banding:
            if (pos - self._press_pos).manhattanLength() > 5:
                x, y = self._press_data_coords if self._press_data_coords else (0, 0)

                x_tolerance = self.xr.get_delta_width(8)
                y_tolerance = self.yr.get_delta_width(8)

                handle = None
                if self._press_item:
                    handle = self._press_item.get_resize_handle_at(x, y, x_tolerance, y_tolerance)

                items = list(self.selection.selected_items)
                if items:
                    self._drag_drop.start_drag(items, self._press_pos, handle)
                    # End banding if it was active
                    if self._selection.banding:
                        self._selection.end_band()
                    self.canvas.viewport().update()
                    return True

        # Update hover state when not dragging or banding
        if not self._drag_drop.dragging and not self._selection.banding:
            self._update_hover_state(pos)

        return False

    def _release(self, evt) -> bool:
        if evt.button() != Qt.MouseButton.LeftButton:
            return False

        was_dragging = self._drag_drop.dragging
        was_banding = self._selection.banding

        # End drag operation FIRST
        if self._drag_drop.dragging:
            success = self._drag_drop.end_drag()
            if success:
                self.selection.clear()

            # Reset cursor
            self.canvas.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            self._hover_item = None
            self._hover_handle = None

        # End rubber band selection
        if self._selection.banding:
            self._selection.end_band()

        # Handle single click selection only if we weren't dragging or banding
        if not was_dragging and not was_banding:
            if self._press_item and not (evt.modifiers() & Qt.KeyboardModifier.ControlModifier):
                if self._press_pos and (evt.position() - self._press_pos).manhattanLength() < 5:
                    self.selection.select(self._press_item, add=False)

        # Clear press state
        self._press_pos = None
        self._press_item = None
        self._press_data_coords = None

        # Update hover state
        if not self._drag_drop.dragging:  # Double-check drag has ended
            self._update_hover_state(evt.position())

        self.canvas.viewport().update()
        return True

    def _update_band(self):
        """Update selection based on current rubber band."""
        if not self._selection.banding or not self.xr or not self.yr:
            return
        if not self._selection.band_start or not self._selection.band_end:
            return

        # Get band bounds in data coordinates
        x1 = self.xr.get_value_at(self._selection.band_start.x())
        x2 = self.xr.get_value_at(self._selection.band_end.x())
        y1 = self.yr.get_value_at(self._selection.band_start.y())
        y2 = self.yr.get_value_at(self._selection.band_end.y())

        # Normalize bounds
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1

        # Clear previous band selection (but keep explicitly selected items)
        # Only clear items that were selected by banding, not by clicking
        for item in list(self._selection.selected_items):
            # Check if item intersects band
            if not (item.x > x2 or
                    item.x + item.width < x1 or
                    item.y > y2 or
                    item.y + item.height < y1):
                continue
            else:
                # Item is outside band, deselect it if it was selected by band
                self._selection.selected_items.discard(item)
                item.selected = False

        # Select items that intersect the band
        for item in self.items:
            # Quick bounds check
            if (item.x > x2 or
                item.x + item.width < x1 or
                item.y > y2 or
                item.y + item.height < y1):
                continue

            # Item intersects band
            self._selection.select(item, add=True)

    def _update_hover_state(self, pos: QPointF):
        """Update hover state, cursor, and tooltip based on mouse position."""
        if not self.xr or not self.yr:
            return

        x, y = self.xr.get_value_at(pos.x()), self.yr.get_value_at(pos.y())

        # Find item under cursor
        new_hover_item = next((i for i in self.items if i.contains(x, y)), None)

        # Check for resize handle if hovering over an item
        new_hover_handle = None
        if new_hover_item and new_hover_item.capabilities.can_resize:
            x_tolerance = self.xr.get_delta_width(8)
            y_tolerance = self.yr.get_delta_width(8)
            new_hover_handle = new_hover_item.get_resize_handle_at(x, y, x_tolerance, y_tolerance)

        # Update cursor if hover state changed
        if new_hover_item != self._hover_item or new_hover_handle != self._hover_handle:
            self._hover_item = new_hover_item
            self._hover_handle = new_hover_handle

            # Set appropriate cursor
            if new_hover_handle:
                # Resize cursors based on handle type
                if new_hover_handle in (ResizeHandle.LEFT, ResizeHandle.RIGHT):
                    self.canvas.viewport().setCursor(Qt.CursorShape.SizeHorCursor)
                elif new_hover_handle in (ResizeHandle.TOP, ResizeHandle.BOTTOM):
                    self.canvas.viewport().setCursor(Qt.CursorShape.SizeVerCursor)
                elif new_hover_handle == ResizeHandle.TOP_LEFT:
                    self.canvas.viewport().setCursor(Qt.CursorShape.SizeFDiagCursor)
                elif new_hover_handle == ResizeHandle.TOP_RIGHT:
                    self.canvas.viewport().setCursor(Qt.CursorShape.SizeBDiagCursor)
                elif new_hover_handle == ResizeHandle.BOTTOM_LEFT:
                    self.canvas.viewport().setCursor(Qt.CursorShape.SizeBDiagCursor)
                elif new_hover_handle == ResizeHandle.BOTTOM_RIGHT:
                    self.canvas.viewport().setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif new_hover_item and new_hover_item.capabilities.can_move:
                # Move cursor for moveable items
                self.canvas.viewport().setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                # Default cursor
                self.canvas.viewport().setCursor(Qt.CursorShape.ArrowCursor)

        # Update tooltip if item changed (hierarchy: callback > static > strategy)
        if self.show_tooltips and new_hover_item != self._last_tooltip_item:
            self._last_tooltip_item = new_hover_item
            if new_hover_item:
                # Get tooltip text
                tooltip = None
                if new_hover_item.get_tooltip:
                    tooltip = new_hover_item.get_tooltip()
                elif new_hover_item.tooltip:
                    tooltip = new_hover_item.tooltip
                elif self.get_item_tooltip:
                    tooltip = self.get_item_tooltip(new_hover_item)

                if tooltip:
                    # Get global position for tooltip
                    global_pos = self.canvas.viewport().mapToGlobal(pos.toPoint())
                    QToolTip.showText(global_pos, tooltip, self.canvas.viewport())
                else:
                    QToolTip.hideText()
            else:
                QToolTip.hideText()
