"""Create and exercise the files that desktop users download and double-click."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(*args: str | Path, **kwargs) -> None:
    subprocess.run([str(arg) for arg in args], check=True, timeout=900, **kwargs)


def check_app(executable: Path, report: Path) -> dict:
    report.unlink(missing_ok=True)
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    # Launch outside the installation folder, just as a desktop shortcut does.
    run(executable, "--self-test", report, cwd=tempfile.gettempdir(), env=env)
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["passed"] and result["utf8_mode"] == 1, result
    return result


def windows_signature_check(path: Path, report: str) -> None:
    mode = "Verify" if os.environ.get("TEXTLAB_WINDOWS_SIGNING_ENABLED") == "true" else "Inventory"
    run("pwsh", "-NoProfile", "-File", ROOT / "scripts" / "sign_windows.ps1",
        "-Path", path, "-Mode", mode, "-Report", ROOT / "build" / report)


def windows(version: str, require_signing: bool = False) -> dict:
    signed = os.environ.get("TEXTLAB_WINDOWS_SIGNING_ENABLED") == "true"
    if require_signing and not signed:
        raise RuntimeError("Windows distribution requires configured code signing")
    portable = ROOT / "dist" / f"TS-TextLab-{version}-windows-x86_64.exe"
    windows_signature_check(portable, "windows-portable-signing.json")
    portable_result = check_app(portable, ROOT / "build" / "portable-test.json")
    compiler = shutil.which("ISCC")
    if not compiler:
        for variable in ("ProgramFiles(x86)", "ProgramFiles"):
            path = Path(os.environ.get(variable, "C:/Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe"
            if path.exists():
                compiler = str(path)
                break
    if not compiler:
        raise RuntimeError("Install Inno Setup 6 before creating the Windows installer")
    signing_args = []
    if signed:
        signing_script = ROOT / "scripts" / "sign_windows.ps1"
        signing_args = ["/DWindowsSigning=1",
                        f'/Stextlab=pwsh -NoProfile -File $q{signing_script}$q -Path $f']
    run(compiler, *signing_args, f"/DAppVersion={version}", f"/DOutputDir={ROOT / 'dist'}",
        f"/DProjectDir={ROOT}", f"/DBundleDir={ROOT / 'dist' / 'TS TextLab'}",
        ROOT / "packaging" / "windows-installer.iss")
    installer = ROOT / "dist" / f"TS-TextLab-{version}-windows-x86_64-Setup.exe"
    windows_signature_check(installer, "windows-installer-signing.json")
    with tempfile.TemporaryDirectory(prefix="textlab-install-") as folder:
        install_dir = Path(folder) / "TS TextLab"
        # DisableProgramGroupPage=yes deliberately fixes this to DefaultGroupName.
        group = "TS TextLab"
        run(installer, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-",
            f"/DIR={install_dir}", "/TASKS=",
            f"/LOG={ROOT / 'build' / 'windows-install.log'}")
        try:
            windows_signature_check(install_dir, "windows-installed-signing.json")
            shortcut = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs" / group / "TS TextLab.lnk"
            assert shortcut.is_file(), "Start menu shortcut is missing"
            result = check_app(install_dir / "TS TextLab.exe", ROOT / "build" / "installed-test.json")
        finally:
            run(install_dir / "unins000.exe", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART")
        assert not (install_dir / "TS TextLab.exe").exists(), "Uninstaller left the application installed"
    return {"file": installer.name, "portable_file": portable.name, "checks": [f"single-file portable application: {len(portable_result['checks'])} checks", "silent installation", "Start menu shortcut", f"installed application: {len(result['checks'])} checks", "uninstall"], "app_test": result, "portable_test": portable_result, "signed": signed}


def macos(version: str, require_signing: bool) -> dict:
    identity = os.environ.get("TEXTLAB_MACOS_SIGN_IDENTITY")
    profile = os.environ.get("TEXTLAB_NOTARY_PROFILE")
    signed = bool(identity and profile)
    if require_signing and not signed:
        raise RuntimeError("Public macOS distribution requires Developer ID signing and a notarytool profile")
    bundle = ROOT / "dist" / "TS TextLab.app"
    notary_args = ["--keychain-profile", profile] if profile else []
    if os.environ.get("TEXTLAB_NOTARY_KEYCHAIN"):
        notary_args += ["--keychain", os.environ["TEXTLAB_NOTARY_KEYCHAIN"]]
    if signed:
        run("codesign", "--verify", "--deep", "--strict", bundle)
        upload = ROOT / "build" / "notarization.zip"
        run("ditto", "-c", "-k", "--keepParent", bundle, upload)
        run("xcrun", "notarytool", "submit", upload, *notary_args, "--wait")
        run("xcrun", "stapler", "staple", bundle)
        run("spctl", "--assess", "--type", "execute", "--verbose", bundle)
    machine = platform.machine().lower()
    suffix = "" if signed else "-unsigned"
    image = ROOT / "dist" / f"TS-TextLab-{version}-macos-{machine}{suffix}.dmg"
    with tempfile.TemporaryDirectory(prefix="textlab-dmg-") as folder:
        stage = Path(folder) / "stage"
        stage.mkdir()
        run("ditto", bundle, stage / bundle.name)
        (stage / "Applications").symlink_to("/Applications", target_is_directory=True)
        run("hdiutil", "create", "-volname", "TS TextLab", "-srcfolder", stage,
            "-format", "UDZO", "-ov", image)
        if signed:
            run("codesign", "--sign", identity, "--timestamp", image)
            run("xcrun", "notarytool", "submit", image, *notary_args, "--wait")
            run("xcrun", "stapler", "staple", image)
            run("xcrun", "stapler", "validate", image)
        mount = Path(folder) / "mounted"
        run("hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", mount, image)
        try:
            assert (mount / "Applications").resolve() == Path("/Applications")
            result = check_app(mount / bundle.name / "Contents/MacOS/TS TextLab", ROOT / "build" / "installed-test.json")
        finally:
            run("hdiutil", "detach", mount)
    return {"file": image.name, "checks": ["disk image mount", "Applications link", f"application launched from read-only image: {len(result['checks'])} checks"], "app_test": result, "signed_and_notarized": signed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-signing", action="store_true")
    args = parser.parse_args()
    version = (ROOT / "version.txt").read_text(encoding="utf-8").strip()
    report = {"version": version, "platform": platform.platform(), "passed": False}
    try:
        if sys.platform == "win32":
            report.update(windows(version, args.require_signing or os.environ.get("REQUIRE_WINDOWS_SIGNING") == "true"))
        elif sys.platform == "darwin":
            report.update(macos(version, args.require_signing or os.environ.get("REQUIRE_MACOS_SIGNING") == "true"))
        else:
            raise RuntimeError("This installer must be built on Windows or macOS")
        report["passed"] = True
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        path = ROOT / "build" / "installer-test.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
