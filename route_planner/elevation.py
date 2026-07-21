"""標高プロファイルの解析（Qt非依存の純粋関数）。

橋・トンネル区間の標高補正、斜度計算、区間統計、Region座標→距離変換。
すべて numpy/リスト演算のみで、UI に依存しない。
"""

import numpy as np

from .geometry import find_nearest_index


def correct_bridge_elevations(distances, elevations):
    """橋・トンネル区間の標高を補正する。

    検出条件:
      1. 標高が急激に低下（前後との差が大きい）
      2. 低い標高が連続する区間
      3. 前後の標高から推定される値と大きく乖離

    補正方法:
      異常区間の始点・終点を検出し、線形補間で標高を推定。

    Returns:
        ``(corrected_elevations, corrected_count)`` のタプル。
        ``corrected_count`` は補正したポイント数。
    """
    if len(elevations) < 3:
        return elevations, 0

    elevations = list(elevations)  # コピーを作成
    n = len(elevations)

    # 1. 移動平均で「期待される標高」を計算
    window = min(50, n // 10) if n > 100 else 5
    expected = []
    for i in range(n):
        start = max(0, i - window)
        end = min(n, i + window + 1)
        expected.append(np.median(elevations[start:end]))

    # 2. 異常区間を検出（期待値から大きく下に外れている）
    threshold_drop = 15  # 期待値より15m以上低い場合を異常とみなす
    anomaly_mask = [False] * n

    for i in range(n):
        # 期待値より大きく低い、または海面近く（5m以下）で周囲が高い
        if elevations[i] < expected[i] - threshold_drop:
            anomaly_mask[i] = True
        elif elevations[i] < 5:
            # 海面近くの場合、前後100点の最大標高を確認
            start = max(0, i - 100)
            end = min(n, i + 100)
            nearby_max = max(elevations[start:end])
            if nearby_max > 30:  # 周囲に30m以上の地点があれば橋の可能性
                anomaly_mask[i] = True

    # 3. 連続した異常区間を特定
    corrected_count = 0
    i = 0
    while i < n:
        if anomaly_mask[i]:
            # 異常区間の開始
            start_idx = i
            # 異常区間の終了を探す
            while i < n and anomaly_mask[i]:
                i += 1
            end_idx = i - 1

            # 補正の基準点を決定
            # 開始点: 異常区間の直前の正常点
            ref_start_idx = start_idx - 1 if start_idx > 0 else start_idx
            ref_start_elev = (
                elevations[ref_start_idx]
                if not anomaly_mask[ref_start_idx]
                else expected[ref_start_idx]
            )

            # 終了点: 異常区間の直後の正常点
            ref_end_idx = end_idx + 1 if end_idx < n - 1 else end_idx
            ref_end_elev = (
                elevations[ref_end_idx]
                if ref_end_idx < n and not anomaly_mask[ref_end_idx]
                else expected[ref_end_idx]
            )

            # 線形補間で補正
            if end_idx > start_idx:
                for j in range(start_idx, end_idx + 1):
                    t = (j - start_idx) / (end_idx - start_idx + 1)
                    elevations[j] = ref_start_elev + t * (ref_end_elev - ref_start_elev)
                    corrected_count += 1
            else:
                elevations[start_idx] = (ref_start_elev + ref_end_elev) / 2
                corrected_count += 1
        else:
            i += 1

    return elevations, corrected_count


def calculate_slopes(distances, elevations, window: int = 50) -> np.ndarray:
    """区間ごとの斜度（%）を計算し、移動平均でスムージングする。"""
    if len(distances) < 2:
        return np.zeros(len(distances))

    # 各区間の斜度を計算
    slopes = np.zeros(len(distances))
    for i in range(1, len(distances)):
        dist_diff = (distances[i] - distances[i - 1]) * 1000  # km to m
        if dist_diff > 0:
            slopes[i] = (elevations[i] - elevations[i - 1]) / dist_diff * 100

    # 移動平均でスムージング
    if len(slopes) >= window:
        kernel = np.ones(window) / window
        slopes_smooth = np.convolve(slopes, kernel, mode="same")
        # 端の処理
        slopes_smooth[: window // 2] = slopes[: window // 2]
        slopes_smooth[-window // 2:] = slopes[-window // 2:]
        return slopes_smooth

    return slopes


def route_statistics(distances, elevations) -> dict:
    """区間の距離・獲得/損失標高・最大/平均斜度を計算する。

    ``calculate_statistics`` / ``calculate_total_statistics`` 共通の算出部。
    ``len(distances) < 2`` の場合は ``None`` を返す。

    Returns:
        ``{"distance", "gain", "loss", "max_slope", "avg_slope"}``（km/m/%）
        または要素不足時に ``None``。
    """
    if distances is None or len(distances) < 2:
        return None

    # 区間の距離
    distance = distances[-1] - distances[0]

    # 獲得・損失標高
    gain = 0
    loss = 0
    for i in range(1, len(elevations)):
        diff = elevations[i] - elevations[i - 1]
        if diff > 0:
            gain += diff
        else:
            loss += abs(diff)

    # 勾配計算
    slopes = []
    for i in range(1, len(elevations)):
        dist_diff = (distances[i] - distances[i - 1]) * 1000  # km to m
        if dist_diff > 0:
            slope = (elevations[i] - elevations[i - 1]) / dist_diff * 100
            slopes.append(slope)

    max_slope = max(slopes) if slopes else 0
    avg_slope = sum(slopes) / len(slopes) if slopes else 0

    return {
        "distance": distance,
        "gain": gain,
        "loss": loss,
        "max_slope": max_slope,
        "avg_slope": avg_slope,
    }


def latlng_to_distance_region(route_coordinates, region_latlng, distances):
    """Region の LatLon 始点・終点を、ルート上の距離範囲に変換する。

    Args:
        route_coordinates: ``[[lat, lng], ...]``
        region_latlng: ``((start_lat, start_lng), (end_lat, end_lng))``
        distances: 距離配列（ルート座標と同順）

    Returns:
        ``(min_distance, max_distance)`` または該当なしで ``None``。
    """
    if not route_coordinates or len(route_coordinates) == 0:
        return None

    start_latlng, end_latlng = region_latlng

    # 始点・終点に最も近いルート上の点
    start_idx = find_nearest_index(route_coordinates, start_latlng[0], start_latlng[1])
    end_idx = find_nearest_index(route_coordinates, end_latlng[0], end_latlng[1])

    if start_idx is None or end_idx is None:
        return None

    # インデックスを正しい順序に
    if start_idx > end_idx:
        start_idx, end_idx = end_idx, start_idx

    # インデックスから距離を取得
    if start_idx < len(distances) and end_idx < len(distances):
        return (distances[start_idx], distances[end_idx])

    return None
