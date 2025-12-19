# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Route Planner
Windows: python -m PyInstaller route_planner.spec
macOS: python -m PyInstaller route_planner.spec
"""

import sys
import os

block_cipher = None

# プラットフォーム判定
is_windows = sys.platform == 'win32'
is_macos = sys.platform == 'darwin'

# データファイル
datas = [
    ('frontend', 'frontend'),
    ('assets', 'assets'),
]

# 隠しインポート（PySide6関連）
hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebChannel',
    'PySide6.QtNetwork',
    'pyqtgraph',
    'numpy',
    'pandas',
    'PIL',
    'requests',
]

a = Analysis(
    ['route_planner.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'IPython',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if is_macos:
    # macOS: .app バンドル
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='RoutePlanner',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon='assets/icon.icns',
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name='RoutePlanner',
    )
    app = BUNDLE(
        coll,
        name='RoutePlanner.app',
        icon='assets/icon.icns',
        bundle_identifier='com.route-planner.app',
        info_plist={
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleVersion': '1.0.0',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '10.15',
        },
    )
else:
    # Windows: onefile モード（upx=Falseで DLLエラー回避）
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='RoutePlanner',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,  # UPX無効（DLLエラー回避）
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon='assets/icon.ico',
    )
