"""
Large-scale employee scheduling application.

Demonstrates:
- 1000 employees with smooth scrolling/zooming
- Two types of items with different movement rules:
  - Vacations: Personal (can't change employee), flexible timing
  - Shifts: Transferable between employees, fixed timing
- Efficient viewport culling for performance
- Custom validation rules and visual feedback
- Professional color scheme with clear visual distinction
"""

from datetime import datetime, timedelta
import random
import sys
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QMainWindow, QToolBar, QLabel, QPushButton, QSpinBox
from PySide6.QtWidgets import QLineEdit

from sprintify.navigation.colors.modes import ColorMap
from sprintify.navigation.interaction.interaction_item import (
    InteractiveItem,
    ItemCapabilities,
    ResizeHandle,
    ItemVisuals,
    ItemShape
)
from sprintify.navigation.interaction.selection import InteractionHandler
from sprintify.navigation.navigation_widget import NavigationWidget
from sprintify.navigation.rulers import ItemRuler, TimelineRuler


class ScheduleItem:
    """Base class for schedule items (shifts/vacations)."""
    def __init__(self, start: datetime, duration: timedelta, employee_id: int, item_type: str):
        self.start = start
        self.duration = duration
        self.employee_id = employee_id
        self.item_type = item_type
        self.original_start = start  # For shifts to snap back
        self.original_employee = employee_id  # For vacations to snap back


class Vacation(ScheduleItem):
    """Vacation - personal to employee, flexible in time."""
    def __init__(self, start: datetime, duration: timedelta, employee_id: int):
        super().__init__(start, duration, employee_id, "vacation")


class Shift(ScheduleItem):
    """Work shift - transferable between employees, fixed in time."""
    def __init__(self, start: datetime, duration: timedelta, employee_id: int):
        super().__init__(start, duration, employee_id, "shift")


class SchedulingApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Enterprise Scheduling System - 1000 Employees")
        self.setMinimumSize(1400, 900)

        # Planning period: 2 months
        self.start_date = datetime(2024, 1, 1)
        self.end_date = datetime(2024, 3, 1)
        self.num_employees = 1000

        # Color scheme
        self.color_map = ColorMap(darkmode=True)

        # Colors for different item types - using distinct colors for on/off duty
        self.vacation_color = self.color_map.get_saturated_color("amber", "fill")  # Amber for time off
        self.vacation_border = self.color_map.get_saturated_color("amber", "border")
        self.shift_color = self.color_map.get_saturated_color("blue", "fill")  # Blue for working
        self.shift_border = self.color_map.get_saturated_color("blue", "border")

        # Create rulers
        self.time_ruler = TimelineRuler(
            self.start_date,
            self.end_date,
            length=1400,
            visible_start=self.start_date,
            visible_stop=self.start_date + timedelta(days=14)  # Start with 2-week view
        )

        self.employee_ruler = ItemRuler(
            item_count=self.num_employees,
            length=900,
            default_pixels_per_item=25,  # Compact view for 1000 employees
            min_pixels_per_item=15,
            max_pixels_per_item=60
        )

        # Create navigation widget
        self.nav_widget = NavigationWidget(
            self.time_ruler,
            self.employee_ruler,
            self.color_map
        )

        # Set employee labels
        self.nav_widget.left_ruler_widget.get_label = lambda i: f"Emp {i+1:04d}"

        # Status label for feedback - create early before any method that might use it
        self.status_label = QLabel("Ready")
        self.statusBar().addWidget(self.status_label)

        # Create toolbar
        self.create_toolbar()

        self.setCentralWidget(self.nav_widget)

        # Setup interaction handler
        self.interaction = InteractionHandler(
            self.nav_widget.canvas,
            self.time_ruler,
            self.employee_ruler
        )

        # Configure interaction
        self.setup_interaction()

        # Spatial index for efficient overlap checking (employee -> sorted list of items by start time)
        self.employee_schedule_index: Dict[int, List[InteractiveItem]] = defaultdict(list)

        # Generate initial schedule
        self.generate_schedule()

        # Performance timer for stats
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(1000)

    def create_toolbar(self):
        """Create toolbar with controls."""
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        # Replace "example-y" controls with a single useful Find
        toolbar.addWidget(QLabel("Find employee:"))
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("0001")
        self.find_edit.setFixedWidth(90)
        self.find_edit.returnPressed.connect(self._on_find_submitted)
        toolbar.addWidget(self.find_edit)

        self.find_status = QLabel("")  # quiet feedback (optional)
        toolbar.addWidget(self.find_status)

    def _on_find_submitted(self):
        raw = (self.find_edit.text() or "").strip()
        try:
            emp_num = int(raw)
        except ValueError:
            self.find_status.setText("invalid")
            return

        if not (1 <= emp_num <= self.num_employees):
            self.find_status.setText("out of range")
            return

        self.find_status.setText("")
        self.goto_employee(emp_num)


    def goto_employee(self, emp_num: int):
        """Scroll to specific employee."""
        emp_index = emp_num - 1

        # Center the employee in view
        visible_count = self.employee_ruler.visible_stop - self.employee_ruler.visible_start
        self.employee_ruler.visible_start = max(0, emp_index - visible_count / 2)
        self.employee_ruler.visible_stop = min(
            self.num_employees,
            self.employee_ruler.visible_start + visible_count
        )
        self.nav_widget.update()

    def setup_interaction(self):
        """Configure interaction rules."""

        # Item-aware snap functions
        def snap_x_move(x: datetime, item: InteractiveItem) -> datetime:
            """Snap X during move based on item type."""
            if isinstance(item.data, Vacation):
                # Vacations can move in time, snap to start of day
                return x.replace(hour=0, minute=0, second=0, microsecond=0)
            elif isinstance(item.data, Shift):
                # Shifts must stay at original time
                return item.data.original_start
            return x

        def snap_y_move(y: float, item: InteractiveItem) -> float:
            """Snap Y during move based on item type."""
            if isinstance(item.data, Vacation):
                # Vacations must stay with original employee
                return float(item.data.original_employee)
            elif isinstance(item.data, Shift):
                # Shifts can move between employees - ensure float return
                return float(round(y))
            return float(round(y))

        def snap_x_resize(x: datetime, item: InteractiveItem) -> datetime:
            """Snap X during resize - vacations snap to day boundaries."""
            if isinstance(item.data, Vacation):
                return x.replace(hour=0, minute=0, second=0, microsecond=0)
            # Shifts can't be resized (handled by capabilities)
            return x

        self.interaction.set_snap_strategy(
            snap_x=snap_x_move,
            snap_y=snap_y_move,
            snap_resize_x=snap_x_resize  # For vacation resizing
        )

        # NEW: Use on_drag_update for clean constraint enforcement
        def constrain_drag(item: InteractiveItem) -> Optional[Tuple[datetime, float, timedelta, float]]:
            """Apply hard constraints during drag.

            Returns:
                None if no constraint needed, or (x, y, width, height) tuple to override position
            """
            schedule_item = item.data

            if isinstance(schedule_item, Vacation):
                # Force vacation to stay with original employee
                return (item.x, float(schedule_item.original_employee), item.width, item.height)
            elif isinstance(schedule_item, Shift):
                # Force shift to stay at original time
                return (schedule_item.original_start, item.y, item.width, item.height)

            return None  # No constraint needed

        self.interaction.on_drag_update = constrain_drag

        # Global size constraints (can be overridden per-item)
        # Keep these as defaults, but items can override
        self.interaction.set_size_constraints(
            min_width=timedelta(hours=1),    # Default 1 hour minimum
            max_width=timedelta(days=30),    # Default 30 days maximum
            min_height=1.0,
            max_height=1.0
        )

        # Validation now purely checks for overlaps (no side effects)
        self.interaction.can_drop = self.validate_drop
        self.interaction.on_drop = self.handle_drop

        # Visual configuration
        self.interaction.item_corner_radius = 4
        self.interaction.get_item_color = self.get_item_color
        self.interaction.get_item_label = self.get_item_label
        self.interaction.show_tooltips = True

    def get_item_color(self, item: InteractiveItem) -> QColor:
        """Get color based on item type."""
        schedule_item = item.data
        if isinstance(schedule_item, Vacation):
            return self.vacation_color
        elif isinstance(schedule_item, Shift):
            return self.shift_color
        return QColor(128, 128, 128)

    def get_item_label(self, item: InteractiveItem) -> str:
        """Get label for item."""
        schedule_item = item.data
        if isinstance(schedule_item, Vacation):
            return "VAC"
        elif isinstance(schedule_item, Shift):
            hours = int(schedule_item.duration.total_seconds() / 3600)
            return f"{hours}h"
        return ""

    def validate_drop(self, items: List[InteractiveItem]) -> bool:
        """Pure validation - check bounds and overlaps, no side effects."""
        for item in items:
            # NEW: Explicit bounds checking
            emp_id = int(round(item.y))
            if emp_id < 0 or emp_id >= self.num_employees:
                return False  # Out of bounds

            # Time bounds check
            if item.x < self.start_date or item.x + item.width > self.end_date:
                return False  # Outside planning period

            # Check for overlaps with existing items - using efficient method
            if self.has_overlap_efficient(item, emp_id, items):
                return False  # Return False to show red/invalid state

        return True

    def has_overlap_efficient(self, item: InteractiveItem, emp_id: int,
                             dragged_items: List[InteractiveItem]) -> bool:
        """Efficiently check if item overlaps using spatial index.

        O(log n) using binary search on sorted employee schedule.
        """
        item_start = item.x
        item_end = item.x + item.width

        # Get schedule for this employee from index
        employee_schedule = self.employee_schedule_index.get(emp_id, [])

        if not employee_schedule:
            return False

        # Find insertion point using binary search
        left_idx = 0
        right_idx = len(employee_schedule)

        while left_idx < right_idx:
            mid_idx = (left_idx + right_idx) // 2
            mid_item = employee_schedule[mid_idx]
            if mid_item.x < item_start:
                left_idx = mid_idx + 1
            else:
                right_idx = mid_idx

        # Robust overlap check: scan backward and forward from insertion point
        # Backward scan: check all items that might extend into our range
        check_idx = left_idx - 1
        while check_idx >= 0:
            other_item = employee_schedule[check_idx]

            # Skip if it's the same item or another dragged item
            if other_item == item or other_item in dragged_items:
                check_idx -= 1
                continue

            other_end = other_item.x + other_item.width

            # Stop scanning when items can no longer overlap
            if other_end <= item_start:
                break

            # Check for overlap
            if item_start < other_end and item_end > other_item.x:
                return True

            check_idx -= 1

        # Forward scan: check all items starting from insertion point
        for idx in range(left_idx, len(employee_schedule)):
            other_item = employee_schedule[idx]

            # Skip if it's the same item or another dragged item
            if other_item == item or other_item in dragged_items:
                continue

            # Stop scanning when items can no longer overlap
            if other_item.x >= item_end:
                break

            # Check for overlap
            other_end = other_item.x + other_item.width
            if item_start < other_end and item_end > other_item.x:
                return True

        return False

    def has_overlap(self, item: InteractiveItem, emp_id: int,
                    dragged_items: List[InteractiveItem]) -> bool:
        """Fallback O(n) overlap check for compatibility."""
        # Use the efficient version
        return self.has_overlap_efficient(item, emp_id, dragged_items)

    def handle_drop(self, items: List[InteractiveItem]):
        """Handle successful drop - sync model with item positions and update index."""
        for item in items:
            old_emp_id = item.data.employee_id
            old_start = item.data.start

            # Update the data model from item position
            # Use sync_to_data if available, otherwise update manually
            if hasattr(item, 'sync_to_data') and callable(item.sync_to_data):
                item.sync_to_data()
            else:
                # Manual update for safety
                schedule_item = item.data
                schedule_item.start = item.x
                schedule_item.duration = item.width
                schedule_item.employee_id = int(round(item.y))

            # The sync_to_data handles common patterns, but we can still do custom logic:
            schedule_item = item.data
            if isinstance(schedule_item, Vacation):
                # Ensure original_employee stays unchanged (safety check)
                schedule_item.employee_id = schedule_item.original_employee

            new_emp_id = schedule_item.employee_id
            new_start = schedule_item.start

            # Update spatial index if employee or time changed
            needs_reindex = (old_emp_id != new_emp_id) or (old_start != new_start)

            if needs_reindex:
                # Remove from old employee's schedule
                if old_emp_id in self.employee_schedule_index:
                    self.employee_schedule_index[old_emp_id] = [
                        i for i in self.employee_schedule_index[old_emp_id] if i != item
                    ]

                # Add to new/same employee's schedule in correct position
                self._add_to_schedule_index(new_emp_id, item)

        self.status_label.setText(f"Moved {len(items)} item(s)")
        self.nav_widget.update()

    def _add_to_schedule_index(self, emp_id: int, item: InteractiveItem):
        """Add item to employee's schedule maintaining sorted order."""
        schedule = self.employee_schedule_index[emp_id]

        # Binary search for insertion point
        left, right = 0, len(schedule)
        while left < right:
            mid = (left + right) // 2
            if schedule[mid].x < item.x:
                left = mid + 1
            else:
                right = mid

        schedule.insert(left, item)

    def generate_schedule(self):
        """Generate initial schedule with vacations and shifts."""
        random.seed(42)  # For reproducibility

        # Clear the spatial index
        self.employee_schedule_index.clear()

        # Generate vacations (5% of employees)
        vacation_employees = random.sample(
            range(self.num_employees),
            k=int(self.num_employees * 0.05)
        )

        for emp_id in vacation_employees:
            # Random vacation between 1-3 weeks, starting on a Monday
            max_start = self.end_date - timedelta(days=21)
            days_range = (max_start - self.start_date).days
            start_day = random.randint(0, max(0, days_range))
            vac_start = self.start_date + timedelta(days=start_day)

            # Snap to start of day
            vac_start = vac_start.replace(hour=0, minute=0, second=0, microsecond=0)

            # Random duration between 1 day and 3 weeks
            duration_days = random.randint(1, 21)
            duration = timedelta(days=duration_days)

            vacation = Vacation(
                start=vac_start,
                duration=duration,
                employee_id=emp_id
            )

            # Create interactive item with model sync
            item = InteractiveItem(
                data=vacation,
                x=vacation.start,
                y=float(emp_id),
                width=vacation.duration,
                height=1.0,
                capabilities=ItemCapabilities(
                    can_move=True,
                    can_resize=True,  # Vacations can be resized
                    resize_handles={ResizeHandle.LEFT, ResizeHandle.RIGHT},
                    # Vacation-specific size constraints
                    min_width=timedelta(days=1),   # 1 day minimum
                    max_width=timedelta(days=21),  # 3 weeks maximum
                ),
                # leave some space above/below inside row
                interaction_rect=(0.0, 0.12, 1.0, 0.88),
                # NEW: Define how to sync from data back to item
                sync_from_data=lambda v: (v.start, float(v.employee_id), v.duration, 1.0)
            )

            # Set visual properties
            item.visuals.fill_color = self.vacation_color
            item.visuals.stroke_color = self.vacation_border
            item.visuals.shape = ItemShape.ROUNDED_RECT
            item.visuals.corner_radius = 4

            # Update label to show duration
            days = int(vacation.duration.total_seconds() / 86400)
            item.visuals.label = f"VAC {days}d"

            # Tooltip
            item.tooltip = f"Vacation: Employee {emp_id+1} ({days} days) - resize with edges, move in time only"

            self.interaction.add_item(item)

            # Add to spatial index
            self._add_to_schedule_index(emp_id, item)

        # Generate shifts (spread across employees, weekdays only)
        current_date = self.start_date
        while current_date < self.end_date:
            # Skip weekends
            if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                # Generate 20-40 shifts per day (distributed across employees)
                num_shifts = random.randint(20, 40)

                for _ in range(num_shifts):
                    emp_id = random.randint(0, self.num_employees - 1)

                    # Random shift between 6:00 and 22:00, 5-10 hours long
                    start_hour = random.randint(6, 16)  # Latest start at 16:00
                    duration_hours = random.randint(5, min(10, 22 - start_hour))

                    shift_start = current_date.replace(hour=start_hour, minute=0, second=0, microsecond=0)

                    # Use efficient overlap check with spatial index
                    dummy_item = InteractiveItem(
                        data=None,
                        x=shift_start,
                        y=float(emp_id),
                        width=timedelta(hours=duration_hours),
                        height=1.0
                    )

                    has_conflict = self.has_overlap_efficient(dummy_item, emp_id, [])

                    if not has_conflict:
                        shift = Shift(
                            start=shift_start,
                            duration=timedelta(hours=duration_hours),
                            employee_id=emp_id
                        )

                        # Create interactive item with model sync
                        item = InteractiveItem(
                            data=shift,
                            x=shift.start,
                            y=float(emp_id),
                            width=shift.duration,
                            height=1.0,
                            capabilities=ItemCapabilities(
                                can_move=True,
                                can_resize=False  # Shifts have fixed duration (no resize at all)
                                # No need to specify size constraints for non-resizable items
                            ),
                            # leave some space above/below inside row
                            interaction_rect=(0.0, 0.12, 1.0, 0.88),
                            # NEW: Define how to sync from data back to item
                            sync_from_data=lambda s: (s.start, float(s.employee_id), s.duration, 1.0)
                        )

                        # Set visual properties
                        item.visuals.fill_color = self.shift_color
                        item.visuals.stroke_color = self.shift_border
                        item.visuals.shape = ItemShape.RECTANGLE
                        item.visuals.label = f"{duration_hours}h"

                        # Tooltip
                        item.tooltip = f"Shift: {duration_hours}h @ Employee {emp_id+1} (move between employees only)"

                        self.interaction.add_item(item)

                        # Add to spatial index
                        self._add_to_schedule_index(emp_id, item)

            current_date += timedelta(days=1)

        self.status_label.setText(
            f"Generated {len([i for i in self.interaction.items if isinstance(i.data, Vacation)])} vacations, "
            f"{len([i for i in self.interaction.items if isinstance(i.data, Shift)])} shifts"
        )

    def update_stats(self):
        """Update performance statistics."""
        visible_items = 0
        viewport_rect = self.nav_widget.canvas.viewport().rect()

        # Count visible items (demonstrates culling)
        x_min = self.time_ruler.get_value_at(0)
        x_max = self.time_ruler.get_value_at(viewport_rect.width())
        y_min = self.employee_ruler.get_value_at(0)
        y_max = self.employee_ruler.get_value_at(viewport_rect.height())

        for item in self.interaction.items:
            if not (item.x > x_max or
                   item.x + item.width < x_min or
                   item.y > y_max or
                   item.y + item.height < y_min):
                visible_items += 1

        total_items = len(self.interaction.items)
        visible_employees = int(y_max - y_min)

        self.setWindowTitle(
            f"Enterprise Scheduling - {self.num_employees} Employees | "
            f"Viewing: {visible_employees} employees | "
            f"Items: {visible_items}/{total_items} visible (culled: {total_items - visible_items})"
        )

# --- main entrypoint ---

def main() -> int:
    app = QApplication(sys.argv)
    window = SchedulingApp()
    window.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())

