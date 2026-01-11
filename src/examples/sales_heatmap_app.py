"""
sales_heatmap_app.py

This example demonstrates a correlation heatmap visualization using ItemRuler on both axes.
Optimized for large datasets (1000+ products) with:
- Fast vectorized correlation calculation
- Direct drawing for large grids (no individual items)
- Interactive items only for smaller grids (with tooltips only, no selection/drag)
"""
from datetime import datetime, timedelta
import random
import math
from dataclasses import dataclass
import numpy as np

from PySide6.QtGui import QBrush, QPen, QColor, QFont, QPainter
from PySide6.QtWidgets import QMainWindow, QProgressDialog, QToolTip
from PySide6.QtCore import Qt, QRectF, QEvent

from sprintify.navigation.colors.modes import ColorMap
from sprintify.navigation.rulers import ItemRuler
from sprintify.navigation.navigation_widget import NavigationWidget
from sprintify.navigation.interaction.interaction_item import InteractiveItem
from sprintify.navigation.interaction.selection import InteractionHandler


class Article:
    """Represents an article/product with sales data."""

    def __init__(self, article_id: int, name: str, category: str):
        self.id = article_id
        self.name = name
        self.category = category
        self.sales_pattern = None  # Will be numpy array

    def generate_sales_pattern_fast(self, days=365):
        """Generate sales pattern using vectorized operations."""
        # Base pattern with seasonality
        base_level = random.uniform(50, 200)
        seasonality_amplitude = random.uniform(20, 80)
        trend = random.uniform(-0.5, 0.5)
        noise_level = random.uniform(5, 20)

        # Vectorized calculation
        day_array = np.arange(days)
        seasonal = seasonality_amplitude * np.sin(2 * np.pi * day_array / 365)
        trend_component = trend * day_array
        noise = np.random.uniform(-noise_level, noise_level, days)
        weekly = np.where(day_array % 7 >= 5, -10, 0)

        sales = base_level + seasonal + trend_component + weekly + noise
        self.sales_pattern = np.maximum(0, sales)


def calculate_correlation_matrix_fast(articles):
    """Calculate correlation matrix using NumPy for speed."""
    n = len(articles)

    # Stack all sales patterns into a matrix
    sales_matrix = np.array([a.sales_pattern for a in articles])

    # Calculate correlation matrix using NumPy
    # Transpose so each column is an article
    sales_T = sales_matrix.T

    # Standardize each column (article)
    means = np.mean(sales_T, axis=0)
    stds = np.std(sales_T, axis=0)

    # Avoid division by zero
    stds[stds == 0] = 1

    standardized = (sales_T - means) / stds

    # Calculate correlation matrix
    correlation_matrix = np.dot(standardized.T, standardized) / (sales_T.shape[0] - 1)

    # Ensure diagonal is exactly 1 and clamp to [-1, 1]
    np.fill_diagonal(correlation_matrix, 1.0)
    correlation_matrix = np.clip(correlation_matrix, -1, 1)

    return correlation_matrix


def create_correlated_articles_fast(base_pattern, correlation_strength, article_id, name, category="Mixed"):
    """Create article with correlated pattern using vectorized operations."""
    new_article = Article(article_id, name, category)

    noise_factor = math.sqrt(max(0, 1 - correlation_strength ** 2))

    # Generate correlated pattern using vectorized operations
    independent_pattern = np.random.uniform(0, 200, len(base_pattern))
    correlated_pattern = correlation_strength * base_pattern + noise_factor * independent_pattern
    new_article.sales_pattern = np.maximum(0, correlated_pattern)

    return new_article


@dataclass
class HeatmapCell:
    """Data for a single heatmap cell."""
    row_idx: int
    col_idx: int
    row_article: Article
    col_article: Article
    correlation: float


class CorrelationHeatmapWindow(QMainWindow):
    def __init__(self, articles=None):
        super().__init__()
        self.articles = articles or []
        self.setWindowTitle("Article Correlation Heatmap")
        self.setMinimumSize(1000, 800)

        self.color_map = ColorMap(darkmode=True)

        # Show progress dialog for large datasets
        progress = None
        if len(self.articles) > 100:
            progress = QProgressDialog("Calculating correlations...", None, 0, 100, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
            progress.setValue(10)

        # Pre-calculate correlation matrix using fast vectorized method
        self.correlation_matrix = calculate_correlation_matrix_fast(self.articles)

        if progress:
            progress.setValue(90)

        # Create ItemRulers for both axes
        self.h_ruler = ItemRuler(
            item_count=len(self.articles),
            length=1200,
            default_pixels_per_item=40 if len(self.articles) < 100 else 10,
            min_pixels_per_item=3,
            max_pixels_per_item=200
        )

        self.v_ruler = ItemRuler(
            item_count=len(self.articles),
            length=1200,
            default_pixels_per_item=40 if len(self.articles) < 100 else 10,
            min_pixels_per_item=3,
            max_pixels_per_item=200
        )

        # Create navigation widget
        self.widget = NavigationWidget(self.h_ruler, self.v_ruler, self.color_map)
        self.widget.left_ruler_widget.get_label = lambda i: self.articles[i].name if i < len(self.articles) else ""
        self.widget.top_ruler_widget.get_label = lambda i: self.articles[i].name if i < len(self.articles) else ""

        self.setCentralWidget(self.widget)

        # For large grids, use direct drawing instead of interactive items
        self.use_direct_drawing = len(self.articles) > 50

        if self.use_direct_drawing:
            # Register direct drawing command for the heatmap
            self.widget.canvas.add_draw_command("heatmap", self._draw_heatmap_direct)
            # Still enable mouse tracking for tooltips
            self.widget.canvas.viewport().setMouseTracking(True)
            self.widget.canvas.viewport().installEventFilter(self)
        else:
            # Use interactive items for smaller grids - simplified setup
            self.interaction = InteractionHandler(
                self.widget.canvas,
                xr=self.h_ruler,
                yr=self.v_ruler,
            )

            # Simply disable interaction - the core API handles this better now
            self.interaction.can_drop = lambda items: False  # No drag/drop
            self.interaction.draw_custom_item = self._draw_heatmap_cell
            self.interaction.show_tooltips = True

            self._create_heatmap_items()

        if progress:
            progress.setValue(100)
            progress.close()

    def _get_color_for_correlation(self, correlation: float) -> QColor:
        """Map correlation value [-1, 1] to a color gradient."""
        # Map correlation to [0, 1] range
        normalized = (correlation + 1.0) / 2.0

        # Create gradient: blue (negative) -> white (zero) -> red (positive)
        if normalized < 0.5:
            # Blue to White
            t = normalized * 2
            return QColor(
                int(0 + 255 * t),
                int(0 + 255 * t),
                255
            )
        else:
            # White to Red
            t = (normalized - 0.5) * 2
            return QColor(
                255,
                int(255 * (1 - t)),
                int(255 * (1 - t))
            )

    def _draw_heatmap_direct(self, painter: QPainter):
        """Direct drawing method for large heatmaps."""
        # Get visible range
        col_start = max(0, int(self.h_ruler.visible_start))
        col_end = min(len(self.articles), int(self.h_ruler.visible_stop) + 1)
        row_start = max(0, int(self.v_ruler.visible_start))
        row_end = min(len(self.articles), int(self.v_ruler.visible_stop) + 1)

        # Draw only visible cells
        for row_idx in range(row_start, row_end):
            for col_idx in range(col_start, col_end):
                correlation = self.correlation_matrix[row_idx, col_idx]

                # Calculate pixel rectangle
                x1 = self.h_ruler.transform(col_idx)
                x2 = self.h_ruler.transform(col_idx + 1)
                y1 = self.v_ruler.transform(row_idx)
                y2 = self.v_ruler.transform(row_idx + 1)
                rect = QRectF(x1, y1, x2 - x1, y2 - y1)

                # Draw cell
                color = self._get_color_for_correlation(correlation)
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(self.color_map.get_object_color("border"), 0.5))
                painter.drawRect(rect)

                # Draw text only if cell is large enough
                if rect.width() > 30 and rect.height() > 20:
                    font = QFont()
                    font.setPointSize(8 if rect.width() > 60 else 7)
                    painter.setFont(font)

                    text_color = Qt.GlobalColor.black if correlation > -0.2 else Qt.GlobalColor.white
                    painter.setPen(QPen(text_color))

                    text = f"{correlation:.2f}"
                    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def eventFilter(self, source, event):
        """Handle tooltips for direct drawing mode."""
        if self.use_direct_drawing and source == self.widget.canvas.viewport():
            if event.type() == QEvent.Type.MouseMove:
                pos = event.position()
                col = int(self.h_ruler.get_value_at(pos.x()))
                row = int(self.v_ruler.get_value_at(pos.y()))

                if 0 <= row < len(self.articles) and 0 <= col < len(self.articles):
                    correlation = self.correlation_matrix[row, col]
                    tooltip = (
                        f"{self.articles[row].name} vs {self.articles[col].name}\n"
                        f"Correlation: {correlation:.3f}"
                    )
                    QToolTip.showText(event.globalPosition().toPoint(), tooltip, self.widget.canvas.viewport())
                else:
                    QToolTip.hideText()
                # Don't consume the event, let other handlers process it too
                return False

        return super().eventFilter(source, event)

    def _create_heatmap_items(self):
        """Create InteractiveItems for small grids only (read-only with tooltips)."""
        from sprintify.navigation.interaction.interaction_item import ItemCapabilities

        for row_idx in range(len(self.articles)):
            for col_idx in range(len(self.articles)):
                cell_data = HeatmapCell(
                    row_idx=row_idx,
                    col_idx=col_idx,
                    row_article=self.articles[row_idx],
                    col_article=self.articles[col_idx],
                    correlation=self.correlation_matrix[row_idx, col_idx]
                )

                # Simplified item creation using new capabilities pattern
                item = InteractiveItem(
                    data=cell_data,
                    x=float(col_idx),
                    y=float(row_idx),
                    width=1.0,
                    height=1.0,
                    capabilities=ItemCapabilities(
                        can_move=False,
                        can_resize=False,
                        resize_handles=set()  # No resize handles
                    ),
                    # Tooltip using the standard pattern
                    tooltip=(
                        f"{cell_data.row_article.name} vs {cell_data.col_article.name}\n"
                        f"Correlation: {cell_data.correlation:.3f}"
                    )
                )

                # Set visuals directly
                item.visuals.fill_color = self._get_color_for_correlation(cell_data.correlation)
                item.visuals.stroke_color = self.color_map.get_object_color("border")
                item.visuals.stroke_width = 0.5

                self.interaction.add_item(item)

    def _draw_heatmap_cell(self, painter: QPainter, item: InteractiveItem, rect: QRectF):
        """Custom drawing for heatmap cells (small grids only)."""
        cell_data = item.data

        color = self._get_color_for_correlation(cell_data.correlation)
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(self.color_map.get_object_color("border"), 0.5))
        painter.drawRect(rect)

        if rect.width() > 30:
            font = QFont()
            font.setPointSize(8 if rect.width() > 60 else 7)
            painter.setFont(font)

            text_color = Qt.GlobalColor.black if cell_data.correlation > -0.2 else Qt.GlobalColor.white
            painter.setPen(QPen(text_color))

            text = f"{cell_data.correlation:.2f}"
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    # Fast generation of 1000 products
    articles = []

    print("Generating 1000 products with sales patterns...")

    # Create base articles for different clusters
    num_clusters = 20
    cluster_bases = []

    for i in range(num_clusters):
        base = Article(i, f"Base-{i}", f"Category-{i % 5}")
        base.generate_sales_pattern_fast()
        articles.append(base)
        cluster_bases.append(base)

    # Generate correlated products for each cluster
    article_id = num_clusters
    for base in cluster_bases:
        # Generate 10-80 correlated products per cluster
        num_products = random.randint(10, 80)
        for _ in range(num_products):
            correlation = random.uniform(0.3, 0.95)
            article = create_correlated_articles_fast(
                base.sales_pattern,
                correlation,
                article_id,
                f"P-{article_id}",
                base.category
            )
            articles.append(article)
            article_id += 1

            if article_id >= 1000:
                break
        if article_id >= 1000:
            break

    # Fill remaining with independent products
    while len(articles) < 1000:
        article = Article(article_id, f"P-{article_id}", f"Category-{article_id % 5}")
        article.generate_sales_pattern_fast()
        articles.append(article)
        article_id += 1

    print(f"Generated {len(articles)} products")

    app = QApplication(sys.argv)
    window = CorrelationHeatmapWindow(articles[:1000])  # Limit to 1000
    window.show()
    sys.exit(app.exec())
