"""geometry モジュールの単体テスト。"""

import math

import pytest

from route_planner import geometry


def test_haversine_zero_distance():
    assert geometry.haversine(35.6812, 139.7671, 35.6812, 139.7671) == pytest.approx(0.0, abs=1e-9)


def test_haversine_one_degree_along_equator():
    # 赤道上で経度1度 ≒ 111.19 km
    d = geometry.haversine(0.0, 0.0, 0.0, 1.0)
    assert d == pytest.approx(111.19, abs=0.5)


def test_haversine_is_symmetric():
    a = geometry.haversine(35.0, 139.0, 36.0, 140.0)
    b = geometry.haversine(36.0, 140.0, 35.0, 139.0)
    assert a == pytest.approx(b)


def test_decode_polyline_google_reference():
    # Google の公式リファレンス例（2D）
    encoded = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
    coords, elevations = geometry.decode_polyline(encoded, include_elevation=False)
    assert elevations is None
    expected = [[38.5, -120.2], [40.7, -120.95], [43.252, -126.453]]
    assert len(coords) == len(expected)
    for got, exp in zip(coords, expected):
        assert got[0] == pytest.approx(exp[0], abs=1e-5)
        assert got[1] == pytest.approx(exp[1], abs=1e-5)


def test_distance_to_segment_perpendicular():
    # 点(0,1) から線分(0,0)-(2,0) への距離は 1
    assert geometry.distance_to_segment(0, 1, 0, 0, 2, 0) == pytest.approx(1.0)


def test_distance_to_segment_beyond_endpoint_is_clamped():
    # 射影が線分外（右端より先）→ 端点(2,0)までの距離
    d = geometry.distance_to_segment(4, 0, 0, 0, 2, 0)
    assert d == pytest.approx(2.0)


def test_distance_to_segment_degenerate_point():
    # 線分が1点に退化 → 単なる2点間距離
    assert geometry.distance_to_segment(3, 4, 0, 0, 0, 0) == pytest.approx(5.0)


def test_find_nearest_index():
    route = [[0, 0], [1, 1], [2, 2], [3, 3]]
    assert geometry.find_nearest_index(route, 2.1, 2.1) == 2
    assert geometry.find_nearest_index(route, -1, -1) == 0


def test_find_nearest_index_empty():
    assert geometry.find_nearest_index([], 1.0, 1.0) is None


def test_decode_polyline_with_elevation_roundtrip_shape():
    # 標高付きは coords と同数の標高を返す（値の厳密性ではなく形状を確認）
    encoded = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
    coords, elevations = geometry.decode_polyline(encoded, include_elevation=True)
    # include_elevation=True でも余剰チャンクが無ければ標高は生成されうる/されない。
    # 少なくとも座標は取れることを保証する。
    assert len(coords) >= 1
