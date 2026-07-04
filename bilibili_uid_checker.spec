# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['bilibili_uid_checker.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('start_chrome_windows.bat', '.'),
        ('assets/app.ico', 'assets'),
    ],
    hiddenimports=[
        'gui',
        'DrissionPage',
        'DrissionPage.common',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'pytest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='BilibiliUIDChecker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/app.ico',
)
