from datetime import datetime, timedelta
import random
import bisect

from PySide6.QtGui import QBrush, QPen
from PySide6.QtWidgets import QMainWindow
from PySide6.QtCore import Qt, QRectF

from sprintify.navigation.colors.modes import ColorMap
from sprintify.navigation.rulers import TimelineRuler, ItemRuler
from sprintify.navigation.navigation_widget import NavigationWidget


# Simple Employee model kept in this file (attached to SchedulingWindow)
class Employee:
    def __init__(self, emp_id: int, name: str):
        self.id = emp_id
        self.name = name
        self.shifts = []

    def add_shift(self, start: datetime, duration: timedelta):
        # Insert the shift so self.shifts stays sorted by 'start' (binary-insert).
        shift = {'start': start, 'duration': duration}
        lo, hi = 0, len(self.shifts)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.shifts[mid]['start'] < start:
                lo = mid + 1
            else:
                hi = mid
        self.shifts.insert(lo, shift)

    def generate_shifts(self, start_date: datetime, end_date: datetime, min_shifts=10, max_shifts=22):
        """
        Generate random shifts for this employee
        """
        period_seconds = int((end_date - start_date).total_seconds())
        num_shifts = random.randint(min_shifts, max_shifts)
        for _ in range(num_shifts):
            shift_start = start_date + timedelta(seconds=random.randint(0, max(0, period_seconds)))
            duration_hours = random.uniform(4, 12)
            shift_duration = timedelta(hours=duration_hours)
            if shift_start + shift_duration > end_date:
                shift_duration = end_date - shift_start
            self.add_shift(shift_start, shift_duration)

    def get_shifts_in_period(self, period_start: datetime, period_end: datetime):
        """
        Return shifts that may touch the interval [period_start, period_end). It is greedy, so the first shift(s) may not touch the period.
        """
        first_possible_start = period_start - max((s['duration'] for s in self.shifts), default=timedelta(0))
        first_shift_ix = bisect.bisect_left([s['start'] for s in self.shifts], first_possible_start)
        last_shift_ix = bisect.bisect_right([s['start'] for s in self.shifts], period_end)
        return self.shifts[first_shift_ix:last_shift_ix]

class SchedulingWindow(QMainWindow):
    def __init__(self, employees=None, start_date=None, end_date=None):
        super().__init__()
        self.employees = employees
        self.person_colors = {}
        self.setWindowTitle("Scheduling Example - persons")
        self.setMinimumSize(1400, 900)

        self.color_map = ColorMap(darkmode=True)

        # Create rulers (lengths are initial guesses; widgets will set real lengths on resize)
        self.time_ruler = TimelineRuler(start_date, end_date, length=1400)
        self.person_ruler = ItemRuler(
            item_count=len(self.employees),
            length=900,
            default_pixels_per_item=30,
            min_pixels_per_item=10,
            max_pixels_per_item=100
        )

        # Create navigation widget with ItemRuler
        self.widget = NavigationWidget(self.time_ruler, self.person_ruler, self.color_map)
        self.widget.left_ruler_widget.get_label = lambda i: self.employees[i].name

        self.setCentralWidget(self.widget)

        # Assign colors to persons
        self.assign_person_colors()
        self.draw_shifts()

    def assign_person_colors(self):
        """Assign a consistent color to each person using ColorMap."""
        color_names = ['red', 'green', 'blue', 'cyan', 'orange', 'purple', 'pink', 'teal', 'lime', 'amber']

        for person_idx, _ in enumerate(self.employees):
            color_name = color_names[person_idx % len(color_names)]
            self.person_colors[person_idx] = self.color_map.get_saturated_color(color_name, "fill")

    def draw_shifts(self):
        """Draw shifts as rectangles on the canvas - only visible ones, using Employee.get_shifts_in_period."""
        def draw_colored_rects(painter):
            painter.setPen(Qt.PenStyle.NoPen)

            # visible time range
            visible_time_start = self.time_ruler.visible_start
            visible_time_stop = self.time_ruler.visible_stop

            for person_idx in range(int(self.person_ruler.visible_start),  min(len(self.employees), int(self.person_ruler.visible_stop) + 1)):
                employee = self.employees[person_idx]
                shifts = employee.get_shifts_in_period(visible_time_start, visible_time_stop)
                color = self.person_colors.get(person_idx)
                if color is None:
                    continue
                painter.setBrush(QBrush(color))

                # draw only shifts returned by the employee helper (clip to visible time)
                for s in shifts:
                    s_start = s['start']
                    s_end = s_start + s['duration']
                    # clip to visible time window
                    draw_start = max(s_start, visible_time_start)
                    draw_end = min(s_end, visible_time_stop)
                    if draw_start >= draw_end:
                        continue

                    x1 = self.time_ruler.transform(draw_start)
                    x2 = self.time_ruler.transform(draw_end)
                    y1 = self.person_ruler.transform(float(person_idx) + 0.05)
                    y2 = self.person_ruler.transform(float(person_idx) + 0.05 + 0.9)
                    painter.drawRect(QRectF(x1, y1, x2 - x1, y2 - y1))

        # register draw command and refresh
        self.widget.add_draw_command("shifts", draw_colored_rects)
        self.widget.update()


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    start_date = datetime(2023, 12, 1)
    end_date = datetime(2024, 2, 1)

    # Create employees externally and populate their shifts
    employees = [Employee(i, f"Person {i}") for i in range(200)]
    for e in employees:
        e.generate_shifts(start_date, end_date, 30, 44)

    app = QApplication(sys.argv)
    window = SchedulingWindow(employees, start_date=start_date, end_date=end_date)
    window.show()
    sys.exit(app.exec())
