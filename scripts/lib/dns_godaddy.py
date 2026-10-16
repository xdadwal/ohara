#!/usr/bin/env python3
"""Standalone Certbot DNS hooks; installed outside the checkout for renewal."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

CREDENTIALS = Path('/etc/ohara/dns-godaddy.json')
STATE = Path('/var/lib/ohara/acme-dns')
API = 'https://api.godaddy.com/v3/domains/zones/'
RESOLVERS = ('https://dns.google/resolve', 'https://cloudflare-dns.com/dns-query')


def credentials(path):
    # O_NOFOLLOW also prevents accidentally reading a symlink as root.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise ValueError('DNS credentials must be a regular private file (chmod 600)')
        if os.geteuid() != 0 and info.st_uid not in (0, os.getuid()):
            raise ValueError('DNS credentials must belong to the invoking user or root')
        try:
            data = json.load(stream)
        except (ValueError, UnicodeError):
            raise ValueError('DNS credentials must contain valid JSON') from None
    if not isinstance(data, dict) or set(data) != {'domain', 'token'}:
        raise ValueError('DNS credentials require exactly domain and token fields')
    domain = data['domain']
    if (not isinstance(domain, str) or len(domain) > 253 or '.' not in domain
            or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
                   for label in domain.split('.'))):
        raise ValueError('DNS credential domain must be a lowercase DNS zone name')
    token = data['token']
    if not isinstance(token, str) or not re.fullmatch(r'[!-~]{16,4096}', token):
        raise ValueError('DNS token is missing or invalid')
    return data


def write_json(path, data):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.ohara-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class GoDaddy:
    def __init__(self, data):
        self.data = data
        self.url = API + urllib.parse.quote(data['domain'], safe='') + '/dns-records'

    def request(self, method, suffix='', body=None):
        request = urllib.request.Request(
            self.url + suffix, method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Authorization': 'Bearer ' + self.data['token'],
                     'Content-Type': 'application/json', 'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            # Provider bodies may echo credentials; expose only the status.
            raise RuntimeError(f'GoDaddy DNS API returned HTTP {error.code}; check PAT scope and account access') from None
        except (OSError, ValueError):
            raise RuntimeError('GoDaddy DNS API request failed; response suppressed') from None

    def records(self, name):
        result = []
        for page in range(1, 101):
            query = urllib.parse.urlencode({'type': 'TXT', 'name': name, 'page': page, 'pageSize': 100})
            data = self.request('GET', '?' + query)
            if not isinstance(data, dict) or not isinstance(data.get('items'), list):
                raise RuntimeError('Unexpected GoDaddy DNS response')
            items = data['items']
            if any(r.get('name') != name or r.get('type') != 'TXT' for r in items):
                raise RuntimeError('Unexpected DNS records returned; refusing changes')
            result.extend(items)
            if len(items) < 100:
                return result
        raise RuntimeError('DNS record pagination limit exceeded')


def challenge(data, env):
    domain = env.get('CERTBOT_DOMAIN', '').removeprefix('*.')
    # Only apex + one-level wildcard are supported; never infer a parent zone.
    if domain != data['domain']:
        raise ValueError('Certificate domain does not match the configured DNS zone')
    value = env.get('CERTBOT_VALIDATION', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}', value):
        raise ValueError('Missing or invalid Certbot DNS challenge')
    return '_acme-challenge', value


def visible(name, value, resolver):
    query = urllib.parse.urlencode({'name': name, 'type': 'TXT', 'cachebust': time.time_ns()})
    request = urllib.request.Request(resolver + '?' + query,
                                     headers={'Accept': 'application/dns-json', 'Cache-Control': 'no-cache'})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
        return data.get('Status') == 0 and any(
            r.get('type') == 16 and r.get('data', '').strip('"') == value
            for r in data.get('Answer', []))
    except (OSError, ValueError):
        return False


def wait_for_dns(data, state):
    pending = [json.loads(p.read_text()) for p in state.glob('*.json')]
    if not pending:
        raise RuntimeError('DNS challenge journal is empty')
    # Wait out the prior positive/negative cache before asking the CA to validate.
    ready = max(r['ready_at'] for r in pending)
    deadline = max(time.time(), ready) + 600
    consecutive = 0
    while time.time() < deadline:
        if time.time() >= ready and all(
                visible('_acme-challenge.' + data['domain'], r['value'], resolver)
                for r in pending for resolver in RESOLVERS):
            consecutive += 1
            if consecutive >= 2:
                return
        else:
            consecutive = 0
        time.sleep(30)
    raise RuntimeError('DNS propagation timed out; existing certificate remains in place')


def run_hook(action, data, state=STATE, env=None):
    env = os.environ if env is None else env
    name, value = challenge(data, env)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    if state.is_symlink() or state.stat().st_uid != os.getuid() or state.stat().st_mode & 0o077:
        raise ValueError('DNS challenge journal must be an owned private directory')
    with (state / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        api = GoDaddy(data)
        journal = state / (hashlib.sha256(value.encode()).hexdigest() + '.json')
        records = api.records(name)
        if action == 'cleanup':
            if journal.exists():
                saved = json.loads(journal.read_text())
                for record in records:
                    if (saved['created'] and record['recordId'] == saved['recordId']
                            and record['data'] == value):
                        api.request('DELETE', '/' + urllib.parse.quote(record['recordId'], safe=''))
                journal.unlink()
            return
        if not journal.exists():
            ttl = max([3600] + [int(r['ttl']) for r in records])
            if ttl > 3600:
                raise ValueError('Lower existing challenge TXT TTL to 3600 or less and wait its old TTL before retrying')
            found = next((r for r in records if r['data'] == value), None)
            created = found is None
            if created:
                found = api.request('POST', body={'name': name, 'type': 'TXT', 'data': value, 'ttl': 600})
            if not isinstance(found, dict) or not isinstance(found.get('recordId'), str):
                raise RuntimeError('GoDaddy did not return a DNS record identifier')
            write_json(journal, {'recordId': found['recordId'], 'created': created,
                                 'value': value, 'ready_at': time.time() + ttl + 60})
    # Certbot invokes auth hooks sequentially; publish both apex/wildcard values
    # before waiting, preserving the first value until its cleanup hook runs.
    if env.get('CERTBOT_REMAINING_CHALLENGES', '0') == '0':
        wait_for_dns(data, state)


if __name__ == '__main__':
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ('auth', 'cleanup'):
            raise ValueError('Usage: dns_godaddy.py auth|cleanup')
        run_hook(sys.argv[1], credentials(CREDENTIALS))
    except (ValueError, OSError, RuntimeError) as error:
        print(f'Ohara DNS: {error}', file=sys.stderr)
        sys.exit(1)
