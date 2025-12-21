# Changelog

## [1.2.0] - 2024-12-21

### Added
- 地図レイヤー選択機能
  - 国土地理院: 淡色/標準/色別標高図/航空写真
  - OpenStreetMap / OpenTopoMap
  - Google Maps: 道路地図/衛星写真/地形図
- ステータスバー（地図とグラフの間に表示）
  - 処理状況をリアルタイム表示
  - 色分けメッセージ（info/success/warning/error）
- GPX/KMLインポート時に始点・終点を自動追加
  - 始点: 「スタート」として経由ポイントに追加
  - 終点: 「ゴール」として経由ポイントに追加

### Fixed
- GPX/KMLインポート時のルート表示不具合修正
  - 座標順序の修正（[lon, lat] → [lat, lon]）
  - 全範囲選択時のRegionライン非表示処理

## [1.1.1] - 2024-12-21

### Fixed
- バンドルアプリでのキャッシュパス修正
  - macOS: ~/Library/Application Support/RoutePlanner/
  - Windows: %LOCALAPPDATA%/RoutePlanner/
  - .app内部にキャッシュが作成される問題を修正

## [1.1.0] - 2024-12-21

### Added
- GPXファイルインポート機能
  - Garmin GPXファイルからルートを直接読み込み
  - GPX内の標高データを使用可能（国土地理院データも選択可）
- KMZ/KMLファイルインポート機能
  - KMZ（ZIP圧縮）とKML両形式に対応
  - 複数のLineStringセグメントを自動結合
  - Placemark/Pointから経由地名を抽出して経由ポイントリストに追加

### Changed
- 標高グラフに斜度オーバーレイを統合（デュアルY軸表示）
  - 左軸: 斜度（%）
  - 右軸: 標高（m）
- 斜度をカラーマップで可視化（青→緑→黄→赤）
- UIレイアウトの最適化
  - ウィンドウサイズ: 1500x900
  - グラフ表示領域の調整
  - 各セクションの余白最適化

### Fixed
- Cmd-Q終了時のセグメンテーションフォルト修正
- pyqtgraphシグナル切断時のクラッシュ防止

## [1.0.0] - 2024-12-20

### Added
- 初期リリース
- OpenRouteServiceによる自転車ルート計算
- 国土地理院5mメッシュDEMから標高データ取得
- 斜度分析とグラフ表示
- 区間選択機能（グラフ上で範囲選択→地図上でハイライト）
- ランドマーク検索（SerpAPI/Nominatim/国土地理院）
- ルート保存/読込（JSON形式）
- 道路スナップ機能（クリック位置を最寄りの道路に補正）
- 橋・トンネル補正（異常な標高変化を平滑化）
- GitHub Actionsによる自動ビルド（macOS/Windows）

### Technical Details
- Python 3.11+
- PySide6 (GUI)
- pyqtgraph (グラフ描画)
- Leaflet (地図表示)
- SQLite (標高キャッシュ)
