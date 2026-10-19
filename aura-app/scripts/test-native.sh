#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
AURA_TEST_DIR=$(mktemp -d)
trap 'rm -rf "$AURA_TEST_DIR"' EXIT
swiftc -parse-as-library \
  macos/AURACompanion/Sources/AmbientLifecycle.swift \
  macos/tests/LifecycleTests.swift \
  -o "$AURA_TEST_DIR/lifecycle-tests"
"$AURA_TEST_DIR/lifecycle-tests"
