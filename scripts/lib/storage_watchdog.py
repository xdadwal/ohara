"""Host storage watchdog: metadata-only checks, bounded systemd recovery, HDD standby."""
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

CONFIG = Path('/etc/ohara/storage-watchdog.json')
STATE = Path('/run/ohara-storage-watchdog/state.json')


def command(args, timeout=15):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed (exit {result.returncode}); inspect journal')
    return result.stdout


def load_config(path):
    if path.is_symlink():
        raise ValueError('Watchdog configuration must not be a symlink')
    c = json.loads(path.read_text())
    if set(c) != {'pool', 'branches', 'hdd_uuid', 'hdd_serial'} or c['pool'] != '/ohara/mnt':
        raise ValueError('Expected explicit Ohara pool, branches and HDD identity')
    if not isinstance(c['branches'], list) or not c['branches']:
        raise ValueError('Expected external branches')
    seen = set()
    for branch in c['branches']:
        if set(branch) != {'uuid', 'mount'} or not re.fullmatch(r'[0-9a-f-]{36}', branch['uuid']):
            raise ValueError('Invalid external branch UUID')
        if not re.fullmatch(r'/mnt/disks/[a-z0-9-]+', branch['mount']):
            raise ValueError('Expected an external disk mountpoint')
        if branch['uuid'] in seen:
            raise ValueError('Duplicate external branch')
        seen.add(branch['uuid'])
    if len({b['mount'] for b in c['branches']}) != len(c['branches']):
        raise ValueError('Duplicate branch mountpoint')
    if c['hdd_uuid'] not in seen or not re.fullmatch(r'[A-Za-z0-9-]+', c['hdd_serial']):
        raise ValueError('HDD identity must match a configured branch')
    return c


def devices(c):
    """Read udev/sysfs only; no disk-sector or media-file reads."""
    result = {}
    for b in c['branches']:
        path = Path('/dev/disk/by-uuid') / b['uuid']
        try:
            s = path.stat()
            if not stat.S_ISBLK(s.st_mode):
                continue
            major, minor = os.major(s.st_rdev), os.minor(s.st_rdev)
            node = Path(f'/sys/dev/block/{major}:{minor}').resolve(strict=True)
            disk = node.parent if (node/'partition').exists() else node
            seq = (disk/'diskseq').read_text().strip()
            result[b['uuid']] = {'dev': f'{major}:{minor}', 'disk': '/dev/'+disk.name,
                                 'generation': f'{major}:{minor}:{seq}'}
        except (OSError, ValueError):
            continue
    return result


def mounts():
    # /proc/self/mountinfo is kernel metadata; findmnt does not stat media here.
    data = json.loads(command(['findmnt', '--kernel', '--json', '--list', '-o',
                               'TARGET,FSTYPE,OPTIONS,MAJ:MIN']))
    return {r['target']: r for r in data.get('filesystems', [])}


def active(unit):
    return command(['systemctl', 'show', unit, '-p', 'ActiveState', '--value']).strip()


def decide(c, state, current, mounted, media, pool, now):
    """Return an action without touching services or disks."""
    fingerprint = {k: v['generation'] for k, v in current.items()}
    generations = state.setdefault('mounted_generation', {})
    for b in c['branches']:
        if b['mount'] not in mounted:
            generations.pop(b['uuid'], None)
    if len(current) != len(c['branches']):
        state.pop('ready_since', None)
        state['fingerprint'] = fingerprint
        return 'stop' if media in ('active', 'activating') or pool in ('active', 'activating') else 'missing'
    for b in c['branches']:
        row = mounted.get(b['mount'])
        if row and (row.get('maj:min') != current[b['uuid']]['dev'] or
                    row.get('fstype') != 'ext4' or 'rw' not in row.get('options', '').split(',')):
            state.pop('ready_since', None)
            return 'unsafe-stop' if media in ('active', 'activating') else 'unsafe'
        if row:
            generation = current[b['uuid']]['generation']
            if generations.get(b['uuid'], generation) != generation:
                state.pop('ready_since', None)
                return 'unsafe-stop' if media in ('active', 'activating') else 'unsafe'
            generations[b['uuid']] = generation
    row = mounted.get(c['pool'])
    if row and (row.get('fstype') != 'fuse.mergerfs' or
                'rw' not in row.get('options', '').split(',') or
                any(b['mount'] not in mounted for b in c['branches'])):
        state.pop('ready_since', None)
        return 'unsafe-stop' if media in ('active', 'activating') else 'unsafe'
    if media == 'active' and (not row or any(b['mount'] not in mounted for b in c['branches'])):
        state.pop('ready_since', None)
        return 'unsafe-stop'
    if media == 'active' and row and all(b['mount'] in mounted for b in c['branches']):
        # A reattached device with a live old mount needs manual inspection.
        if state.get('fingerprint', fingerprint) != fingerprint:
            state.pop('ready_since', None)
            return 'unsafe-stop'
        state['fingerprint'] = fingerprint
        state.pop('ready_since', None)
        return 'healthy'
    if media in ('activating', 'deactivating') or pool in ('activating', 'deactivating'):
        return 'busy'
    if state.get('fingerprint') != fingerprint:
        state['fingerprint'] = fingerprint
        state['ready_since'] = now
    state.setdefault('ready_since', now)
    if now - state['ready_since'] < 60:
        return 'settling'
    attempts = [t for t in state.get('attempts', []) if now-t < 3600]
    state['attempts'] = attempts
    if len(attempts) >= 3 or (attempts and now-attempts[-1] < 300):
        return 'cooldown'
    attempts.append(now)
    return 'recover'


def apply_standby(c, state, current):
    info = current.get(c['hdd_uuid'])
    if not info or state.get('standby_generation') == info['generation']:
        return
    # Mark the attempt so unsupported bridges are not poked every 30 seconds.
    state['standby_generation'] = info['generation']
    props = command(['udevadm', 'info', '--query=property', '--name='+info['disk']])
    props = dict(line.split('=', 1) for line in props.splitlines() if '=' in line)
    disk = Path('/sys/class/block')/Path(info['disk']).name
    if props.get('ID_SERIAL_SHORT') != c['hdd_serial'] or (disk/'queue/rotational').read_text().strip() != '1':
        print('HDD identity/rotational check failed; standby unchanged', flush=True)
        return
    try:
        command(['/usr/sbin/hdparm', '-S', '242', info['disk']], timeout=20)
        print('Applied HDD firmware standby timeout: 60 minutes; physical spindown not yet verified', flush=True)
    except (RuntimeError, subprocess.TimeoutExpired):
        print('USB adapter did not accept standby command; no forced spindown attempted', flush=True)


def tick(c, state, now=None):
    current = devices(c)
    action = decide(c, state, current, mounts(), active('ohara-media.service'),
                    active('ohara-mnt.mount'), time.monotonic() if now is None else now)
    if action != state.get('last_action'):
        print('Storage watchdog: '+action, flush=True)
    state['last_action'] = action
    if action == 'stop':
        command(['systemctl', 'stop', '--no-block', 'ohara-media.service', 'ohara-mnt.mount'])
    elif action == 'unsafe-stop':
        command(['systemctl', 'stop', '--no-block', 'ohara-media.service'])
    elif action == 'recover':
        # RequiresMountsFor mounts both branches and pool before ExecStart runs.
        command(['systemctl', 'start', '--no-block', 'ohara-media.service'])
    apply_standby(c, state, current)
    return action


def run():
    if os.geteuid() != 0:
        raise ValueError('Storage watchdog requires root')
    c = load_config(CONFIG)
    try:
        state = json.loads(STATE.read_text())
    except FileNotFoundError:
        state = {}
    try:
        tick(c, state)
    finally:
        STATE.parent.mkdir(mode=0o700, exist_ok=True)
        temp = STATE.with_suffix('.tmp')
        temp.write_text(json.dumps(state)+'\n')
        temp.chmod(0o600)
        temp.replace(STATE)


def install(root, source):
    if os.geteuid() != 0:
        raise ValueError('Use sudo scripts/storage-watchdog install --config PATH')
    c = load_config(source)
    # Check that declared branch UUIDs/mountpoints agree with this host's fstab.
    rows = json.loads(command(['findmnt', '--fstab', '--json', '--list', '-o',
                               'TARGET,SOURCE,FSTYPE'])).get('filesystems', [])
    for b in c['branches']:
        if not any(r['target'] == b['mount'] and r['source'] == 'UUID='+b['uuid']
                   and r['fstype'] == 'ext4' for r in rows):
            raise ValueError('Watchdog branch does not match this host fstab')
    if not any(r['target'] == c['pool'] and r['fstype'] == 'fuse.mergerfs' for r in rows):
        raise ValueError('Pool is not configured in this host fstab')
    if not Path('/usr/sbin/hdparm').is_file():
        raise ValueError('Install the distribution hdparm package first')
    if not Path('/etc/systemd/system/ohara-media.service').is_file():
        raise ValueError('Install the existing guarded media unit first')
    files = {
        Path('/usr/local/lib/ohara/storage_watchdog.py'): (root/'scripts/lib/storage_watchdog.py').read_text(),
        CONFIG: json.dumps(c, indent=2)+'\n',
    }
    for suffix in ['service', 'timer']:
        name = 'ohara-storage-watchdog.'+suffix
        files[Path('/etc/systemd/system')/name] = (root/'configs/systemd'/name).read_text()
    for target in files:
        if target.is_symlink() or any(p.is_symlink() for p in target.parents):
            raise ValueError('Symlink installation target; inspect manually')
        if target.exists() and target not in (CONFIG, Path('/usr/local/lib/ohara/storage_watchdog.py')):
            if not target.read_text().startswith('# Managed by Ohara storage-watchdog'):
                raise ValueError('Preserve existing unmanaged watchdog unit')
        if target.exists() and target in (CONFIG, Path('/usr/local/lib/ohara/storage_watchdog.py')):
            # A rerun may update only files already matching this implementation/config.
            if target.read_text() != files[target]:
                raise ValueError('Existing watchdog config/code differs; back up and reconcile manually')
    for target, content in files.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        target.chmod(0o600 if target == CONFIG else 0o644)
        os.chown(target, 0, 0)
    command(['systemd-analyze', 'verify', '/etc/systemd/system/ohara-storage-watchdog.service',
             '/etc/systemd/system/ohara-storage-watchdog.timer'])
    command(['systemctl', 'daemon-reload'])
    command(['systemctl', 'enable', '--now', 'ohara-storage-watchdog.timer'])
    print('Storage watchdog timer enabled; inspect journal for recovery and standby status.')


if __name__ == '__main__':
    try:
        run()
    except Exception as error:
        print('Storage watchdog: '+str(error), flush=True)
        raise SystemExit(1)
