"""アプリケーションのエントリポイントと QApplication ライフサイクル。"""

import os
import sys

from PySide6.QtWidgets import QApplication

from .ui.main_window import RoutePlanner
from .ui.styles import configure_pyqtgraph_theme


def main():
    # QWebEngine のクラッシュを防ぐための設定
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"

    # pyqtgraph のテーマ（背景・前景色）をウィジェット生成前に設定
    configure_pyqtgraph_theme()

    app = QApplication(sys.argv)

    # アプリケーション終了時のクリーンアップを確実に
    app.setQuitOnLastWindowClosed(True)

    window = RoutePlanner()

    # Cmd-Q 等でのアプリ終了時にも確実にクリーンアップ
    def on_about_to_quit():
        window.cleanup()
        # イベント処理を複数回実行して Chromium スレッドの終了を待つ
        for _ in range(3):
            QApplication.processEvents()

    app.aboutToQuit.connect(on_about_to_quit)

    # 初期テーマを適用
    window.apply_theme("dark")
    window.show()

    # 終了コードを取得
    ret = app.exec()

    # macOS での QtWebEngine 終了時クラッシュ回避
    # Python のモジュールシャットダウン時に Chromium スレッドがクラッシュするため
    # os._exit() で直接終了する（PySide6 + QtWebEngine + macOS の既知問題）
    if sys.platform == "darwin":
        os._exit(ret)
    else:
        sys.exit(ret)


if __name__ == "__main__":
    main()
