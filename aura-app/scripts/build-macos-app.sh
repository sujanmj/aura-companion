#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
APP="release/AURA Companion.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
swiftc -parse-as-library -O -target arm64-apple-macosx13.0 \
  -framework SwiftUI -framework AppKit -framework AVFoundation \
  -framework Speech -framework Vision -framework Security \
  -o "$APP/Contents/MacOS/AURACompanion" \
  macos/AURACompanion/Sources/main.swift
cp macos/AURACompanion/Info.plist "$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Add :NSLocalNetworkUsageDescription string "AURA connects to its companion service on this Mac."' "$APP/Contents/Info.plist"
codesign --force --deep --sign - "$APP"
echo "Built $APP (locally signed; not notarized)."
