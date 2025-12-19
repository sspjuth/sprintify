"""
sales_heatmap_app.py

This example demonstrates a correlation heatmap visualization using ItemRuler on both axes.
It shows relationships between articles/products as a color-coded matrix where:
- Each cell represents the correlation between two articles
- Color intensity indicates correlation strength (blue=low, green=medium, yellow/red=high)
- Correlation values are displayed when zoomed in enough
- Hovering shows article names and correlation value

Key features demonstrated:
- **ItemRuler on both axes**: For categorical data (articles/products)
- **Color mapping**: Using a gradient to represent numerical values
- **Conditional rendering**: Show text only when cells are large enough
- **Mouse tracking**: Display hover information
"""
from datetime import datetime, timedelta
import random
import math

from PySide6.QtGui import QBrush, QPen, QColor, QFont
from PySide6.QtWidgets import QMainWindow, QToolTip
from PySide6.QtCore import Qt, QRectF, QPoint

from sprintify.navigation.colors.modes import ColorMap
from sprintify.navigation.rulers import ItemRuler
from sprintify.navigation.navigation_widget import NavigationWidget


class Article:
    """Represents an article/product with sales data."""

    def __init__(self, article_id: int, name: str, category: str):
        self.id = article_id
        self.name = name
        self.category = category
        self.sales_pattern = []  # Daily sales over time

    def generate_sales_pattern(self, days=365):
        """Generate a sales pattern that can be correlated with other articles."""
        # Base pattern with seasonality
        base_level = random.uniform(50, 200)
        seasonality_amplitude = random.uniform(20, 80)
        trend = random.uniform(-0.5, 0.5)
        noise_level = random.uniform(5, 20)

        for day in range(days):
            # Seasonal pattern (annual cycle)
            seasonal = seasonality_amplitude * math.sin(2 * math.pi * day / 365)
            # Trend
            trend_component = trend * day
            # Random noise
            noise = random.uniform(-noise_level, noise_level)
            # Weekly pattern (lower on weekends)
            weekly = -10 if day % 7 in [5, 6] else 0

            sales = base_level + seasonal + trend_component + weekly + noise
            sales = max(0, sales)
            self.sales_pattern.append(sales)


def calculate_correlation(article1: Article, article2: Article):
    """Calculate Pearson correlation between two articles' sales patterns."""
    if article1.id == article2.id:
        return 1.0  # Perfect correlation with itself

    x = article1.sales_pattern
    y = article2.sales_pattern
    n = len(x)

    if n == 0:
        return 0.0

    # Calculate means
    mean_x = sum(x) / n
    mean_y = sum(y) / n

    # Calculate correlation
    numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    denominator_x = math.sqrt(sum((x[i] - mean_x) ** 2 for i in range(n)))
    denominator_y = math.sqrt(sum((y[i] - mean_y) ** 2 for i in range(n)))

    if denominator_x == 0 or denominator_y == 0:
        return 0.0

    correlation = numerator / (denominator_x * denominator_y)
    return max(-1.0, min(1.0, correlation))  # Clamp to [-1, 1]


def create_correlated_articles(base_article: Article, correlation_strength: float, article_id: int, name: str, category: str = None):
    """Create a new article with a specific correlation to the base article."""
    if category is None:
        category = base_article.category
    new_article = Article(article_id, name, category)

    # Generate correlated sales pattern
    noise_factor = math.sqrt(1 - correlation_strength ** 2)

    for i in range(len(base_article.sales_pattern)):
        base_value = base_article.sales_pattern[i]
        # Mix base pattern with independent noise
        correlated_value = (correlation_strength * base_value +
                          noise_factor * random.uniform(0, 200))
        new_article.sales_pattern.append(max(0, correlated_value))

    return new_article


class CorrelationHeatmapWindow(QMainWindow):
    def __init__(self, articles=None):
        super().__init__()
        self.articles = articles or []
        self.setWindowTitle("Article Correlation Heatmap")
        self.setMinimumSize(1200, 1200)

        self.color_map = ColorMap(darkmode=True)

        # Pre-calculate correlation matrix
        n = len(self.articles)
        self.correlation_matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                self.correlation_matrix[i][j] = calculate_correlation(
                    self.articles[i], self.articles[j]
                )

        # Create ItemRulers for both axes
        self.h_ruler = ItemRuler(
            item_count=len(self.articles),
            length=1200,
            default_pixels_per_item=40,
            min_pixels_per_item=10,
            max_pixels_per_item=200
        )

        self.v_ruler = ItemRuler(
            item_count=len(self.articles),
            length=1200,
            default_pixels_per_item=40,
            min_pixels_per_item=10,
            max_pixels_per_item=200
        )

        # Create navigation widget
        self.widget = NavigationWidget(self.h_ruler, self.v_ruler, self.color_map)
        self.widget.left_ruler_widget.get_label = lambda i: self.articles[i].name if i < len(self.articles) else ""
        self.widget.top_ruler_widget.get_label = lambda i: self.articles[i].name if i < len(self.articles) else ""

        # Enable mouse tracking for hover
        self.widget.canvas.setMouseTracking(True)
        self.widget.canvas.mouseMoveEvent = self._handle_mouse_move

        self.setCentralWidget(self.widget)

        # Draw heatmap
        self.draw_heatmap()

    def _handle_mouse_move(self, event):
        """Handle mouse move for tooltip display."""
        # Get mouse position in ruler coordinates
        mouse_x = event.position().x()
        mouse_y = event.position().y()

        # Use get_value_at instead of inverse_transform
        h_value = self.h_ruler.get_value_at(mouse_x)
        v_value = self.v_ruler.get_value_at(mouse_y)

        # Check if hovering over a valid cell
        if 0 <= h_value < len(self.articles) and 0 <= v_value < len(self.articles):
            h_idx = int(h_value)
            v_idx = int(v_value)

            article_x = self.articles[h_idx]
            article_y = self.articles[v_idx]
            correlation = self.correlation_matrix[v_idx][h_idx]

            tooltip_text = (f"{article_y.name} vs {article_x.name}\n"
                          f"Correlation: {correlation:.3f}")

            QToolTip.showText(event.globalPosition().toPoint(), tooltip_text, self.widget.canvas)
        else:
            QToolTip.hideText()

    def _get_color_for_correlation(self, correlation: float) -> QColor:
        """Map correlation value [-1, 1] to a color gradient."""
        # Map correlation to [0, 1] range
        normalized = (correlation + 1.0) / 2.0

        # Create gradient: blue (0) -> cyan (0.3) -> green (0.5) -> yellow (0.7) -> red (1)
        if normalized < 0.25:
            # Blue to Cyan
            t = normalized / 0.25
            return QColor(
                int(0 * (1-t) + 0 * t),
                int(0 * (1-t) + 150 * t),
                int(200 * (1-t) + 200 * t)
            )
        elif normalized < 0.5:
            # Cyan to Green
            t = (normalized - 0.25) / 0.25
            return QColor(
                int(0 * (1-t) + 0 * t),
                int(150 * (1-t) + 200 * t),
                int(200 * (1-t) + 100 * t)
            )
        elif normalized < 0.75:
            # Green to Yellow
            t = (normalized - 0.5) / 0.25
            return QColor(
                int(0 * (1-t) + 255 * t),
                int(200 * (1-t) + 255 * t),
                int(100 * (1-t) + 0 * t)
            )
        else:
            # Yellow to Red
            t = (normalized - 0.75) / 0.25
            return QColor(
                255,
                int(255 * (1-t) + 50 * t),
                0
            )

    def draw_heatmap(self):
        """Draw the correlation heatmap with colors and optional text."""
        def draw_cells(painter):
            # Get visible range
            first_h = int(self.h_ruler.visible_start)
            last_h = min(len(self.articles), int(self.h_ruler.visible_stop) + 1)
            first_v = int(self.v_ruler.visible_start)
            last_v = min(len(self.articles), int(self.v_ruler.visible_stop) + 1)

            # Check if cells are large enough for text
            sample_h_start = self.h_ruler.transform(float(first_h))
            sample_h_end = self.h_ruler.transform(float(first_h + 1))
            cell_width = sample_h_end - sample_h_start
            show_text = cell_width > 30  # Show text if cell is wider than 30 pixels

            # Set up font for text
            if show_text:
                font = QFont()
                font.setPointSize(8 if cell_width > 60 else 7)
                painter.setFont(font)

            # Draw each visible cell
            for v_idx in range(first_v, last_v):
                for h_idx in range(first_h, last_h):
                    correlation = self.correlation_matrix[v_idx][h_idx]

                    # Get cell boundaries
                    x1 = self.h_ruler.transform(float(h_idx))
                    x2 = self.h_ruler.transform(float(h_idx + 1))
                    y1 = self.v_ruler.transform(float(v_idx))
                    y2 = self.v_ruler.transform(float(v_idx + 1))

                    # Draw cell background
                    color = self._get_color_for_correlation(correlation)
                    painter.setBrush(QBrush(color))
                    painter.setPen(QPen(self.color_map.get_object_color("border"), 0.5))
                    painter.drawRect(QRectF(x1, y1, x2 - x1, y2 - y1))

                    # Draw text if cells are large enough
                    if show_text:
                        # Choose text color based on background brightness
                        text_color = Qt.GlobalColor.black if correlation > 0.3 else Qt.GlobalColor.white
                        painter.setPen(QPen(text_color))

                        # Draw correlation value
                        text = f"{correlation:.2f}"
                        painter.drawText(
                            QRectF(x1, y1, x2 - x1, y2 - y1),
                            Qt.AlignmentFlag.AlignCenter,
                            text
                        )

        self.widget.add_draw_command("heatmap", draw_cells)
        self.widget.update()


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    # Create articles with different correlation patterns
    articles = []

    # Create base articles for different categories
    base_electronics = Article(0, "Laptop Pro", "Electronics")
    base_electronics.generate_sales_pattern()
    articles.append(base_electronics)

    # Create correlated electronics
    articles.append(create_correlated_articles(base_electronics, 0.85, 1, "Mouse Wireless", "Electronics"))
    articles.append(create_correlated_articles(base_electronics, 0.75, 2, "Keyboard Mech", "Electronics"))
    articles.append(create_correlated_articles(base_electronics, 0.60, 3, "Monitor 27in", "Electronics"))

    # Create base for clothing
    base_clothing = Article(4, "T-Shirt Basic", "Clothing")
    base_clothing.generate_sales_pattern()
    articles.append(base_clothing)

    articles.append(create_correlated_articles(base_clothing, 0.70, 5, "Jeans Slim", "Clothing"))
    articles.append(create_correlated_articles(base_clothing, 0.65, 6, "Jacket Denim", "Clothing"))

    # Create base for food
    base_food = Article(7, "Coffee Beans", "Food")
    base_food.generate_sales_pattern()
    articles.append(base_food)

    articles.append(create_correlated_articles(base_food, 0.80, 8, "Coffee Filters", "Food"))
    articles.append(create_correlated_articles(base_food, 0.55, 9, "Sugar Pack", "Food"))

    # Create many more articles (up to 1000 total)
    article_id = 10

    # Create some more base articles with clusters
    for cluster_idx in range(20):
        base_article = Article(article_id, f"Base-Product-{cluster_idx}", "Mixed")
        base_article.generate_sales_pattern()
        articles.append(base_article)
        article_id += 1

        # Create 5-10 correlated articles for each base
        num_correlated = random.randint(5, 10)
        for j in range(num_correlated):
            correlation = random.uniform(0.4, 0.9)
            correlated = create_correlated_articles(
                base_article,
                correlation,
                article_id,
                f"Product-{article_id}",
                "Mixed"
            )
            articles.append(correlated)
            article_id += 1

    # Fill remaining slots with independent articles
    while len(articles) < 300:
        article = Article(article_id, f"Product-{article_id}", "Mixed")
        article.generate_sales_pattern()
        articles.append(article)
        article_id += 1

    app = QApplication(sys.argv)
    window = CorrelationHeatmapWindow(articles)
    window.show()
    sys.exit(app.exec())
