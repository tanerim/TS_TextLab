# -*- mode: python ; coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules


spec_path = Path(SPECPATH).resolve()
project_root = spec_path if (spec_path / "main.py").exists() else spec_path.parent

datas = []
binaries = []
hiddenimports = []

for package_name in ("spacy", "thinc", "ts_tokenizer"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package_name)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += [
        item
        for item in package_hiddenimports
        if not item.startswith(("spacy.tests", "thinc.tests", "ts_tokenizer.unit_test"))
    ]

hiddenimports += collect_submodules("spacy.lang.tr")

model_candidates = [
    project_root / "models" / "ts_postagger_model",
    project_root / "ts_pos_tagger" / "model-best",
]
for model_path in model_candidates:
    if model_path.exists():
        datas.append((str(model_path), str(model_path.relative_to(project_root))))
        break


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
    [],
    exclude_binaries=True,
    name="TS TextLab",
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
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TS TextLab",
)
