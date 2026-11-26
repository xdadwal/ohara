"""Install one host-specific Nginx site file: validate, reload, roll back on failure.

Used by the single-file route installers (immich_proxy, lan_proxy). The main
routes use proxy.apply_config and the Bambuddy/ntfy pair uses
bambuddy_proxy.deploy; their rollback rules differ on purpose.
"""

import os
import subprocess
import tempfile

import runtime

NGINX = '/usr/sbin/nginx'


def existing(target):
    """Return (content, mode, (uid, gid)) of TARGET; (None, 0644, root) when absent."""
    if not target.exists():
        return None, 0o644, (0, 0)
    state = target.stat()
    return target.read_bytes(), state.st_mode & 0o777, (state.st_uid, state.st_gid)


def write(target, data, mode, owner, prefix):
    """Atomically replace TARGET with DATA, flushed to disk, with MODE and OWNER."""
    descriptor, temporary = tempfile.mkstemp(prefix=prefix, dir=target.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.chown(temporary, *owner)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def install(target, content, previous, mode, owner, *, prefix, failure):
    """Write content() as 0644, then test and reload Nginx.

    PREVIOUS, MODE and OWNER come from `existing(target)`, read before the change.
    CONTENT is a callable returning bytes; it runs inside the guarded section.
    If producing the content, writing, the test or the reload fails, the previous
    content and mode are restored (or the new file removed), Nginx is tested and
    reloaded again, and RuntimeError(failure) is raised.
    """
    try:
        write(target, content(), 0o644, owner, prefix)
        runtime.run([NGINX, '-t'])
        runtime.run(['systemctl', 'reload', 'nginx'])
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        if previous is None:
            target.unlink(missing_ok=True)
        else:
            write(target, previous, mode, owner, prefix)
        runtime.run([NGINX, '-t'])
        runtime.run(['systemctl', 'reload', 'nginx'])
        raise RuntimeError(failure) from None
