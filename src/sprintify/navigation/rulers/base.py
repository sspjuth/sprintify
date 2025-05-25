class BaseRuler:
    def __init__(self, window_start, window_stop, visible_start=None, visible_stop=None, reverse=False):
        self.offset_start = 20
        self.offset_end = 0
        self.window_start = window_start
        self.window_stop = window_stop
        self.visible_start = visible_start if visible_start else window_start
        self.visible_stop = visible_stop if visible_stop else window_stop
        self.window_length = self.window_stop - self.window_start
        self.visible_length = self.visible_stop - self.visible_start
        self.reverse = reverse

    def transform(self, value, widget_length):
        width = widget_length - self.offset_start - self.offset_end
        if self.reverse:
            return self.offset_start + ((self.visible_stop - value)  / self.visible_length) * width
        else:
            return self.offset_start + ((value - self.visible_start) / self.visible_length) * width

    def get_value_at(self, x, widget_length):
        if self.reverse:
            return self.visible_start +  self.visible_length * ((widget_length - x) / widget_length)
        else:
            return self.visible_start + self.visible_length * (x / widget_length)

    def get_delta_width(self, delta, widget_width):
        width = widget_width - self.offset_start - self.offset_end
        return self.visible_length * (delta / width)

    def zoom(self, zoom_in, mouse_pos, widget_length):
        value_at_mouse = self.get_value_at(mouse_pos, widget_length)
        zoom_factor = 1.2 if zoom_in else 0.9

        new_visible_length = min(self.window_length, (self.visible_stop - self.visible_start) * zoom_factor)
        if new_visible_length >= self.window_length:
            self.visible_start = self.window_start
            self.visible_stop = self.window_stop
        else:
            self.visible_start = max(self.window_start, value_at_mouse - (value_at_mouse - self.visible_start) * zoom_factor)
            self.visible_stop = min(self.window_stop, self.visible_start + new_visible_length)
        self.visible_length = self.visible_stop - self.visible_start

    def pan(self, delta, width):
        value_delta = delta / width * (self.visible_stop - self.visible_start)
        if delta > 0:
            self.visible_start = max(self.window_start, self.visible_start - value_delta)
        else:
            self.visible_start = min(self.window_stop - self.visible_length, self.visible_start - value_delta)
        self.visible_stop = self.visible_start + self.visible_length

    def get_visible_range_str(self):
        return f"{self.visible_start} - {self.visible_stop}"