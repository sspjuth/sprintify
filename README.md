# Sprintify Navigation

A navigation widget based on PySide6. So draw graphs and other timebased data and let your user navigate your data with keyboard or mouse.

## Installation

To install the package, run:

```sh
pip install sprintify-navigation
```

## Usage

```python
from sprintify.navigation import NavigationWidget, ColorMap, TimelineRuler, NumberRuler
from PySide6.QtWidgets import QMainWindow, QApplication
from datetime import datetime
import sys

class SmartHomeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SmartHome Navigation")
        self.color_map = ColorMap(darkmode=True)
        self.top_ruler = TimelineRuler(datetime(2024, 4, 1), datetime(2024, 5, 1))
        self.left_ruler = NumberRuler(0, 50000, reverse=True)
        self.ruler_widget = NavigationWidget(self.top_ruler, self.left_ruler, self.color_map, parent=self)
        self.setCentralWidget(self.ruler_widget)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SmartHomeWindow()
    window.show()
    sys.exit(app.exec())
```

## Development
Still a private project.

## License
This project is licensed under the MIT License - see the LICENSE file for details.