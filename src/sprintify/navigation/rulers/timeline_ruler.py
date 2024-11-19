from rulers.base_ruler import  BaseRuler
from datetime import datetime, timedelta

class TimelineRuler(BaseRuler):
    def __init__(self, window_start, window_stop, visible_start=None, visible_stop=None, reverse=False):
        super().__init__(window_start, window_stop, visible_start, visible_stop, reverse)

    def transform(self, value, widget_width):
        return (value - self.visible_start).total_seconds() * widget_width / self.visible_length.total_seconds()

    def reverse_transform(self, x, widget_width):
        return self.visible_start + timedelta(seconds=(x / widget_width) * self.visible_length.total_seconds())

    def get_value_delta(self, delta, width):
        return timedelta(seconds=delta / width * (self.visible_stop - self.visible_start).total_seconds())

