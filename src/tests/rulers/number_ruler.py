import unittest
from rulers.number_ruler import NumberRuler

class TestNumberRuler(unittest.TestCase):
    def setUp(self):
        self.ruler = NumberRuler(0, 100, 20, 80)

    def test_transform(self):
        self.assertEqual(self.ruler.transform(50, 100), 50)
        self.assertEqual(self.ruler.transform(20, 100), 0)
        self.assertEqual(self.ruler.transform(80, 100), 100)
        self.assertEqual(self.ruler.get_value_at(self.ruler.transform(50, 100), 100), 50)

    def test_reverse_transform(self):
        self.assertEqual(self.ruler.get_value_at(50, 100), 50)
        self.assertEqual(self.ruler.get_value_at(0, 100), 20)
        self.assertEqual(self.ruler.get_value_at(100, 100), 80)
        self.assertEqual(self.ruler.transform(self.ruler.get_value_at(50, 100), 100), 50)

    def test_zoom_in(self):
        old_visible_length = self.ruler.visible_length
        self.ruler.zoom(True, 50, 100)
        self.assertGreater(self.ruler.visible_length, old_visible_length)
        self.assertGreaterEqual(self.ruler.visible_start, self.ruler.window_start)
        self.assertLessEqual(self.ruler.visible_stop, self.ruler.window_stop)

    def test_zoom_out(self):
        old_visible_length = self.ruler.visible_length
        self.ruler.zoom(False, 50, 100)
        self.assertLess(self.ruler.visible_length, old_visible_length)
        self.assertGreaterEqual(self.ruler.visible_start, self.ruler.window_start)
        self.assertLessEqual(self.ruler.visible_stop, self.ruler.window_stop)

    def test_pan(self):
        self.ruler.pan(10, 100)
        self.assertGreaterEqual(self.ruler.visible_start, self.ruler.window_start)
        self.assertLessEqual(self.ruler.visible_stop, self.ruler.window_stop)

if __name__ == '__main__':
    unittest.main()