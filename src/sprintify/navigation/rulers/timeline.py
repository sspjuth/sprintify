from .base import  BaseRuler
from datetime import datetime, timedelta

class TimelineRuler(BaseRuler):
    def __init__(self, window_start, window_stop, visible_start=None, visible_stop=None, reverse=False):
        super().__init__(window_start, window_stop, visible_start, visible_stop, reverse)

    #def transform(self, value, widget_width):
     #   width = widget_width - self.offset_start - self.offset_end
      #  return self.offset_start + ((value - self.visible_start) / self.visible_length) * width

    #def reverse_transform(self, x, widget_width):
     #   width = widget_width - self.offset_end - self.offset_start
      #  return self.visible_start + self.visible_length * ((x - self.offset_start) / width)


