# PyInstaller spec — one-file executable for Windows, Linux and macOS.
#   pip install pyinstaller
#   pyinstaller pico.spec
# Produces dist/pico(.exe). The web UI and packs are bundled as data.
import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

a = Analysis(
    ['pico.py'],
    pathex=[],
    binaries=[],
    datas=[('web/index.html', 'web'), ('packs', 'packs'), ('templates', 'templates')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='pico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)
