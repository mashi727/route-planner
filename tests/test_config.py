"""config モジュール（移動手段の定義）の単体テスト。"""

import pytest

from route_planner import config


def test_travel_modes_are_bicycle_and_car():
    keys = [m.key for m in config.TRAVEL_MODES]
    assert keys == ["bicycle", "car"]


def test_default_mode_is_bicycle():
    mode = config.get_travel_mode(config.DEFAULT_TRAVEL_MODE_KEY)
    assert mode.key == "bicycle"
    assert mode.ors_profile == "cycling-regular"
    assert mode.osrm_profile == "bike"


def test_car_mode_profiles():
    mode = config.get_travel_mode("car")
    assert mode.ors_profile == "driving-car"
    assert mode.osrm_profile == "driving"


def test_unknown_key_falls_back_to_default():
    assert config.get_travel_mode("motorcycle").key == "bicycle"
    assert config.get_travel_mode("").key == "bicycle"


def test_driving_car_must_not_avoid_steps():
    """ORS の avoid_features はプロファイル依存。

    driving-car に "steps" を渡すと不正値としてAPIエラーになるため、
    絶対に含めてはならない（リグレッション防止）。
    """
    car = config.get_travel_mode("car")
    assert "steps" not in car.avoid_features


def test_bicycle_avoids_ferries_and_steps():
    bike = config.get_travel_mode("bicycle")
    assert set(bike.avoid_features) == {"ferries", "steps"}


@pytest.mark.parametrize("mode", config.TRAVEL_MODES, ids=lambda m: m.key)
def test_every_mode_is_fully_specified(mode):
    assert mode.label
    assert mode.ors_profile
    assert mode.osrm_profile
    assert isinstance(mode.avoid_features, tuple)


def test_travel_mode_is_immutable():
    mode = config.get_travel_mode("bicycle")
    with pytest.raises(Exception):
        mode.ors_profile = "driving-car"
