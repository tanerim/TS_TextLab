"""Sign private copies before PyInstaller creates either distribution format."""
from pathlib import Path
import shutil
import subprocess

PE_SUFFIXES = {'.exe', '.dll', '.pyd'}


def stage_and_sign(tocs, root: Path):
    stage = root / 'build' / 'windows-signing-stage'
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    staged_tocs = []
    sources = {}
    for toc in tocs:
        staged = []
        for destination, source, kind in toc:
            path = Path(source)
            if path.suffix.lower() in PE_SUFFIXES:
                # Copy once per source; never modify the Python environment or wheel files.
                key = str(path.resolve())
                if key not in sources:
                    target = stage / str(len(sources)) / path.name
                    target.parent.mkdir(parents=True)
                    shutil.copy2(path, target)
                    sources[key] = target
                source = str(sources[key])
            staged.append((destination, source, kind))
        staged_tocs.append(staged)
    subprocess.run(['pwsh', '-NoProfile', '-File', str(root / 'scripts' / 'sign_windows.ps1'),
                    '-Path', str(stage), '-Report', str(root / 'build' / 'windows-dependencies-signing.json')],
                   check=True, timeout=1800)
    return staged_tocs
