# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

import sys
import os
import sysconfig

import shutil

binaries = []
if sys.platform == 'darwin':
    try:
        # Explicitly find and include libpython on macOS to fix "Failed to load Python shared library"
        lib_name = sysconfig.get_config_var('LDLIBRARY')
        lib_dir = sysconfig.get_config_var('LIBDIR')
        if lib_name and lib_dir:
            lib_path = os.path.join(lib_dir, lib_name)
            if os.path.exists(lib_path):
                print(f"Adding {lib_path} to binaries")
                # PyInstaller on macOS expects libpython in _internal
                binaries.append((lib_path, '_internal'))
            else:
                print(f"Warning: Could not find libpython at {lib_path}")
                # Fallback: try to find it in sys.base_prefix/lib
                fallback_path = os.path.join(sys.base_prefix, 'lib', lib_name)
                if os.path.exists(fallback_path):
                    print(f"Found fallback libpython at {fallback_path}")
                    binaries.append((fallback_path, '_internal'))

    except Exception as e:
        print(f"Warning: Error trying to add libpython: {e}")

# Add ffmpeg and ffprobe to binaries
ffmpeg_path = shutil.which('ffmpeg')
ffprobe_path = shutil.which('ffprobe')

if ffmpeg_path:
    print(f"Adding ffmpeg from {ffmpeg_path}")
    binaries.append((ffmpeg_path, '.'))
else:
    print("Warning: ffmpeg not found")

if ffprobe_path:
    print(f"Adding ffprobe from {ffprobe_path}")
    binaries.append((ffprobe_path, '.'))
else:
    print("Warning: ffprobe not found")


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=[
        ('index.html', '.'),
        ('main.css', '.'),
        ('newTranscription.html', '.'),
        ('newTranscription.js', '.'),
        ('settings.js', '.'),
        ('transcriptionManager.js', '.'),
        ('vendor', 'vendor'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Simple Schedules Transcribe',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Simple Schedules Transcribe',
)
app = BUNDLE(
    coll,
    name='Simple Schedules Transcribe.app',
    icon=None,
    bundle_identifier='com.simpleschedules.transcribe',
)
