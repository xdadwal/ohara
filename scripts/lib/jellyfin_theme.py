"""Pinned Abyss assets, persistent read-only web overlay and supported Jellyfin APIs."""

import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.parse

import config
import credentials
import media
import runtime

FILES = ('abyss.css', 'abyss-je.css', 'spotlight.html', 'spotlight.css', 'spotlight-loader.js')
START = '/* OHARA ABYSS START */'
END = '/* OHARA ABYSS END */'
TAG = '<script src="ui/spotlight-loader.js" data-abyss-spotlight></script>'


def safe(path):
    path = Path(path)
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('Symlink theme storage is unsupported')
    return path


def state(c):
    path = safe(Path(c['DATA_ROOT']) / 'jellyfin-theme/manifest.json')
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (ValueError, OSError):
        raise ValueError('Unreadable Jellyfin theme manifest; review it before startup') from None
    if data.get('schema') != 1 or not isinstance(data.get('enabled'), bool):
        raise ValueError('Unsupported Jellyfin theme manifest')
    return data


def override(c, root):
    manifest = state(c)
    if not manifest or not manifest['enabled']:
        return []
    if manifest.get('image') != config.images(root / 'versions/stack.env')['JELLYFIN_IMAGE']:
        raise ValueError(
            'Jellyfin image changed: run scripts/jellyfin-theme install to refresh its web overlay'
        )
    expected = {'index.html'} | {'ui/' + name for name in FILES}
    if set(manifest.get('files', {})) != expected:
        raise ValueError('Unexpected files in Jellyfin theme manifest')
    for name, digest in manifest['files'].items():
        path = safe(Path(c['DATA_ROOT']) / 'jellyfin-theme' / name)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Jellyfin theme assets changed or are missing; review before startup')
    return ['-f', str(root / 'compose/overrides/jellyfin-theme.yaml')]


def write(path, data, c):
    path = safe(path)
    if path.exists() and path.read_bytes() == data:
        return
    fd, temporary = tempfile.mkstemp(prefix='.theme-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.chmod(temporary, 0o644)
        if os.geteuid() == 0:
            os.chown(temporary, int(c['RUN_UID']), int(c['RUN_GID']))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def prepare(c, root, *, enabled=None):
    import host
    import runtime

    base = safe(Path(c['DATA_ROOT']) / 'jellyfin-theme')
    previous = state(c)
    source = root / 'configs/jellyfin/abyss'
    upstream = json.loads((source / 'upstream.json').read_text())
    for name, digest in upstream['sha256'].items():
        if (
            name not in {*FILES, 'LICENSE'}
            or hashlib.sha256((source / name).read_bytes()).hexdigest() != digest
        ):
            raise ValueError('Vendored Abyss assets do not match the reviewed upstream manifest')
    image = config.images(root / 'versions/stack.env')['JELLYFIN_IMAGE']
    # Read the pristine index from the exact pinned image, never an already patched
    # running container. No volumes, networking, privileged mode or shell installer.
    original = runtime.run(
        runtime.docker_prefix()
        + [
            'run',
            '--rm',
            '--network',
            'none',
            '--cap-drop',
            'ALL',
            '--security-opt',
            'no-new-privileges:true',
            '--user',
            c['RUN_UID'] + ':' + c['RUN_GID'],
            '--entrypoint',
            '/bin/cat',
            image,
            '/jellyfin/jellyfin-web/index.html',
        ],
        capture=True,
        timeout=90,
    )
    html = inject(original)
    contents = {
        'index.html': html.encode(),
        **{'ui/' + name: (source / name).read_bytes() for name in FILES},
    }
    # Preserve manual edits instead of overwriting them on a repeat installation.
    for name, data in contents.items():
        path = safe(base / name)
        if path.exists() and path.read_bytes() != data:
            known = (previous or {}).get('files', {}).get(name)
            if hashlib.sha256(path.read_bytes()).hexdigest() != known:
                raise ValueError(
                    'Theme files contain unmanaged edits; preserve/review them before reinstalling'
                )
    for directory in (base, base / 'ui'):
        host.ensure_directory(directory, int(c['RUN_UID']), int(c['RUN_GID']))
    for name, data in contents.items():
        write(base / name, data, c)
    manifest = {
        'schema': 1,
        'enabled': bool((previous or {}).get('enabled')) if enabled is None else enabled,
        'image': image,
        'upstream': upstream['commit'],
        'files': {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()},
    }
    write(base / 'manifest.json', (json.dumps(manifest, indent=2) + '\n').encode(), c)
    return manifest


def inject(html):
    html = re.sub(r'<script\b[^>]*\bdata-abyss-spotlight\b[^>]*></script>', '', html, flags=re.I)
    if not re.search(r'</body>', html, re.I):
        raise ValueError('Pinned Jellyfin web index has no closing body tag')
    return re.sub(r'</body>', lambda match: TAG + match.group(), html, count=1, flags=re.I)


def css(existing, *, remove=False):
    existing = re.sub(
        re.escape(START) + r'.*?' + re.escape(END) + r'\n?', '', existing or '', flags=re.S
    )
    existing = re.sub(
        r'\n/\* OHARA LOGIN ALIGNMENT START \*/.*?/\* OHARA LOGIN ALIGNMENT END \*/\n?',
        '',
        existing,
        flags=re.S,
    )
    if remove:
        return existing
    return (
        START + "\n@import url('/web/ui/abyss.css');\n"
        "@import url('/web/ui/abyss-je.css');\n"
        + END
        + '\n'
        + existing
        + '\n/* OHARA LOGIN ALIGNMENT START */\n'
        '/* Center the Jellyfin 12 login logo independently of header spacers. */\n'
        'body:has(#loginPage:not(.hide)) header.MuiAppBar-root .MuiToolbar-root > .MuiStack-root:has(a img[src*="icon-transparent"]) {\n'
        '  position: absolute !important; left: 50% !important; transform: translateX(-50%) !important;\n}\n'
        'body:has(#loginPage:not(.hide)) header.MuiAppBar-root .MuiButton-startIcon:has(img[src*="icon-transparent"]) {\n'
        '  margin: 0 !important;\n}\n/* OHARA LOGIN ALIGNMENT END */\n'
    )


def client(root):
    key = 'HOMEPAGE_VAR_JELLYFIN_API_KEY'
    values = credentials.read_env(root, {key})
    api = media.Client('http://127.0.0.1:8096')
    api.headers['Authorization'] = (
        'MediaBrowser Client="Ohara Theme", Device="Server", '
        'DeviceId="ohara-theme", Version="1", Token="' + values[key] + '"'
    )
    api.call('/Users')  # Validate before creating files or changing configuration.
    return api


def apply(api, root, *, remove=False):
    import host

    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup = safe(root / 'local/jellyfin-theme-backups' / stamp)
    for directory in (root / 'local', backup.parent, backup):
        host.ensure_directory(directory, os.getuid(), os.getgid(), 0o700)
    branding = api.call('/Branding/Configuration')
    config.create_file(backup / 'branding.json', json.dumps(branding, indent=2) + '\n')
    updated = {**branding, 'CustomCss': css(branding.get('CustomCss'), remove=remove)}
    preferences = []
    if not remove:
        for user in api.call('/Users'):
            user_id = user['Id']
            if not re.fullmatch(r'[a-fA-F0-9-]{32,36}', user_id):
                raise ValueError('Unexpected Jellyfin user ID')
            path = '/DisplayPreferences/usersettings?' + urllib.parse.urlencode(
                {'userId': user_id, 'client': 'emby'}
            )
            prefs = api.call(path)
            config.create_file(backup / (user_id + '.json'), json.dumps(prefs, indent=2) + '\n')
            custom = {
                **(prefs.get('CustomPrefs') or {}),
                'appTheme': 'dark',
                'dashboardTheme': 'dark',
            }
            preferences.append((path, prefs, {**prefs, 'CustomPrefs': custom}))
    changed = []
    try:
        api.call('/System/Configuration/Branding', updated)
        for path, before, after in preferences:
            changed.append((path, before))
            api.call(path, after)
    except (ValueError, OSError, RuntimeError):
        rollback_failed = False
        for path, before in reversed(changed):
            try:
                api.call(path, before)
            except (ValueError, OSError, RuntimeError):
                rollback_failed = True
        try:
            api.call('/System/Configuration/Branding', branding)
        except (ValueError, OSError, RuntimeError):
            rollback_failed = True
        if rollback_failed:
            raise RuntimeError(
                'Theme API rollback incomplete; inspect private backup ' + str(backup)
            ) from None
        raise
    return backup


def _recreate(c, root):
    """Recreate only Jellyfin so a changed overlay mount takes effect."""
    runtime.compose(
        c,
        root,
        [
            'up',
            '-d',
            '--no-deps',
            '--force-recreate',
            '--wait',
            '--wait-timeout',
            '120',
            'jellyfin',
        ],
        timeout=240,
    )


def _disable(c, manifest):
    manifest['enabled'] = False
    write(
        Path(c['DATA_ROOT']) / 'jellyfin-theme/manifest.json',
        (json.dumps(manifest, indent=2) + '\n').encode(),
        c,
    )


def install(c, root):
    """Enable the overlay, recreate Jellyfin and apply branding; return the private backup.

    A failure after enabling restores the previous disabled state before re-raising.
    """
    api = client(root)
    was_enabled = bool((state(c) or {}).get('enabled'))
    prepare(c, root, enabled=True)
    try:
        _recreate(c, root)
        return apply(api, root)
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired):
        if not was_enabled:
            _disable(c, state(c))
            _recreate(c, root)
        raise


def uninstall(c, root):
    """Remove managed CSS and Spotlight, disable the overlay; return the private backup."""
    api = client(root)
    backup = apply(api, root, remove=True)
    manifest = state(c)
    if manifest:
        _disable(c, manifest)
    _recreate(c, root)
    return backup
