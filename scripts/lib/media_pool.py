"""Opt-in mergerfs preflight and systemd startup for media consumers only."""
import json
import os
from pathlib import Path
import config
import runtime

SERVICES = ('jellyfin', 'navidrome', 'radarr', 'sonarr', 'lidarr', 'bazarr', 'qbittorrent')
MARKER = '# Managed by Ohara media-pool\n'


def require_mount(c):
    mount = c.get('MEDIA_POOL_MOUNT')
    if not mount:
        return
    info = json.loads(runtime.run(['findmnt', '--json', '--mountpoint', mount,
                                  '-o', 'TARGET,FSTYPE'], capture=True))
    rows = info.get('filesystems', [])
    if len(rows) != 1 or rows[0]['target'] != mount or rows[0]['fstype'] != 'fuse.mergerfs':
        raise ValueError('MEDIA_POOL_MOUNT is not the active mergerfs mount; start its systemd mount first')


def override(c, root):
    return ['-f', str(root/'compose.media-pool.yaml')] if c.get('MEDIA_POOL_MOUNT') else []


def unit(c, root):
    mount = c.get('MEDIA_POOL_MOUNT')
    if not mount:
        raise ValueError('Configure MEDIA_POOL_MOUNT and MEDIA_ROOT before installing the unit')
    if not config.PATH.fullmatch(str(root)):
        raise ValueError('Systemd integration requires a repository path without spaces or special characters')
    mount_unit = runtime.run(['systemd-escape', '--path', '--suffix=mount', mount], capture=True).strip()
    return MARKER + f'''[Unit]
Description=Ohara media services on mergerfs
RequiresMountsFor={mount}
BindsTo={mount_unit} docker.service
After={mount_unit} docker.service
PartOf=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart={root}/scripts/media-pool start
ExecStopPost={root}/scripts/media-pool stop
TimeoutStartSec=300
TimeoutStopSec=180

[Install]
WantedBy=docker.service
'''


def install(c, root):
    if os.geteuid() != 0:
        raise ValueError('Use sudo scripts/media-pool install-unit')
    require_mount(c)
    content = unit(c, root)
    path = Path('/etc/systemd/system/ohara-media.service')
    if path.is_symlink() or (path.exists() and not path.read_text().startswith(MARKER)):
        raise ValueError('Existing unmanaged ohara-media.service; preserve and review it')
    path.write_text(content)
    path.chmod(0o644)
    runtime.run(['systemctl', 'daemon-reload'])
    runtime.run(['systemctl', 'enable', 'ohara-media.service'])
    print('Media unit installed/enabled; not started. Start it after checking playback.')


def start(c, root):
    require_mount(c)
    runtime.check(c, root)
    runtime.compose(c, root, ['up', '-d', '--no-deps', '--wait', '--wait-timeout', '180', *SERVICES], timeout=240)


def stop(c, root):
    # Deliberately works when the pool is absent; only these consumers are stopped.
    runtime.compose(c, root, ['stop', '--timeout', '20', *SERVICES], timeout=170)
