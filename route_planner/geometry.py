"""幾何・エンコード計算（Qt非依存の純粋関数）。

地図座標に関する距離計算・ポリラインデコード・最近傍探索など、
UI やネットワークに依存しない計算をまとめる。単体テスト可能。
"""

import math


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """2点間のGreat-circle距離を km で返す。"""
    R = 6371  # 地球の半径（km）

    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def decode_polyline(encoded: str, include_elevation: bool = True):
    """Google Polyline 形式をデコードする（3D対応：標高付き）。

    Args:
        encoded: エンコードされたポリライン文字列
        include_elevation: 3D（標高付き）としてデコードするか

    Returns:
        ``(coordinates, elevations)`` のタプル。
        - coordinates: ``[[lat, lng], ...]``
        - elevations: ``[m, ...]``（標高が無ければ ``None``）
    """
    decoded = []
    elevations = []
    i = 0
    lat = 0
    lng = 0
    ele = 0

    while i < len(encoded):
        # 緯度
        shift = 0
        result = 0
        while i < len(encoded):
            b = ord(encoded[i]) - 63
            i += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        lat += (~(result >> 1) if result & 1 else result >> 1)

        # 経度
        shift = 0
        result = 0
        while i < len(encoded):
            b = ord(encoded[i]) - 63
            i += 1
            result |= (b & 0x1f) << shift
            shift += 5
            if b < 0x20:
                break
        lng += (~(result >> 1) if result & 1 else result >> 1)

        # 標高（3D polylineの場合）
        if include_elevation and i < len(encoded):
            shift = 0
            result = 0
            while i < len(encoded):
                b = ord(encoded[i]) - 63
                i += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            ele += (~(result >> 1) if result & 1 else result >> 1)
            elevations.append(ele / 100.0)  # 標高は100で割る

        decoded.append([lat / 1e5, lng / 1e5])

    return decoded, (elevations if elevations else None)


def distance_to_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """点(px, py) から線分(x1,y1)-(x2,y2) への最短距離。"""
    # 線分の長さの2乗
    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = dx * dx + dy * dy

    if seg_len_sq == 0:
        # 線分が点の場合
        return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)

    # 点から線分への射影のパラメータt (0-1の範囲にクランプ)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / seg_len_sq))

    # 最近点
    nearest_x = x1 + t * dx
    nearest_y = y1 + t * dy

    return math.sqrt((px - nearest_x) ** 2 + (py - nearest_y) ** 2)


def find_nearest_index(route_coordinates, lat: float, lng: float):
    """指定座標に最も近いルート上の点のインデックスを返す。

    厳密なhaversineではなく平面近似の2乗距離で比較（相対比較で十分なため）。
    ルートが空なら ``None``。
    """
    if not route_coordinates:
        return None

    min_dist = float("inf")
    nearest_idx = 0

    for i, coord in enumerate(route_coordinates):
        coord_lat, coord_lng = coord[0], coord[1]
        dist = (lat - coord_lat) ** 2 + (lng - coord_lng) ** 2
        if dist < min_dist:
            min_dist = dist
            nearest_idx = i

    return nearest_idx
