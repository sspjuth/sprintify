from sprintify.navigation.colors.palette import colors
from PySide6.QtGui import QColor


class ColorMap:

    # Neutral color level map for light & dark mode
    _neutral_levels = {
        "neutral-0": [QColor(255, 255, 255), QColor(0, 0, 0)],
        "neutral-50": [QColor(246, 247, 249), QColor(20, 24, 31)],
        "neutral-100": [QColor(237, 240, 242), QColor(31, 38, 51)],
        "neutral-200": [QColor(225, 229, 234), QColor(39, 49, 63)],
        "neutral-300": [QColor(211, 219, 228), QColor(47, 59, 76)],
        "neutral-400": [QColor(195, 206, 215), QColor(66, 82, 102)],
        "neutral-500": [QColor(176, 190, 203), QColor(98, 112, 132)],
        "neutral-600": [QColor(146, 159, 177), QColor(138, 150, 163)],
        "neutral-700": [QColor(96, 110, 128), QColor(182, 191, 201)],
        "neutral-800": [QColor(64, 75, 90), QColor(211, 216, 223)],
        "neutral-900": [QColor(24, 29, 37), QColor(237, 239, 243)],
        "neutral-1000": [QColor(0, 0, 0), QColor(255, 255, 255)],
    }

    def __init__(self, darkmode=True):
        self.darkmode = darkmode

    def get_object_color(self, name, darkmode=None):
        layout_and_text_colors = {
            "surface-base": ["neutral-0", "neutral-50"],
            "surface-lower": ["neutral-100", "neutral-0"],
            "surface-raised": ["neutral-0", "neutral-100"],
            "surface-subtle": ["neutral-50", "neutral-100"],
            "border": ["neutral-200", "neutral-200"],
            "border-intense": ["neutral-400", "neutral-400"],
            "text-base": ["neutral-900", "neutral-900"],
            "text-secondary": ["neutral-700", "neutral-700"],
            "text-muted": ["neutral-600", "neutral-600"],
        }
        return self._get_neutral_color(layout_and_text_colors[name][self._mode_loc(darkmode)], darkmode)

    def get_saturated_color(self, color, name, darkmode=None):
        saturations = {
            "subtle-tint": [100, 900],
            "light-tint": [200, 800],
            "background": [400, 600],
            "fill": [400, 600],
            "border": [500, 600],
            "line": [500, 600],
            "text-base": [500, 600],
        }
        return colors[color][saturations[name][self._mode_loc(darkmode)]]

    def _get_neutral_color(self, level, darkmode=None):
        return ColorMap._neutral_levels[level][self._mode_loc(darkmode)]

    def _mode_loc(self, darkmode):
        if darkmode is not None:
            darkmode = darkmode
        else:
            darkmode = self.darkmode
        return 1 if darkmode else 0


saturations = {
    "subtle-tint": [100, 900],
    "light-tint": [200, 800],
    "background": [400, 600],
    "border": [500, 600],
    "text": [500, 600],
}

darkmode2 = {
    "weekday": colors["grey"][200],
    "saturday": colors["blue"][500],
    "sunday": colors["deep_orange"][500],
    "line_color": colors["grey"][600],
}

lightmode = {
    "weekday": colors["grey"][700],
    "saturday": colors["blue"][500],
    "sunday": colors["deep_orange"][500],
    "line_color": colors["grey"][300],
}