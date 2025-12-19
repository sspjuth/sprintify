from datetime import datetime
from .base import BaseRuler


class TimelineRuler(BaseRuler):
    """Ruler for datetime-based timelines with second-precision mapping."""

    def __init__(self, window_start: datetime, window_stop: datetime, length: float = 1.0, visible_start: datetime | None = None, visible_stop: datetime | None = None, reverse: bool = False) -> None:
        """Create timeline ruler spanning [window_start, window_stop] datetimes."""
        super().__init__(window_start, window_stop, length, visible_start, visible_stop, reverse)
