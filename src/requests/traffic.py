"""
requests.traffic
~~~~~~~~~~~~~~~~

This module provides traffic (bandwidth) tracking for HTTP requests and responses.
"""

import threading


class TrafficInfo:
    """Holds upload, download and total traffic byte counts for an HTTP exchange."""

    def __init__(self, upload=0, download=0):
        self._upload = upload
        self._download = download

    @property
    def upload(self):
        """Number of bytes uploaded (sent) in the request."""
        return self._upload

    @property
    def download(self):
        """Number of bytes downloaded (received) in the response."""
        return self._download

    @property
    def total(self):
        """Total number of bytes transferred (upload + download)."""
        return self._upload + self._download

    def __repr__(self):
        return (
            f"<TrafficInfo upload={self._upload} "
            f"download={self._download} "
            f"total={self.total}>"
        )


class _GlobalTrafficAccumulator:
    """Thread-safe accumulator for total traffic across all requests."""

    def __init__(self):
        self._upload = 0
        self._download = 0
        self._lock = threading.Lock()

    @property
    def upload(self):
        with self._lock:
            return self._upload

    @property
    def download(self):
        with self._lock:
            return self._download

    @property
    def total(self):
        with self._lock:
            return self._upload + self._download

    def add(self, upload, download):
        with self._lock:
            self._upload += upload
            self._download += download

    def reset(self):
        """Reset the accumulated traffic counters to zero."""
        with self._lock:
            self._upload = 0
            self._download = 0

    def __repr__(self):
        with self._lock:
            return (
                f"<GlobalTraffic upload={self._upload} "
                f"download={self._download} "
                f"total={self._upload + self._download}>"
            )


#: Global traffic accumulator — tracks total bytes across all requests made
#: through the top-level ``requests.*`` convenience functions.
total_traffic = _GlobalTrafficAccumulator()


def _calculate_upload_bytes(prepared_request):
    """Estimate the number of bytes sent for a PreparedRequest.

    Calculates the size of the HTTP request line, headers and body as they
    would appear on the wire (using CRLF line endings per RFC 7230).
    """
    from urllib3.util import parse_url

    url = prepared_request.url
    try:
        parsed = parse_url(url)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
    except Exception:
        path = "/"

    request_line = f"{prepared_request.method} {path} HTTP/1.1\r\n"
    size = len(request_line.encode("utf-8"))

    if prepared_request.headers:
        for name, value in prepared_request.headers.items():
            header_line = f"{name}: {value}\r\n"
            size += len(header_line.encode("utf-8"))

    # End of headers
    size += 2  # \r\n

    body = prepared_request.body
    if body is not None:
        if isinstance(body, bytes):
            size += len(body)
        elif isinstance(body, str):
            size += len(body.encode("utf-8"))
        # generators / file-like objects: size already reflected in
        # Content-Length header if present; we don't double-count.

    return size


def _calculate_download_bytes(response):
    """Estimate the number of bytes received for a Response.

    Calculates the size of the HTTP status line, headers and decoded body as
    they would appear on the wire (using CRLF line endings per RFC 7230).

    For streaming responses (where the body has not yet been consumed), the
    ``Content-Length`` response header is used as a best-effort estimate.
    """
    reason = response.reason or ""
    status_line = f"HTTP/1.1 {response.status_code} {reason}\r\n"
    size = len(status_line.encode("utf-8"))

    for name, value in response.headers.items():
        header_line = f"{name}: {value}\r\n"
        size += len(header_line.encode("utf-8"))

    # End of headers
    size += 2  # \r\n

    if response._content_consumed:
        # Content is already in memory — use exact byte count.
        content = response.content
        if content:
            size += len(content)
    else:
        # Streaming response: body not yet consumed.  Use Content-Length if
        # available so we don't inadvertently drain the socket.
        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            try:
                size += int(content_length)
            except (ValueError, TypeError):
                pass

    return size
