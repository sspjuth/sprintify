from .base import BaseRuler


class NumberRuler(BaseRuler):
    """Ruler for numeric ranges with linear mapping."""

    def __init__(self, window_start: float, window_stop: float, length: float = 1.0, visible_start: float | None = None, visible_stop: float | None = None, reverse: bool = False) -> None:
        """Create numeric ruler spanning [window_start, window_stop]."""
        super().__init__(window_start, window_stop, length, visible_start, visible_stop, reverse)
