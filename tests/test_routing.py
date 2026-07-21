"""routing モジュールの単体テスト（HTTP はモックする）。"""

import pytest

from route_planner import routing


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text="{}"):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_fetch_route_requires_api_key():
    with pytest.raises(routing.RoutingError):
        routing.fetch_route([(35.0, 139.0, "a"), (36.0, 140.0, "b")], api_key="")


def test_fetch_route_geojson(monkeypatch):
    payload = {
        "routes": [
            {"geometry": {"coordinates": [[139.0, 35.0], [139.1, 35.1]]}}
        ]
    }

    def fake_post(url, json=None, headers=None, timeout=None):
        # [lng, lat] 形式で送っていることを確認
        assert json["coordinates"] == [[139.0, 35.0], [140.0, 36.0]]
        assert headers["Authorization"] == "KEY"
        return _FakeResponse(payload=payload)

    monkeypatch.setattr(routing.requests, "post", fake_post)

    result = routing.fetch_route(
        [(35.0, 139.0, "a"), (36.0, 140.0, "b")], api_key="KEY"
    )
    # GeoJSON は [lng,lat] → [lat,lng] へ変換される
    assert result.coordinates == [[35.0, 139.0], [35.1, 139.1]]
    assert result.elevations is None


def test_fetch_route_http_error(monkeypatch):
    def fake_post(url, json=None, headers=None, timeout=None):
        return _FakeResponse(
            status_code=403,
            payload={"error": {"message": "quota exceeded"}},
            text='{"error": {"message": "quota exceeded"}}',
        )

    monkeypatch.setattr(routing.requests, "post", fake_post)

    with pytest.raises(routing.RoutingError) as excinfo:
        routing.fetch_route([(35.0, 139.0, "a"), (36.0, 140.0, "b")], api_key="KEY")
    assert "403" in str(excinfo.value)


def test_fetch_route_network_error(monkeypatch):
    import requests as _requests

    def fake_post(*args, **kwargs):
        raise _requests.exceptions.ConnectionError("boom")

    monkeypatch.setattr(routing.requests, "post", fake_post)

    with pytest.raises(routing.RoutingError):
        routing.fetch_route([(35.0, 139.0, "a"), (36.0, 140.0, "b")], api_key="KEY")
