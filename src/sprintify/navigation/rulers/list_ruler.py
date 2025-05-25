from sprintify.navigation.rulers.base import BaseRuler

class ListRuler(BaseRuler):
    def __init__(self, items, item_widths, visible_start=None, visible_stop=None, reverse=False):
        self.items = items
        self.item_widths = item_widths
        self.item_positions = self._calculate_positions()
        super().__init__(0, self.item_positions[-1], visible_start, visible_stop, reverse)

    def _calculate_positions(self):
        # Calculate cumulative positions based on item widths
        positions = [0]
        for width in self.item_widths:
            positions.append(positions[-1] + width)
        return positions

    def get_item_at(self, position):
        # Find the item at a specific position
        for i, (start, end) in enumerate(zip(self.item_positions[:-1], self.item_positions[1:])):
            if start <= position < end:
                return self.items[i]
        return None

    def get_item_width(self, index):
        # Get the width of a specific item
        if 0 <= index < len(self.item_widths):
            return self.item_widths[index]
        return None