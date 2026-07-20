"""PyInstaller / 直接実行用のランチャ。

パッケージのエントリポイント ``route_planner.app.main`` を呼び出す。
（``python -m route_planner`` と等価。PyInstaller はスクリプトを起点にするため用意）
"""

from route_planner.app import main

if __name__ == "__main__":
    main()
