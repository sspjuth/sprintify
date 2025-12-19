from typing import Union
from datetime import datetime


class BaseRuler:
    """Base class for all rulers providing coordinate transformation and navigation."""

    def __init__(self, window_start: Union[float, datetime], window_stop: Union[float, datetime], length: float = 1.0, visible_start: Union[float, datetime, None] = None, visible_stop: Union[float, datetime, None] = None, reverse: bool = False) -> None:
        """Create ruler with total data range [window_start, window_stop] and initial visible range."""
        self.window_start = window_start
        self.window_stop = window_stop
        self.visible_start = visible_start if visible_start else window_start
        self.visible_stop = visible_stop if visible_stop else window_stop
        self.window_length = self.window_stop - self.window_start
        self.visible_length = self.visible_stop - self.visible_start
        self.reverse = reverse
        self.length = length

    def transform(self, value: Union[float, datetime]) -> float:
        """Convert data value to pixel position."""
        if self.reverse:
            ratio = (self.visible_stop - value) / self.visible_length
        else:
            ratio = (value - self.visible_start) / self.visible_length
        return ratio * self.length

    def get_value_at(self, x: float) -> Union[float, datetime]:
        """Convert pixel position to data value."""
        normalized = x / self.length
        normalized = max(0.0, min(1.0, normalized))
        if self.reverse:
            return self.visible_stop - normalized * self.visible_length
        return self.visible_start + normalized * self.visible_length

    def get_delta_width(self, delta: float) -> float:
        """Convert pixel delta to data value delta."""
        return self.visible_length * (delta / self.length)

    def zoom(self, zoom_in: bool, mouse_pos: float) -> None:
        """Zoom in/out while keeping the value at mouse_pos fixed in place."""
        value_at_mouse = self.get_value_at(mouse_pos)
        zoom_factor = 1.1 if zoom_in else 0.93
        new_visible_length = self.visible_length / zoom_factor
        if new_visible_length > self.window_length:
            new_visible_length = self.window_length
        offset = (value_at_mouse - self.visible_start) / self.visible_length
        self.visible_start = value_at_mouse - offset * new_visible_length
        self.visible_stop = self.visible_start + new_visible_length
        if self.visible_start < self.window_start:
            self.visible_start = self.window_start
            self.visible_stop = self.visible_start + new_visible_length
        if self.visible_stop > self.window_stop:
            self.visible_stop = self.window_stop
            self.visible_start = self.visible_stop - new_visible_length
        self.visible_length = self.visible_stop - self.visible_start

    def pan(self, delta: float) -> None:
        """Pan viewport by delta pixels. Positive moves right/down, negative moves left/up."""
        value_delta = delta / self.length * self.visible_length
        if delta > 0:
            self.visible_start = max(self.window_start, self.visible_start - value_delta)
        else:
            self.visible_start = min(self.window_stop - self.visible_length, self.visible_start - value_delta)
        self.visible_stop = self.visible_start + self.visible_length

    def get_visible_range_str(self) -> str:
        """Get string representation of current visible range."""
        return f"{self.visible_start} - {self.visible_stop}"