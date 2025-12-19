"""
設定管理モジュール
APIキーやパスなどの設定を一元管理
"""

from pathlib import Path


# APIキーファイルのパス
API_KEY_PATHS = {
    "openrouteservice": Path.home() / ".token" / "openstreetmap" / "api_key",
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


# 設定値
class Config:
    # 地図の初期表示位置（東京）
    DEFAULT_LAT = 35.6812
    DEFAULT_LNG = 139.7671
    DEFAULT_ZOOM = 10

    # API設定
    ORS_PROFILE = "cycling-regular"
    ORS_AVOID_FEATURES = ["ferries", "steps"]

    # キャッシュ設定
    ELEVATION_CACHE_DB = "elevation_cache.db"

    # UI設定
    POLL_INTERVAL_MS = 200  # 地図イベントポーリング間隔
    FIT_DELAY_MS = 1000     # Region変更後のフィット遅延
