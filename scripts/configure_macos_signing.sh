#!/bin/bash
set -euo pipefail

if [ -z "${MACOS_CERTIFICATE_BASE64:-}" ]; then
  echo 'No Developer ID certificate configured; creating an unsigned test DMG.'
  exit 0
fi
: "${MACOS_CERTIFICATE_PASSWORD:?Missing certificate password}"
: "${TEXTLAB_MACOS_SIGN_IDENTITY:?Missing Developer ID Application identity}"
: "${APPLE_ID:?Missing Apple ID}"
: "${APPLE_TEAM_ID:?Missing Apple team ID}"
: "${APPLE_APP_PASSWORD:?Missing app-specific Apple password}"

task_keychain="$RUNNER_TEMP/textlab-signing.keychain-db"
task_certificate="$RUNNER_TEMP/textlab-certificate.p12"
task_password=$(openssl rand -hex 32)
printf '%s' "$MACOS_CERTIFICATE_BASE64" | base64 -D > "$task_certificate"
security create-keychain -p "$task_password" "$task_keychain"
security set-keychain-settings -lut 21600 "$task_keychain"
security unlock-keychain -p "$task_password" "$task_keychain"
security import "$task_certificate" -k "$task_keychain" -P "$MACOS_CERTIFICATE_PASSWORD" -T /usr/bin/codesign
security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$task_password" "$task_keychain"
security list-keychains -d user -s "$task_keychain" "$HOME/Library/Keychains/login.keychain-db"
rm "$task_certificate"
xcrun notarytool store-credentials textlab-ci --keychain "$task_keychain" \
  --apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" --password "$APPLE_APP_PASSWORD"
printf 'TEXTLAB_NOTARY_PROFILE=textlab-ci\nTEXTLAB_NOTARY_KEYCHAIN=%s\n' "$task_keychain" >> "$GITHUB_ENV"
