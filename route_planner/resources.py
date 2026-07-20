"""リソース・パス解決ユーティリティ。

PyInstaller でバンドルされた場合（``sys.frozen``）と開発実行時の双方で、
同梱リソース（frontend/map.html など）を正しく解決するための薄いヘルパ。
"""

import sys
from pathlib import Path


def _package_dir() -> Path:
    """このパッケージ（route_planner/）のディレクトリ。"""
    return Path(__file__).resolve().parent


def project_root() -> Path:
    """プロジェクトルート（パッケージの親）。

    開発実行時のキャッシュDB配置などに使用する。
    """
    return _package_dir().parent


def resource_path(rel: str) -> Path:
    """同梱リソースの絶対パスを返す。

    - frozen（PyInstaller）時: ``sys._MEIPASS`` 直下を基準
    - 開発時: パッケージディレクトリを基準

    Args:
        rel: パッケージ/バンドルルートからの相対パス（例: "frontend/map.html"）
    """
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", _package_dir()))
    else:
        base = _package_dir()
    return base / rel
