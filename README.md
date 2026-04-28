# os-pushover

Pushover push notification plugin for OPNsense. Adds a **Services → Pushover** page to the web UI with a persistent background daemon and event hooks for system notifications.

## Requirements

- OPNsense 26.1 (FreeBSD 14, PHP 8.3, Python 3)
- A [Pushover](https://pushover.net) account with an application API token and user/group key

## Installation

Both methods require SSH access to your firewall as root. Get the files onto OPNsense by whatever means (git clone, scp, USB, etc.), then run as root:

### Method 1 — Native package (recommended)

Requires the OPNsense plugin toolchain. If `/usr/plugins/Mk/plugins.mk` does not exist on your firewall, clone it first:

```sh
git clone https://github.com/opnsense/plugins /usr/plugins
```

Then run:

```sh
sh /path/to/os-pushover/build_pkg.sh
```

Builds and installs a FreeBSD `.pkg`. Tracked by `pkg info` and survives upgrades cleanly.

### Method 2 — Direct install

```sh
sh /path/to/os-pushover/install.sh
```

Copies files directly. Simpler but not tracked by `pkg`.

After either method, **Services → Pushover** will appear in the web UI.

## Configuration

1. Navigate to **Services → Pushover** → **Pushover Configuration** tab
2. Check **Enable**
3. Enter your **API Token** and **User / Group Key**
4. Optionally set a target **Device**, **Priority**, and **Sound**
5. Switch to the **Monitors** tab and enable the events you want
6. Click **Save** then **Test notification** to verify delivery

All notifications are prefixed with the system hostname.

## Monitors

### Network & Connectivity

| Monitor | Description |
| --- | --- |
| **Gateway down / up** | Fires when a gateway goes down and when it recovers |
| **Gateway threshold violations** *(experimental)* | Fires when a gateway exceeds its dpinger loss or delay thresholds |
| **WireGuard peer down / up** | Fires when a peer handshake goes stale. Configurable threshold (default: 300 s) |
| **OpenVPN client down / up** | Fires when a client stays disconnected past the threshold. Configurable threshold (default: 60 s) |

### Services

| Monitor | Description |
| --- | --- |
| **Unbound DNS up / down** | Fires when Unbound stops or recovers. Brief restarts are suppressed |
| **ISC DHCPv4 up / down** | Fires when the DHCPv4 server stops or recovers. Brief restarts are suppressed |
| **ISC DHCPv6 up / down** *(experimental)* | Fires when the DHCPv6 server stops or recovers |

### Hardware

| Monitor | Description |
| --- | --- |
| **CPU temperature** *(experimental)* | Fires when any core exceeds the threshold and when it recovers. Configurable threshold (default: 80 °C) |
| **Fan stopped** *(experimental)* | Fires when a fan reads 0 RPM past the threshold. Configurable threshold (default: 30 s) |

### System

| Monitor | Description |
| --- | --- |
| **System reboot / startup** | Fires on shutdown and after boot |
| **Configuration changes** | Fires when the OPNsense config is saved, including the change description and user. Internal saves are suppressed |
| **Firmware / package updates available** | Fires when updates are detected, and again when the system is up to date |
| **APCUPSd events** | Fires on power failure, restore, battery exhausted, and comms events. Requires apcupsd writing to `/var/log/apcupsd.events` |

## Sending notifications from the CLI

```sh
configctl pushover notify "Your+message+here"
```

The message must be URL-encoded (spaces as `+` or `%20`).
