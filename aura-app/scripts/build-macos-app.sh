#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
APP="release/AURA Companion.app"
SIGN_IDENTITY="${AURA_MACOS_SIGN_IDENTITY:--}"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
swiftc -parse-as-library -O -target arm64-apple-macosx13.0 \
  -framework SwiftUI -framework AppKit -framework AVFoundation \
  -framework Speech -framework Vision -framework Security \
  -o "$APP/Contents/MacOS/AURACompanion" \
  macos/AURACompanion/Sources/main.swift \
  macos/AURACompanion/Sources/AmbientLifecycle.swift
cp macos/AURACompanion/Info.plist "$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Add :NSLocalNetworkUsageDescription string "AURA connects to its companion service on this Mac."' "$APP/Contents/Info.plist"
codesign --force --options runtime --entitlements macos/AURACompanion/Entitlements.plist --sign "$SIGN_IDENTITY" "$APP"
codesign --verify --strict --verbose=2 "$APP"
SIGNED_ENTITLEMENTS="$(mktemp)"
trap 'rm -f "$SIGNED_ENTITLEMENTS"' EXIT
codesign -d --entitlements :- "$APP" > "$SIGNED_ENTITLEMENTS" 2>/dev/null
for entitlement in com.apple.security.device.audio-input com.apple.security.device.camera; do
  if [[ "$(/usr/libexec/PlistBuddy -c "Print :$entitlement" "$SIGNED_ENTITLEMENTS")" != "true" ]]; then
    echo "Missing required macOS device entitlement: $entitlement" >&2
    exit 1
  fi
done
if ! codesign -dv --verbose=4 "$APP" 2>&1 | grep 'flags=.*runtime' > /dev/null; then
  echo "The AURA app must use the Hardened Runtime." >&2
  exit 1
fi
echo "Built $APP (identity: $SIGN_IDENTITY; not notarized)."
