import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Type

from PySide6.QtCore import QEvent, QPointF, Qt, QTimer, QObject
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from sprintify.navigation.colors.modes import ColorMap
from sprintify.navigation.colors.palette import colors
from sprintify.navigation.interaction.interaction_item import InteractiveItem, ItemShape, ItemVisuals, ItemCapabilities
from sprintify.navigation.interaction.selection import InteractionHandler
from sprintify.navigation.navigation_widget import NavigationWidget
from sprintify.navigation.rulers import NumberRuler


# --- Device Classes ---

class SmartDevice:
    width = 1.0
    height = 1.0

    def __init__(self, uid: str, x: float, y: float, connected_to: list = None):
        self.id = uid
        self.x = x
        self.y = y
        self.connected_to: Set[str] = set(connected_to or [])

    def to_dict(self) -> dict:
        return {
            "type": self.__class__.__name__.lower(),
            "x": self.x,
            "y": self.y,
            "connected_to": list(self.connected_to),
        }

    def create_item(self, mode: str) -> InteractiveItem:
        """Create InteractiveItem with appropriate visual properties."""
        item = InteractiveItem(
            data=self,
            x=self.x,
            y=self.y,
            width=self.width,
            height=self.height,
            capabilities=ItemCapabilities(
                can_move=(mode == "edit"),
                can_resize=False
            ),
            visuals=ItemVisuals(
                label=self.id
            )
        )
        # Set initial visuals based on current state
        self.update_item_visuals(item)
        return item

    def update_item_visuals(self, item: InteractiveItem) -> None:
        """Update item visuals based on current device state. Override in subclasses."""
        pass


class Bulb(SmartDevice):
    width = 0.6
    height = 0.6

    def __init__(self, uid: str, x: float, y: float, state: bool = False, **kwargs):
        super().__init__(uid, x, y, **kwargs)
        self.state = state

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["state"] = self.state
        return data

    def create_item(self, mode: str) -> InteractiveItem:
        item = super().create_item(mode)
        item.visuals.shape = ItemShape.ELLIPSE
        item.visuals.label_color = QColor(colors["grey"][900])
        # Set initial visuals
        self.update_item_visuals(item)
        return item

    def update_item_visuals(self, item: InteractiveItem) -> None:
        """Update visuals based on bulb state."""
        if self.state:
            item.visuals.fill_color = QColor(colors["amber"][400])
            item.visuals.stroke_color = QColor(colors["amber"][600])
            item.visuals.glow_color = QColor(255, 238, 88, 120)
            item.visuals.glow_radius = 0.75
        else:
            item.visuals.fill_color = QColor(colors["grey"][200])
            item.visuals.stroke_color = QColor(colors["grey"][500])
            item.visuals.glow_color = None
            item.visuals.glow_radius = 0.0


class Switch(SmartDevice):
    width = 0.8
    height = 0.4

    def __init__(self, uid: str, x: float, y: float, state: bool = False, **kwargs):
        super().__init__(uid, x, y, **kwargs)
        self.state = state

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["state"] = self.state
        return data

    def create_item(self, mode: str) -> InteractiveItem:
        item = super().create_item(mode)
        item.visuals.shape = ItemShape.ROUNDED_RECT
        item.visuals.corner_radius = 5
        item.visuals.label_color = QColor(colors["grey"][50])
        # Set initial visuals
        self.update_item_visuals(item)
        return item

    def update_item_visuals(self, item: InteractiveItem) -> None:
        """Update visuals based on switch state."""
        if self.state:
            item.visuals.fill_color = QColor(colors["green"][400])
            item.visuals.stroke_color = QColor(colors["green"][700])
        else:
            item.visuals.fill_color = QColor(colors["red"][400])
            item.visuals.stroke_color = QColor(colors["red"][700])


class Thermostat(SmartDevice):
    width = 1.0
    height = 0.9

    def __init__(
        self,
        uid: str,
        x: float,
        y: float,
        current_temp: float = 20.0,
        target_temp: float = 21.0,
        **kwargs
    ):
        super().__init__(uid, x, y, **kwargs)
        self.curr = current_temp
        self.target = target_temp

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["current_temp"] = self.curr
        data["target_temp"] = self.target
        return data

    def create_item(self, mode: str) -> InteractiveItem:
        item = super().create_item(mode)
        item.visuals.shape = ItemShape.ROUNDED_RECT
        item.visuals.corner_radius = 8
        item.visuals.fill_color = QColor(colors["blue_grey"][100])
        item.visuals.stroke_color = QColor(colors["blue_grey"][600])
        item.visuals.label_color = QColor(colors["blue_grey"][700])
        # Set initial label
        self.update_item_visuals(item)
        return item

    def update_item_visuals(self, item: InteractiveItem) -> None:
        """Update label to show current temperature."""
        item.visuals.label = f"{self.id}\n{self.curr:.1f}°\n→{self.target:.0f}°"


# --- Handler ---

class DeviceHandler(QObject):
    DEVICE_TYPES: Dict[str, Type[SmartDevice]] = {
        "bulb": Bulb,
        "switch": Switch,
        "thermostat": Thermostat,
    }

    def __init__(self, widget: NavigationWidget):
        super().__init__(widget)
        self.widget = widget
        self.devices: Dict[str, SmartDevice] = {}
        self.mode = "operate"
        self.connect_src: Optional[str] = None
        self.connect_pt: Optional[QPointF] = None
        self.next_ids = {k: 1 for k in self.DEVICE_TYPES}

        # Initialize core interaction handler
        self.interaction = InteractionHandler(
            self.widget.canvas,
            xr=self.widget.top_ruler,
            yr=self.widget.left_ruler,
        )

        # Configure interaction
        self.interaction.on_drop = self._on_devices_dropped

        # Custom draw only for additional features (switch knobs)
        # Remove custom drawing - let standard drawing handle everything
        # We'll add switch knobs as an overlay instead

        # Install event filter for device-specific interactions
        self.widget.canvas.viewport().installEventFilter(self)

        self.timer = QTimer(timeout=self._simulate_physics)
        self.timer.start(1000)

        # Add overlay drawing for switch knobs
        self.widget.canvas.add_draw_command("__overlay__switch_knobs", self._draw_switch_knobs)

        self.update_drawings()

    def add_device(self, type_str: str, x: float = 10, y: float = 7.5):
        cls = self.DEVICE_TYPES[type_str]
        prefix = type_str[0].upper()
        uid = f"{prefix}{self.next_ids[type_str]}"
        self.next_ids[type_str] += 1

        dev = cls(uid, x, y)
        self.devices[uid] = dev

        # Create interactive item with visual properties
        item = dev.create_item(self.mode)
        self.interaction.add_item(item)
        self.update_drawings()

    def remove_device(self, uid: str):
        if uid in self.devices:
            dev = self.devices[uid]
            item = self.interaction.find_item_by_data(dev)
            if item:
                self.interaction.remove_item(item)

            del self.devices[uid]
            for d in self.devices.values():
                d.connected_to.discard(uid)

            # Ensure overlay is redrawn
            self.widget.canvas.viewport().update()
            self.update_drawings()

    def _draw_switch_knobs(self, painter: QPainter):
        """Draw switch knobs as an overlay on top of standard switch rendering."""
        if not self.interaction.xr or not self.interaction.yr:
            return

        # Get visible bounds for culling
        viewport_rect = self.widget.canvas.viewport().rect()
        visible_x_min = self.interaction.xr.get_value_at(0)
        visible_x_max = self.interaction.xr.get_value_at(viewport_rect.width())
        visible_y_min = self.interaction.yr.get_value_at(0)
        visible_y_max = self.interaction.yr.get_value_at(viewport_rect.height())

        for item in self.interaction.items:
            dev = item.data

            # Only process switches that are visible
            if not isinstance(dev, Switch):
                continue

            if (item.x > visible_x_max or
                item.x + item.width < visible_x_min or
                item.y > visible_y_max or
                item.y + item.height < visible_y_min):
                continue

            # Get pixel rectangle for the switch
            rect = item.get_interaction_rect_px(self.interaction.xr, self.interaction.yr)

            # Draw switch knob
            painter.setBrush(QBrush(QColor(colors["grey"][50])))
            painter.setPen(Qt.PenStyle.NoPen)
            offset = 1 if dev.state else -1
            cx = rect.center().x() + (rect.width() * 0.3 * offset)
            radius = rect.width() * 0.12
            painter.drawEllipse(QPointF(cx, rect.center().y()), radius, radius)

    def _on_devices_dropped(self, items: List[InteractiveItem]):
        """Sync new coordinates back to SmartDevice objects after drag."""
        for item in items:
            dev = item.data
            dev.x = item.x
            dev.y = item.y
        self.update_drawings()

    def set_mode(self, mode: str):
        self.mode = mode
        # Update move capability for all items
        can_move = (mode == "edit")
        for item in self.interaction.items:
            item.capabilities.can_move = can_move

        # Clear selection and connection state when switching modes
        self.interaction.clear_selection()
        self.connect_src = None
        self.widget.update()

    def _simulate_physics(self):
        updated = False
        for d in self.devices.values():
            if isinstance(d, Thermostat):
                diff = d.target - d.curr
                if abs(diff) > 0.1:
                    change = 0.3 if diff > 0 else -0.3
                    d.curr += change if abs(diff) > 0.3 else diff
                    # Update the item's visual when temperature changes
                    item = self.interaction.find_item_by_data(d)
                    if item:
                        d.update_item_visuals(item)
                    updated = True

        if updated:
            self.widget.update()

    def eventFilter(self, source, event):
        if source != self.widget.canvas.viewport():
            return super().eventFilter(source, event)

        evt_type = event.type()

        # Let core handle most mouse events, we only intercept specific cases
        if evt_type == QEvent.Type.MouseButtonPress:
            pos = event.position()
            x = self.widget.top_ruler.get_value_at(pos.x())
            y = self.widget.left_ruler.get_value_at(pos.y())

            # Right-click for connections (Edit mode)
            if event.button() == Qt.MouseButton.RightButton and self.mode == "edit":
                item = next((i for i in self.interaction.items if i.contains(x, y)), None)
                if item and not isinstance(item.data, Thermostat):
                    self.connect_src = item.data.id
                    self.connect_pt = pos
                    self.update_drawings()  # Update drag line immediately
                    return True

            # Left-click for operate mode
            elif event.button() == Qt.MouseButton.LeftButton and self.mode == "operate":
                item = next((i for i in self.interaction.items if i.contains(x, y)), None)
                if item:
                    dev = item.data
                    if isinstance(dev, (Switch, Bulb)):
                        dev.state = not dev.state
                        # Update visuals after state change
                        dev.update_item_visuals(item)
                        if isinstance(dev, Switch):
                            self._sync_switch(dev)
                        self.widget.update()
                        return True

        elif evt_type == QEvent.Type.MouseMove and self.connect_src:
            self.connect_pt = event.position()
            self.update_drawings()  # Update drag line as it moves
            return True

        elif evt_type == QEvent.Type.MouseButtonRelease and self.connect_src:
            pos = event.position()
            x = self.widget.top_ruler.get_value_at(pos.x())
            y = self.widget.left_ruler.get_value_at(pos.y())

            target_item = next((i for i in self.interaction.items if i.contains(x, y)), None)
            if target_item and target_item.data.id != self.connect_src:
                self._finish_connection(target_item.data.id)

            self.connect_src = None
            self.connect_pt = None
            self.update_drawings()  # Clear drag line
            return True

        elif evt_type == QEvent.Type.MouseButtonDblClick:
            pos = event.position()
            x = self.widget.top_ruler.get_value_at(pos.x())
            y = self.widget.left_ruler.get_value_at(pos.y())

            item = next((i for i in self.interaction.items if i.contains(x, y)), None)
            if item and isinstance(item.data, Thermostat):
                dev = item.data
                val, ok = QInputDialog.getDouble(
                    self.widget, "Temp", "Target:", dev.target, 15, 30, 1
                )
                if ok:
                    dev.target = val
                    # Update visuals after target change
                    dev.update_item_visuals(item)
                    self.widget.update()
                return True

        elif evt_type == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Delete and self.mode == "edit":
                # Use public API to get selected items
                to_delete = [item.data.id for item in self.interaction.selected_items]
                for uid in to_delete:
                    self.remove_device(uid)
                return True

        return super().eventFilter(source, event)

    def _finish_connection(self, target_id: str):
        src = self.devices[self.connect_src]
        dst = self.devices[target_id]

        if target_id in src.connected_to:
            src.connected_to.discard(target_id)
            dst.connected_to.discard(self.connect_src)
        else:
            src.connected_to.add(target_id)
            dst.connected_to.add(self.connect_src)

        if isinstance(src, Switch):
            self._sync_switch(src)

        self.update_drawings()  # Update connection lines

    def _sync_switch(self, switch: Switch):
        for uid in switch.connected_to:
            dev = self.devices.get(uid)
            if isinstance(dev, Bulb):
                dev.state = switch.state
                # Update bulb visual when synced with switch
                item = self.interaction.find_item_by_data(dev)
                if item:
                    dev.update_item_visuals(item)

    def update_drawings(self):
        # Connection lines
        self.widget.remove_draw_command("conn")

        # Get visible bounds for culling
        viewport_rect = self.widget.canvas.viewport().rect()
        x_min = self.widget.top_ruler.get_value_at(0)
        x_max = self.widget.top_ruler.get_value_at(viewport_rect.width())
        y_min = self.widget.left_ruler.get_value_at(0)
        y_max = self.widget.left_ruler.get_value_at(viewport_rect.height())

        lines = []
        for src_id, src_dev in self.devices.items():
            # Skip if source device is not visible
            if (src_dev.x > x_max or src_dev.x + src_dev.width < x_min or
                src_dev.y > y_max or src_dev.y + src_dev.height < y_min):
                continue

            for dst_id in src_dev.connected_to:
                if src_id < dst_id and dst_id in self.devices:
                    dst_dev = self.devices[dst_id]
                    # Skip if destination is also not visible
                    if (dst_dev.x > x_max or dst_dev.x + dst_dev.width < x_min or
                        dst_dev.y > y_max or dst_dev.y + dst_dev.height < y_min):
                        continue

                    lines.append((
                        src_dev.x + src_dev.width / 2,
                        src_dev.y + src_dev.height / 2,
                        dst_dev.x + dst_dev.width / 2,
                        dst_dev.y + dst_dev.height / 2
                    ))

        if lines:
            self.widget.draw_lines(
                "conn",
                lambda: lines,
                pen=QPen(QColor(colors["grey"][400]), 2, Qt.PenStyle.DashLine),
            )

        # Drag line for connections
        self.widget.remove_draw_command("drag_line")
        if self.connect_src and self.connect_pt:
            src = self.devices[self.connect_src]
            ex = self.widget.top_ruler.get_value_at(self.connect_pt.x())
            ey = self.widget.left_ruler.get_value_at(self.connect_pt.y())
            self.widget.draw_lines(
                "drag_line",
                lambda: [(src.x + src.width / 2, src.y + src.height / 2, ex, ey)],
                pen=QPen(QColor(colors["blue"][500]), 2),
            )

    def to_json(self) -> dict:
        return {
            "devices": {uid: dev.to_dict() for uid, dev in self.devices.items()},
            "next_ids": self.next_ids,
        }

    def from_json(self, data: dict):
        self.devices.clear()
        self.interaction.clear_items()

        dev_map = data.get("devices", {})

        for uid, props_orig in dev_map.items():
            # Make a copy to avoid mutating the original data
            props = dict(props_orig)
            type_str = props.pop("type", None)
            if type_str in self.DEVICE_TYPES:
                try:
                    cls = self.DEVICE_TYPES[type_str]
                    dev = cls(uid, **props)
                    self.devices[uid] = dev

                    # Create item with visual properties
                    item = dev.create_item(self.mode)
                    self.interaction.add_item(item)
                except TypeError:
                    continue

        # Restore connections
        valid_ids = set(self.devices.keys())
        for dev in self.devices.values():
            dev.connected_to &= valid_ids

        self.next_ids = data.get("next_ids", self.next_ids)
        self.update_drawings()
        self.widget.update()


# --- Main Window ---

class SmartHomeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Home")
        self.setMinimumSize(1200, 800)

        assets = Path(__file__).parent / "assets"
        bg_path = assets / "floor_plan.png"
        self.bg_image = str(bg_path) if bg_path.exists() else None

        self.nav = NavigationWidget(
            NumberRuler(0, 20, length=1200),
            NumberRuler(0, 15, length=800),
            ColorMap(False),
            background_image=self.bg_image,
        )
        self.handler = DeviceHandler(self.nav)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        toolbar = QHBoxLayout()
        layout.addLayout(toolbar)
        layout.addWidget(self.nav)

        toolbar.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Operate", "Edit"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        toolbar.addWidget(self.mode_combo)

        btn_help = QPushButton("Help")
        btn_help.clicked.connect(self._show_help)
        toolbar.addWidget(btn_help)
        toolbar.addStretch()

        self.edit_tools = QWidget()
        edit_lyt = QHBoxLayout(self.edit_tools)
        edit_lyt.setContentsMargins(0, 0, 0, 0)

        btn_save = QPushButton("Save")
        btn_save.clicked.connect(self._save)
        edit_lyt.addWidget(btn_save)

        btn_load = QPushButton("Load")
        btn_load.clicked.connect(self._load)
        edit_lyt.addWidget(btn_load)

        for t_str in sorted(self.handler.DEVICE_TYPES.keys()):
            btn = QPushButton(f"+ {t_str.title()}")
            btn.clicked.connect(lambda _, t=t_str: self.handler.add_device(t))
            edit_lyt.addWidget(btn)

        toolbar.addWidget(self.edit_tools)
        self.edit_tools.setVisible(False)

        # Create demo devices
        self._create_demo()

        # Force initial update to ensure everything is drawn
        self.handler.update_drawings()
        self.nav.update()

    def _on_mode_changed(self, idx):
        mode = "edit" if idx == 1 else "operate"
        self.handler.set_mode(mode)
        self.edit_tools.setVisible(idx == 1)
        self.nav.update()

    def _show_help(self):
        QMessageBox.information(
            self,
            "Help",
            "Operate Mode:\n- Click switches/bulbs to toggle\n- Double-click thermostat to adjust\n\n"
            "Edit Mode:\n- Drag devices to move\n- Right-click device + drag to connect\n- Del to remove",
        )

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save", "home.json", "JSON (*.json)")
        if not path:
            return

        try:
            data = {"bg": self.bg_image, "home": self.handler.to_json()}
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load", "", "JSON (*.json)")
        if not path:
            return

        try:
            with open(path, "r") as f:
                data = json.load(f)

            self.bg_image = data.get("bg")
            self.nav.canvas.set_background_image(self.bg_image)

            if "home" in data:
                self.handler.from_json(data["home"])

            # Repaint everything including linked widgets
            self.nav._notify_linked()

        except json.JSONDecodeError:
            QMessageBox.warning(self, "Load Failed", "File is empty or corrupted.")
        except Exception as e:
            QMessageBox.critical(self, "Load Failed", str(e))

    def _create_demo(self):
        # Add multiple devices with different positions to ensure visibility
        self.handler.add_device("bulb", 5, 4)
        self.handler.add_device("bulb", 7, 4)
        self.handler.add_device("switch", 3, 4.5)
        self.handler.add_device("thermostat", 6, 8)

        # Additional devices to make the issue more obvious if they're not showing
        self.handler.add_device("bulb", 10, 6)
        self.handler.add_device("switch", 12, 7)

        if "S1" in self.handler.devices:
            s1 = self.handler.devices["S1"]
            s1.connected_to = {"B1", "B2"}
            if "B1" in self.handler.devices:
                self.handler.devices["B1"].connected_to.add("S1")
            if "B2" in self.handler.devices:
                self.handler.devices["B2"].connected_to.add("S1")

        # Ensure devices are visible
        self.handler.update_drawings()
        self.nav.update()

        # Debug: Print created devices
        print(f"Created {len(self.handler.devices)} devices:")
        for uid, dev in self.handler.devices.items():
            print(f"  - {uid}: {dev.__class__.__name__} at ({dev.x}, {dev.y})")


# Add the missing main execution block
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SmartHomeWindow()
    window.show()
    sys.exit(app.exec())

