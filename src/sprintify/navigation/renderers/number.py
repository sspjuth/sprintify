from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPen

import numpy as np
import math

class NumberRulerRenderer:
    def __init__(self, ruler, color_map, orientation='x'):
        self.ruler = ruler
        self.color_map = color_map
        self.orientation = orientation

    def draw_ruler(self, painter, widget_length):
        start = self.ruler.visible_start
        stop = self.ruler.visible_stop
        pixels_per_unit = 100  # Do not use more space than this for a ticker text

        for ticker in self.get_tickers():
            painter.setPen(QPen(self.color_map.get_object_color("text-base"), 1))
            pos = self.ruler.transform(ticker, widget_length)
            if self.orientation == 'x':
                painter.drawText(QRectF(pos - pixels_per_unit / 2, 0, pixels_per_unit, 20), Qt.AlignmentFlag.AlignCenter, self.format_ticker(ticker))
            else:
                painter.save()
                painter.translate(0, 0)
                painter.rotate(-90)
                painter.drawText(QRectF(-pos - pixels_per_unit / 2, 0, pixels_per_unit, 20), Qt.AlignmentFlag.AlignCenter, self.format_ticker(ticker))
                painter.restore()

        for ticker in self.get_tickers():
            pos = self.ruler.transform(ticker, widget_length)
            painter.setPen(QPen(self.color_map.get_object_color("text-base"), 1))
            if self.orientation == 'x':
                painter.drawLine(int(pos), 17, int(pos), 20)
            else:
                painter.drawLine(17, int(pos), 20, int(pos))

    def get_tickers(self):
        range_start = self.ruler.visible_start
        range_stop = self.ruler.visible_stop
        minimum_ticks = 4
        y_range = range_stop - range_start

        if y_range == 0:
            ticks = [range_start]
        else:
            raw_step = y_range / (minimum_ticks - 1)
            magnitude = 10 ** np.floor(np.log10(raw_step))

            if raw_step / magnitude < 2:
                step = magnitude
            elif raw_step / magnitude < 5:
                step = 2 * magnitude
            else:
                step = 5 * magnitude

            ticks = np.arange(np.floor(range_start / step) * step, np.ceil(range_stop / step) * step + step, step)
        return ticks

    def format_ticker(self, ticker):
        if ticker == 0:
            return "0"
        magnitude = int(math.floor(math.log10(abs(ticker)) / 3) * 3)
        suffixes = {
            15: 'P',
            12: 'T',
            9: 'G',
            6: 'M',
            3: 'k',
            0: '',
            -3: 'm',
            -6: 'µ',
            -9: 'n'
        }
        value = ticker / (10 ** magnitude)
        suffix = suffixes.get(magnitude, '')
        return f"{int(value)}{suffix}" if value.is_integer() else f"{value:.6g}{suffix}"