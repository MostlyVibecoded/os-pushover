#!/usr/local/bin/python3

# Copyright (C) 2025 MostlyVibecoded
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
# OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import configparser
import json
import os
import sys
import urllib.error
import urllib.request
import urllib.parse

CONF_PATH = '/usr/local/etc/pushover/pushover.conf'
PUSHOVER_API = 'https://api.pushover.net/1/messages.json'

PRIORITY_MAP = {
    'lowest': '-2',
    'low':    '-1',
    'normal':  '0',
    'high':    '1',
}

_VALID_NUMERIC_PRIORITIES = {'-2', '-1', '0', '1'}


def _join_errors(errors, fallback: str) -> str:
    if isinstance(errors, list):
        parts = [e if isinstance(e, str) else json.dumps(e) for e in errors]
        parts = [p for p in parts if p.strip()]
        return ', '.join(parts) if parts else fallback
    if isinstance(errors, str):
        return errors if errors.strip() else fallback
    if isinstance(errors, dict):
        return json.dumps(errors) if errors else fallback
    return fallback


def _resolve_priority(raw):
    if raw in PRIORITY_MAP:
        return PRIORITY_MAP[raw]
    if raw in _VALID_NUMERIC_PRIORITIES:
        return raw
    return '0'


def load_config(path=None):
    cfg = configparser.RawConfigParser()
    try:
        cfg.read(path or CONF_PATH)
    except (configparser.Error, UnicodeDecodeError):
        return None
    if 'general' not in cfg:
        return None
    return cfg['general']


def send(message, conf_path=None, timeout=10):
    conf = load_config(conf_path)
    if conf is None:
        return {'status': 'failed', 'message': 'Pushover is not enabled or config is missing'}

    api_token = conf.get('api_token', '').strip()
    user_key = conf.get('user_key', '').strip()

    if not api_token or not user_key:
        return {'status': 'failed', 'message': 'API token or user key is not configured'}

    payload = {
        'token': api_token,
        'user': user_key,
        'message': message,
    }

    device = conf.get('device', '').strip()
    if device:
        payload['device'] = device

    priority = _resolve_priority(conf.get('priority', 'normal').strip())
    payload['priority'] = priority

    sound = conf.get('sound', '').strip()
    if sound:
        payload['sound'] = sound

    data = urllib.parse.urlencode(payload).encode('utf-8')
    req = urllib.request.Request(PUSHOVER_API, data=data, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    req.add_header('User-Agent', 'os-pushover/1.0 OPNsense')

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode('utf-8'))
            if not isinstance(body, dict):
                return {'status': 'failed', 'message': 'unexpected API response format'}
            if type(body.get('status')) is int and body.get('status') == 1 and not body.get('errors'):
                return {'status': 'ok', 'message': 'Notification sent'}
            return {'status': 'failed', 'message': _join_errors(body.get('errors'), 'Unknown error')}
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode('utf-8'))
            if not isinstance(body, dict):
                return {'status': 'failed', 'message': str(e)}
            return {'status': 'failed', 'message': _join_errors(body.get('errors'), str(e))}
        except Exception:
            return {'status': 'failed', 'message': str(e)}
    except Exception as e:
        return {'status': 'failed', 'message': str(e)}


if __name__ == '__main__':
    msg = urllib.parse.unquote_plus(' '.join(sys.argv[1:]).strip()) if len(sys.argv) > 1 else ''
    if not msg:
        print(json.dumps({'status': 'failed', 'message': 'No message provided'}))
        sys.exit(1)
    _timeout = int(os.environ.get('PUSHOVER_TIMEOUT', '10'))
    # PUSHOVER_CONF_PATH is intentional: allows test isolation without touching the real conf.
    # It is never set in production; only root can influence the daemon's environment.
    result = send(msg, conf_path=os.environ.get('PUSHOVER_CONF_PATH'), timeout=_timeout)
    print(json.dumps(result))
    sys.exit(0 if result.get('status') == 'ok' else 1)
