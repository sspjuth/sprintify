from typing import Tuple
from .base import BaseRuler


class ItemRuler(BaseRuler):
    """
    Ruler for discrete items where each item occupies height = 1 in data space.

    Logical space: [0, item_count] where each item occupies 1 unit.
    Item 0: [0, 1), Item 1: [1, 2), etc.

    Supports smooth zoom and pan with configurable min/max pixels per item.
    """

    def __init__(self, item_count: int, length: float = 1.0, visible_start: float | None = None, visible_stop: float | None = None, reverse: bool = False, default_pixels_per_item: float = 30, min_pixels_per_item: float = 10, max_pixels_per_item: float = 100) -> None:
        """Create ruler for discrete items. Each item occupies 1 unit in data space [0, item_count)."""
        self.item_count = item_count
        self.default_pixels_per_item = default_pixels_per_item
        self.min_pixels_per_item = min_pixels_per_item
        self.max_pixels_per_item = max_pixels_per_item

        # Calculate initial visible range based on default pixels per item
        if visible_start is None and visible_stop is None:
            visible_items = max(1, length / default_pixels_per_item)
            visible_start = 0.0
            visible_stop = min(visible_items, float(item_count))

        super().__init__(
            window_start=0.0,
            window_stop=float(item_count),
            length=length,
            visible_start=visible_start,
            visible_stop=visible_stop,
            reverse=reverse
        )

    def zoom(self, zoom_in: bool, mouse_pos: float) -> None:
        """Zoom while respecting min/max pixels per item constraints."""
        # Calculate current pixels per item
        current_pixels_per_item = self.length / self.visible_length if self.visible_length > 0 else self.default_pixels_per_item

        # Apply zoom
        zoom_factor = 1.2 if zoom_in else 0.9
        new_pixels_per_item = current_pixels_per_item * zoom_factor

        # Clamp to min/max
        new_pixels_per_item = max(self.min_pixels_per_item, min(new_pixels_per_item, self.max_pixels_per_item))

        # Calculate new visible length
        new_visible_length = self.length / new_pixels_per_item
        new_visible_length = min(new_visible_length, self.window_length)

        # Keep value at mouse fixed
        value_at_mouse = self.get_value_at(mouse_pos)
        offset = (value_at_mouse - self.visible_start) / self.visible_length if self.visible_length > 0 else 0.5

        self.visible_start = value_at_mouse - offset * new_visible_length
        self.visible_stop = self.visible_start + new_visible_length

        # Clamp to window bounds
        if self.visible_start < self.window_start:
            self.visible_start = self.window_start
            self.visible_stop = self.visible_start + new_visible_length
        if self.visible_stop > self.window_stop:
            self.visible_stop = self.window_stop
            self.visible_start = self.visible_stop - new_visible_length

        self.visible_length = self.visible_stop - self.visible_start

    def transform_item(self, item_index: int) -> float:
        """Convert item index to pixel position of its top edge."""
        return self.transform(float(item_index))

    def get_item_at(self, y: float) -> int:
        """Get item index at pixel position, clamped to valid range [0, item_count)."""
        value = self.get_value_at(y)
        item_index = int(value)
        return max(0, min(item_index, self.item_count - 1))

    def get_item_bounds(self, item_index: int) -> Tuple[float, float]:
        """Get pixel bounds (start, stop) for an item."""
        y_start = self.transform(float(item_index))
        y_stop = self.transform(float(item_index + 1))
        return (y_start, y_stop)
