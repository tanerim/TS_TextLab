"""Run the frozen app's smoke checks and create a platform-named archive."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    version = (root / "version.txt").read_text(encoding="utf-8").strip()
    system = platform.system().lower()
    machine = platform.machine().lower().replace("amd64", "x86_64").replace("aarch64", "arm64")
    bundle = root / "dist" / ("TS TextLab.app" if sys.platform == "darwin" else "TS TextLab")
    executable = bundle / ("TS TextLab.exe" if sys.platform == "win32" else "TS TextLab")
    if sys.platform == "darwin":
        executable = bundle / "Contents" / "MacOS" / "TS TextLab"
    report = root / "build" / "packaged-test.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    # An old report must not mask a failed launch of a new build.
    report.unlink(missing_ok=True)
    environment = dict(os.environ)
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    subprocess.run([str(executable), "--self-test", str(report)], cwd=bundle.parent,
                   env=environment, check=True, timeout=300)
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["passed"] and result["version"] == version, result
    if sys.platform.startswith("linux"):
        shutil.copy2(root / "packaging" / "com.tscorpus.textlab.desktop", bundle)
        shutil.copy2(root / "app" / "theme" / "app-icon.png", bundle / "com.tscorpus.textlab.png")
        installer = bundle / "install-linux.sh"
        shutil.copy2(root / "packaging" / "install-linux.sh", installer)
        installer.chmod(0o755)
    name = f"TS-TextLab-{version}-{system}-{machine}"
    archive_format = "gztar" if sys.platform.startswith("linux") else "zip"
    archive = shutil.make_archive(str(root / "dist" / name), archive_format,
                                  root_dir=bundle.parent, base_dir=bundle.name)
    print(f"Packaged tests passed: {len(result['checks'])} checks")
    print(f"Distribution: {archive}")


if __name__ == "__main__":
    main()
