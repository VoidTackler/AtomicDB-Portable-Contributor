# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Build Specification for AtomicDB Portable (--onefile standalone)
Builds a single standalone Windows x64 .exe with zero dependencies and zero admin requirements.
"""

import os
import sys

block_cipher = None
base_dir = os.path.abspath(SPECPATH)

added_datas = [
    (os.path.join(base_dir, 'worker'), 'worker'),
]

# Ensure worker directory exists before analysis
if not os.path.exists(os.path.join(base_dir, 'worker')):
    os.makedirs(os.path.join(base_dir, 'worker'), exist_ok=True)

a = Analysis(
    ['AtomicDBPortable.py'],
    pathex=[base_dir, os.path.join(base_dir, 'src')],
    binaries=[],
    datas=added_datas,
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtWidgets',
        'PySide6.QtGui',
        'psutil',
        'requests',
        'cryptography',
        'urllib3',
        'runpy',
        'chess',
        'logging.handlers',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'unittest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Single Standalone .EXE (--onefile)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AtomicDBPortable',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # Windowed GUI without black console popup
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=False,         # Zero Administrator Privileges (runs asInvoker)
    uac_uiaccess=False,
)
