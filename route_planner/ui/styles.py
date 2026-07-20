"""テーマ・スタイル定義。

- ``DARK_STYLESHEET`` / ``LIGHT_STYLESHEET``: QApplication 全体のスタイルシート
- ``configure_pyqtgraph_theme()``: pyqtgraph のグローバル既定色（背景・前景）

これらは Qt ウィジェットへ適用する「文字列・設定」であり、ロジックを持たない。
"""

import pyqtgraph as pg


def configure_pyqtgraph_theme():
    """pyqtgraph のグローバル既定（アンチエイリアス・背景・前景）を設定する。

    ウィジェット生成前に一度呼ぶこと。
    """
    pg.setConfigOptions(antialias=True)
    pg.setConfigOption("background", "#1e1e2e")
    pg.setConfigOption("foreground", "#cdd6f4")


DARK_STYLESHEET = """
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


LIGHT_STYLESHEET = """
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
