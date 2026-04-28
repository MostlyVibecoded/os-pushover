#!/bin/sh
# install.sh — Direct install of os-pushover onto OPNsense (no pkg required).
# Run as root on the firewall from wherever you placed the files:
#
#   sh /path/to/os-pushover/install.sh
#
# For a native pkg install instead, use build_pkg.sh.

set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This script must be run as root." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$SCRIPT_DIR/src"
PREFIX="/usr/local"

install_file() {
    src="$1"
    dst="$2"
    mode="$3"
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
    chmod "$mode" "$dst"
}

# MVC — controllers
install_file "$SRC/opnsense/mvc/app/controllers/OPNsense/Pushover/IndexController.php"                "$PREFIX/opnsense/mvc/app/controllers/OPNsense/Pushover/IndexController.php"                0644
install_file "$SRC/opnsense/mvc/app/controllers/OPNsense/Pushover/Api/ServiceController.php"          "$PREFIX/opnsense/mvc/app/controllers/OPNsense/Pushover/Api/ServiceController.php"          0644
install_file "$SRC/opnsense/mvc/app/controllers/OPNsense/Pushover/Api/SettingsController.php"         "$PREFIX/opnsense/mvc/app/controllers/OPNsense/Pushover/Api/SettingsController.php"         0644
install_file "$SRC/opnsense/mvc/app/controllers/OPNsense/Pushover/forms/general.xml"                  "$PREFIX/opnsense/mvc/app/controllers/OPNsense/Pushover/forms/general.xml"                  0644
install_file "$SRC/opnsense/mvc/app/controllers/OPNsense/Pushover/forms/monitors.xml"                 "$PREFIX/opnsense/mvc/app/controllers/OPNsense/Pushover/forms/monitors.xml"                 0644

# MVC — models
install_file "$SRC/opnsense/mvc/app/models/OPNsense/Pushover/Pushover.php"                            "$PREFIX/opnsense/mvc/app/models/OPNsense/Pushover/Pushover.php"                            0644
install_file "$SRC/opnsense/mvc/app/models/OPNsense/Pushover/Pushover.xml"                            "$PREFIX/opnsense/mvc/app/models/OPNsense/Pushover/Pushover.xml"                            0644
install_file "$SRC/opnsense/mvc/app/models/OPNsense/Pushover/ACL/ACL.xml"                             "$PREFIX/opnsense/mvc/app/models/OPNsense/Pushover/ACL/ACL.xml"                             0644
install_file "$SRC/opnsense/mvc/app/models/OPNsense/Pushover/Menu/Menu.xml"                           "$PREFIX/opnsense/mvc/app/models/OPNsense/Pushover/Menu/Menu.xml"                           0644

# MVC — views
install_file "$SRC/opnsense/mvc/app/views/OPNsense/Pushover/index.volt"                               "$PREFIX/opnsense/mvc/app/views/OPNsense/Pushover/index.volt"                               0644

# Scripts
install_file "$SRC/opnsense/scripts/OPNsense/Pushover/sendNotification.py"                            "$PREFIX/opnsense/scripts/OPNsense/Pushover/sendNotification.py"                            0755
install_file "$SRC/opnsense/scripts/OPNsense/Pushover/pushover_monitor.py"                            "$PREFIX/opnsense/scripts/OPNsense/Pushover/pushover_monitor.py"                            0755

# configd
install_file "$SRC/opnsense/service/conf/actions.d/actions_pushover.conf"                             "$PREFIX/opnsense/service/conf/actions.d/actions_pushover.conf"                             0644
install_file "$SRC/opnsense/service/templates/OPNsense/Pushover/+TARGETS"                             "$PREFIX/opnsense/service/templates/OPNsense/Pushover/+TARGETS"                             0644
install_file "$SRC/opnsense/service/templates/OPNsense/Pushover/pushover.conf"                        "$PREFIX/opnsense/service/templates/OPNsense/Pushover/pushover.conf"                        0644

# rc scripts and syshooks
install_file "$SRC/etc/rc.d/pushover"                                                                  "$PREFIX/etc/rc.d/pushover"                                                                  0755
install_file "$SRC/etc/rc.syshook.d/config/30-pushover"                                               "$PREFIX/etc/rc.syshook.d/config/30-pushover"                                               0755
install_file "$SRC/etc/rc.syshook.d/monitor/30-pushover"                                              "$PREFIX/etc/rc.syshook.d/monitor/30-pushover"                                              0755
install_file "$SRC/etc/rc.syshook.d/start/30-pushover"                                                "$PREFIX/etc/rc.syshook.d/start/30-pushover"                                                0755
install_file "$SRC/etc/rc.syshook.d/stop/30-pushover"                                                 "$PREFIX/etc/rc.syshook.d/stop/30-pushover"                                                 0755

# Plugin registration (Services page)
install_file "$SRC/etc/inc/plugins.inc.d/pushover.inc"                                                "$PREFIX/etc/inc/plugins.inc.d/pushover.inc"                                                0644

echo "==> Reloading configd and template..."
service configd restart
configctl template reload OPNsense/Pushover

echo "==> Clearing menu cache..."
TMPDIR=$(php -r "require_once '/usr/local/opnsense/mvc/script/load_phalcon.php'; echo (new OPNsense\Core\AppConfig())->application->tempDir;" 2>/dev/null)
rm -f "${TMPDIR}/opnsense_menu_cache.xml" "${TMPDIR}/opnsense_acl_cache.json"

echo ""
echo "Done. Navigate to Services > Pushover in the OPNsense web UI to configure."
