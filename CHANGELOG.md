# Changelog

## [Unreleased]

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
