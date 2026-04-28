#!/usr/local/bin/python3
"""
Persistent Pushover notification daemon.
Monitors apcupsd events and service states; sends notifications via Pushover.
Managed by rc.d as the 'pushover' service; pidfile is written by daemon(8).
"""

import glob
import json
import os
import re
import signal
import socket
import subprocess
import time
import urllib.parse

EVENTS_FILE   = '/var/log/apcupsd.events'
STATE_FILE    = '/var/run/pushover_ups_state.json'
NOTIFY_BIN    = '/usr/local/opnsense/scripts/OPNsense/Pushover/sendNotification.py'
CONF_FILE     = '/usr/local/etc/pushover/pushover.conf'
POLL_INTERVAL = 5  # seconds
HOSTNAME      = socket.gethostname().split('.')[0]

# (conf_key, pidfile, label_down, label_up, state_key)
SERVICE_MONITORS = [
    ('notify_unbound', '/var/run/unbound.pid',
     'Unbound DNS is down', 'Unbound DNS restored', 'unbound'),
    ('notify_dhcp', '/var/dhcpd/var/run/dhcpd.pid',
     'ISC DHCPv4 is down', 'ISC DHCPv4 restored', 'dhcp'),
    ('notify_dhcp6', '/var/dhcpd/var/run/dhcpdv6.pid',
     'ISC DHCPv6 is down', 'ISC DHCPv6 restored', 'dhcp6'),
]

# (pattern, message, state_key, new_state_value, always_notify)
UPS_EVENTS = [
    ('Communications with UPS lost',
     'UPS: Communications lost',        'comm',    'lost',      False),
    ('Communications with UPS restored',
     'UPS: Communications restored',    'comm',    'ok',        False),
    ('Power failure',
     'UPS: Power failure - on battery', 'power',   'battery',   False),
    ('Power is back',
     'UPS: Power restored',             'power',   'ok',        False),
    ('Battery exhausted',
     'UPS: Battery exhausted',          'battery', 'exhausted', True),
    ('Initiating system shutdown',
     'UPS: Shutdown initiated',         'shutdown', 'yes',      True),
]

_running = True


def _handle_signal(signum, frame):
    global _running
    _running = False


def _read_conf():
    conf = {}
    try:
        with open(CONF_FILE) as f:
            for line in f:
                k, _, v = line.partition('=')
                conf[k.strip()] = v.strip()
    except OSError:
        pass
    return conf


def _load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        pass
    defaults = {
        'offset': 0,
        'comm': 'ok', 'power': 'ok', 'battery': 'ok', 'shutdown': 'no',
    }
    for _, _, _, _, key in SERVICE_MONITORS:
        defaults[key] = 'ok'
        defaults[key + '_suspect'] = False
    return defaults


def _save_state(state):
    try:
        tmp = STATE_FILE + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(state, f)
        os.replace(tmp, STATE_FILE)
    except OSError:
        pass


def _send(msg):
    encoded = urllib.parse.quote(f'{HOSTNAME}: {msg}')
    env = dict(os.environ, PUSHOVER_TIMEOUT='10')
    subprocess.run(
        ['/usr/local/bin/python3', NOTIFY_BIN, encoded],
        env=env, capture_output=True
    )


def _poll_ups(state):
    if not os.path.exists(EVENTS_FILE):
        return state
    try:
        with open(EVENTS_FILE, 'rb') as f:
            f.seek(0, 2)
            current_size = f.tell()
            if current_size < state['offset']:
                state['offset'] = 0
            f.seek(state['offset'])
            new_data = f.read()
            state['offset'] = current_size
    except OSError:
        return state

    for line in new_data.decode('utf-8', errors='replace').splitlines():
        line = line.strip()
        if not line:
            continue
        for pattern, msg, state_key, new_val, always_notify in UPS_EVENTS:
            if pattern in line:
                if always_notify or state.get(state_key) != new_val:
                    _send(msg)
                    state[state_key] = new_val
                break

    return state


def _pid_running(pidfile):
    try:
        with open(pidfile) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


_OVPN_STATES = frozenset({
    'CONNECTING', 'WAIT', 'AUTH', 'GET_CONFIG',
    'ASSIGN_IP', 'ADD_ROUTES', 'CONNECTED', 'RECONNECTING', 'EXITING',
})


def _query_ovpn_socket(path):
    """Return the current OpenVPN state string, or None on failure."""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect(path)
        buf = b''
        while b'\n' not in buf:
            chunk = sock.recv(512)
            if not chunk:
                break
            buf += chunk
            if len(buf) > 4096:
                break
        sock.sendall(b'state\nquit\n')
        resp = b''
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                chunk = sock.recv(1024)
            except OSError:
                break
            if not chunk:
                break
            resp += chunk
            if b'END' in resp:
                break
        sock.close()
    except OSError:
        return None
    for line in resp.decode('utf-8', errors='replace').splitlines():
        parts = line.split(',')
        if len(parts) >= 2 and parts[1] in _OVPN_STATES:
            return parts[1]
    return None


def _ovpn_devname(stat_path):
    try:
        with open(stat_path) as f:
            return json.load(f).get('devname', '')
    except Exception:
        return ''


def _get_fan_sysctls():
    try:
        result = subprocess.run(
            ['sysctl', '-a'], capture_output=True, text=True, timeout=15
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    fans = {}
    for line in result.stdout.splitlines():
        raw_key, _, val = line.partition(':')
        key = raw_key.strip()
        if not ('fan' in key.lower() or 'rpm' in key.lower()):
            continue
        try:
            fans[key] = int(val.strip())
        except ValueError:
            pass
    return fans


FIRMWARE_STATUS_FILE = '/tmp/pkg_upgrade.json'


def _poll_firmware(state):
    try:
        mtime = os.path.getmtime(FIRMWARE_STATUS_FILE)
    except OSError:
        return state

    if mtime == state.get('firmware_mtime'):
        return state
    state['firmware_mtime'] = mtime

    try:
        with open(FIRMWARE_STATUS_FILE) as f:
            data = json.load(f)
    except Exception:
        return state

    count = (
        len(data.get('upgrade_packages', [])) +
        len(data.get('new_packages', [])) +
        len(data.get('upgrade_sets', []))
    )
    had_updates = state.get('firmware') == 'updates_available'

    if count > 0 and not had_updates:
        _send(f'OPNsense: {count} update(s) available')
        state['firmware'] = 'updates_available'
    elif count == 0 and had_updates:
        _send('OPNsense: packages are up to date')
        state['firmware'] = 'ok'

    return state


def _poll_fan(state, threshold):
    fans = _get_fan_sysctls()
    now = time.time()
    seen = set()

    for key, rpm in fans.items():
        state_key = f'fan_{key}'
        since_key = state_key + '_since'
        seen.add(state_key)
        was_stopped = state.get(state_key) == 'stopped'

        if rpm > 0:
            if was_stopped:
                _send(f'Fan recovered: {key} at {rpm} RPM')
                state[state_key] = 'ok'
            state.pop(since_key, None)
        else:
            if since_key not in state:
                state[since_key] = now
            if not was_stopped and (now - state[since_key]) >= threshold:
                _send(f'Fan stopped: {key} reads 0 RPM')
                state[state_key] = 'stopped'

    for k in [k for k in list(state) if k.startswith('fan_') and k not in seen and not k.endswith('_since')]:
        state.pop(k, None)
        state.pop(k + '_since', None)

    return state


def _poll_cpu_temp(state, threshold):
    try:
        result = subprocess.run(
            ['sysctl', '-a', 'dev.cpu'],
            capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return state

    temps = {}
    for line in result.stdout.splitlines():
        if '.temperature:' not in line:
            continue
        key, _, val = line.partition(':')
        try:
            core = int(key.strip().split('.')[2])
            temps[core] = float(val.strip().rstrip('C'))
        except (ValueError, IndexError):
            pass

    if not temps:
        return state

    max_core = max(temps, key=temps.get)
    max_temp = temps[max_core]
    was_hot = state.get('cpu_temp') == 'hot'

    if not was_hot and max_temp >= threshold:
        _send(f'CPU temp alert: {max_temp:.0f}C (threshold {threshold:.0f}C, hottest core {max_core})')
        state['cpu_temp'] = 'hot'
    elif was_hot and max_temp < (threshold - 5):
        _send(f'CPU temp recovered: {max_temp:.0f}C (all {len(temps)} cores below threshold)')
        state['cpu_temp'] = 'ok'

    return state


def _poll_openvpn(state, threshold):
    seen = set()
    now = time.time()

    for sock_path in glob.glob('/var/etc/openvpn/instance-*.sock'):
        prefix = '/var/etc/openvpn/instance-'
        uuid = sock_path[len(prefix):-len('.sock')]
        devname = _ovpn_devname(f'{prefix}{uuid}.stat') or uuid[:8]
        key = f'ovpn_{uuid}'
        since_key = key + '_since'
        seen.add(key)

        vpn_state = _query_ovpn_socket(sock_path)
        was_down = state.get(key) == 'down'

        if vpn_state == 'CONNECTED':
            if was_down:
                _send(f'OpenVPN: {devname} reconnected')
                state[key] = 'ok'
            state.pop(since_key, None)
        else:
            label = f'is {vpn_state}' if vpn_state else 'unreachable'
            if since_key not in state:
                state[since_key] = now
            if not was_down and (now - state[since_key]) >= threshold:
                _send(f'OpenVPN: {devname} {label}')
                state[key] = 'down'

    for k in [k for k in list(state) if k.startswith('ovpn_') and k not in seen and not k.endswith('_since')]:
        state.pop(k, None)
        state.pop(k + '_since', None)

    return state


def _poll_wireguard(state, threshold):
    try:
        result = subprocess.run(
            ['wg', 'show', 'all', 'dump'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return state
    except (OSError, subprocess.TimeoutExpired):
        return state

    now = int(time.time())
    seen = set()

    for line in result.stdout.splitlines():
        parts = line.split('\t')
        if len(parts) != 9:
            continue  # interface line has 5 fields; peer lines have 9
        iface   = parts[0]
        pubkey  = parts[1]
        if not re.fullmatch(r'[A-Za-z0-9_\-]{1,15}', iface):
            continue
        if not re.fullmatch(r'[A-Za-z0-9+/]{43}=', pubkey):
            continue
        last_hs = int(parts[5]) if parts[5].isdigit() else 0
        if last_hs == 0:
            continue  # never handshaked — skip

        key     = f'wg_{iface}_{pubkey}'
        seen.add(key)
        age     = now - last_hs
        was_down = state.get(key) == 'down'
        is_stale = age > threshold

        if was_down and not is_stale:
            _send(f'WireGuard: {iface} peer {pubkey[:8]}... reconnected')
            state[key] = 'ok'
        elif not was_down and is_stale:
            mins = age // 60
            _send(f'WireGuard: {iface} peer {pubkey[:8]}... no handshake for {mins}m')
            state[key] = 'down'

    for k in [k for k in list(state) if k.startswith('wg_') and k not in seen and not k.endswith('_since')]:
        state.pop(k, None)
        state.pop(k + '_since', None)

    return state


def _poll_service(state, pidfile, label_down, label_up, key):
    suspect_key = key + '_suspect'
    currently_up = _pid_running(pidfile)

    if currently_up:
        if state.get(key) == 'down':
            _send(label_up)
            state[key] = 'ok'
        state[suspect_key] = False
    else:
        if state.get(suspect_key):
            if state.get(key) != 'down':
                _send(label_down)
                state[key] = 'down'
            state[suspect_key] = False
        else:
            state[suspect_key] = True

    return state


def main():
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    state = _load_state()
    while _running:
        conf = _read_conf()
        if conf.get('notify_firmware') == '1':
            state = _poll_firmware(state)
        if conf.get('notify_fan') == '1':
            fan_threshold = max(int(conf.get('fan_threshold') or 30), 5)
            state = _poll_fan(state, fan_threshold)
        if conf.get('notify_cpu_temp') == '1':
            cpu_threshold = max(float(conf.get('cpu_temp_threshold') or 80), 1.0)
            state = _poll_cpu_temp(state, cpu_threshold)
        if conf.get('notify_ups') == '1':
            state = _poll_ups(state)
        if conf.get('notify_openvpn') == '1':
            ovpn_threshold = max(int(conf.get('ovpn_threshold') or 60), 5)
            state = _poll_openvpn(state, ovpn_threshold)
        if conf.get('notify_wireguard') == '1':
            threshold = max(int(conf.get('wg_threshold') or 300), 5)
            state = _poll_wireguard(state, threshold)
        for conf_key, pidfile, label_down, label_up, key in SERVICE_MONITORS:
            if conf.get(conf_key) == '1':
                state = _poll_service(state, pidfile, label_down, label_up, key)
        _save_state(state)
        time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    main()
