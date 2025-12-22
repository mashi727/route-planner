"""
ルートプランニングツール
出発地・経由地・目的地を指定して、事前に斜度や走行距離を把握する
"""

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QListWidget, QListWidgetItem, QLabel, QLineEdit,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QAbstractItemView, QCheckBox, QProgressBar, QFileDialog, QMenuBar, QMenu,
    QDialogButtonBox
)
from PySide6.QtCore import Qt, QUrl, QTimer, QSize
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWebEngineWidgets import QWebEngineView

import sys
import json
import requests
import numpy as np
import pandas as pd
import xml.etree.ElementTree as ET
import zipfile
import io
from pathlib import Path
import pyqtgraph as pg
from elevation_cache import ElevationCache

# pyqtgraphのダークテーマ設定
pg.setConfigOptions(antialias=True)
pg.setConfigOption('background', '#1e1e2e')
pg.setConfigOption('foreground', '#cdd6f4')

# 設定とAPIキーの読み込み
from config import load_api_key, Config
ORS_API_KEY = load_api_key("openrouteservice")


class RoutePlanner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ルートプランナー")
        # ウィンドウサイズを固定（地図800x800、15%拡大）
        self.setFixedSize(1500, 900)

        self.waypoints = []  # [(lat, lng, name), ...]
        self.route_coordinates = []  # ルート座標
        self.elevation_data = []  # 標高データ
        self._decoded_elevations = None  # デコードした標高
        self.slopes = np.array([])  # 斜度データ
        self.search_results = []  # ランドマーク検索結果

        # 地図フィット用タイマー
        self.fit_timer = QTimer()
        self.fit_timer.setSingleShot(True)
        self.fit_timer.timeout.connect(self._do_fit_to_region)
        self._pending_fit_coords = None
        self._suppress_region_fit = False  # プログラム的なRegion変更時のフィット抑制フラグ

        # Region選択状態の保持（ポイント追加・移動時にRegionを維持するため）
        self._region_active = False  # Region選択中かどうか（全範囲選択でない場合True）
        self._region_start_latlng = None  # Region始点のLatLon (lat, lng)
        self._region_end_latlng = None    # Region終点のLatLon (lat, lng)

        # 標高キャッシュ
        self.elevation_cache = ElevationCache()
        self.use_gsi_elevation = True  # 国土地理院標高を使用するか


        self.init_ui()
        self.load_map()

    def _open_file_dialog(self, title, extensions, save=False):
        """カスタムファイルダイアログを開く（拡張子フィルタ付き）

        Args:
            title: ダイアログタイトル
            extensions: 許可する拡張子のリスト (例: ['.json'], ['.gpx'], ['.kmz', '.kml'])
            save: True=保存ダイアログ, False=開くダイアログ

        Returns:
            選択されたファイルパス、またはNone
        """
        dialog = QFileDialog(self)
        dialog.setWindowTitle(title)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)

        if save:
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        else:
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
            dialog.setFileMode(QFileDialog.FileMode.ExistingFile)

        # フィルタ文字列を作成（対象の拡張子のみ表示）
        ext_str = ' '.join([f'*{ext}' for ext in extensions])
        ext_names = '/'.join([ext.upper().replace('.', '') for ext in extensions])
        dialog.setNameFilter(f"{ext_names} Files ({ext_str})")

        # 内部のファイルシステムモデルにフィルタを適用（対象外ファイルを非表示）
        from PySide6.QtWidgets import QFileSystemModel
        for model in dialog.findChildren(QFileSystemModel):
            model.setNameFilters([f'*{ext}' for ext in extensions])
            model.setNameFilterDisables(False)  # False=非表示、True=グレーアウト

        if dialog.exec() == QFileDialog.Accepted:
            files = dialog.selectedFiles()
            if files:
                return files[0]
        return None

    def cleanup(self):
        """リソースのクリーンアップ"""
        if getattr(self, '_cleaned_up', False):
            return
        self._cleaned_up = True

        # すべてのタイマーを停止
        for timer_name in ['poll_timer', 'fit_timer', 'search_timer']:
            timer = getattr(self, timer_name, None)
            if timer:
                timer.stop()

        # pyqtgraphシグナルを切断
        if hasattr(self, 'region') and self.region is not None:
            try:
                self.region.sigRegionChanged.disconnect()
            except:
                pass

        # WebEngineViewのクリーンアップ（Chromiumスレッド終了待機）
        if hasattr(self, 'map_view') and self.map_view is not None:
            try:
                self.map_view.stop()
                self.map_view.setUrl(QUrl("about:blank"))
                self.map_view.page().deleteLater()
                self.map_view.deleteLater()
            except:
                pass

        # イベント処理を完了させる
        QApplication.processEvents()

    def closeEvent(self, event):
        """アプリケーション終了時のクリーンアップ"""
        self.hide()  # まずウィンドウを隠す
        self.cleanup()
        event.accept()

    def update_status(self, message: str, level: str = "info"):
        """ステータスバーにメッセージを表示

        Args:
            message: 表示するメッセージ
            level: メッセージレベル ("info", "success", "warning", "error")
        """
        colors = {
            "info": "#89b4fa",      # 青
            "success": "#a6e3a1",   # 緑
            "warning": "#f9e2af",   # 黄
            "error": "#f38ba8",     # 赤
        }
        color = colors.get(level, colors["info"])

        if hasattr(self, 'status_label'):
            self.status_label.setStyleSheet(f"""
                QLabel {{
                    color: {color};
                    background-color: #313244;
                    border-radius: 3px;
                    padding: 2px 8px;
                    font-size: 18px;
                }}
            """)
            self.status_label.setText(message)
            QApplication.processEvents()

    def init_ui(self):
        # メニューバー
        menubar = self.menuBar()

        # ファイルメニュー
        file_menu = menubar.addMenu("ファイル")

        quit_action = QAction("終了", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # 表示メニュー
        view_menu = menubar.addMenu("表示")

        # テーマサブメニュー
        theme_menu = view_menu.addMenu("テーマ")
        self.theme_action_group = QActionGroup(self)
        self.theme_action_group.setExclusive(True)

        self.dark_theme_action = QAction("ダーク", self, checkable=True)
        self.dark_theme_action.setChecked(True)
        self.dark_theme_action.triggered.connect(lambda: self.set_theme("dark"))
        theme_menu.addAction(self.dark_theme_action)
        self.theme_action_group.addAction(self.dark_theme_action)

        self.light_theme_action = QAction("ライト", self, checkable=True)
        self.light_theme_action.triggered.connect(lambda: self.set_theme("light"))
        theme_menu.addAction(self.light_theme_action)
        self.theme_action_group.addAction(self.light_theme_action)

        # 現在のテーマを保持
        self.current_theme = "dark"

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)

        # 左側: 地図とグラフ
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # 地図
        self.map_view = QWebEngineView()
        self.map_view.setFixedSize(1020, 567)
        self.map_view.setContextMenuPolicy(Qt.NoContextMenu)  # 右クリックメニュー無効化
        left_layout.addWidget(self.map_view)

        # ステータスバー（地図とグラフの間）
        self.status_label = QLabel("")
        self.status_label.setFixedHeight(28)
        self.status_label.setStyleSheet("""
            QLabel {
                color: #89b4fa;
                background-color: #313244;
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 18px;
            }
        """)
        left_layout.addWidget(self.status_label)

        # グラフ（高度、Region、ヒストグラム）
        self.graph_widget = pg.GraphicsLayoutWidget()
        self.graph_widget.setMinimumHeight(180)
        self.graph_widget.ci.layout.setContentsMargins(0, 10, 0, 0)
        self.graph_widget.ci.layout.setSpacing(5)

        # プロットエリアを確保（2行: 高度、Region）
        self.dist_plot = self.graph_widget.addPlot(row=0, col=0)
        self.region_plot = self.graph_widget.addPlot(row=1, col=0)
        self.hist_plot = self.graph_widget.addPlot(row=0, col=1, rowspan=2)

        # レイアウト設定
        self.graph_widget.ci.layout.setColumnStretchFactor(0, 3)
        self.graph_widget.ci.layout.setColumnStretchFactor(1, 1)
        self.graph_widget.ci.layout.setRowStretchFactor(0, 10)
        self.graph_widget.ci.layout.setRowStretchFactor(1, 2)

        # 高度グラフ設定
        self.dist_plot.setLabel('right', '高度(m)')
        self.dist_plot.setLabel('left', '斜度(%)')
        self.dist_plot.showGrid(x=True, y=True, alpha=0.3)
        self.dist_plot.showAxis('right')
        self.dist_plot.showAxis('left')
        self.dist_plot.getAxis('right').setWidth(50)
        self.dist_plot.getAxis('left').setWidth(50)
        self.dist_plot.setLabel('bottom', '距離(km)')

        # 斜度スケール係数を保存（グラフ更新時に使用）
        self.slope_scale_factor = 1.0

        # Region選択グラフ設定
        # 左右の軸を表示して幅を高度グラフと揃える（ラベルなし）
        self.region_plot.showAxis('left')
        self.region_plot.showAxis('right')
        self.region_plot.getAxis('left').setWidth(50)
        self.region_plot.getAxis('right').setWidth(50)
        self.region_plot.getAxis('left').setStyle(showValues=False)
        self.region_plot.getAxis('right').setStyle(showValues=False)
        self.region_plot.hideAxis('bottom')

        # ヒストグラム設定
        self.hist_plot.setLabel('bottom', '斜度(%)')
        self.hist_plot.setLabel('right', '頻度')
        self.hist_plot.showGrid(x=True, y=True, alpha=0.3)
        self.hist_plot.showAxis('right')
        self.hist_plot.hideAxis('left')

        # 斜度用カラーマップ（ver11.pyと同様、太めに）
        self.slope_colormap = pg.colormap.get('CET-L19')
        self.slope_colormap.setMappingMode('diverging')
        self.slope_pen = self.slope_colormap.getPen(span=(-10, 10), width=4)
        self.slope_pen_h = self.slope_colormap.getPen(span=(-10, 10), orientation='horizontal', width=3)

        # LinearRegionItem（テーマカラー）
        self.region = pg.LinearRegionItem(
            brush=pg.mkBrush(137, 180, 250, 50),  # 89b4fa with alpha
            pen=pg.mkPen(color='#89b4fa', width=2)
        )
        self.region.setZValue(10)
        self.region_plot.addItem(self.region, ignoreBounds=True)
        self.region.sigRegionChanged.connect(self.on_region_changed)

        left_layout.addWidget(self.graph_widget, stretch=1)

        main_layout.addWidget(left_widget, stretch=3)

        # 右側: コントロールパネル
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(14)
        right_layout.setContentsMargins(4, 4, 4, 4)
        right_widget.setFixedWidth(450)

        # ランドマーク検索
        search_group = QGroupBox("ランドマーク検索")
        search_layout = QVBoxLayout(search_group)
        search_layout.setSpacing(1)
        search_layout.setContentsMargins(4, 4, 4, 4)

        search_input_layout = QHBoxLayout()
        self.landmark_input = QLineEdit()
        self.landmark_input.setPlaceholderText("地名・施設名を入力")
        self.landmark_input.returnPressed.connect(self.search_landmark)

        # インクリメンタルサーチ用タイマー（0.5秒デバウンス）
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.search_landmark)
        self.landmark_input.textChanged.connect(self._on_search_text_changed)

        search_input_layout.addWidget(self.landmark_input)

        search_btn = QPushButton("検索")
        search_btn.clicked.connect(self.search_landmark)
        search_input_layout.addWidget(search_btn)
        search_layout.addLayout(search_input_layout)

        # 検索結果リスト
        self.search_result_list = QListWidget()
        self.search_result_list.setMaximumHeight(100)
        self.search_result_list.itemDoubleClicked.connect(self.add_search_result)
        search_layout.addWidget(self.search_result_list)

        search_layout.addWidget(QLabel("※ ダブルクリックでポイント追加"))

        # SerpApi設定
        serpapi_layout = QHBoxLayout()
        self.serpapi_checkbox = QCheckBox("SerpAPI使用")
        self.serpapi_checkbox.setChecked(False)  # デフォルトはOFF
        self.serpapi_checkbox.stateChanged.connect(self.on_serpapi_checkbox_changed)
        serpapi_layout.addWidget(self.serpapi_checkbox)
        self.serpapi_remaining_label = QLabel("")
        serpapi_layout.addWidget(self.serpapi_remaining_label)
        serpapi_layout.addStretch()
        search_layout.addLayout(serpapi_layout)

        # SerpApiキーのパスを保持
        self._serpapi_key_path = None

        # 起動時はSerpApi情報を取得しない（OFFなので）

        right_layout.addWidget(search_group)

        # ポイントリスト
        list_group = QGroupBox("経由ポイント（地図クリックでも追加可）")
        list_group_layout = QVBoxLayout(list_group)
        list_group_layout.setSpacing(1)
        list_group_layout.setContentsMargins(4, 4, 4, 4)

        # 上部: リストとボタン
        list_layout = QHBoxLayout()

        # 左: ポイントリスト
        self.point_list = QListWidget()
        self.point_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.point_list.model().rowsMoved.connect(self.on_points_reordered)
        list_layout.addWidget(self.point_list, stretch=1)

        # 右: 削除ボタン（縦配置）
        list_btn_layout = QVBoxLayout()
        delete_btn = QPushButton("削除")
        delete_btn.clicked.connect(self.delete_selected_point)
        clear_btn = QPushButton("全削除")
        clear_btn.clicked.connect(self.clear_all_points)
        list_btn_layout.addWidget(delete_btn)
        list_btn_layout.addWidget(clear_btn)
        list_btn_layout.addStretch()
        list_layout.addLayout(list_btn_layout)

        list_group_layout.addLayout(list_layout, stretch=1)

        # 下部: 自動フィットチェックボックス
        self.auto_fit_checkbox = QCheckBox("ポイント変更時に地図を自動フィット")
        self.auto_fit_checkbox.setChecked(True)
        self.auto_fit_checkbox.stateChanged.connect(self.on_auto_fit_changed)
        list_group_layout.addWidget(self.auto_fit_checkbox)

        right_layout.addWidget(list_group, stretch=1)

        # ルート情報（縦表示）
        info_group = QGroupBox("ルート情報")
        info_layout = QGridLayout(info_group)
        info_layout.setSpacing(6)
        info_layout.setContentsMargins(4, 6, 4, 6)

        # ヘッダー行
        info_layout.addWidget(QLabel(""), 0, 0)  # 空欄
        selection_header = QLabel("選択範囲")
        selection_header.setStyleSheet("font-weight: bold;")
        total_header = QLabel("全経路")
        total_header.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(selection_header, 0, 1)
        info_layout.addWidget(total_header, 0, 2)

        # 選択範囲のラベル
        self.distance_label = QLabel("-")
        self.gain_label = QLabel("-")
        self.loss_label = QLabel("-")
        self.max_slope_label = QLabel("-")
        self.avg_slope_label = QLabel("-")

        # 全経路のラベル
        self.total_distance_label = QLabel("-")
        self.total_gain_label = QLabel("-")
        self.total_loss_label = QLabel("-")
        self.total_max_slope_label = QLabel("-")
        self.total_avg_slope_label = QLabel("-")

        # 行ラベル（左）、選択範囲（中）、全経路（右）
        info_layout.addWidget(QLabel("距離:"), 1, 0)
        info_layout.addWidget(self.distance_label, 1, 1)
        info_layout.addWidget(self.total_distance_label, 1, 2)

        info_layout.addWidget(QLabel("獲得標高（↑）:"), 2, 0)
        info_layout.addWidget(self.gain_label, 2, 1)
        info_layout.addWidget(self.total_gain_label, 2, 2)

        info_layout.addWidget(QLabel("獲得標高（↓）:"), 3, 0)
        info_layout.addWidget(self.loss_label, 3, 1)
        info_layout.addWidget(self.total_loss_label, 3, 2)

        info_layout.addWidget(QLabel("最大勾配:"), 4, 0)
        info_layout.addWidget(self.max_slope_label, 4, 1)
        info_layout.addWidget(self.total_max_slope_label, 4, 2)

        info_layout.addWidget(QLabel("平均勾配:"), 5, 0)
        info_layout.addWidget(self.avg_slope_label, 5, 1)
        info_layout.addWidget(self.total_avg_slope_label, 5, 2)

        right_layout.addWidget(info_group)

        # 標高データ設定
        elevation_group = QGroupBox("標高データ設定")
        elevation_layout = QGridLayout(elevation_group)
        elevation_layout.setSpacing(8)
        elevation_layout.setContentsMargins(4, 6, 4, 6)

        self.gsi_checkbox = QCheckBox("国土地理院5mメッシュを使用")
        self.gsi_checkbox.setChecked(True)
        self.gsi_checkbox.stateChanged.connect(self.on_gsi_checkbox_changed)
        elevation_layout.addWidget(self.gsi_checkbox, 0, 0)

        self.bridge_correction_checkbox = QCheckBox("橋・トンネル区間を自動補正")
        self.bridge_correction_checkbox.setChecked(True)
        self.bridge_correction_checkbox.stateChanged.connect(self.on_bridge_correction_changed)
        elevation_layout.addWidget(self.bridge_correction_checkbox, 1, 0)

        # キャッシュ情報
        self.cache_label = QLabel("キャッシュ: -")
        elevation_layout.addWidget(self.cache_label, 2, 0)
        self.update_cache_label()

        right_layout.addWidget(elevation_group)

        right_layout.addStretch()

        # 保存・読み込みボタン（最下段）
        save_load_layout = QHBoxLayout()
        gpx_btn = QPushButton("GPX")
        gpx_btn.clicked.connect(self.load_gpx)
        kmz_btn = QPushButton("KMZ/KML")
        kmz_btn.clicked.connect(self.load_kmz)
        load_btn = QPushButton("読込")
        load_btn.clicked.connect(self.load_waypoints)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_waypoints)
        save_load_layout.addWidget(gpx_btn)
        save_load_layout.addWidget(kmz_btn)
        save_load_layout.addWidget(load_btn)
        save_load_layout.addWidget(save_btn)
        right_layout.addLayout(save_load_layout)

        main_layout.addWidget(right_widget, stretch=1)

    def load_map(self):
        """Leaflet地図を生成してWebViewに表示（クリック・ドラッグ対応）"""
        # 外部HTMLファイルから読み込み
        html_path = Path(__file__).parent / "frontend" / "map.html"
        html = html_path.read_text(encoding="utf-8")
        self.map_view.setHtml(html)

        # ページロード完了を待ってからポーリング開始
        self.map_view.loadFinished.connect(self.on_map_loaded)

    def on_map_loaded(self):
        """地図のロード完了時"""
        # 定期的にイベントをポーリング
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.poll_map_events)
        self.poll_timer.start(200)  # 200msごとにチェック

    def poll_map_events(self):
        """地図のイベントキューをチェック"""
        self.map_view.page().runJavaScript("getEvents()", self.handle_map_events)

    def snap_to_road(self, lat, lng):
        """クリック位置を最寄りの道路座標にスナップ

        Args:
            lat: 緯度
            lng: 経度

        Returns:
            (snapped_lat, snapped_lng) または スナップ失敗時は (lat, lng)
        """
        try:
            # OSRM nearest APIを使用（自転車用）
            url = f"https://router.project-osrm.org/nearest/v1/bike/{lng},{lat}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 'Ok' and data.get('waypoints'):
                    snapped = data['waypoints'][0]['location']
                    snapped_lng, snapped_lat = snapped[0], snapped[1]
                    return snapped_lat, snapped_lng
        except Exception as e:
            self.update_status(f"スナップエラー: {e}", "warning")

        # スナップ失敗時は元の座標を返す
        return lat, lng

    def handle_map_events(self, events_json):
        """地図からのイベントを処理"""
        if not events_json:
            return
        try:
            events = json.loads(events_json)
            for event in events:
                if event['type'] == 'add':
                    lat = event['lat']
                    lng = event['lng']
                    # 遅延実行でセグフォ回避（スナップもこの中で行う）
                    QTimer.singleShot(10, lambda la=lat, ln=lng: self._process_add_event(la, ln))

                elif event['type'] == 'move':
                    index = event['index']
                    lat = event['lat']
                    lng = event['lng']
                    # 遅延実行でセグフォ回避（スナップもこの中で行う）
                    QTimer.singleShot(10, lambda idx=index, la=lat, ln=lng: self._process_move_event(idx, la, ln))

        except json.JSONDecodeError:
            pass

    def _process_add_event(self, lat, lng):
        """add イベントの遅延処理"""
        # 道路にスナップ
        lat, lng = self.snap_to_road(lat, lng)
        # ルートが存在する場合は、クリック位置に最も近い区間にWaypointを挿入
        if len(self.waypoints) >= 2 and self.route_coordinates:
            self.insert_waypoint_at_best_position(lat, lng)
        else:
            self.add_waypoint(lat, lng)
            self.update_status(f"ポイント追加: {lat:.5f}, {lng:.5f}")

    def _process_move_event(self, index, lat, lng):
        """move イベントの遅延処理"""
        # 道路にスナップ
        lat, lng = self.snap_to_road(lat, lng)
        self._move_waypoint_deferred(index, lat, lng)

    def _move_waypoint_deferred(self, index, lat, lng):
        """遅延実行用のウェイポイント移動"""
        if 0 <= index < len(self.waypoints):
            old = self.waypoints[index]
            self.waypoints[index] = (lat, lng, old[2])
            # リスト表示を更新
            item = self.point_list.item(index)
            if item:
                item.setText(f"{old[2]} ({lat:.5f}, {lng:.5f})")
            self.update_status(f"ポイント移動: {old[2]} ({lat:.5f}, {lng:.5f})")
            # マーカー位置を更新（スナップ後の座標に）
            self.update_map_markers()
            # 自動ルート計算（Region選択中はLatLon座標を渡して復元）
            if self._region_active and self._region_start_latlng and self._region_end_latlng:
                self.auto_calculate_route(preserve_region_latlng=(self._region_start_latlng, self._region_end_latlng))
            else:
                self.auto_calculate_route()
                # fitBounds（Region選択中でない場合のみ）
                self.fit_map_to_waypoints()

    def _snap_to_road(self, lat, lng):
        """座標を最寄りの道路にスナップ（OSRM Nearest API使用）"""
        try:
            # OSRMのNearest API（自転車プロファイル）
            url = f"http://router.project-osrm.org/nearest/v1/bike/{lng},{lat}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 'Ok' and data.get('waypoints'):
                    waypoint = data['waypoints'][0]
                    snapped_lng, snapped_lat = waypoint['location']
                    distance = waypoint.get('distance', 0)
                    if distance < 1000:  # 1km以内なら採用
                        self.update_status(f"道路にスナップ: {snapped_lat:.5f},{snapped_lng:.5f} (距離: {distance:.0f}m)")
                        return snapped_lat, snapped_lng
        except Exception as e:
            self.update_status(f"スナップエラー: {e}", "warning")
        return None, None

    def add_waypoint(self, lat, lng, name=None):
        """ウェイポイントを追加（道路にスナップ）"""
        if name is None:
            name = f"地点{len(self.waypoints) + 1}"

        # 道路にスナップ
        snapped_lat, snapped_lng = self._snap_to_road(lat, lng)
        if snapped_lat is not None:
            lat, lng = snapped_lat, snapped_lng

        self.waypoints.append((lat, lng, name))

        # リストに追加
        item = QListWidgetItem(f"{name} ({lat:.5f}, {lng:.5f})")
        self.point_list.addItem(item)

        # 地図にマーカー追加
        self.update_map_markers()

        # 自動ルート計算（Region選択中はLatLon座標を渡して復元）
        if self._region_active and self._region_start_latlng and self._region_end_latlng:
            self.auto_calculate_route(preserve_region_latlng=(self._region_start_latlng, self._region_end_latlng))
        else:
            self.auto_calculate_route()
            # fitBounds（Region選択中でない場合のみ）
            self.fit_map_to_waypoints()

    def insert_waypoint_at_best_position(self, lat, lng):
        """クリック位置に最も近いWaypoint区間の間にWaypointを挿入"""
        if len(self.waypoints) < 2:
            self.add_waypoint(lat, lng)
            return

        # クリック位置に最も近いWaypoint区間を見つける
        min_dist = float('inf')
        insert_index = len(self.waypoints)  # デフォルトは末尾

        for i in range(len(self.waypoints) - 1):
            wp1 = self.waypoints[i]
            wp2 = self.waypoints[i + 1]

            # 点と線分の距離を計算
            dist = self._distance_to_segment(lat, lng, wp1[0], wp1[1], wp2[0], wp2[1])

            if dist < min_dist:
                min_dist = dist
                insert_index = i + 1

        # 新しい経由地点を挿入
        name = f"経由{insert_index}"
        self.waypoints.insert(insert_index, (lat, lng, name))

        # リスト表示を更新
        self._refresh_point_list()

        # 地図を更新
        self.update_map_markers()

        self.update_status(f"経由地点挿入: {insert_index}番目 ({lat:.5f}, {lng:.5f})")

        # 自動ルート計算（Region選択中はLatLon座標を渡して復元）
        if self._region_active and self._region_start_latlng and self._region_end_latlng:
            self.auto_calculate_route(preserve_region_latlng=(self._region_start_latlng, self._region_end_latlng))
        else:
            self.auto_calculate_route()
            # fitBounds（Region選択中でない場合のみ）
            self.fit_map_to_waypoints()

    def _distance_to_segment(self, px, py, x1, y1, x2, y2):
        """点(px, py)から線分(x1,y1)-(x2,y2)への距離を計算"""
        import math

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

        # 距離
        return math.sqrt((px - nearest_x) ** 2 + (py - nearest_y) ** 2)

    def _refresh_point_list(self):
        """ポイントリストの表示を更新"""
        self.point_list.clear()
        for lat, lng, name in self.waypoints:
            item = QListWidgetItem(f"{name} ({lat:.5f}, {lng:.5f})")
            self.point_list.addItem(item)

    def delete_selected_point(self):
        """選択したポイントを削除"""
        row = self.point_list.currentRow()
        if row >= 0:
            # 現在のRegion範囲を保存
            saved_region = self.region.getRegion()

            self.point_list.takeItem(row)
            del self.waypoints[row]
            self.update_map_markers()
            # 自動ルート計算（Region保持モード）
            self.auto_calculate_route(preserve_region=saved_region)
            # fitBounds
            self.fit_map_to_waypoints()

    def clear_all_points(self):
        """全ポイントを削除"""
        self.point_list.clear()
        self.waypoints.clear()
        # 地図上のマーカーとルートをクリア
        self.map_view.page().runJavaScript(
            "setMarkers([]); clearMarkers(); clearRegionLine(); clearRegionMarkers();"
            "if(routeLine){map.removeLayer(routeLine);routeLine=null;}"
        )
        # グラフをクリア
        self.route_coordinates = []
        self.elevation_data = []
        self.dist_plot.clear()
        self.region_plot.clear()
        self.hist_plot.clear()

    def on_points_reordered(self):
        """ポイントの並び替え時"""
        new_order = []
        for i in range(self.point_list.count()):
            item_text = self.point_list.item(i).text()
            # テキストからインデックスを特定して並び替え
            for wp in self.waypoints:
                if f"({wp[0]:.5f}, {wp[1]:.5f})" in item_text:
                    new_order.append(wp)
                    break
        self.waypoints = new_order
        self.update_map_markers()
        # 自動ルート計算
        self.auto_calculate_route()
        # fitBounds
        self.fit_map_to_waypoints()

    def update_map_markers(self, auto_zoom=True):
        """地図のマーカーを更新"""
        # ウェイポイントデータをJSON形式で渡し、JavaScript側で一括処理
        waypoints_data = [
            {"lat": lat, "lng": lng, "label": f"{i+1}. {name}"}
            for i, (lat, lng, name) in enumerate(self.waypoints)
        ]
        waypoints_json = json.dumps(waypoints_data)
        self.map_view.page().runJavaScript(f"setMarkers({waypoints_json});")

    def fit_map_to_waypoints(self):
        """地図をウェイポイント全体にフィット（チェックボックスで制御）"""
        if not self.auto_fit_checkbox.isChecked():
            return
        if not self.waypoints:
            return
        # 少し遅延させて、他のJS処理が完了してからfitBoundsを実行
        QTimer.singleShot(300, self._do_fit_bounds)

    def _do_fit_bounds(self):
        """実際のfitBounds処理"""
        if not self.waypoints:
            return
        lats = [wp[0] for wp in self.waypoints]
        lngs = [wp[1] for wp in self.waypoints]
        self.map_view.page().runJavaScript(
            f"doFitBounds({min(lats)}, {min(lngs)}, {max(lats)}, {max(lngs)});"
        )

    def on_auto_fit_changed(self, state):
        """自動フィットチェックボックスの状態変更"""
        # stateは整数値: 0=Unchecked, 2=Checked
        is_checked = (state == 2)
        if is_checked and self.route_coordinates and self.elevation_data:
            # ONにした時に現在のRegion範囲にフィット
            minX, maxX = self.region.getRegion()
            distances = np.array([d[0] for d in self.elevation_data])
            indices = np.where((distances >= minX) & (distances <= maxX))[0]
            if len(indices) > 0:
                region_coords = [self.route_coordinates[i] for i in indices]
                coords_js = json.dumps(region_coords)
                self.map_view.page().runJavaScript(f"fitToRegion({coords_js});")

    def on_gsi_checkbox_changed(self, state):
        """国土地理院標高チェックボックスの状態変更"""
        self.use_gsi_elevation = (state == Qt.Checked)

    def on_bridge_correction_changed(self):
        """橋補正チェックボックスの状態変更時"""
        if len(self.waypoints) >= 2:
            self.auto_calculate_route()

    def set_theme(self, theme):
        """テーマを設定"""
        self.current_theme = theme
        self.apply_theme(theme)
        # pyqtgraphの色も更新
        if theme == "dark":
            bg_color = '#1e1e2e'
            fg_color = '#cdd6f4'
            pg.setConfigOption('background', bg_color)
            pg.setConfigOption('foreground', fg_color)
            # LinearRegionItemの色
            self.region.setBrush(pg.mkBrush(137, 180, 250, 50))
            for line in self.region.lines:
                line.setPen(pg.mkPen(color='#89b4fa', width=2))
        else:
            bg_color = '#eff1f5'
            fg_color = '#4c4f69'
            pg.setConfigOption('background', bg_color)
            pg.setConfigOption('foreground', fg_color)
            # LinearRegionItemの色（ライト用）
            self.region.setBrush(pg.mkBrush(30, 102, 245, 50))
            for line in self.region.lines:
                line.setPen(pg.mkPen(color='#1e66f5', width=2))

        # グラフウィジェットの背景色を更新
        self.graph_widget.setBackground(bg_color)

        # 各プロットの軸の色を更新
        for plot in [self.dist_plot, self.region_plot, self.hist_plot]:
            for axis_name in ['left', 'right', 'top', 'bottom']:
                axis = plot.getAxis(axis_name)
                axis.setPen(pg.mkPen(color=fg_color))
                axis.setTextPen(pg.mkPen(color=fg_color))

        # グラフを再描画
        if self.elevation_data:
            self.update_elevation_graph()

    def apply_theme(self, theme):
        """テーマを適用"""
        if theme == "dark":
            stylesheet = self._get_dark_stylesheet()
        else:
            stylesheet = self._get_light_stylesheet()
        QApplication.instance().setStyleSheet(stylesheet)

    def _get_dark_stylesheet(self):
        """ダークテーマのスタイルシート"""
        return """
            QMainWindow { background-color: #1e1e2e; }
            QWidget {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: 'Hiragino Sans', 'Yu Gothic UI', 'Meiryo', sans-serif;
                font-size: 18px;
            }
            QGroupBox {
                background-color: transparent;
                border: 1px solid #45475a;
                border-radius: 8px;
                margin-top: 8px;
                padding: 8px;
                padding-top: 16px;
                font-weight: bold;
                font-size: 18px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                top: 0px;
                padding: 0 6px;
                background-color: #1e1e2e;
                color: #89b4fa;
            }
            QPushButton {
                background-color: #45475a;
                border: none;
                border-radius: 6px;
                padding: 12px 18px;
                color: #cdd6f4;
                font-weight: 500;
                font-size: 18px;
            }
            QPushButton:hover { background-color: #585b70; }
            QPushButton:pressed { background-color: #89b4fa; color: #1e1e2e; }
            QLineEdit {
                background-color: #313244;
                border: 2px solid #45475a;
                border-radius: 6px;
                padding: 10px 14px;
                color: #cdd6f4;
                font-size: 18px;
                selection-background-color: #89b4fa;
            }
            QLineEdit:focus { border-color: #89b4fa; }
            QListWidget {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 4px;
                font-size: 18px;
            }
            QListWidget::item { padding: 8px 10px; border-radius: 4px; }
            QListWidget::item:selected { background-color: #89b4fa; color: #1e1e2e; }
            QListWidget::item:hover { background-color: #45475a; }
            QComboBox {
                background-color: #313244;
                border: 2px solid #45475a;
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 18px;
                min-width: 100px;
            }
            QComboBox:hover { border-color: #585b70; }
            QComboBox:focus { border-color: #89b4fa; }
            QComboBox::drop-down { border: none; width: 28px; }
            QComboBox::down-arrow {
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 7px solid #cdd6f4;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #313244;
                border: 1px solid #45475a;
                selection-background-color: #89b4fa;
                selection-color: #1e1e2e;
                padding: 4px;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px 12px;
                min-height: 24px;
            }
            QCheckBox { spacing: 10px; font-size: 18px; }
            QCheckBox::indicator {
                width: 20px; height: 20px;
                border: 2px solid #45475a;
                border-radius: 4px;
                background-color: #313244;
            }
            QCheckBox::indicator:checked { background-color: #89b4fa; border-color: #89b4fa; }
            QCheckBox::indicator:hover { border-color: #89b4fa; }
            QTableWidget {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                font-size: 18px;
            }
            QTableWidget::item { padding: 8px; }
            QTableWidget::item:selected { background-color: #89b4fa; color: #1e1e2e; }
            QHeaderView::section {
                background-color: #45475a;
                color: #cdd6f4;
                padding: 10px;
                border: none;
                font-weight: bold;
                font-size: 18px;
            }
            QProgressBar {
                background-color: #313244;
                border: none;
                border-radius: 5px;
                height: 10px;
            }
            QProgressBar::chunk { background-color: #89b4fa; border-radius: 5px; }
            QLabel { color: #bac2de; font-size: 18px; }
            QScrollBar:vertical {
                background-color: #313244;
                width: 14px;
                border-radius: 7px;
            }
            QScrollBar::handle:vertical {
                background-color: #45475a;
                border-radius: 7px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover { background-color: #585b70; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal {
                background-color: #313244;
                height: 14px;
                border-radius: 7px;
            }
            QScrollBar::handle:horizontal {
                background-color: #45475a;
                border-radius: 7px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover { background-color: #585b70; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        """

    def _get_light_stylesheet(self):
        """ライトテーマのスタイルシート"""
        return """
            QMainWindow { background-color: #eff1f5; }
            QWidget {
                background-color: #eff1f5;
                color: #4c4f69;
                font-family: 'Hiragino Sans', 'Yu Gothic UI', 'Meiryo', sans-serif;
                font-size: 18px;
            }
            QGroupBox {
                background-color: transparent;
                border: 1px solid #ccd0da;
                border-radius: 8px;
                margin-top: 8px;
                padding: 8px;
                padding-top: 16px;
                font-weight: bold;
                font-size: 18px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                top: 0px;
                padding: 0 6px;
                background-color: #eff1f5;
                color: #1e66f5;
            }
            QPushButton {
                background-color: #ccd0da;
                border: none;
                border-radius: 6px;
                padding: 12px 18px;
                color: #4c4f69;
                font-weight: 500;
                font-size: 18px;
            }
            QPushButton:hover { background-color: #bcc0cc; }
            QPushButton:pressed { background-color: #1e66f5; color: #eff1f5; }
            QLineEdit {
                background-color: #e6e9ef;
                border: 2px solid #ccd0da;
                border-radius: 6px;
                padding: 10px 14px;
                color: #4c4f69;
                font-size: 18px;
                selection-background-color: #1e66f5;
                selection-color: #eff1f5;
            }
            QLineEdit:focus { border-color: #1e66f5; }
            QListWidget {
                background-color: #e6e9ef;
                border: 1px solid #ccd0da;
                border-radius: 6px;
                padding: 4px;
                font-size: 18px;
            }
            QListWidget::item { padding: 8px 10px; border-radius: 4px; }
            QListWidget::item:selected { background-color: #1e66f5; color: #eff1f5; }
            QListWidget::item:hover { background-color: #ccd0da; }
            QComboBox {
                background-color: #e6e9ef;
                border: 2px solid #ccd0da;
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 18px;
                min-width: 100px;
            }
            QComboBox:hover { border-color: #bcc0cc; }
            QComboBox:focus { border-color: #1e66f5; }
            QComboBox::drop-down { border: none; width: 28px; }
            QComboBox::down-arrow {
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 7px solid #4c4f69;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #e6e9ef;
                border: 1px solid #ccd0da;
                selection-background-color: #1e66f5;
                selection-color: #eff1f5;
                padding: 4px;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px 12px;
                min-height: 24px;
            }
            QCheckBox { spacing: 10px; font-size: 18px; }
            QCheckBox::indicator {
                width: 20px; height: 20px;
                border: 2px solid #ccd0da;
                border-radius: 4px;
                background-color: #e6e9ef;
            }
            QCheckBox::indicator:checked { background-color: #1e66f5; border-color: #1e66f5; }
            QCheckBox::indicator:hover { border-color: #1e66f5; }
            QTableWidget {
                background-color: #e6e9ef;
                border: 1px solid #ccd0da;
                border-radius: 6px;
                font-size: 18px;
            }
            QTableWidget::item { padding: 8px; }
            QTableWidget::item:selected { background-color: #1e66f5; color: #eff1f5; }
            QHeaderView::section {
                background-color: #ccd0da;
                color: #4c4f69;
                padding: 10px;
                border: none;
                font-weight: bold;
                font-size: 18px;
            }
            QProgressBar {
                background-color: #ccd0da;
                border: none;
                border-radius: 5px;
                height: 10px;
            }
            QProgressBar::chunk { background-color: #1e66f5; border-radius: 5px; }
            QLabel { color: #5c5f77; font-size: 18px; }
            QScrollBar:vertical {
                background-color: #e6e9ef;
                width: 14px;
                border-radius: 7px;
            }
            QScrollBar::handle:vertical {
                background-color: #ccd0da;
                border-radius: 7px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover { background-color: #bcc0cc; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal {
                background-color: #e6e9ef;
                height: 14px;
                border-radius: 7px;
            }
            QScrollBar::handle:horizontal {
                background-color: #ccd0da;
                border-radius: 7px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover { background-color: #bcc0cc; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        """

    def auto_calculate_route(self, preserve_region=None, preserve_region_latlng=None):
        """ポイント変更時に自動でルートを計算

        Args:
            preserve_region: Regionの範囲を保持する場合は (minX, maxX) のタプル（距離ベース）
            preserve_region_latlng: Regionの範囲を保持する場合は ((start_lat, start_lng), (end_lat, end_lng))（座標ベース）
        """
        if len(self.waypoints) < 2:
            # 2点未満の場合はルートをクリア
            self.map_view.page().runJavaScript("if(routeLine){map.removeLayer(routeLine);routeLine=null;}")
            self.map_view.page().runJavaScript("clearRegionLine();")
            self.route_coordinates = []
            self.elevation_data = []
            self.dist_plot.clear()
            self.region_plot.clear()
            self.hist_plot.clear()
            # Region状態もリセット
            self._region_active = False
            self._region_start_latlng = None
            self._region_end_latlng = None
            return

        # ルート計算を実行（エラーは表示しない）
        self._calculate_route_silent(preserve_region=preserve_region, preserve_region_latlng=preserve_region_latlng)

    def _calculate_route_silent(self, preserve_region=None, preserve_region_latlng=None):
        """ルート計算（OpenRouteService使用、エラーダイアログなし）

        Args:
            preserve_region: Regionの範囲を保持する場合は (minX, maxX) のタプル（距離ベース）
            preserve_region_latlng: Regionの範囲を保持する場合は ((start_lat, start_lng), (end_lat, end_lng))（座標ベース）
        """
        if not ORS_API_KEY:
            self.update_status("ORS APIキーが設定されていません", "error")
            return

        # OpenRouteService API呼び出し
        coordinates = [[wp[1], wp[0]] for wp in self.waypoints]  # [lng, lat]形式
        url = "https://api.openrouteservice.org/v2/directions/cycling-regular"

        headers = {
            "Authorization": ORS_API_KEY,
            "Content-Type": "application/json"
        }

        body = {
            "coordinates": coordinates,
            "elevation": True,
            "instructions": False,
            "geometry_simplify": False,
            "extra_info": ["steepness"],
            "preference": "recommended",
            "options": {
                "avoid_features": ["ferries", "steps"]  # フェリー・階段を回避
            }
        }

        try:
            response = requests.post(url, json=body, headers=headers, timeout=30)

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                error_msg = f"ORSエラー: {response.status_code}"
                if 'error' in error_data:
                    error_msg += f" - {error_data.get('error', {}).get('message', '')}"
                self.update_status(error_msg, "error")
                return

            data = response.json()

            # ルート座標を取得
            geometry = data['routes'][0]['geometry']

            # geometryがpolyline文字列かGeoJSON形式かを判定
            if isinstance(geometry, str):
                # Polyline形式をデコード（3D: 標高付き）
                self._decoded_elevations = None
                self.route_coordinates = self.decode_polyline(geometry, include_elevation=True)
            elif isinstance(geometry, dict) and 'coordinates' in geometry:
                # GeoJSON形式
                coords = geometry['coordinates']
                self.route_coordinates = [[c[1], c[0]] for c in coords]
            else:
                self.update_status(f"不明なgeometry形式: {type(geometry)}", "error")
                return

            # 地図にルートを描画
            coords_js = json.dumps(self.route_coordinates)
            self.map_view.page().runJavaScript(f"drawRoute({coords_js});")

            # 標高データを分析（国土地理院から取得）
            self.analyze_elevation(None, preserve_region=preserve_region, preserve_region_latlng=preserve_region_latlng)

        except requests.exceptions.RequestException as e:
            self.update_status(f"ルート計算エラー: {e}", "error")
        except Exception as e:
            self.update_status(f"ルート処理エラー: {e}", "error")

    def update_cache_label(self):
        """キャッシュ情報ラベルを更新"""
        stats = self.elevation_cache.get_stats()
        self.cache_label.setText(
            f"キャッシュ: {stats['tile_count']}タイル / {stats['db_size_mb']:.1f}MB"
        )

    def on_serpapi_checkbox_changed(self, state):
        """SerpApiチェックボックスの状態変更"""
        from geocode import set_api_key_path
        from config import get_api_key_path, load_api_key

        if state != 2:  # 2 = Checked
            self.serpapi_remaining_label.setText("")
            return

        # ONにした場合、APIキーを確認

        # まず保存されたカスタムパスを確認
        if self._serpapi_key_path and self._serpapi_key_path.exists():
            key = load_api_key("serpapi", self._serpapi_key_path)
            if key:
                set_api_key_path(self._serpapi_key_path)
                self.update_serpapi_remaining()
                return

        # デフォルトパスを確認
        default_path = get_api_key_path("serpapi")
        if default_path and default_path.exists():
            key = load_api_key("serpapi")
            if key:
                self._serpapi_key_path = default_path
                set_api_key_path(default_path)
                self.update_serpapi_remaining()
                return

        # キーが見つからない場合、ファイル選択ダイアログを表示
        msg = QMessageBox(self)
        msg.setWindowTitle("SerpAPI キー")
        msg.setText(f"SerpAPI キーファイルが見つかりません。\n\nデフォルトの場所:\n{default_path}")
        msg.setInformativeText("キーファイルの場所を指定しますか？")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)

        if msg.exec() == QMessageBox.Yes:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "SerpAPI キーファイルを選択",
                str(Path.home()),
                "All Files (*)",
                options=QFileDialog.Option.DontUseNativeDialog
            )
            if file_path:
                key_path = Path(file_path)
                try:
                    key = key_path.read_text().strip()
                    if key:
                        self._serpapi_key_path = key_path
                        set_api_key_path(key_path)
                        self.update_serpapi_remaining()
                        return
                except Exception as e:
                    QMessageBox.warning(self, "エラー", f"キーファイルの読み込みに失敗しました:\n{e}")

        # キーが確認できなかった場合、チェックボックスをOFFに戻す
        self.serpapi_checkbox.blockSignals(True)
        self.serpapi_checkbox.setChecked(False)
        self.serpapi_checkbox.blockSignals(False)
        self.serpapi_remaining_label.setText("(キー未設定)")

    def update_serpapi_remaining(self):
        """SerpApi残りリクエスト数を更新"""
        try:
            from geocode import get_account_info
            info = get_account_info()
            if info:
                remaining = info['plan_searches_left']
                total = info['searches_per_month']
                self.serpapi_remaining_label.setText(f"(残り {remaining}/{total})")
                # 残り0の場合はチェックボックスを無効化
                if remaining <= 0:
                    self.serpapi_checkbox.setChecked(False)
                    self.serpapi_checkbox.setEnabled(False)
                else:
                    self.serpapi_checkbox.setEnabled(True)
            else:
                self.serpapi_remaining_label.setText("(取得失敗)")
        except Exception as e:
            self.serpapi_remaining_label.setText("(エラー)")

    def _on_search_text_changed(self, text):
        """検索テキスト変更時（デバウンス付きインクリメンタルサーチ）"""
        if text.strip():
            self.search_timer.start(500)  # 0.5秒後に検索
        else:
            self.search_timer.stop()
            self.search_result_list.clear()
            self.search_results = []

    def search_landmark(self):
        """ランドマーク名から座標を検索（国土地理院 + Nominatim併用）"""
        query = self.landmark_input.text().strip()
        if not query:
            return

        # 緯度経度形式のチェック（例: 35.6812, 139.7671 または 35.6812,139.7671）
        import re
        latlon_pattern = r'^(-?\d+\.?\d*)\s*[,、]\s*(-?\d+\.?\d*)$'
        match = re.match(latlon_pattern, query)
        if match:
            try:
                lat = float(match.group(1))
                lon = float(match.group(2))
                # 日本の範囲チェック（緯度20-46、経度122-154）
                if 20 <= lat <= 46 and 122 <= lon <= 154:
                    self.search_result_list.clear()
                    self.search_results = [{
                        'lat': lat,
                        'lon': lon,
                        'name': f"座標 ({lat:.5f}, {lon:.5f})",
                        'source': 'manual'
                    }]
                    item = QListWidgetItem(f"座標 ({lat:.5f}, {lon:.5f})")
                    self.search_result_list.addItem(item)
                    self.landmark_input.clear()
                    return
            except ValueError:
                pass

        self.search_result_list.clear()
        self.search_results = []  # 検索結果を保持

        # 1. SerpAPI（Google AI概要から緯度経度を抽出）
        if self.serpapi_checkbox.isChecked() and self.serpapi_checkbox.isEnabled():
            try:
                from geocode import get_coordinates
                self.update_status(f"SerpAPI検索中: {query}")
                result = get_coordinates(query)
                if result:
                    self.search_results.append({
                        'lat': result['lat'],
                        'lon': result['lng'],
                        'name': f"[Google] {result['name']}",
                        'source': 'google'
                    })
                # 使用後に残り回数を更新
                self.update_serpapi_remaining()
            except Exception as e:
                self.update_status(f"SerpAPI検索エラー: {e}", "warning")

        # 2. Nominatim API（OSM - 駅名・施設名に強い）
        try:
            url_nom = "https://nominatim.openstreetmap.org/search"
            params = {
                "q": query,
                "format": "json",
                "limit": 5,
                "countrycodes": "jp"
            }
            headers = {"User-Agent": "RoutePlanner/1.0"}
            response = requests.get(url_nom, params=params, headers=headers, timeout=5)
            if response.status_code == 200:
                results = response.json()
                for result in results:
                    # 短い表示名
                    display = result['display_name'].split(',')[0]
                    self.search_results.append({
                        'lat': float(result['lat']),
                        'lon': float(result['lon']),
                        'name': f"[OSM] {display}",
                        'source': 'osm'
                    })
        except:
            pass

        # 3. 国土地理院 地名検索API（住所に強い）
        try:
            url_gsi = "https://msearch.gsi.go.jp/address-search/AddressSearch"
            response = requests.get(url_gsi, params={"q": query}, timeout=5)
            if response.status_code == 200:
                results = response.json()
                for result in results[:5]:
                    coords = result['geometry']['coordinates']
                    name = result['properties']['title']
                    self.search_results.append({
                        'lat': coords[1],
                        'lon': coords[0],
                        'name': f"[GSI] {name}",
                        'source': 'gsi'
                    })
        except:
            pass

        # 結果を表示
        if not self.search_results:
            self.search_result_list.addItem("検索結果なし")
            return

        for result in self.search_results:
            item = QListWidgetItem(result['name'])
            self.search_result_list.addItem(item)

    def add_search_result(self, item):
        """検索結果からポイントを追加"""
        index = self.search_result_list.row(item)
        if 0 <= index < len(self.search_results):
            result = self.search_results[index]
            # [GSI] や [OSM], [Google] プレフィックスを除去
            name = result['name']
            if name.startswith('[GSI] '):
                name = name[6:]
            elif name.startswith('[OSM] '):
                name = name[6:]
            elif name.startswith('[Google] '):
                name = name[9:]

            self.add_waypoint(result['lat'], result['lon'], name)

            # 地図をその位置に移動（チェックボックスがONの場合のみ）
            if self.auto_fit_checkbox.isChecked():
                self.map_view.page().runJavaScript(
                    f"map.setView([{result['lat']}, {result['lon']}], 14);"
                )

            # 入力欄と検索結果をクリア
            self.landmark_input.clear()
            self.search_result_list.clear()
            self.search_results = []

    def on_region_changed(self):
        """Region選択範囲が変更された時の処理（ver11.pyスタイル）"""
        if not self.elevation_data or not hasattr(self, 'slopes'):
            return

        minX, maxX = self.region.getRegion()

        # メイングラフのX軸範囲を更新
        self.dist_plot.setXRange(minX, maxX, padding=0)

        # 選択範囲のデータを抽出
        distances = np.array([d[0] for d in self.elevation_data])
        elevations = np.array([d[1] for d in self.elevation_data])

        # 範囲内のインデックスを取得
        indices = np.where((distances >= minX) & (distances <= maxX))[0]

        if len(indices) == 0:
            return

        # ヒストグラムの更新（ver11.pyと同様）
        self.hist_plot.clear()
        self.hist_plot.setAutoVisible(y=True)

        region_slopes = self.slopes[indices]
        # NaN除去
        region_slopes = region_slopes[~np.isnan(region_slopes)]

        if len(region_slopes) > 0:
            slope_min = np.nanmin(region_slopes)
            slope_max = np.nanmax(region_slopes)

            if not (np.isnan(slope_min) or np.isnan(slope_max)) and slope_max > slope_min:
                resol = max(int((np.ceil(slope_max) - np.floor(slope_min)) * 16), 2)
                y, x = np.histogram(region_slopes,
                                    bins=np.linspace(np.floor(slope_min), np.ceil(slope_max), resol))
                hist_x = np.delete(x, 0)  # 最初の要素を削除
                self.hist_plot.addItem(
                    pg.PlotDataItem(hist_x, y, pen=self.slope_pen_h,
                                    symbolBrush=None, symbolPen=None, symbolSize=5)
                )

        # 選択範囲の座標を地図にハイライト表示
        # 全範囲選択時はRegionラインを非表示（青いルートラインを見せる）
        region_coords = [self.route_coordinates[i] for i in indices]
        is_full_range = (len(indices) >= len(self.route_coordinates) - 1)
        if is_full_range:
            self.map_view.page().runJavaScript("clearRegionLine();")
            # 全範囲選択時はRegion状態をリセット
            self._region_active = False
            self._region_start_latlng = None
            self._region_end_latlng = None
        else:
            coords_js = json.dumps(region_coords)
            self.map_view.page().runJavaScript(f"drawRegionLine({coords_js});")
            # Region選択中の座標を保存（ポイント追加・移動時に維持するため）
            self._region_active = True
            self._region_start_latlng = (region_coords[0][0], region_coords[0][1])
            self._region_end_latlng = (region_coords[-1][0], region_coords[-1][1])

        # 地図を選択範囲にフィット（1秒遅延、ユーザー操作時のみ）
        if not self._suppress_region_fit:
            self._pending_fit_coords = region_coords
            self.fit_timer.start(1000)

        # Region端マーカーを地図上に表示（始点:緑、終点:赤）
        if len(region_coords) > 0:
            start_coord = region_coords[0]
            end_coord = region_coords[-1]
            self.map_view.page().runJavaScript(
                f"updateRegionMarkers({start_coord[0]}, {start_coord[1]}, {end_coord[0]}, {end_coord[1]});"
            )

        # 選択範囲の統計を計算
        region_distances = distances[indices].tolist()
        region_elevations = elevations[indices].tolist()
        self.calculate_statistics(region_distances, region_elevations)

    def _do_fit_to_region(self):
        """タイマーから呼ばれて地図をフィット"""
        if self._pending_fit_coords:
            coords_js = json.dumps(self._pending_fit_coords)
            self.map_view.page().runJavaScript(f"fitToRegion({coords_js});")

    def decode_polyline(self, encoded, include_elevation=True):
        """Google Polyline形式をデコード（3D対応：標高付き）"""
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

        self._decoded_elevations = elevations if elevations else None
        return decoded

    def analyze_elevation(self, elevations_from_api=None, preserve_region=None, preserve_region_latlng=None):
        """標高データを分析

        Args:
            elevations_from_api: APIから取得した標高データ
            preserve_region: Regionの範囲を保持する場合は (minX, maxX) のタプル（距離ベース）
            preserve_region_latlng: Regionの範囲を保持する場合は ((start_lat, start_lng), (end_lat, end_lng))（座標ベース）
        """
        if not self.route_coordinates:
            return

        distances = [0]

        # 距離計算
        for i in range(1, len(self.route_coordinates)):
            lat, lng = self.route_coordinates[i]
            prev_lat, prev_lng = self.route_coordinates[i-1]
            dist = self.haversine(prev_lat, prev_lng, lat, lng)
            distances.append(distances[-1] + dist)

        # 標高データ
        if elevations_from_api and len(elevations_from_api) == len(self.route_coordinates):
            # APIから取得した標高を使用
            elevations = elevations_from_api
            self.update_status(f"標高データ取得完了: {len(elevations)}ポイント", "success")
        elif self.use_gsi_elevation:
            # 国土地理院5mメッシュから標高を取得
            self.update_status("国土地理院5mメッシュから標高取得中...")

            coordinates = [(lat, lng) for lat, lng in self.route_coordinates]

            elevations = self.elevation_cache.get_elevations_batch(coordinates)

            # Noneを0に置換
            elevations = [e if e is not None else 0 for e in elevations]

            self.update_cache_label()  # キャッシュ情報を更新
            self.update_status(f"標高データ取得完了: {len(elevations)}ポイント", "success")
        else:
            # 標高データがない場合は0で埋める
            elevations = [0] * len(self.route_coordinates)
            self.update_status("警告: 標高データがありません", "warning")

        # 橋・トンネル区間の標高補正
        if self.bridge_correction_checkbox.isChecked():
            elevations = self._correct_bridge_elevations(distances, elevations)

        self.elevation_data = list(zip(distances, elevations))

        # グラフ更新
        self.update_elevation_graph(preserve_region=preserve_region, preserve_region_latlng=preserve_region_latlng)

        # 全ルートの統計計算
        self.calculate_total_statistics(distances, elevations)

        # 選択範囲の統計計算（初期は全範囲）
        self.calculate_statistics(distances, elevations)

    def _correct_bridge_elevations(self, distances, elevations):
        """橋・トンネル区間の標高を補正

        検出条件:
        1. 標高が急激に低下（前後との差が大きい）
        2. 低い標高が連続する区間
        3. 前後の標高から推定される値と大きく乖離

        補正方法:
        - 異常区間の始点と終点を検出
        - 線形補間で橋/トンネルの標高を推定
        """
        if len(elevations) < 3:
            return elevations

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
                ref_start_elev = elevations[ref_start_idx] if not anomaly_mask[ref_start_idx] else expected[ref_start_idx]

                # 終了点: 異常区間の直後の正常点
                ref_end_idx = end_idx + 1 if end_idx < n - 1 else end_idx
                ref_end_elev = elevations[ref_end_idx] if ref_end_idx < n and not anomaly_mask[ref_end_idx] else expected[ref_end_idx]

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

        if corrected_count > 0:
            self.update_status(f"橋・トンネル補正: {corrected_count}ポイントを補正", "success")

        return elevations

    def get_elevation_gsi(self, lat, lng):
        """国土地理院の標高タイルから標高を取得"""
        import math

        zoom = 15
        x = int((lng + 180) / 360 * (2 ** zoom))
        y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * (2 ** zoom))

        # DEM5Aを試行、なければDEM10B
        for dem_type in ['dem5a_png', 'dem5b_png', 'dem5c_png', 'dem_png']:
            url = f"https://cyberjapandata.gsi.go.jp/xyz/{dem_type}/{zoom}/{x}/{y}.txt"
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    # テキスト形式の標高データをパース
                    lines = response.text.strip().split('\n')
                    # タイル内の位置を計算
                    tile_size = 256
                    px = int((lng - (x * 360 / (2 ** zoom) - 180)) * (2 ** zoom) * tile_size / 360) % tile_size
                    py = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * (2 ** zoom) * tile_size) % tile_size

                    if py < len(lines):
                        values = lines[py].split(',')
                        if px < len(values) and values[px] != 'e':
                            return float(values[px])
            except:
                continue

        return None

    def haversine(self, lat1, lng1, lat2, lng2):
        """2点間の距離を計算（km）"""
        import math
        R = 6371  # 地球の半径（km）

        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        return R * c

    def update_elevation_graph(self, preserve_region=None, preserve_region_latlng=None):
        """高度プロファイルグラフを更新（ver11.pyスタイル）

        Args:
            preserve_region: Regionの範囲を保持する場合は (minX, maxX) のタプル（距離ベース）
            preserve_region_latlng: Regionの範囲を保持する場合は ((start_lat, start_lng), (end_lat, end_lng))（座標ベース）
        """
        self.dist_plot.clear()
        self.region_plot.clear()
        self.hist_plot.clear()

        if not self.elevation_data:
            return

        distances = np.array([d[0] for d in self.elevation_data])
        elevations = np.array([d[1] for d in self.elevation_data])

        # preserve_region_latlngが指定されている場合、LatLonから距離に変換
        if preserve_region_latlng is not None and preserve_region is None:
            preserve_region = self._latlng_to_distance_region(preserve_region_latlng, distances)

        # 斜度を計算（移動平均付き）
        self.slopes = self._calculate_slopes(distances, elevations)

        # テーマに応じた色を選択
        is_dark = self.current_theme == "dark"
        elevation_color = '#04d9c4' if is_dark else '#0a7a7a'

        # 高度グラフ（下部を半透明グレーで塗りつぶし）
        pen_dist = pg.mkPen(color=elevation_color, width=3)
        fill_brush = pg.mkBrush(color=(128, 128, 128, 80))
        self.dist_plot.plot(distances, elevations, pen=pen_dist, fillLevel=0, brush=fill_brush)

        # 斜度グラフを高度0を基準に重ねる
        # 斜度±10%が高度範囲の1/8程度になるようスケール
        elev_max = elevations.max() if len(elevations) > 0 else 100
        self.slope_scale_factor = elev_max / 80  # 斜度の表示幅を大きめに
        scaled_slopes = self.slopes * self.slope_scale_factor
        self.dist_plot.plot(distances, scaled_slopes, pen=self.slope_pen)

        # 左軸の目盛りを斜度値で表示
        left_axis = self.dist_plot.getAxis('left')
        slope_ticks = [(-10, '-10'), (-5, '-5'), (0, '0'), (5, '5'), (10, '10')]
        tick_vals = [(s * self.slope_scale_factor, label) for s, label in slope_ticks]
        left_axis.setTicks([tick_vals])

        # Region用グラフ（高度を破線で表示）
        region_color = '#f5a524' if is_dark else '#b06b00'
        region_pen = pg.mkPen(color=region_color, width=2, style=Qt.DashLine)
        self.region_plot.plot(distances, elevations, pen=region_pen)

        # 両プロットのX軸・Y軸範囲を設定
        if len(distances) > 0:
            x_min, x_max = distances[0], distances[-1]
            self.dist_plot.setXRange(x_min, x_max, padding=0)
            self.region_plot.setXRange(x_min, x_max, padding=0)

            # Y軸の自動スケーリング
            self.dist_plot.enableAutoRange(axis='y')
            self.region_plot.enableAutoRange(axis='y')

        # Regionを追加し直す（clearで消えるため）
        self.region_plot.addItem(self.region, ignoreBounds=True)

        # Regionの範囲を設定（プログラム的な変更なのでフィット抑制）
        if len(distances) > 0:
            self._suppress_region_fit = True
            region_restored = False
            try:
                if preserve_region is not None:
                    # 保存されたRegion範囲を復元（データ範囲内にクランプ）
                    min_x = max(preserve_region[0], distances[0])
                    max_x = min(preserve_region[1], distances[-1])
                    # 範囲が有効な場合のみ設定
                    if min_x < max_x:
                        self.region.setRegion([min_x, max_x])
                        region_restored = True
                    else:
                        self.region.setRegion([distances[0], distances[-1]])
                else:
                    self.region.setRegion([distances[0], distances[-1]])
            finally:
                self._suppress_region_fit = False

            # preserve_region_latlngからRegionを復元した場合、地図もフィットさせる
            if region_restored and preserve_region_latlng is not None:
                # Region範囲の座標を取得
                min_x, max_x = self.region.getRegion()
                indices = np.where((distances >= min_x) & (distances <= max_x))[0]
                if len(indices) > 0:
                    region_coords = [self.route_coordinates[i] for i in indices]
                    # Regionラインを描画
                    is_full_range = (len(indices) >= len(self.route_coordinates) - 1)
                    if not is_full_range:
                        coords_js = json.dumps(region_coords)
                        self.map_view.page().runJavaScript(f"drawRegionLine({coords_js});")
                        # Region端マーカーを更新
                        start_coord = region_coords[0]
                        end_coord = region_coords[-1]
                        self.map_view.page().runJavaScript(
                            f"updateRegionMarkers({start_coord[0]}, {start_coord[1]}, {end_coord[0]}, {end_coord[1]});"
                        )
                        # Region座標を更新
                        self._region_start_latlng = (start_coord[0], start_coord[1])
                        self._region_end_latlng = (end_coord[0], end_coord[1])
                    # 地図をフィット
                    coords_js = json.dumps(region_coords)
                    self.map_view.page().runJavaScript(f"fitToRegion({coords_js});")

    def _latlng_to_distance_region(self, region_latlng, distances):
        """LatLon座標からルート上の最近傍点を見つけて距離範囲に変換

        Args:
            region_latlng: ((start_lat, start_lng), (end_lat, end_lng))
            distances: 距離配列

        Returns:
            (min_distance, max_distance) のタプル、または None
        """
        if not self.route_coordinates or len(self.route_coordinates) == 0:
            return None

        start_latlng, end_latlng = region_latlng

        # 始点に最も近いルート上の点を見つける
        start_idx = self._find_nearest_route_index(start_latlng[0], start_latlng[1])
        # 終点に最も近いルート上の点を見つける
        end_idx = self._find_nearest_route_index(end_latlng[0], end_latlng[1])

        if start_idx is None or end_idx is None:
            return None

        # インデックスを正しい順序に
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx

        # インデックスから距離を取得
        if start_idx < len(distances) and end_idx < len(distances):
            return (distances[start_idx], distances[end_idx])

        return None

    def _find_nearest_route_index(self, lat, lng):
        """指定座標に最も近いルート上の点のインデックスを返す"""
        if not self.route_coordinates:
            return None

        min_dist = float('inf')
        nearest_idx = 0

        for i, coord in enumerate(self.route_coordinates):
            coord_lat, coord_lng = coord[0], coord[1]
            # 簡易距離計算（厳密なhaversineは不要、相対比較のため）
            dist = (lat - coord_lat) ** 2 + (lng - coord_lng) ** 2
            if dist < min_dist:
                min_dist = dist
                nearest_idx = i

        return nearest_idx

    def _calculate_slopes(self, distances, elevations, window=50):
        """斜度を計算（移動平均付き）"""
        if len(distances) < 2:
            return np.zeros(len(distances))

        # 各区間の斜度を計算
        slopes = np.zeros(len(distances))
        for i in range(1, len(distances)):
            dist_diff = (distances[i] - distances[i-1]) * 1000  # km to m
            if dist_diff > 0:
                slopes[i] = (elevations[i] - elevations[i-1]) / dist_diff * 100

        # 移動平均でスムージング
        if len(slopes) >= window:
            kernel = np.ones(window) / window
            slopes_smooth = np.convolve(slopes, kernel, mode='same')
            # 端の処理
            slopes_smooth[:window//2] = slopes[:window//2]
            slopes_smooth[-window//2:] = slopes[-window//2:]
            return slopes_smooth

        return slopes

    def calculate_statistics(self, distances, elevations):
        """統計情報を計算してラベル更新"""
        if not distances or len(distances) < 2:
            return

        # 選択範囲の距離
        region_distance = distances[-1] - distances[0]

        # 獲得標高
        gain = 0
        loss = 0
        for i in range(1, len(elevations)):
            diff = elevations[i] - elevations[i-1]
            if diff > 0:
                gain += diff
            else:
                loss += abs(diff)

        # 勾配計算
        slopes = []
        for i in range(1, len(elevations)):
            dist_diff = (distances[i] - distances[i-1]) * 1000  # km to m
            if dist_diff > 0:
                slope = (elevations[i] - elevations[i-1]) / dist_diff * 100
                slopes.append(slope)

        max_slope = max(slopes) if slopes else 0
        avg_slope = sum(slopes) / len(slopes) if slopes else 0

        # ラベル更新
        self.distance_label.setText(f"{region_distance:.2f} km")
        self.gain_label.setText(f"{gain:.0f} m")
        self.loss_label.setText(f"{loss:.0f} m")
        self.max_slope_label.setText(f"{max_slope:.1f} %")
        self.avg_slope_label.setText(f"{avg_slope:.1f} %")

    def calculate_total_statistics(self, distances, elevations):
        """全ルートの統計情報を計算してラベル更新"""
        if not distances or len(distances) < 2:
            return

        # 全ルートの距離
        total_distance = distances[-1] - distances[0]

        # 獲得標高
        gain = 0
        loss = 0
        for i in range(1, len(elevations)):
            diff = elevations[i] - elevations[i-1]
            if diff > 0:
                gain += diff
            else:
                loss += abs(diff)

        # 勾配計算
        slopes = []
        for i in range(1, len(elevations)):
            dist_diff = (distances[i] - distances[i-1]) * 1000  # km to m
            if dist_diff > 0:
                slope = (elevations[i] - elevations[i-1]) / dist_diff * 100
                slopes.append(slope)

        max_slope = max(slopes) if slopes else 0
        avg_slope = sum(slopes) / len(slopes) if slopes else 0

        # 全ルートラベル更新
        self.total_distance_label.setText(f"{total_distance:.2f} km")
        self.total_gain_label.setText(f"{gain:.0f} m")
        self.total_loss_label.setText(f"{loss:.0f} m")
        self.total_max_slope_label.setText(f"{max_slope:.1f} %")
        self.total_avg_slope_label.setText(f"{avg_slope:.1f} %")

    def save_waypoints(self):
        """ルート情報をJSONファイルに保存"""
        if not self.waypoints:
            QMessageBox.warning(self, "エラー", "保存するルートがありません")
            return

        filename = self._open_file_dialog("ルート保存", ['.json'], save=True)

        if filename:
            if not filename.endswith('.json'):
                filename += '.json'

            data = {
                "waypoints": [
                    {"lat": lat, "lng": lng, "name": name}
                    for lat, lng, name in self.waypoints
                ]
            }

            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                QMessageBox.warning(self, "エラー", f"保存に失敗しました:\n{e}")

    def load_waypoints(self):
        """JSONファイルからルート情報を読み込み"""
        filename = self._open_file_dialog("ルート読込", ['.json'])

        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 既存の地点をクリア
                self.clear_all_points()

                # 地点を追加
                for wp in data.get("waypoints", []):
                    self.add_waypoint(wp["lat"], wp["lng"], wp.get("name"))

            except Exception as e:
                QMessageBox.warning(self, "エラー", f"読み込みに失敗しました:\n{e}")

    def load_gpx(self):
        """GPXファイルからルート情報を読み込み（ルート計算なし）"""
        filename = self._open_file_dialog("GPX読込", ['.gpx'])

        if not filename:
            return

        try:
            tree = ET.parse(filename)
            root = tree.getroot()

            # GPX名前空間を取得
            ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}
            if root.tag.startswith('{'):
                ns_uri = root.tag.split('}')[0] + '}'
                ns = {'gpx': ns_uri[1:-1]}

            # トラックポイントを抽出
            track_points = []

            # trk/trkseg/trkpt を探す
            for trkpt in root.findall('.//gpx:trkpt', ns):
                lat = float(trkpt.get('lat'))
                lon = float(trkpt.get('lon'))
                ele_elem = trkpt.find('gpx:ele', ns)
                ele = float(ele_elem.text) if ele_elem is not None else None
                track_points.append({'lat': lat, 'lon': lon, 'ele': ele})

            # 名前空間なしでも試す
            if not track_points:
                for trkpt in root.findall('.//trkpt'):
                    lat = float(trkpt.get('lat'))
                    lon = float(trkpt.get('lon'))
                    ele_elem = trkpt.find('ele')
                    ele = float(ele_elem.text) if ele_elem is not None else None
                    track_points.append({'lat': lat, 'lon': lon, 'ele': ele})

            if not track_points:
                QMessageBox.warning(self, "エラー", "GPXファイルにトラックポイントが見つかりません")
                return

            # インポートしたルートを表示
            self._display_imported_route(track_points, "GPX")

        except Exception as e:
            QMessageBox.warning(self, "エラー", f"GPX読み込みに失敗しました:\n{e}")

    def load_kmz(self):
        """KMZ/KMLファイルからルート情報を読み込み（ルート計算なし）"""
        filename = self._open_file_dialog("KMZ/KML読込", ['.kmz', '.kml'])

        if not filename:
            return

        try:
            # KMZかKMLかを判定
            if filename.lower().endswith('.kmz'):
                # KMZはZIPファイル、中のdoc.kmlを読み込む
                with zipfile.ZipFile(filename, 'r') as zf:
                    # doc.kmlまたは*.kmlファイルを探す
                    kml_files = [f for f in zf.namelist() if f.endswith('.kml')]
                    if not kml_files:
                        QMessageBox.warning(self, "エラー", "KMZファイル内にKMLが見つかりません")
                        return
                    # doc.kmlを優先、なければ最初のkmlファイル
                    kml_name = 'doc.kml' if 'doc.kml' in kml_files else kml_files[0]
                    with zf.open(kml_name) as kml_file:
                        kml_content = kml_file.read()
                        root = ET.fromstring(kml_content)
            else:
                # KMLファイルを直接読み込む
                tree = ET.parse(filename)
                root = tree.getroot()

            # KML名前空間を取得
            ns = {'kml': 'http://www.opengis.net/kml/2.2'}
            if root.tag.startswith('{'):
                ns_uri = root.tag.split('}')[0] + '}'
                ns = {'kml': ns_uri[1:-1]}

            # ルート座標を抽出（LineString）
            track_points = []
            # 経由地を抽出（Placemark/Point）
            waypoints = []

            # Placemarkを探す
            placemarks = root.findall('.//kml:Placemark', ns)
            if not placemarks:
                placemarks = root.findall('.//Placemark')

            for placemark in placemarks:
                # 名前を取得
                name_elem = placemark.find('kml:name', ns)
                if name_elem is None:
                    name_elem = placemark.find('name')
                name = name_elem.text if name_elem is not None else None

                # LineString（ルート）を探す
                linestring = placemark.find('.//kml:LineString', ns)
                if linestring is None:
                    linestring = placemark.find('.//LineString')

                if linestring is not None:
                    coords_elem = linestring.find('kml:coordinates', ns)
                    if coords_elem is None:
                        coords_elem = linestring.find('coordinates')
                    if coords_elem is not None and coords_elem.text:
                        coords_text = coords_elem.text.strip()
                        for coord in coords_text.split():
                            parts = coord.split(',')
                            if len(parts) >= 2:
                                lon = float(parts[0])
                                lat = float(parts[1])
                                ele = float(parts[2]) if len(parts) >= 3 else None
                                track_points.append({'lat': lat, 'lon': lon, 'ele': ele})

                # Point（経由地）を探す
                point = placemark.find('.//kml:Point', ns)
                if point is None:
                    point = placemark.find('.//Point')

                if point is not None:
                    coords_elem = point.find('kml:coordinates', ns)
                    if coords_elem is None:
                        coords_elem = point.find('coordinates')
                    if coords_elem is not None and coords_elem.text:
                        parts = coords_elem.text.strip().split(',')
                        if len(parts) >= 2:
                            lon = float(parts[0])
                            lat = float(parts[1])
                            ele = float(parts[2]) if len(parts) >= 3 else None
                            waypoints.append({'lat': lat, 'lon': lon, 'ele': ele, 'name': name})

            # ルートがない場合は経由地から作成
            if not track_points and waypoints:
                track_points = [{'lat': wp['lat'], 'lon': wp['lon'], 'ele': wp.get('ele')} for wp in waypoints]

            if not track_points:
                QMessageBox.warning(self, "エラー", "KML/KMZファイルに座標データが見つかりません")
                return

            # インポートしたルートを表示（経由地情報付き）
            self._display_imported_route(track_points, "KML", waypoints=waypoints)

        except Exception as e:
            QMessageBox.warning(self, "エラー", f"KMZ/KML読み込みに失敗しました:\n{e}")

    def _display_imported_route(self, track_points, source_type="GPX", waypoints=None):
        """インポートしたルートを表示（GPX/KML共通）

        Args:
            track_points: [{'lat': float, 'lon': float, 'ele': float or None}, ...]
            source_type: データソース名（"GPX" or "KML"）
            waypoints: [{'lat': float, 'lon': float, 'name': str}, ...] 経由地情報（オプション）
        """
        # 既存データをクリア
        self.clear_all_points()

        # ルート座標を設定（ルート計算をスキップ）
        self.route_coordinates = [(pt['lat'], pt['lon']) for pt in track_points]

        # 地図にルートを表示（Leafletは[lat, lon]形式）
        route_json = json.dumps(self.route_coordinates)
        self.map_view.page().runJavaScript(f"drawRoute({route_json});")

        # スタートとゴールを必ず追加し、中間の経由地があれば追加
        if len(track_points) >= 2:
            start = track_points[0]
            end = track_points[-1]

            # スタート
            self.waypoints = [(start['lat'], start['lon'], "スタート")]

            # 中間の経由地（KMLのPlacemarkなど）
            if waypoints and len(waypoints) > 0:
                for i, wp in enumerate(waypoints):
                    # スタート/ゴールと重複しない経由地のみ追加
                    wp_lat, wp_lon = wp['lat'], wp['lon']
                    # スタート・ゴールとの距離をチェック（100m以内なら重複とみなす）
                    dist_to_start = self.haversine(wp_lat, wp_lon, start['lat'], start['lon'])
                    dist_to_end = self.haversine(wp_lat, wp_lon, end['lat'], end['lon'])
                    if dist_to_start > 0.1 and dist_to_end > 0.1:  # 100m以上離れている
                        name = wp.get('name') or f"経由{i+1}"
                        self.waypoints.append((wp_lat, wp_lon, name))

            # ゴール
            self.waypoints.append((end['lat'], end['lon'], "ゴール"))

            # ポイントリストを更新
            self.point_list.clear()
            for lat, lng, name in self.waypoints:
                self.point_list.addItem(f"{name} ({lat:.5f}, {lng:.5f})")

        self.update_map_markers(auto_zoom=False)

        # 標高データを処理
        self._process_imported_elevation(track_points, source_type)

        # 地図を全ルートにフィット
        if self.auto_fit_checkbox.isChecked() and track_points:
            lats = [pt['lat'] for pt in track_points]
            lons = [pt['lon'] for pt in track_points]
            self.map_view.page().runJavaScript(
                f"doFitBounds({min(lats)}, {min(lons)}, {max(lats)}, {max(lons)});"
            )

    def _process_imported_elevation(self, track_points, source_type):
        """インポートしたルートの標高データを処理

        Args:
            track_points: [{'lat': float, 'lon': float, 'ele': float or None}, ...]
            source_type: データソース名
        """
        # GPX/KMLの標高データを使用するか、国土地理院から取得するか
        has_elevation = all(pt.get('ele') is not None for pt in track_points)

        if has_elevation and not self.gsi_checkbox.isChecked():
            # インポートデータの標高を使用
            elevations = [pt['ele'] for pt in track_points]
            self.update_status(f"{source_type}の標高データを使用: {len(elevations)}ポイント")
            self.analyze_elevation(elevations_from_api=elevations)
        else:
            # 国土地理院から標高を取得
            self.analyze_elevation()


def main():
    # QWebEngineのクラッシュを防ぐための設定
    import os
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"

    app = QApplication(sys.argv)

    # アプリケーション終了時のクリーンアップを確実に
    app.setQuitOnLastWindowClosed(True)

    window = RoutePlanner()

    # Cmd-Q等でのアプリ終了時にも確実にクリーンアップ
    def on_about_to_quit():
        window.cleanup()
        # イベント処理を複数回実行してChromiumスレッドの終了を待つ
        for _ in range(3):
            QApplication.processEvents()

    app.aboutToQuit.connect(on_about_to_quit)

    # 初期テーマを適用
    window.apply_theme("dark")
    window.show()

    # 終了コードを取得
    ret = app.exec()

    # macOSでのQtWebEngine終了時クラッシュ回避
    # Pythonのモジュールシャットダウン時にChromiumスレッドがクラッシュするため
    # os._exit()で直接終了する（PySide6 + QtWebEngine + macOSの既知問題）
    if sys.platform == 'darwin':
        os._exit(ret)
    else:
        sys.exit(ret)


if __name__ == '__main__':
    main()
