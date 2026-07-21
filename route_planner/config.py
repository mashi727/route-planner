"""
設定管理モジュール
APIキーやパスなどの設定を一元管理
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


# APIキーファイルのパス
API_KEY_PATHS = {
    "openrouteservice": Path.home() / ".apikey" / "OpenRouteService",
    "serpapi": Path.home() / ".apikey" / "SerpApi",
}


def get_api_key_path(service: str) -> Path | None:
    """
    指定されたサービスのAPIキーファイルパスを取得

    Args:
        service: サービス名 ("openrouteservice", "serpapi")

    Returns:
        パス、または未知のサービスの場合はNone
    """
    return API_KEY_PATHS.get(service)


def load_api_key(service: str, key_path: Path | None = None) -> str | None:
    """
    指定されたサービスのAPIキーを読み込む

    Args:
        service: サービス名 ("openrouteservice", "serpapi")
        key_path: カスタムキーファイルパス（省略時はデフォルトパス）

    Returns:
        APIキー文字列、または見つからない場合はNone
    """
    if key_path is None:
        key_path = API_KEY_PATHS.get(service)

    if key_path is None:
        raise ValueError(f"未知のサービス: {service}")

    if not key_path.exists():
        return None

    return key_path.read_text().strip()


@dataclass(frozen=True)
class TravelMode:
    """移動手段の定義（ルート計算と道路スナップの設定をひとまとめにする）。

    Attributes:
        key: 内部識別子
        label: UI 表示名
        ors_profile: OpenRouteService のプロファイル
        osrm_profile: OSRM Nearest API（道路スナップ）のプロファイル
        avoid_features: ORS の avoid_features

    Note:
        ``avoid_features`` の有効値は **プロファイル依存** である。
        たとえば ``steps`` は cycling/foot では有効だが ``driving-car`` では
        不正値となりAPIエラーになるため、モードごとに個別に定義する。
    """

    key: str
    label: str
    ors_profile: str
    osrm_profile: str
    avoid_features: Tuple[str, ...]


# 対応する移動手段（UI の並び順と一致）
TRAVEL_MODES = (
    TravelMode(
        key="bicycle",
        label="自転車",
        ors_profile="cycling-regular",
        osrm_profile="bike",
        avoid_features=("ferries", "steps"),  # フェリー・階段を回避
    ),
    TravelMode(
        key="car",
        label="自動車",
        ors_profile="driving-car",
        osrm_profile="driving",
        avoid_features=("ferries",),  # driving-car に steps は指定不可
    ),
)

DEFAULT_TRAVEL_MODE_KEY = "bicycle"


def get_travel_mode(key: str) -> TravelMode:
    """キーから移動手段を取得する（未知のキーは既定の移動手段を返す）。"""
    for mode in TRAVEL_MODES:
        if mode.key == key:
            return mode
    return get_travel_mode(DEFAULT_TRAVEL_MODE_KEY) if key != DEFAULT_TRAVEL_MODE_KEY else TRAVEL_MODES[0]


# 設定値
class Config:
    # 地図の初期表示位置（東京）
    DEFAULT_LAT = 35.6812
    DEFAULT_LNG = 139.7671
    DEFAULT_ZOOM = 10

    # キャッシュ設定
    ELEVATION_CACHE_DB = "elevation_cache.db"

    # UI設定
    POLL_INTERVAL_MS = 200  # 地図イベントポーリング間隔
    FIT_DELAY_MS = 1000     # Region変更後のフィット遅延
