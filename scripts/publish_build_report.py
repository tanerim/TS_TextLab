"""Save CI results as Git notes without creating repository branches."""

import json
import os
import subprocess
from pathlib import Path


def git(*arguments, content=None):
    return subprocess.check_output(["git", *arguments], input=content).decode().strip()


root = Path(__file__).resolve().parent.parent
os.chdir(root)
run_id = os.environ["GITHUB_RUN_ID"]
platform_name = os.environ["BUILD_PLATFORM"]
report = {
    "commit": os.environ["GITHUB_SHA"],
    "platform": platform_name,
    "status": os.environ["BUILD_STATUS"],
    "url": f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{run_id}",
    "artifact": f"TS-TextLab-{platform_name}",
    "steps": json.loads(os.environ["BUILD_STEPS"]),
}
for name in ("source-test", "packaged-test", "installer-test", "installed-test"):
    path = root / "build" / f"{name}.json"
    if path.exists():
        report[name] = json.loads(path.read_text(encoding="utf-8"))
git("config", "user.name", "github-actions[bot]")
git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
notes_ref = f"refs/notes/desktop-build/{platform_name}"
for attempt in range(5):
    existing = git("ls-remote", "origin", notes_ref)
    if existing:
        subprocess.run(["git", "fetch", "origin", f"+{notes_ref}:{notes_ref}"], check=True)
    git("notes", f"--ref={notes_ref}", "add", "-f", "-F", "-", report["commit"],
        content=json.dumps(report, indent=2).encode())
    pushed = subprocess.run(["git", "push", "origin", f"{notes_ref}:{notes_ref}"])
    if pushed.returncode == 0:
        break
else:
    raise RuntimeError("Could not save CI results after five attempts")
print(f"Saved {report['status']} build report as a Git note on {report['commit']}")
