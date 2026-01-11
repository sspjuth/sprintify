from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generic, Optional, Set, Tuple, TypeVar, Union
from datetime import datetime, timedelta

from PySide6.QtGui import QColor

T = TypeVar("T")

# Type aliases for coordinate/size values that support both numeric and temporal types
CoordType = Union[float, int, datetime]
SizeType = Union[float, int, timedelta]


class ResizeHandle(Enum):
    """Resize handle positions on an item."""
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


class ItemShape(Enum):
    """Shape for drawing items."""
    RECTANGLE = "rectangle"
    ELLIPSE = "ellipse"
    ROUNDED_RECT = "rounded_rect"


@dataclass
class ItemVisuals:
    """Visual properties for an interactive item.

    All properties are static values that must be explicitly updated when state changes.
    Precedence: item values > handler defaults
    """
    # Shape
    shape: ItemShape = ItemShape.RECTANGLE
    corner_radius: float = 4.0  # For ROUNDED_RECT

    # Colors (static values only)
    fill_color: Optional[QColor] = None
    stroke_color: Optional[QColor] = None
    stroke_width: float = 2.0

    # Label (static value only)
    label: Optional[str] = None
    label_color: Optional[QColor] = None
    label_align: int = 0x0084  # Qt.AlignCenter

    # Effects (static values only)
    glow_color: Optional[QColor] = None
    glow_radius: float = 0.0  # Multiplier of item width

    def update_colors(self, fill: Optional[QColor] = None, stroke: Optional[QColor] = None) -> None:
        """Update fill and/or stroke colors."""
        if fill is not None:
            self.fill_color = fill
        if stroke is not None:
            self.stroke_color = stroke

    def update_glow(self, color: Optional[QColor] = None, radius: float = 0.0) -> None:
        """Update glow effect."""
        self.glow_color = color
        self.glow_radius = radius

    def update_label(self, text: Optional[str] = None, color: Optional[QColor] = None) -> None:
        """Update label text and/or color."""
        if text is not None:
            self.label = text
        if color is not None:
            self.label_color = color


@dataclass
class ItemCapabilities:
    """Interaction capabilities for an item."""
    can_move: bool = True
    can_resize: bool = True
    resize_handles: Set[ResizeHandle] = field(
        default_factory=lambda: {ResizeHandle.LEFT, ResizeHandle.RIGHT}
    )

    # Per-item size constraints (None means use global defaults)
    min_width: Optional[SizeType] = None
    min_height: Optional[SizeType] = None
    max_width: Optional[SizeType] = None
    max_height: Optional[SizeType] = None

@dataclass(eq=False)
class InteractiveItem(Generic[T]):
    """Interactive wrapper for domain objects with position, size and visual properties.

    Args:
        data: Your domain object
        x: Horizontal position (float/int/datetime)
        y: Vertical position (float/int)
        width: Width (float/int/timedelta)
        height: Height (float/int/timedelta)
        visuals: Visual styling configuration
        capabilities: Interaction capabilities (move/resize)
        tooltip: Static tooltip text
        get_tooltip: Dynamic tooltip callback (for data-dependent tooltips only)
        interaction_rect: Custom interaction area as ratios of visual bounds
        sync_from_data: Optional callback to sync item properties from data object
    """
    # Core properties
    data: T
    x: CoordType
    y: Union[float, int]
    width: SizeType
    height: SizeType = 1.0

    # Grouped properties
    visuals: ItemVisuals = field(default_factory=ItemVisuals)
    capabilities: ItemCapabilities = field(default_factory=ItemCapabilities)

    # State
    selected: bool = False

    # Tooltip (static or dynamic for data-dependent content)
    tooltip: Optional[str] = None
    get_tooltip: Optional[Callable[[], str]] = None

    # Custom interaction area (x0, y0, x1, y1) as ratios [0-1] of visual rect
    interaction_rect: Optional[Tuple[float, float, float, float]] = None

    # Model sync callback - maps data state back to item properties
    sync_from_data: Optional[Callable[[T], Tuple]] = None

    def update_visuals_from_state(self, state_mapper: Callable[[T], ItemVisuals]) -> None:
        """Update visuals based on current data state.

        Args:
            state_mapper: Function that maps data object to visual properties
        """
        new_visuals = state_mapper(self.data)
        self.visuals = new_visuals

    def sync_with_data(self) -> None:
        """Synchronize item position/size with data object using sync_from_data callback.

        Returns True if any properties changed.
        """
        if not self.sync_from_data:
            return False

        result = self.sync_from_data(self.data)
        if not result:
            return False

        changed = False
        if len(result) >= 4:
            new_x, new_y, new_width, new_height = result[:4]
            if (self.x != new_x or self.y != new_y or
                self.width != new_width or self.height != new_height):
                self.x, self.y, self.width, self.height = new_x, new_y, new_width, new_height
                changed = True
        elif len(result) >= 2:
            new_x, new_y = result[:2]
            if self.x != new_x or self.y != new_y:
                self.x, self.y = new_x, new_y
                changed = True

        return changed

    def sync_to_data(self, sync_to_data: Optional[Callable[[T, CoordType, Union[float, int], SizeType, SizeType], None]] = None) -> None:
        """Update data object from current item position/size.

        Args:
            sync_to_data: Optional callback (data, x, y, width, height) -> None
                         If not provided, tries common attribute patterns
        """
        if sync_to_data:
            sync_to_data(self.data, self.x, self.y, self.width, self.height)
        else:
            # Try common attribute patterns
            if hasattr(self.data, 'x'):
                self.data.x = self.x
            if hasattr(self.data, 'y'):
                self.data.y = self.y
            if hasattr(self.data, 'width'):
                self.data.width = self.width
            if hasattr(self.data, 'height'):
                self.data.height = self.height

            # Common alternative names
            if hasattr(self.data, 'start'):
                self.data.start = self.x
            if hasattr(self.data, 'duration'):
                self.data.duration = self.width
            if hasattr(self.data, 'employee_id') and isinstance(self.y, (int, float)):
                self.data.employee_id = int(round(self.y))

    def contains(self, x: CoordType, y: Union[float, int]) -> bool:
        """Check if point (x,y) is inside this item's data bounds."""
        return (
            self.x <= x <= self.x + self.width
            and self.y <= y <= self.y + self.height
        )

    def get_resize_handle_at(
        self,
        x: CoordType,
        y: Union[float, int],
        x_tolerance: SizeType = 0.1,
        y_tolerance: Union[float, int] = 0.1,
    ) -> Optional[ResizeHandle]:
        """Get resize handle at position, if any.

        Args:
            x, y: Position in data coordinates
            x_tolerance, y_tolerance: Hit tolerance in data units

        Returns:
            ResizeHandle enum or None
        """
        if not self.capabilities.can_resize or not self.contains(x, y):
            return None

        x_left_dist = abs(x - self.x)
        x_right_dist = abs(x - (self.x + self.width))
        y_top_dist = abs(y - self.y)
        y_bottom_dist = abs(y - (self.y + self.height))

        handles = self.capabilities.resize_handles

        if ResizeHandle.LEFT in handles and x_left_dist < x_tolerance:
            return ResizeHandle.LEFT
        if ResizeHandle.RIGHT in handles and x_right_dist < x_tolerance:
            return ResizeHandle.RIGHT
        if ResizeHandle.TOP in handles and y_top_dist < y_tolerance:
            return ResizeHandle.TOP
        if ResizeHandle.BOTTOM in handles and y_bottom_dist < y_tolerance:
            return ResizeHandle.BOTTOM

        return None

    def get_interaction_rect_px(self, xr, yr) -> "QRectF":
        """Get pixel rectangle for interaction (internal use)."""
        from PySide6.QtCore import QRectF

        x1 = xr.transform(self.x)
        x2 = xr.transform(self.x + self.width)
        y1 = yr.transform(self.y)
        y2 = yr.transform(self.y + self.height)
        rect = QRectF(x1, y1, x2 - x1, y2 - y1).normalized()

        if not self.interaction_rect:
            return rect

        px1, py1, px2, py2 = self.interaction_rect
        return QRectF(
            rect.x() + rect.width() * px1,
            rect.y() + rect.height() * py1,
            rect.width() * (px2 - px1),
            rect.height() * (py2 - py1),
        )
