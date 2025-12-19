"""
stock_app.py

This example demonstrates stock market visualization using real data from Yahoo Finance.
Features:
- Price line chart for each stock (blue)
- 20-day moving average (orange)
- RSI highlighting: red rectangles for overbought (RSI > 70), green for oversold (RSI < 30)
- One row per stock using ItemRuler
- TimelineRuler for date navigation
- Parallel data downloading for faster startup

Requirements:
    pip install yfinance
"""
from datetime import datetime, timedelta
import yfinance as yf
from PySide6.QtGui import QBrush, QPen, QColor
from PySide6.QtWidgets import QMainWindow
from PySide6.QtCore import Qt
from concurrent.futures import ThreadPoolExecutor, as_completed

from sprintify.navigation.colors.modes import ColorMap
from sprintify.navigation.rulers import TimelineRuler, ItemRuler
from sprintify.navigation.navigation_widget import NavigationWidget


class Stock:
    """Represents a stock with price history and technical indicators."""

    def __init__(self, ticker: str):
        self.ticker = ticker
        self.dates = []
        self.prices = []
        self.ma20 = []  # 20-day moving average
        self.rsi = []   # RSI values

    def fetch_data(self, start_date: datetime, end_date: datetime):
        """Fetch stock data from Yahoo Finance and calculate indicators."""
        try:
            stock = yf.Ticker(self.ticker)
            df = stock.history(start=start_date, end=end_date)

            if df.empty:
                print(f"No data for {self.ticker}")
                return False

            # Convert timezone-aware datetimes to timezone-naive
            self.dates = [dt.replace(tzinfo=None) for dt in df.index.to_pydatetime().tolist()]
            self.prices = df['Close'].tolist()

            # Calculate 20-day moving average
            self.ma20 = self._calculate_ma(self.prices, 20)

            # Calculate RSI
            self.rsi = self._calculate_rsi(self.prices, 14)

            return True
        except Exception as e:
            print(f"Error fetching {self.ticker}: {e}")
            return False

    def _calculate_ma(self, prices, period):
        """Calculate simple moving average."""
        ma = []
        for i in range(len(prices)):
            if i < period - 1:
                ma.append(None)
            else:
                ma.append(sum(prices[i-period+1:i+1]) / period)
        return ma

    def _calculate_rsi(self, prices, period=14):
        """Calculate Relative Strength Index."""
        if len(prices) < period + 1:
            return [None] * len(prices)

        rsi = [None] * period
        gains = []
        losses = []

        # Calculate price changes
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(max(0, change))
            losses.append(max(0, -change))

        # Calculate initial average gain/loss
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        # Calculate first RSI
        if avg_loss == 0:
            rsi.append(100)
        else:
            rs = avg_gain / avg_loss
            rsi.append(100 - (100 / (1 + rs)))

        # Calculate remaining RSI values using smoothed averages
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss == 0:
                rsi.append(100)
            else:
                rs = avg_gain / avg_loss
                rsi.append(100 - (100 / (1 + rs)))

        return rsi

    def get_price_points(self, visible_start: datetime, visible_end: datetime):
        """Return price line points within visible range, including one point before and after."""
        points = []
        found_first = False

        for i, (date, price) in enumerate(zip(self.dates, self.prices)):
            if price is None:
                continue

            # Include one point before visible range
            if not found_first and date >= visible_start:
                found_first = True
                # Add previous point if it exists
                if i > 0 and self.prices[i-1] is not None:
                    points.append((self.dates[i-1], self.prices[i-1]))

            if date >= visible_start and date <= visible_end:
                points.append((date, price))

            # Include one point after visible range, then stop
            if date > visible_end:
                points.append((date, price))
                break

        return points

    def get_ma20_points(self, visible_start: datetime, visible_end: datetime):
        """Return MA20 line points within visible range, including one point before and after."""
        points = []
        found_first = False

        for i, (date, ma) in enumerate(zip(self.dates, self.ma20)):
            if ma is None:
                continue

            # Include one point before visible range
            if not found_first and date >= visible_start:
                found_first = True
                # Add previous point if it exists
                if i > 0 and self.ma20[i-1] is not None:
                    points.append((self.dates[i-1], self.ma20[i-1]))

            if date >= visible_start and date <= visible_end:
                points.append((date, ma))

            # Include one point after visible range, then stop
            if date > visible_end:
                points.append((date, ma))
                break

        return points

    def get_rsi_highlights(self, visible_start: datetime, visible_end: datetime):
        """Return periods where RSI is overbought (>70) or oversold (<30)."""
        overbought = []  # RSI > 70
        oversold = []    # RSI < 30

        in_overbought = False
        in_oversold = False
        ob_start = None
        os_start = None

        for i, (date, rsi_val) in enumerate(zip(self.dates, self.rsi)):
            if date < visible_start:
                continue
            if date > visible_end:
                break

            if rsi_val is None:
                continue

            # Check overbought (RSI > 70)
            if rsi_val > 70 and not in_overbought:
                in_overbought = True
                ob_start = date
            elif rsi_val <= 70 and in_overbought:
                in_overbought = False
                if ob_start:
                    overbought.append((ob_start, date))
                ob_start = None

            # Check oversold (RSI < 30)
            if rsi_val < 30 and not in_oversold:
                in_oversold = True
                os_start = date
            elif rsi_val >= 30 and in_oversold:
                in_oversold = False
                if os_start:
                    oversold.append((os_start, date))
                os_start = None

        # Close any open periods
        if in_overbought and ob_start:
            overbought.append((ob_start, visible_end))
        if in_oversold and os_start:
            oversold.append((os_start, visible_end))

        return overbought, oversold

    def get_price_range(self):
        """Get min and max price for normalization."""
        valid_prices = [p for p in self.prices if p is not None]
        valid_ma = [m for m in self.ma20 if m is not None]
        all_values = valid_prices + valid_ma

        if not all_values:
            return 0, 100

        return min(all_values), max(all_values)


class StockMarketWindow(QMainWindow):
    def __init__(self, stocks=None, start_date=None, end_date=None):
        super().__init__()
        self.stocks = stocks or []
        self.setWindowTitle("Stock Market Dashboard")
        self.setMinimumSize(1400, 900)

        self.color_map = ColorMap(darkmode=True)

        # Colors for visualization
        self.price_color = self.color_map.get_saturated_color('blue', 'border')
        self.ma_color = self.color_map.get_saturated_color('orange', 'border')
        self.overbought_color = QColor(self.color_map.get_saturated_color('red', 'fill'))
        self.overbought_color.setAlpha(60)
        self.oversold_color = QColor(self.color_map.get_saturated_color('green', 'fill'))
        self.oversold_color.setAlpha(60)

        # Create rulers
        self.time_ruler = TimelineRuler(start_date, end_date, length=1400)
        self.stock_ruler = ItemRuler(
            item_count=len(self.stocks),
            length=900,
            default_pixels_per_item=40,
            min_pixels_per_item=20,
            max_pixels_per_item=150
        )

        # Create navigation widget
        self.widget = NavigationWidget(self.time_ruler, self.stock_ruler, self.color_map)
        self.widget.left_ruler_widget.get_label = self._get_stock_label

        self.setCentralWidget(self.widget)

        # Draw visualizations
        self.draw_rsi_highlights()
        self.draw_ma20_lines()
        self.draw_price_lines()

    def _get_stock_label(self, item_index: int):
        """Generate label for each stock row."""
        if item_index >= len(self.stocks):
            return ""
        return self.stocks[item_index].ticker

    def draw_rsi_highlights(self):
        """Draw rectangles for overbought/oversold RSI periods."""
        def draw_rsi_rects(painter):
            painter.setPen(Qt.PenStyle.NoPen)

            visible_time_start = self.time_ruler.visible_start
            visible_time_stop = self.time_ruler.visible_stop

            first_item = int(self.stock_ruler.visible_start)
            last_item = min(len(self.stocks), int(self.stock_ruler.visible_stop) + 1)

            for item_index in range(first_item, last_item):
                stock = self.stocks[item_index]
                overbought, oversold = stock.get_rsi_highlights(visible_time_start, visible_time_stop)

                y1 = self.stock_ruler.transform(float(item_index) + 0.05)
                y2 = self.stock_ruler.transform(float(item_index) + 0.95)

                # Draw overbought periods (red)
                painter.setBrush(QBrush(self.overbought_color))
                for period_start, period_end in overbought:
                    x1 = self.time_ruler.transform(period_start)
                    x2 = self.time_ruler.transform(period_end)
                    painter.drawRect(x1, y1, x2 - x1, y2 - y1)

                # Draw oversold periods (green)
                painter.setBrush(QBrush(self.oversold_color))
                for period_start, period_end in oversold:
                    x1 = self.time_ruler.transform(period_start)
                    x2 = self.time_ruler.transform(period_end)
                    painter.drawRect(x1, y1, x2 - x1, y2 - y1)

        self.widget.add_draw_command("rsi_highlights", draw_rsi_rects)

    def draw_price_lines(self):
        """Draw price line graphs for each stock."""
        def draw_lines(painter):
            visible_time_start = self.time_ruler.visible_start
            visible_time_stop = self.time_ruler.visible_stop

            first_item = int(self.stock_ruler.visible_start)
            last_item = min(len(self.stocks), int(self.stock_ruler.visible_stop) + 1)

            painter.setPen(QPen(self.price_color, 2))

            for item_index in range(first_item, last_item):
                stock = self.stocks[item_index]
                points = stock.get_price_points(visible_time_start, visible_time_stop)

                if len(points) < 2:
                    continue

                # Get price range for this stock
                min_price, max_price = stock.get_price_range()
                price_range = max_price - min_price
                if price_range == 0:
                    price_range = 1

                # Calculate row boundaries
                y_top = self.stock_ruler.transform(float(item_index) + 0.05)
                y_bottom = self.stock_ruler.transform(float(item_index) + 0.95)
                row_height = y_bottom - y_top

                # Draw line segments
                for i in range(len(points) - 1):
                    date1, price1 = points[i]
                    date2, price2 = points[i + 1]

                    x1 = self.time_ruler.transform(date1)
                    x2 = self.time_ruler.transform(date2)

                    # Normalize prices to row height
                    y1 = y_top + row_height * (1 - (price1 - min_price) / price_range)
                    y2 = y_top + row_height * (1 - (price2 - min_price) / price_range)

                    painter.drawLine(x1, y1, x2, y2)

        self.widget.add_draw_command("price_lines", draw_lines)

    def draw_ma20_lines(self):
        """Draw 20-day moving average lines."""
        def draw_lines(painter):
            visible_time_start = self.time_ruler.visible_start
            visible_time_stop = self.time_ruler.visible_stop

            first_item = int(self.stock_ruler.visible_start)
            last_item = min(len(self.stocks), int(self.stock_ruler.visible_stop) + 1)

            painter.setPen(QPen(self.ma_color, 1.5))

            for item_index in range(first_item, last_item):
                stock = self.stocks[item_index]
                points = stock.get_ma20_points(visible_time_start, visible_time_stop)

                if len(points) < 2:
                    continue

                # Get price range for this stock
                min_price, max_price = stock.get_price_range()
                price_range = max_price - min_price
                if price_range == 0:
                    price_range = 1

                # Calculate row boundaries
                y_top = self.stock_ruler.transform(float(item_index) + 0.05)
                y_bottom = self.stock_ruler.transform(float(item_index) + 0.95)
                row_height = y_bottom - y_top

                # Draw line segments
                for i in range(len(points) - 1):
                    date1, ma1 = points[i]
                    date2, ma2 = points[i + 1]

                    x1 = self.time_ruler.transform(date1)
                    x2 = self.time_ruler.transform(date2)

                    # Normalize MA to row height
                    y1 = y_top + row_height * (1 - (ma1 - min_price) / price_range)
                    y2 = y_top + row_height * (1 - (ma2 - min_price) / price_range)

                    painter.drawLine(x1, y1, x2, y2)

        self.widget.add_draw_command("ma20_lines", draw_lines)
        self.widget.update()


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    # Popular stock tickers
    tickers = [
        # Tech
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'AMD', 'INTC', 'NFLX',
        # Finance
        'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'BLK', 'SCHW', 'AXP', 'V',
        # Consumer
        'WMT', 'HD', 'NKE', 'MCD', 'SBUX', 'DIS', 'COST', 'TGT', 'LOW', 'PG',
        # Healthcare
        'JNJ', 'UNH', 'PFE', 'ABBV', 'MRK', 'TMO', 'ABT', 'LLY', 'BMY', 'CVS',
        # Energy & Industrial
        'XOM', 'CVX', 'COP', 'BA', 'CAT', 'GE', 'MMM', 'HON', 'UPS', 'RTX'
    ]

    start_date = datetime(2023, 1, 1)
    end_date = datetime.now()

    print("Fetching stock data in parallel...")

    def fetch_stock(ticker):
        """Helper function to fetch a single stock's data."""
        stock = Stock(ticker)
        if stock.fetch_data(start_date, end_date):
            return stock
        return None

    stocks = []

    # Use ThreadPoolExecutor to download data in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all fetch tasks
        future_to_ticker = {executor.submit(fetch_stock, ticker): ticker for ticker in tickers}

        # Process results as they complete
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                stock = future.result()
                if stock:
                    stocks.append(stock)
                    print(f"✓ {ticker} ({len(stocks)}/{len(tickers)})")
                else:
                    print(f"✗ {ticker} - no data")
            except Exception as e:
                print(f"✗ {ticker} - error: {e}")

    print(f"\nSuccessfully loaded {len(stocks)} stocks")

    app = QApplication(sys.argv)
    window = StockMarketWindow(stocks, start_date=start_date, end_date=end_date)
    window.show()
    sys.exit(app.exec())
