#!/bin/bash
# Builds Greybox.app from the Swift package.
# Must be run on macOS with Xcode command line tools installed.

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="Greybox.app"
BUILD_DIR="$DIR/.build/release"
APP_DIR="$DIR/dist/$APP_NAME"

echo "== Building Greybox menu bar app =="

cd "$DIR"
swift build -c release

echo "[*] Assembling app bundle..."
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

cp "$BUILD_DIR/GreyboxMenuBar" "$APP_DIR/Contents/MacOS/GreyboxMenuBar"
cp "$DIR/Resources/Info.plist" "$APP_DIR/Contents/Info.plist"
if [ -f "$DIR/Resources/AppIcon.icns" ]; then
    cp "$DIR/Resources/AppIcon.icns" "$APP_DIR/Contents/Resources/AppIcon.icns"
fi

echo ""
echo "[+] Built: $APP_DIR"
echo ""
echo "Next steps:"
echo "  open \"$APP_DIR\"                          # run it once to test"
echo "  cp -R \"$APP_DIR\" /Applications/           # install"
echo ""
echo "First launch will prompt for Automation permission (System Settings ->"
echo "Privacy & Security -> Automation) so it can read the active browser tab."
