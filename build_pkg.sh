#!/bin/sh
# build_pkg.sh — Build and install os-pushover as a native OPNsense package.
#
# Run this script ON your OPNsense firewall from wherever you placed the files:
#
#   sh /path/to/os-pushover/build_pkg.sh
#
# Requires root. Builds a .pkg using the OPNsense plugin toolchain, installs
# it with pkg add, then cleans up the build directory.

set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This script must be run as root." >&2
    exit 1
fi

if [ ! -f /usr/plugins/Mk/plugins.mk ]; then
    echo "ERROR: OPNsense plugin toolchain not found at /usr/plugins/Mk/plugins.mk" >&2
    echo "       Clone it first: git clone https://github.com/opnsense/plugins /usr/plugins" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Build directory must sit two levels under /usr/plugins/ so the Makefile's
# relative path "../../Mk/plugins.mk" resolves to /usr/plugins/Mk/plugins.mk
BUILD_DIR="/usr/plugins/sysutils/os-pushover-build"

echo "==> Setting up build directory..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cp -r "$SCRIPT_DIR/src" "$BUILD_DIR/src"
cp "$SCRIPT_DIR/Makefile" "$SCRIPT_DIR/pkg-descr" "$BUILD_DIR/"
[ -f "$SCRIPT_DIR/+POST_INSTALL.post" ] && cp "$SCRIPT_DIR/+POST_INSTALL.post" "$BUILD_DIR/"

echo "==> Fixing execute bits..."
chmod +x \
    "$BUILD_DIR/src/etc/rc.d/pushover" \
    "$BUILD_DIR/src/etc/rc.syshook.d/monitor/30-pushover" \
    "$BUILD_DIR/src/etc/rc.syshook.d/start/30-pushover" \
    "$BUILD_DIR/src/etc/rc.syshook.d/stop/30-pushover" \
    "$BUILD_DIR/src/etc/rc.syshook.d/config/30-pushover" \
    "$BUILD_DIR/src/opnsense/scripts/OPNsense/Pushover/sendNotification.py" \
    "$BUILD_DIR/src/opnsense/scripts/OPNsense/Pushover/pushover_monitor.py"

echo "==> Building package..."
cd "$BUILD_DIR" && make package

PKG=$(find "$BUILD_DIR/work/pkg" -name '*.pkg' | head -1)
if [ -z "$PKG" ]; then
    echo "ERROR: No .pkg file found after build." >&2
    exit 1
fi

echo "==> Installing $PKG ..."
pkg add "$PKG"

echo "==> Fixing installed execute bits..."
chmod +x \
    /usr/local/etc/rc.d/pushover \
    /usr/local/etc/rc.syshook.d/monitor/30-pushover \
    /usr/local/etc/rc.syshook.d/start/30-pushover \
    /usr/local/etc/rc.syshook.d/stop/30-pushover \
    /usr/local/etc/rc.syshook.d/config/30-pushover \
    /usr/local/opnsense/scripts/OPNsense/Pushover/sendNotification.py \
    /usr/local/opnsense/scripts/OPNsense/Pushover/pushover_monitor.py

echo "==> Cleaning up..."
rm -rf "$BUILD_DIR"

echo ""
echo "Done. Navigate to Services > Pushover in the OPNsense web UI to configure."
