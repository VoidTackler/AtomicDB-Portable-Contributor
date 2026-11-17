# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Build Specification for Background Processing Utility (--onefile standalone)
Optimized for fast build time and minimal standalone executable size.
"""

import os

block_cipher = None
base_dir = os.path.abspath(SPECPATH)
worker_dir = os.path.join(base_dir, 'worker')
os.makedirs(worker_dir, exist_ok=True)

_UNUSED_MODULES = [
    'tkinter', '_tkinter', 'matplotlib', 'scipy', 'numpy', 'pandas', 'PIL',
    'unittest', 'pytest', 'pydoc', 'doctest', 'sqlite3', '_sqlite3', 'lib2to3',
    'ensurepip', 'idlelib', 'turtle', 'turtledemo', 'curses', 'xmlrpc', 'cryptography',
    'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebChannel',
    'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets', 'PySide6.QtQuickControls2',
    'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.Qt3DInput', 'PySide6.Qt3DLogic',
    'PySide6.Qt3DExtras', 'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
    'PySide6.QtPdf', 'PySide6.QtPdfWidgets', 'PySide6.QtSql', 'PySide6.QtSvg',
    'PySide6.QtSvgWidgets', 'PySide6.QtNetwork', 'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets',
    'PySide6.QtPrintSupport', 'PySide6.QtTest', 'PySide6.QtXml', 'PySide6.QtDesigner',
    'PySide6.QtHelp', 'PySide6.QtCharts', 'PySide6.QtDataVisualization',
    'PySide6.QtPositioning', 'PySide6.QtSensors', 'PySide6.QtSerialPort',
    'PySide6.QtBluetooth', 'PySide6.QtNfc', 'PySide6.QtRemoteObjects', 'PySide6.QtScxml',
    'PySide6.QtStateMachine', 'PySide6.QtWebSockets', 'PySide6.QtWebView',
    'PySide6.QtDBus', 'PySide6.QtHttpServer', 'PySide6.QtSpatialAudio', 'PySide6.QtTextToSpeech',
]

a = Analysis(
    ['AtomicDBPortable.py'],
    pathex=[base_dir, os.path.join(base_dir, 'src')],
    binaries=[],
    datas=[(worker_dir, 'worker')],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtWidgets',
        'PySide6.QtGui',
        'psutil',
        'requests',
        'urllib3',
        'runpy',
        'chess',
        'chess.syzygy',
        'chess.variant',
        'gzip',
        'ast',
        'secrets',
        'platform',
        'urllib.parse',
        'logging.handlers',
        'chess_notation',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_UNUSED_MODULES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=1,
)

# Strip heavy unused Qt DLLs, QML, translations, and unused plugins for smaller & faster EXE builds
_SKIP_BINARY_PATTERNS = (
    'qt6qml', 'qt6quick', 'qt6network', 'qt6opengl', 'qt6pdf', 'qt6svg',
    'qt6multimedia', 'qt6webengine', 'qt63d', 'qt6designer', 'qt6sql',
    'qt6charts', 'qt6virtualkeyboard', 'qt6datavisualization', 'qt6positioning',
    'qt6sensors', 'qt6serialport', 'qt6bluetooth', 'qt6websockets', 'qt6test',
    'opengl32sw.dll', 'd3dcompiler_47.dll', 'libegl', 'libglesv2',
    'qsvg', 'qtiff', 'qwebp', 'qgif', 'qicns', 'qtga', 'qwbmp', 'qpdf',
)
_SKIP_DATA_PREFIXES = (
    'pyside6/translations', 'pyside6\\translations',
    'pyside6/qml', 'pyside6\\qml',
    'pyside6/resources', 'pyside6\\resources',
    'pyside6/examples', 'pyside6\\examples',
)

a.binaries = [
    item for item in a.binaries
    if not any(pat in item[0].lower() for pat in _SKIP_BINARY_PATTERNS)
]
a.datas = [
    item for item in a.datas
    if not item[0].lower().startswith(_SKIP_DATA_PREFIXES)
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Background Processing Utility',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # Skip slow UPX pass; zlib bundle compression + Qt pruning keep size down & build fast
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='NONE',             # Use Windows default application icon: IDI_APPLICATION (MAKEINTRESOURCE(32512))
    uac_admin=False,
    uac_uiaccess=False,
)
