"""
国土地理院 5mメッシュ標高データのオンデマンドキャッシュ

- SQLiteでタイル単位にキャッシュ
- DEM5A（5mメッシュ）を優先、なければDEM10Bにフォールバック
- レート制限を考慮（リクエスト間隔を設定可能）
- PNG形式のDEMタイルをデコード
"""

import sqlite3
import math
import time
import os
import sys
import requests
from pathlib import Path
from typing import Optional, Tuple, List
import threading
import io

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def get_cache_dir() -> Path:
    """キャッシュディレクトリを取得

    PyInstallerでバンドルされた場合は~/Library/Application Support/RoutePlanner/
    開発時はスクリプトと同じディレクトリ
    """
    if getattr(sys, 'frozen', False):
        # PyInstallerでバンドルされた場合
        if sys.platform == 'darwin':
            cache_dir = Path.home() / 'Library' / 'Application Support' / 'RoutePlanner'
        elif sys.platform == 'win32':
            # Windows: %LOCALAPPDATA%\RoutePlanner
            local_app_data = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
            cache_dir = local_app_data / 'RoutePlanner'
        else:
            # Linux等: ~/.local/share/RoutePlanner
            cache_dir = Path.home() / '.local' / 'share' / 'RoutePlanner'
    else:
        # 開発時はスクリプトと同じディレクトリ
        cache_dir = Path(__file__).parent

    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


class ElevationCache:
    """標高データのオンデマンドキャッシュ"""

    # DEMタイルの種類（優先順）
    DEM_TYPES = ['dem5a_png', 'dem5b_png', 'dem5c_png', 'dem_png']

    def __init__(self,
                 db_path: str = None,
                 request_interval: float = 0.1,  # リクエスト間隔（秒）
                 zoom_level: int = 14):  # ズームレベル14が最適
        """
        Args:
            db_path: SQLiteデータベースのパス（Noneならデフォルト）
            request_interval: APIリクエスト間の待機時間（秒）
            zoom_level: タイルのズームレベル（14推奨、DEM5Aは14まで）
        """
        if db_path is None:
            db_path = get_cache_dir() / 'elevation_cache.db'

        self.db_path = Path(db_path)
        self.request_interval = request_interval
        self.zoom_level = zoom_level
        self._last_request_time = 0
        self._lock = threading.Lock()

        if not HAS_PIL:
            print("警告: PILがインストールされていません。pip install Pillow を実行してください")

        self._init_database()

    def _init_database(self):
        """データベースを初期化"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tiles (
                    zoom INTEGER,
                    x INTEGER,
                    y INTEGER,
                    dem_type TEXT,
                    data BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (zoom, x, y)
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_tiles_coords
                ON tiles (zoom, x, y)
            ''')

            # 統計情報用テーブル
            conn.execute('''
                CREATE TABLE IF NOT EXISTS stats (
                    key TEXT PRIMARY KEY,
                    value INTEGER
                )
            ''')
            conn.commit()

    def _lat_lng_to_tile(self, lat: float, lng: float) -> Tuple[int, int]:
        """緯度経度からタイル座標を計算"""
        n = 2 ** self.zoom_level
        x = int((lng + 180) / 360 * n)
        y = int((1 - math.log(math.tan(math.radians(lat)) +
                1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
        return x, y

    def _lat_lng_to_pixel(self, lat: float, lng: float, tile_x: int, tile_y: int) -> Tuple[int, int]:
        """緯度経度からタイル内のピクセル座標を計算"""
        n = 2 ** self.zoom_level

        # タイルの左上の緯度経度
        tile_lng = tile_x / n * 360 - 180
        tile_lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * tile_y / n))))

        # タイルの右下の緯度経度
        next_tile_lng = (tile_x + 1) / n * 360 - 180
        next_tile_lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (tile_y + 1) / n))))

        # タイル内の相対位置（0-255）
        px = int((lng - tile_lng) / (next_tile_lng - tile_lng) * 256)
        py = int((lat - tile_lat) / (next_tile_lat - tile_lat) * 256)

        # 範囲内に収める
        px = max(0, min(255, px))
        py = max(0, min(255, py))

        return px, py

    def _rate_limit(self):
        """レート制限を適用"""
        with self._lock:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.request_interval:
                time.sleep(self.request_interval - elapsed)
            self._last_request_time = time.time()

    def _decode_dem_png(self, png_data: bytes) -> Optional[List[List[float]]]:
        """PNG形式のDEMデータをデコード

        国土地理院DEMタイルのエンコーディング:
        - 標高 = (R * 256 + G + B / 256) - 100000 (単位: 0.01m)
        - 実際の標高(m) = 上記値 / 100
        - RGB = (128, 0, 0) は無効値
        """
        if not HAS_PIL:
            return None

        try:
            img = Image.open(io.BytesIO(png_data))
            img = img.convert('RGB')
            width, height = img.size

            data = []
            for y in range(height):
                row = []
                for x in range(width):
                    r, g, b = img.getpixel((x, y))

                    # 無効値チェック (128, 0, 0)
                    if r == 128 and g == 0 and b == 0:
                        row.append(None)
                    else:
                        # 標高を計算（単位: m）
                        # 公式: x = 2^16*R + 2^8*G + B
                        # 標高 = (x < 2^23) ? x*0.01 : (x-2^24)*0.01
                        x_val = r * 65536 + g * 256 + b
                        if x_val < 8388608:  # 2^23
                            elevation = x_val * 0.01
                        else:
                            elevation = (x_val - 16777216) * 0.01  # 2^24
                        row.append(elevation)
                data.append(row)

            return data

        except Exception as e:
            print(f"PNG decode error: {e}")
            return None

    def _fetch_tile(self, x: int, y: int) -> Optional[Tuple[str, List[List[float]]]]:
        """国土地理院からタイルデータを取得"""
        self._rate_limit()

        for dem_type in self.DEM_TYPES:
            url = f"https://cyberjapandata.gsi.go.jp/xyz/{dem_type}/{self.zoom_level}/{x}/{y}.png"

            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = self._decode_dem_png(response.content)
                    if data and len(data) > 0:
                        return dem_type, data

            except requests.exceptions.RequestException:
                continue

        return None

    def _get_cached_tile(self, x: int, y: int) -> Optional[List[List[float]]]:
        """キャッシュからタイルを取得"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT data FROM tiles WHERE zoom = ? AND x = ? AND y = ?',
                (self.zoom_level, x, y)
            )
            row = cursor.fetchone()
            if row:
                import json
                return json.loads(row[0])
        return None

    def _cache_tile(self, x: int, y: int, dem_type: str, data: List[List[float]]):
        """タイルをキャッシュに保存"""
        import json
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                '''INSERT OR REPLACE INTO tiles (zoom, x, y, dem_type, data)
                   VALUES (?, ?, ?, ?, ?)''',
                (self.zoom_level, x, y, dem_type, json.dumps(data))
            )
            # 統計を更新
            conn.execute(
                '''INSERT OR REPLACE INTO stats (key, value)
                   VALUES ('tile_count',
                           COALESCE((SELECT value FROM stats WHERE key = 'tile_count'), 0) + 1)'''
            )
            conn.commit()

    def get_elevation(self, lat: float, lng: float) -> Optional[float]:
        """
        指定座標の標高を取得（キャッシュ優先）

        Args:
            lat: 緯度
            lng: 経度

        Returns:
            標高（メートル）、取得できない場合はNone
        """
        tile_x, tile_y = self._lat_lng_to_tile(lat, lng)

        # キャッシュを確認
        tile_data = self._get_cached_tile(tile_x, tile_y)

        if tile_data is None:
            # キャッシュになければ取得
            result = self._fetch_tile(tile_x, tile_y)
            if result is None:
                return None

            dem_type, tile_data = result
            self._cache_tile(tile_x, tile_y, dem_type, tile_data)

        # タイル内のピクセル座標を計算
        px, py = self._lat_lng_to_pixel(lat, lng, tile_x, tile_y)

        # 標高を取得
        if 0 <= py < len(tile_data) and 0 <= px < len(tile_data[py]):
            return tile_data[py][px]

        return None

    def get_elevations_batch(self, coordinates: List[Tuple[float, float]],
                             progress_callback=None) -> List[Optional[float]]:
        """
        複数座標の標高を一括取得（タイル単位でキャッシュ効率化）

        Args:
            coordinates: [(lat, lng), ...] のリスト
            progress_callback: 進捗コールバック関数 (current, total) -> None

        Returns:
            標高のリスト（取得できない場合はNone）
        """
        total = len(coordinates)

        # タイルごとにグループ化して効率的に取得
        tile_groups = {}
        for i, (lat, lng) in enumerate(coordinates):
            tile_x, tile_y = self._lat_lng_to_tile(lat, lng)
            key = (tile_x, tile_y)
            if key not in tile_groups:
                tile_groups[key] = []
            tile_groups[key].append((i, lat, lng))

        results = [None] * total
        processed = 0

        for (tile_x, tile_y), points in tile_groups.items():
            # タイルデータを取得（キャッシュ優先）
            tile_data = self._get_cached_tile(tile_x, tile_y)

            if tile_data is None:
                result = self._fetch_tile(tile_x, tile_y)
                if result:
                    dem_type, tile_data = result
                    self._cache_tile(tile_x, tile_y, dem_type, tile_data)

            # 各ポイントの標高を取得
            for i, lat, lng in points:
                if tile_data:
                    px, py = self._lat_lng_to_pixel(lat, lng, tile_x, tile_y)
                    if 0 <= py < len(tile_data) and 0 <= px < len(tile_data[py]):
                        results[i] = tile_data[py][px]

                processed += 1
                if progress_callback:
                    progress_callback(processed, total)

        return results

    def get_stats(self) -> dict:
        """キャッシュの統計情報を取得"""
        with sqlite3.connect(self.db_path) as conn:
            # タイル数
            cursor = conn.execute('SELECT COUNT(*) FROM tiles')
            tile_count = cursor.fetchone()[0]

            # DEM種類別の内訳
            cursor = conn.execute(
                'SELECT dem_type, COUNT(*) FROM tiles GROUP BY dem_type'
            )
            dem_counts = dict(cursor.fetchall())

            # データベースサイズ
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

        return {
            'tile_count': tile_count,
            'dem_counts': dem_counts,
            'db_size_mb': db_size / (1024 * 1024),
            'db_path': str(self.db_path)
        }

    def clear_cache(self):
        """キャッシュをクリア"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM tiles')
            conn.execute('DELETE FROM stats')
            conn.commit()

        # VACUUMでファイルサイズを縮小
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('VACUUM')


# グローバルインスタンス（シングルトン的に使用）
_cache_instance = None

def get_cache(db_path: str = None) -> ElevationCache:
    """キャッシュインスタンスを取得（シングルトン）"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = ElevationCache(db_path=db_path)
    return _cache_instance


if __name__ == '__main__':
    # テスト
    cache = ElevationCache()

    # 東京駅付近の標高を取得
    test_points = [
        (35.6812, 139.7671),  # 東京駅
        (35.7101, 139.8107),  # 浅草
        (35.6586, 139.7454),  # 六本木
        (35.3606, 138.7274),  # 富士山付近
    ]

    print("標高データ取得テスト:")
    for lat, lng in test_points:
        elev = cache.get_elevation(lat, lng)
        print(f"  ({lat}, {lng}): {elev}m")

    print("\nキャッシュ統計:")
    stats = cache.get_stats()
    print(f"  タイル数: {stats['tile_count']}")
    print(f"  DBサイズ: {stats['db_size_mb']:.2f} MB")
    print(f"  DEM種類: {stats['dem_counts']}")
