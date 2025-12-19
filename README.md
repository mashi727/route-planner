# Route Planner

自転車ルート計画ツール。出発地・経由地・目的地を指定して、事前に斜度や走行距離を把握できます。

## 機能

- **ルート計算**: OpenRouteServiceを使用した自転車ルート計算
- **標高プロファイル**: 国土地理院5mメッシュDEMから高精度な標高データを取得
- **斜度分析**: 区間ごとの斜度をグラフで可視化
- **区間選択**: グラフ上で範囲を選択し、その区間を地図上でハイライト表示
- **ランドマーク検索**: SerpAPI/Nominatim/国土地理院を使用した地名検索
- **ルート保存/読込**: JSON形式でルートを保存・読込

## スクリーンショット

（準備中）

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

1. **OpenRouteService** (ルート計算用)
   - https://openrouteservice.org/ でアカウント作成
   - APIキーを `~/.apikey/OpenRouteService` に保存

2. **SerpAPI** (Google検索によるジオコーディング用、オプション)
   - https://serpapi.com/ でアカウント作成
   - APIキーを `~/.apikey/SerpApi` に保存

## 使用方法

```bash
python route_planner.py
```

### 基本操作

1. **ポイント追加**: 地図をクリック
2. **ポイント移動**: マーカーをドラッグ
3. **区間選択**: 標高グラフ上で範囲をドラッグ
4. **ランドマーク検索**: 右パネルの検索ボックスに地名を入力

## プロジェクト構造

```
route/
├── route_planner.py    # メインアプリケーション
├── config.py           # 設定管理
├── geocode.py          # ジオコーディング (SerpAPI)
├── elevation_cache.py  # 標高データキャッシュ
├── frontend/
│   └── map.html        # Leaflet地図 (HTML/CSS/JS)
└── requirements.txt
```

## 今後の予定

- Tauriへの移植（Rust + TypeScript）
- オフライン対応
- GPXエクスポート

## ライセンス

MIT License
