"""Tests for network traffic tracking."""

import pytest
import requests
from requests.structures import NetworkTraffic


class TestNetworkTraffic:
    """Test NetworkTraffic class functionality."""

    def test_network_traffic_creation(self):
        """Test creating NetworkTraffic objects."""
        traffic = NetworkTraffic(upload=100, download=200)
        assert traffic.upload == 100
        assert traffic.download == 200

    def test_network_traffic_default_values(self):
        """Test NetworkTraffic with default values."""
        traffic = NetworkTraffic()
        assert traffic.upload == 0
        assert traffic.download == 0

    def test_network_traffic_repr(self):
        """Test NetworkTraffic string representation."""
        traffic = NetworkTraffic(upload=100, download=200)
        assert repr(traffic) == "NetworkTraffic(upload=100, download=200)"

    def test_network_traffic_addition(self):
        """Test adding two NetworkTraffic objects."""
        traffic1 = NetworkTraffic(upload=100, download=200)
        traffic2 = NetworkTraffic(upload=50, download=150)
        result = traffic1 + traffic2
        assert result.upload == 150
        assert result.download == 350

    def test_network_traffic_iadd(self):
        """Test in-place addition of NetworkTraffic objects."""
        traffic1 = NetworkTraffic(upload=100, download=200)
        traffic2 = NetworkTraffic(upload=50, download=150)
        traffic1 += traffic2
        assert traffic1.upload == 150
        assert traffic1.download == 350


class TestTrafficTracking:
    """Test traffic tracking in requests."""

    def test_response_has_traffic_attribute(self, httpbin):
        """Test that Response objects have a traffic attribute."""
        r = requests.get(httpbin("get"))
        assert hasattr(r, "traffic")
        assert isinstance(r.traffic, NetworkTraffic)

    def test_traffic_has_positive_values(self, httpbin):
        """Test that traffic values are positive for successful requests."""
        r = requests.get(httpbin("get"))
        assert r.traffic.upload > 0
        assert r.traffic.download > 0

    def test_post_request_traffic(self, httpbin):
        """Test traffic tracking for POST requests."""
        data = {"key": "value", "number": 1}
        r = requests.post(httpbin("post"), json=data)
        assert r.traffic.upload > 0
        assert r.traffic.download > 0
        # POST requests should have larger upload due to body
        assert r.traffic.upload > 100  # At least some reasonable size

    def test_total_traffic_tracking(self, httpbin):
        """Test that total_traffic accumulates across requests."""
        # Reset total_traffic before test
        requests.total_traffic = NetworkTraffic()
        
        # Make first request
        r1 = requests.get(httpbin("get"))
        traffic_after_r1 = NetworkTraffic(
            upload=requests.total_traffic.upload,
            download=requests.total_traffic.download
        )
        
        # Make second request
        r2 = requests.get(httpbin("get"))
        
        # Total traffic should be sum of both requests
        assert requests.total_traffic.upload == traffic_after_r1.upload + r2.traffic.upload
        assert requests.total_traffic.download == traffic_after_r1.download + r2.traffic.download

    def test_traffic_with_headers(self, httpbin):
        """Test that traffic includes custom headers."""
        headers = {"Authorization": "Bearer test123", "Custom-Header": "custom-value"}
        r = requests.get(httpbin("get"), headers=headers)
        # Verify traffic is tracked
        assert r.traffic.upload > 0
        assert r.traffic.download > 0

    def test_traffic_with_query_params(self, httpbin):
        """Test traffic tracking with query parameters."""
        params = {"param1": "value1", "param2": "value2"}
        r = requests.get(httpbin("get"), params=params)
        assert r.traffic.upload > 0
        assert r.traffic.download > 0

    def test_response_traffic_in_session(self, httpbin):
        """Test that traffic tracking works with sessions."""
        session = requests.Session()
        r1 = session.get(httpbin("get"))
        r2 = session.get(httpbin("get"))
        
        # Both requests should have traffic data
        assert r1.traffic.upload > 0
        assert r1.traffic.download > 0
        assert r2.traffic.upload > 0
        assert r2.traffic.download > 0

    def test_traffic_preserved_in_history(self, httpbin):
        """Test that redirected responses preserve traffic information."""
        # Make a request that redirects
        r = requests.get(httpbin("redirect", "1"), allow_redirects=True)
        
        # Final response should have traffic
        assert r.traffic.upload > 0
        assert r.traffic.download > 0
        
        # Historical responses should also have traffic
        if r.history:
            for historical_response in r.history:
                assert hasattr(historical_response, "traffic")
                assert isinstance(historical_response.traffic, NetworkTraffic)
