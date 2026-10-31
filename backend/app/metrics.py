from prometheus_client import Counter, Gauge, Histogram


SOCKET_CONNECTIONS = Gauge(
    "bantr_socket_connections", "Open Socket.IO connections on this process"
)
MESSAGES_SENT = Counter("bantr_messages_sent", "Messages accepted and stored")
CACHE_REQUESTS = Counter(
    "bantr_message_cache_requests",
    "Channel-open reads by cache result",
    ["result"],  # hit | miss | error
)
HTTP_REQUESTS = Counter(
    "bantr_http_requests", "HTTP requests", ["method", "route", "status"]
)
HTTP_LATENCY = Histogram(
    "bantr_http_request_seconds",
    "HTTP request latency in seconds",
    ["route"],
    buckets=(0.002, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5),
)


def cache_result(result: str) -> None:
    CACHE_REQUESTS.labels(result=result).inc()