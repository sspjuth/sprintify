from .base import BaseRuler


class NumberRuler(BaseRuler):
    def __init__(self, window_start, window_stop, visible_start=None, visible_stop=None, reverse=False):
        super().__init__(window_start, window_stop, visible_start, visible_stop, reverse)