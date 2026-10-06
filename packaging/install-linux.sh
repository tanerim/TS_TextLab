#!/bin/sh
set -eu
# Keep the extracted application folder in its final location before running this script.
task_bundle=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
task_data=${XDG_DATA_HOME:-"$HOME/.local/share"}
mkdir -p "$task_data/applications"
cat > "$task_data/applications/com.tscorpus.textlab.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TS TextLab
Comment=Turkish text analysis with TS Corpus
Exec="$task_bundle/TS TextLab"
Icon=$task_bundle/com.tscorpus.textlab.png
Terminal=false
Categories=Education;Science;
StartupWMClass=TS TextLab
EOF
printf 'TS TextLab launcher installed for %s\n' "$task_bundle"
