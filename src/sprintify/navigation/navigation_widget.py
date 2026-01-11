from __future__ import annotations

from typing import Callable, Optional, TypeAlias, Any, Union
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QGridLayout
from PySide6.QtGui import QPainter, QPixmap

from sprintify.navigation.rulers import NumberRuler, TimelineRuler, ItemRuler
from sprintify.navigation.widgets import NumberRulerWidget, TimelineRulerWidget, DrawingWidget, ItemRulerWidget

DrawCommand: TypeAlias = Callable[[QPainter], None]


class NavigationWidget(QWidget):
    """
    Composite navigation widget with rulers + drawing canvas.

    Layout:
      - top_ruler_widget (timeline/number/item)
      - left_ruler_widget (number/item)
      - canvas (DrawingWidget)

    Notes:
      - All widgets share the same ruler model instances (pan/zoom is applied to the model).
      - Use link_widget() when you have multiple NavigationWidget instances sharing the same rulers and
        you want them to repaint together during interaction.
    """

    def __init__(
        self,
        top_ruler: Any,
        left_ruler: Any,
        color_map: Any,
        right_ruler: Any = None,
        bottom_ruler: Any = None,
        background_image: Optional[Union[str, Path, QPixmap]] = None,
        parent: Optional[QWidget] = None,
    ):
        if top_ruler is None or left_ruler is None:
            raise ValueError("NavigationWidget: top_ruler and left_ruler must be provided")
        if color_map is None:
            raise ValueError("NavigationWidget: color_map must be provided")
        super().__init__(parent)
        self.color_map = color_map
        self.top_ruler = top_ruler
        self.left_ruler = left_ruler
        self.right_ruler = right_ruler
        self.bottom_ruler = bottom_ruler

        # Create ruler widgets (share the BaseRuler instances)
        if isinstance(top_ruler, TimelineRuler):
            self.top_ruler_widget = TimelineRulerWidget(top_ruler, color_map, self)
        elif isinstance(top_ruler, ItemRuler):
            self.top_ruler_widget = ItemRulerWidget(top_ruler, color_map, orientation='x', parent=self)
        else:
            self.top_ruler_widget = NumberRulerWidget(top_ruler, color_map, 'x', self)

        if isinstance(left_ruler, ItemRuler):
            self.left_ruler_widget = ItemRulerWidget(left_ruler, color_map, orientation='y', parent=self)
        else:
            self.left_ruler_widget = NumberRulerWidget(left_ruler, color_map, 'y', self)

        # Create bottom ruler widget (share the BaseRuler instances)
        self.bottom_ruler_widget = None
        if bottom_ruler:
            if isinstance(bottom_ruler, TimelineRuler):
                self.bottom_ruler_widget = TimelineRulerWidget(bottom_ruler, color_map, self)
            elif isinstance(bottom_ruler, ItemRuler):
                self.bottom_ruler_widget = ItemRulerWidget(bottom_ruler, color_map, orientation='x', parent=self)
            else:
                self.bottom_ruler_widget = NumberRulerWidget(bottom_ruler, color_map, 'x', self)

        # Create drawing widget (shares the same BaseRuler instances)
        self.canvas = DrawingWidget(top_ruler, left_ruler, color_map, background_image, self)

        # Layout
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Explicitly set stretch factors:
        # Row 1 (Canvas) gets all extra vertical space.
        # Rows 0 (Top Ruler) and 2 (Bottom Ruler) stay their minimum/fixed size.
        layout.setRowStretch(0, 0)
        layout.setRowStretch(1, 1)
        layout.setRowStretch(2, 0)

        # Column 1 (Canvas) gets all extra horizontal space.
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 1)

        corner_height = 30 if isinstance(top_ruler, TimelineRuler) else (80 if isinstance(top_ruler, ItemRuler) else 20)
        corner_width = 80 if isinstance(left_ruler, ItemRuler) else 20
        corner = QWidget()
        corner.setFixedSize(corner_width, corner_height)
        corner.paintEvent = lambda e: QPainter(corner).fillRect(corner.rect(), color_map.get_object_color("surface-base"))

        layout.addWidget(corner, 0, 0)
        layout.addWidget(self.top_ruler_widget, 0, 1)
        layout.addWidget(self.left_ruler_widget, 1, 0)
        layout.addWidget(self.canvas, 1, 1)

        # Add bottom ruler if present
        if self.bottom_ruler_widget:
            layout.addWidget(self.bottom_ruler_widget, 2, 1)

            # Bottom-Left Corner
            corner_bl = QWidget()
            h_bottom = 30 if isinstance(bottom_ruler, TimelineRuler) else (80 if isinstance(bottom_ruler, ItemRuler) else 20)
            corner_bl.setFixedSize(corner_width, h_bottom)
            corner_bl.paintEvent = lambda e: QPainter(corner_bl).fillRect(corner_bl.rect(), color_map.get_object_color("surface-base"))
            layout.addWidget(corner_bl, 2, 0)

        self.setMouseTracking(True)

        # Linked widgets repaint together (useful for stacked views sharing timeline)
        self._linked_widgets: set["NavigationWidget"] = set()

    def link_widget(self, other: "NavigationWidget") -> None:
        """Link two NavigationWidget instances so they repaint together on pan/zoom."""
        if other is None:
            raise ValueError("link_widget: other must be a NavigationWidget")
        if other is self:
            return
        self._linked_widgets.add(other)
        other._linked_widgets.add(self)

    def update(self) -> None:
        """Override update to ensure canvas viewport is repainted (needed for ScrollArea)."""
        super().update()
        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.viewport().update()

    def _notify_linked(self) -> None:
        """Repaint this widget and any linked widgets."""
        self.update()
        # Explicitly update ruler widgets so they reflect scroll/zoom changes immediately
        self.top_ruler_widget.update()
        self.left_ruler_widget.update()
        if self.bottom_ruler_widget:
            self.bottom_ruler_widget.update()

        # Ensure our own canvas scrollbars are synced (in case the trigger came from a linked widget)
        if hasattr(self.canvas, "_update_scrollbars"):
            self.canvas._update_scrollbars()

        for w in tuple(self._linked_widgets):
            w.update()

            # Sync linked canvas scrollbars to match the shared ruler state
            if hasattr(w.canvas, "_update_scrollbars"):
                w.canvas._update_scrollbars()

            w.canvas.update()
            w.top_ruler_widget.update()
            w.left_ruler_widget.update()
            if w.bottom_ruler_widget:
                w.bottom_ruler_widget.update()

    # ---- Drawing API (delegated to canvas) ---------------------------------

    def __getattr__(self, name: str):
        """Delegate drawing commands to canvas (e.g. draw_rects, add_draw_command)."""
        if hasattr(self.canvas, name) and name.startswith(("draw_", "add_draw", "remove_draw", "clear_draw")):
            return getattr(self.canvas, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
