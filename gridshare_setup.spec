# gridshare_setup.spec
# PyInstaller spec file — produces a single Windows .exe
#
# Build command (run from this folder):
#   pyinstaller gridshare_setup.spec

block_cipher = None

a = Analysis(
    ['gridshare_setup.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'urllib.request',
        'urllib.error',
        'urllib.parse',
        'json',
        'hashlib',
        'socket',
        'threading',
        'tempfile',
        'subprocess',
        'pathlib',
        'platform',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude heavy packages we don't need
        'matplotlib', 'numpy', 'scipy', 'PIL', 'cv2',
        'tkinter', 'wx', 'PyQt5', 'PyQt6',
        'IPython', 'jupyter', 'notebook',
        'pandas', 'sqlalchemy',
    ],
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
    name='GridShare_Setup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                  # compress with UPX if available (smaller exe)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,              # keep console window — we need it for output
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,                 # add an .ico file path here if you have one
)
