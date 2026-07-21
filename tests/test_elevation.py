"""elevation モジュールの単体テスト。"""

import numpy as np
import pytest

from route_planner import elevation


def test_route_statistics_basic():
    # distances(km): [0,1,2], elevations(m): [0,10,5]
    s = elevation.route_statistics([0, 1, 2], [0, 10, 5])
    assert s["distance"] == pytest.approx(2.0)
    assert s["gain"] == pytest.approx(10.0)
    assert s["loss"] == pytest.approx(5.0)
    # 斜度: 区間1 = 10m / 1000m = 1.0%, 区間2 = -5m / 1000m = -0.5%
    assert s["max_slope"] == pytest.approx(1.0)
    assert s["avg_slope"] == pytest.approx(0.25)


def test_route_statistics_too_short_returns_none():
    assert elevation.route_statistics([0], [0]) is None
    assert elevation.route_statistics([], []) is None


def test_calculate_slopes_short_array_raw():
    # 既定 window=50 より短い → 生の区間斜度を返す
    slopes = elevation.calculate_slopes([0, 1], [0, 10])
    assert isinstance(slopes, np.ndarray)
    assert slopes[0] == pytest.approx(0.0)
    assert slopes[1] == pytest.approx(1.0)  # 10m / 1000m * 100


def test_calculate_slopes_flat_is_zero():
    n = 100
    distances = list(np.linspace(0, 10, n))
    elevations = [50.0] * n
    slopes = elevation.calculate_slopes(distances, elevations)
    assert np.allclose(slopes, 0.0, atol=1e-9)


def test_correct_bridge_elevations_fills_dip():
    # 平坦な50mの中央に深い落ち込み（橋/トンネル異常）を作る
    n = 200
    distances = list(np.linspace(0, 20, n))
    elevations = [50.0] * n
    for i in range(100, 106):
        elevations[i] = 0.0

    corrected, count = elevation.correct_bridge_elevations(distances, elevations)

    assert count > 0
    # 補正後、落ち込み区間はおよそ50m近傍に戻る
    for i in range(100, 106):
        assert corrected[i] == pytest.approx(50.0, abs=5.0)


def test_correct_bridge_elevations_noop_on_flat():
    distances = [0, 1, 2, 3]
    elevations = [10.0, 10.0, 10.0, 10.0]
    corrected, count = elevation.correct_bridge_elevations(distances, elevations)
    assert count == 0
    assert corrected == elevations


def test_correct_bridge_elevations_too_short():
    corrected, count = elevation.correct_bridge_elevations([0, 1], [5, 6])
    assert count == 0
    assert corrected == [5, 6]


def test_latlng_to_distance_region():
    route = [[0, 0], [0, 1], [0, 2], [0, 3]]
    distances = [0.0, 1.0, 2.0, 3.0]
    region_latlng = ((0, 0.9), (0, 2.1))  # ≒ index1..index2
    lo, hi = elevation.latlng_to_distance_region(route, region_latlng, distances)
    assert lo == pytest.approx(1.0)
    assert hi == pytest.approx(2.0)


def test_latlng_to_distance_region_orders_indices():
    route = [[0, 0], [0, 1], [0, 2], [0, 3]]
    distances = [0.0, 1.0, 2.0, 3.0]
    # 始点・終点が逆順でも (min, max) に整列される
    region_latlng = ((0, 2.9), (0, 0.1))
    lo, hi = elevation.latlng_to_distance_region(route, region_latlng, distances)
    assert lo == pytest.approx(0.0)
    assert hi == pytest.approx(3.0)


def test_latlng_to_distance_region_empty_route():
    assert elevation.latlng_to_distance_region([], ((0, 0), (0, 1)), []) is None
