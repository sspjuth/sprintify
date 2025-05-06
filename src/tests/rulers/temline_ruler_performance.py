import timeit
from datetime import datetime, timedelta
from sprintify.navigation.rulers.timeline import TimelineRuler

# Setup for TimelineRuler
window_start = datetime(2024, 4, 1)
window_stop = datetime(2024, 5, 1)
visible_start = datetime(2024, 4, 10)
visible_stop = datetime(2024, 4, 20)
widget_width = 800

timeline_ruler = TimelineRuler(window_start, window_stop, visible_start, visible_stop)

# Benchmarking functions
def benchmark_transform():
    return timeline_ruler.transform(datetime(2024, 4, 15), widget_width)

def benchmark_reverse_transform():
    return timeline_ruler.get_value_at(400, widget_width)

def benchmark_get_value_delta():
    return timeline_ruler.get_delta_width(100, widget_width)

# Running benchmarks
iterations = 100000

transform_time = timeit.timeit(benchmark_transform, number=iterations)
reverse_transform_time = timeit.timeit(benchmark_reverse_transform, number=iterations)
get_value_delta_time = timeit.timeit(benchmark_get_value_delta, number=iterations)

print(f"transform: {transform_time:.6f} seconds")
print(f"reverse_transform: {reverse_transform_time:.6f} seconds")
print(f"get_value_delta: {get_value_delta_time:.6f} seconds")