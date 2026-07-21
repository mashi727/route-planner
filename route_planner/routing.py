"""OpenRouteService ルーティングクライアント（Qt非依存）。

ルート計算のHTTP呼び出しとレスポンス（polyline / GeoJSON）の解釈をまとめる。
UI（ステータス表示・地図描画）は呼び出し側の責務とし、ここでは
``RouteResult`` を返すか ``RoutingError`` を送出する。
"""

from dataclasses import dataclass
from typing import Optional

import requests

from .geometry import decode_polyline

ORS_ENDPOINT = "https://api.openrouteservice.org/v2/directions/{profile}"


class RoutingError(Exception):
    """ルート計算の失敗（APIキー未設定・HTTPエラー・形式不明など）。"""


@dataclass
class RouteResult:
    """ルート計算結果。

    Attributes:
        coordinates: ``[[lat, lng], ...]`` のルート座標
        elevations: polyline 3D から得た標高 ``[m, ...]``（無ければ ``None``）
    """

    coordinates: list
    elevations: Optional[list]


def fetch_route(
    waypoints,
    api_key: str,
    *,
    profile: str = "cycling-regular",
    avoid_features=("ferries", "steps"),
    timeout: int = 30,
) -> RouteResult:
    """OpenRouteService でルートを計算する。

    Args:
        waypoints: ``[(lat, lng, name), ...]``（name は無視される）
        api_key: OpenRouteService APIキー
        profile: ORS プロファイル（例: "cycling-regular"）
        avoid_features: 回避する経路要素（例: ferries, steps）
        timeout: HTTP タイムアウト（秒）

    Returns:
        RouteResult

    Raises:
        RoutingError: APIキー未設定・HTTP/ORSエラー・不明なgeometry形式
    """
    if not api_key:
        raise RoutingError("ORS APIキーが設定されていません")

    coordinates = [[wp[1], wp[0]] for wp in waypoints]  # [lng, lat] 形式
    url = ORS_ENDPOINT.format(profile=profile)
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
    }
    body = {
        "coordinates": coordinates,
        "elevation": True,
        "instructions": False,
        "geometry_simplify": False,
        "extra_info": ["steepness"],
        "preference": "recommended",
        "options": {
            "avoid_features": list(avoid_features),
        },
    }

    try:
        response = requests.post(url, json=body, headers=headers, timeout=timeout)
    except requests.exceptions.RequestException as e:
        raise RoutingError(f"ルート計算エラー: {e}") from e

    if response.status_code != 200:
        error_data = response.json() if response.text else {}
        error_msg = f"ORSエラー: {response.status_code}"
        if "error" in error_data:
            error_msg += f" - {error_data.get('error', {}).get('message', '')}"
        raise RoutingError(error_msg)

    data = response.json()
    geometry = data["routes"][0]["geometry"]

    # geometry が polyline 文字列か GeoJSON 形式かを判定
    if isinstance(geometry, str):
        # Polyline 形式をデコード（3D: 標高付き）
        coords, elevations = decode_polyline(geometry, include_elevation=True)
        return RouteResult(coordinates=coords, elevations=elevations)
    elif isinstance(geometry, dict) and "coordinates" in geometry:
        # GeoJSON 形式
        coords = [[c[1], c[0]] for c in geometry["coordinates"]]
        return RouteResult(coordinates=coords, elevations=None)
    else:
        raise RoutingError(f"不明なgeometry形式: {type(geometry)}")
