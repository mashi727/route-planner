# Route Planner

自転車ルート計画ツール。出発地・経由地・目的地を指定して、事前に斜度や走行距離を把握できます。

![Demo](route_demo.mp4)

## ダウンロード

| OS | ダウンロード |
|----|-------------|
| macOS | [RoutePlanner-macOS.dmg](https://github.com/mashi727/route-planner/releases/latest/download/RoutePlanner-macOS.dmg) |
| Windows | [RoutePlanner.exe](https://github.com/mashi727/route-planner/releases/latest/download/RoutePlanner.exe) |

> **Note**: 初回起動時にAPIキーの設定が必要です（下記参照）

## 機能

### ルート計算
- **OpenRouteService連携**: 自転車向けのルート計算
- **道路スナップ**: クリック位置を最寄りの道路に自動補正
- **経由地対応**: 複数の経由地を設定可能

### 標高・斜度分析
- **国土地理院5mメッシュDEM**: 高精度な標高データを取得
- **斜度可視化**: カラーマップ（青→緑→黄→赤）で斜度を直感的に表示
- **デュアルY軸グラフ**: 標高（右軸）と斜度（左軸）を同時表示
- **橋・トンネル補正**: 異常な標高変化を自動的に平滑化

### 区間選択
- **グラフ上で範囲選択**: 標高グラフ上でドラッグして区間を選択
- **地図連動**: 選択区間を地図上で赤くハイライト表示
- **区間情報表示**: 選択区間の距離・標高差・平均斜度を表示

### ファイル入出力
- **ルート保存/読込**: JSON形式でルートを保存・読込
- **GPXインポート**: Garmin等のGPXファイルからルートを直接読み込み
- **KMZ/KMLインポート**: Google Earth等のKMZ/KMLファイルに対応
  - 複数セグメントの自動結合
  - 経由地（Placemark）の名前を自動抽出

### ランドマーク検索
- **SerpAPI**: Google検索によるジオコーディング
- **Nominatim**: OpenStreetMapベースの検索
- **国土地理院**: 日本の地名検索

## 使用技術

| カテゴリ | 技術 |
|---------|------|
| GUI | PySide6 (Qt for Python) |
| グラフ | pyqtgraph |
| 地図 | Leaflet + OpenStreetMap |
| ルート計算 | OpenRouteService API |
| 標高データ | 国土地理院 5mメッシュDEM |
| キャッシュ | SQLite |
| ビルド | PyInstaller |
| CI/CD | GitHub Actions |

## 必要要件

- Python 3.11+
- PySide6
- pyqtgraph

## インストール

```bash
pip install -r requirements.txt
```

## APIキーの設定

以下のAPIキーが必要です：

### 1. OpenRouteService（必須）
ルート計算に使用します。

1. https://openrouteservice.org/ でアカウント作成
2. APIキーを取得
3. `~/.apikey/OpenRouteService` に保存

```bash
mkdir -p ~/.apikey
echo "your-api-key" > ~/.apikey/OpenRouteService
```

### 2. SerpAPI（オプション）
Google検索によるジオコーディングに使用します。

1. https://serpapi.com/ でアカウント作成
2. APIキーを取得
3. `~/.apikey/SerpApi` に保存

```bash
echo "your-api-key" > ~/.apikey/SerpApi
```

> SerpAPIキーがない場合はNominatim/国土地理院が使用されます

## 使用方法

```bash
python route_planner.py
```

### 基本操作

| 操作 | 説明 |
|------|------|
| 地図クリック | ポイント追加 |
| マーカードラッグ | ポイント移動 |
| グラフドラッグ | 区間選択 |
| 検索ボックス | ランドマーク検索 |

### ボタン操作

| ボタン | 説明 |
|--------|------|
| GPX | GPXファイルを読み込み |
| KMZ/KML | KMZ/KMLファイルを読み込み |
| 読込 | 保存したルートを読み込み |
| 保存 | 現在のルートを保存 |
| クリア | 全ポイントをクリア |
| ルート計算 | ルートを再計算 |

### GPX/KMZインポート

GPXまたはKMZ/KMLファイルをインポートする場合：
- ルート計算は行わず、ファイル内の座標をそのまま使用
- 標高データはファイル内のデータまたは国土地理院から取得
- KMZの経由地（Placemark）は経由ポイントリストに追加

## プロジェクト構造

```
route/
├── route_planner.py    # メインアプリケーション
├── config.py           # 設定管理
├── geocode.py          # ジオコーディング (SerpAPI)
├── elevation_cache.py  # 標高データキャッシュ
├── frontend/
│   └── map.html        # Leaflet地図 (HTML/CSS/JS)
├── assets/
│   └── icon.*          # アプリケーションアイコン
├── .github/
│   └── workflows/
│       └── build.yml   # GitHub Actions ビルド設定
├── requirements.txt
├── route_planner.spec  # PyInstaller設定
├── CHANGELOG.md        # 変更履歴
└── README.md
```

## ビルド

### ローカルビルド

```bash
pip install pyinstaller
python -m PyInstaller --clean route_planner.spec
```

### GitHub Actionsビルド

タグをプッシュすると自動的にビルドが実行されます：

```bash
git tag v1.1.0
git push origin v1.1.0
```

## 今後の予定

- [ ] GPXエクスポート
- [ ] Stravaルートインポート
- [ ] オフライン対応
- [ ] Tauriへの移植（Rust + TypeScript）

## ライセンス

MIT License

## 謝辞

- [OpenRouteService](https://openrouteservice.org/) - ルート計算API
- [国土地理院](https://www.gsi.go.jp/) - 標高データ
- [OpenStreetMap](https://www.openstreetmap.org/) - 地図タイル
- [Leaflet](https://leafletjs.com/) - 地図ライブラリ
