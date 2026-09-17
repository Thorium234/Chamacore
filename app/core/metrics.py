"""Minimal Prometheus-exposition HTTP metrics (review follow-up #7).

Dependency-free on purpose so the core stays small: a thread-safe registry
that renders the standard Prometheus text exposition format for counters and
histograms. A future OpenTelemetry migration can replace this implementation
behind the same ``/metrics`` surface.
"""

import threading
import time
from collections.abc import Sequence

from fastapi import Request

_INF = float("inf")


def _format_labels(label_names: Sequence[str], values: Sequence[str]) -> str:
    if not label_names:
        return ""
    parts = ",".join(f'{name}="{value}"' for name, value in zip(label_names, values))
    return "{" + parts + "}"


class Counter:
    def __init__(self, name: str, description: str, label_names: Sequence[str] = ()):
        self.name = name
        self.description = description
        self.label_names = tuple(label_names)
        self._lock = threading.Lock()
        self._values: dict[tuple[str, ...], int] = {}

    def inc(self, label_values: Sequence[str] = (), amount: int = 1) -> None:
        values = tuple(label_values)
        with self._lock:
            self._values[values] = self._values.get(values, 0) + amount

    def reset(self) -> None:
        with self._lock:
            self._values.clear()

    def lines(self) -> list[str]:
        out = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} counter",
        ]
        with self._lock:
            items = sorted(self._values.items())
        for values, count in items:
            out.append(
                f"{self.name}{_format_labels(self.label_names, values)} {count}"
            )
        return out


class Histogram:
    DEFAULT_BUCKETS = (
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
        _INF,
    )

    def __init__(
        self,
        name: str,
        description: str,
        label_names: Sequence[str] = (),
        buckets: Sequence[float] = DEFAULT_BUCKETS,
    ):
        self.name = name
        self.description = description
        self.label_names = tuple(label_names)
        self.buckets = tuple(buckets)
        self._lock = threading.Lock()
        self._counts: dict[tuple[str, ...], int] = {}
        self._sums: dict[tuple[str, ...], float] = {}
        self._bucket_counts: dict[tuple[tuple[str, ...], float], int] = {}

    def observe(self, value: float, label_values: Sequence[str] = ()) -> None:
        values = tuple(label_values)
        with self._lock:
            self._counts[values] = self._counts.get(values, 0) + 1
            self._sums[values] = self._sums.get(values, 0.0) + value
            for bucket in self.buckets:
                if value <= bucket:
                    key = (values, bucket)
                    self._bucket_counts[key] = self._bucket_counts.get(key, 0) + 1

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()
            self._sums.clear()
            self._bucket_counts.clear()

    def lines(self) -> list[str]:
        out = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} histogram",
        ]
        with self._lock:
            label_values = sorted(self._counts)
        for values in label_values:
            labels = _format_labels(self.label_names, values)
            for bucket in self.buckets:
                le = "+Inf" if bucket == _INF else str(bucket)
                count = self._bucket_counts.get((values, bucket), 0)
                bucket_labels = _format_labels(
                    self.label_names + ("le",), values + (le,)
                )
                out.append(f"{self.name}_bucket{bucket_labels} {count}")
            out.append(f"{self.name}_sum{labels} {self._sums[values]}")
            out.append(f"{self.name}_count{labels} {self._counts[values]}")
        return out


class MetricsRegistry:
    def __init__(self) -> None:
        self._metrics: dict[str, Counter | Histogram] = {}
        self._lock = threading.Lock()

    def counter(self, name: str, description: str, label_names: Sequence[str] = ()) -> Counter:
        metric = Counter(name, description, label_names)
        with self._lock:
            self._metrics[name] = metric
        return metric

    def histogram(
        self,
        name: str,
        description: str,
        label_names: Sequence[str] = (),
        buckets: Sequence[float] = Histogram.DEFAULT_BUCKETS,
    ) -> Histogram:
        metric = Histogram(name, description, label_names, buckets)
        with self._lock:
            self._metrics[name] = metric
        return metric

    def reset(self) -> None:
        with self._lock:
            metrics = list(self._metrics.values())
        for metric in metrics:
            metric.reset()

    def render(self) -> str:
        with self._lock:
            metrics = [self._metrics[name] for name in sorted(self._metrics)]
        lines: list[str] = []
        for metric in metrics:
            lines.extend(metric.lines())
        return "\n".join(lines) + "\n"


REGISTRY = MetricsRegistry()

http_requests_total = REGISTRY.counter(
    "chamacore_http_requests_total",
    "HTTP requests handled by route template, method, and status class.",
    ("route", "method", "status"),
)

http_request_duration_seconds = REGISTRY.histogram(
    "chamacore_http_request_duration_seconds",
    "HTTP handler latency in seconds by route template and method.",
    ("route", "method"),
)


def reset_metrics() -> None:
    """Clear recorded metrics so a fresh test case starts empty."""
    REGISTRY.reset()


def _status_class(status_code: int) -> str:
    return f"{status_code // 100}xx"


def _route_label(request: Request) -> str:
    """Return the route template path (e.g. ``/api/v1/chamas/{chama_id}``) so
    metric cardinality stays bounded; fall back to the raw path."""
    endpoint = request.scope.get("endpoint")
    app = getattr(request, "app", None)
    route_paths = getattr(app, "_chamacore_route_paths", None)
    if route_paths is None and app is not None:
        route_paths = {
            route.endpoint: route.path
            for route in app.routes
            if hasattr(route, "endpoint") and hasattr(route, "path")
        }
        try:
            app._chamacore_route_paths = route_paths
        except (TypeError, AttributeError):
            pass
    if endpoint is not None:
        path = (route_paths or {}).get(endpoint)
        if path:
            return path
    return request.url.path


async def request_metrics_middleware(request: Request, call_next):
    started = time.monotonic()
    method = request.method
    try:
        response = await call_next(request)
    except Exception:
        route = _route_label(request)
        http_requests_total.inc((route, method, "5xx"))
        http_request_duration_seconds.observe(time.monotonic() - started, (route, method))
        raise
    else:
        route = _route_label(request)
        http_requests_total.inc((route, method, _status_class(response.status_code)))
        http_request_duration_seconds.observe(time.monotonic() - started, (route, method))
        return response