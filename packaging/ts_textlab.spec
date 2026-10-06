# -*- mode: python ; coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path
import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules


spec_path = Path(SPECPATH).resolve()
project_root = spec_path if (spec_path / "main.py").exists() else spec_path.parent

datas = []
binaries = []
hiddenimports = []

datas += [(str(path), "app/theme") for path in (project_root / "app" / "theme").glob("*") if path.is_file()]
datas.append((str(project_root / "version.txt"), "."))
version = (project_root / "version.txt").read_text(encoding="utf-8").strip()

for package_name in ("spacy", "spacy_legacy", "spacy_loggers", "thinc", "ts_tokenizer", "ts_postagger"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package_name)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += [
        item
        for item in package_hiddenimports
        if ".tests" not in item and not item.startswith("ts_tokenizer.unit_test")
    ]

hiddenimports += collect_submodules("spacy.lang.tr")


a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["spacy.tests", "thinc.tests", "ts_tokenizer.unit_test"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [('X utf8=1', None, 'OPTION')],
    exclude_binaries=True,
    name="TS TextLab",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    icon=str(project_root / "app" / "theme" / "app-icon.ico") if sys.platform == "win32" else None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=os.environ.get("TEXTLAB_MACOS_SIGN_IDENTITY"),
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="TS TextLab",
)

# A Windows user can also launch this single file directly without installation.
if sys.platform == "win32":
    portable = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [('X utf8=1', None, 'OPTION')],
        name=f"TS-TextLab-{version}-windows-x86_64",
        console=False,
        icon=str(project_root / "app" / "theme" / "app-icon.ico"),
        upx=False,
    )

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="TS TextLab.app",
        icon=str(project_root / "app" / "theme" / "app-icon.icns"),
        bundle_identifier="com.tscorpus.textlab",
        info_plist={
            "CFBundleShortVersionString": version,
            "CFBundleVersion": version,
            "NSHighResolutionCapable": True,
        },
    )
